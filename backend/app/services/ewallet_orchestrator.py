"""Durable, owner-scoped e-wallet transaction orchestration."""
from __future__ import annotations
import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, or_
from app.core.errors import EWalletTransactionError
from app.models.db_models import (
    EWalletTransactionRecord as Tx, EWalletQuote, EWalletIntake,
    EWalletCoinSession, GatewayEventRecord, InventoryHold, ClaimRecord, PhysicalOperation,
)
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import calculate_change, DispensePlan
from app.services.ewallet_policy import POLICY_VERSION, TERMINAL, INTAKE, BILLS, TRANSITIONS, intake_options, serialized
from app.services.ewallet_intake import EWalletIntakeMixin
from app.services.paymongo_client import PROVIDER_BICS, PayMongoClient
logger = logging.getLogger(__name__)


class EWalletOrchestrator(EWalletIntakeMixin):
    def __init__(self, settings, gateway, bill_acceptor, dispenser, machine_status,
                 ws_manager, db_session_factory, operation_mode=None, receipt_service=None,
                 coin_controller=None, claim_service=None, inventory_service=None):
        self._settings, self._gateway = settings, gateway
        self._bill_acceptor, self._dispenser = bill_acceptor, dispenser
        self._status, self._ws, self._db_factory = machine_status, ws_manager, db_session_factory
        self._operation_mode, self._receipt_service = operation_mode, receipt_service
        self._coin_controller, self._claim_service = coin_controller, claim_service
        self._inventory = inventory_service
        self._active_transaction_id = self._operation_owner = None
        self._mutation_lock = asyncio.Lock()
        self._mutation_owner = None
        self._timeout_tasks = {}
        self._worker = None
        self._heartbeats = {}

    @property
    def has_active_transaction(self):
        return self._active_transaction_id is not None

    async def _record(self, tx_id):
        async with self._db_factory() as session:
            record = await session.get(Tx, tx_id)
            if record is None:
                raise EWalletTransactionError("Transaction not found")
            return record

    def _check_ready(self, direction):
        snapshot = self._status.snapshot()
        if not self._status.is_online:
            raise EWalletTransactionError("Kiosk is offline")
        if snapshot.security.tamper_active or not snapshot.security.locked:
            raise EWalletTransactionError("Security lockdown or open door")
        if not snapshot.consumables.inventory_consistent:
            raise EWalletTransactionError("Inventory reconciliation is required")
        if not self._settings.use_mock_hardware:
            if snapshot.bill_device.connection != "connected" or snapshot.coin_device.connection != "connected":
                raise EWalletTransactionError("Required hardware is disconnected")
            if not snapshot.sorter.homed:
                raise EWalletTransactionError("Bill sorter is not homed")
            if not snapshot.startup_checks.performed or snapshot.startup_checks.has_errors:
                raise EWalletTransactionError("Startup checks require operator attention")
        if isinstance(self._gateway, PayMongoClient):
            if not self._settings.paymongo_secret_key or not self._settings.paymongo_webhook_secret:
                raise EWalletTransactionError("Payment gateway is not configured")
            if direction == "cash-in" and not self._settings.paymongo_source_account_number:
                raise EWalletTransactionError("Wallet funding account is not configured")
            if direction == "cash-out" and not self._settings.paymongo_public_key:
                raise EWalletTransactionError("QR gateway is not configured")

    async def _available(self, tx_id=None):
        if self._inventory:
            await self._inventory.refresh_runtime()
        snapshot = self._status.snapshot()
        bills = dict(snapshot.consumables.bill_dispenser_counts)
        coins = dict(snapshot.consumables.coin_counts)
        if tx_id and self._inventory:
            async with self._db_factory() as session:
                hold = await session.get(InventoryHold, tx_id)
                if hold and hold.state == "HELD":
                    for key, count in hold.quantities.items():
                        location, denom = key.split(":")
                        target = coins if location == "COIN_DISPENSER" else bills
                        target[denom] = target.get(denom, 0) + count
        return bills, coins

    async def _options(self, record):
        _, coins = await self._available(record.id)
        return await self._safe_options(record.total_due - record.inserted_amount, coins)

    async def _safe_options(self, remaining, coins, storing_bill=None):
        counts = self._status.snapshot().consumables.bill_storage_counts
        bills = {v: max(0, self._settings.storage_slot_capacity - counts.get(f"PHP_{v}", 0) - (1 if storing_bill == v else 0)) for v in BILLS}
        return intake_options(remaining, coins, bills, await self._coin_storage_available(remaining))

    async def _coin_storage_available(self, remaining):
        if self._settings.use_mock_hardware:
            return True
        from app.models.db_models import InventoryBalance
        if self._inventory is None:
            return False
        async with self._db_factory() as session:
            rows = (await session.execute(select(InventoryBalance).where(InventoryBalance.location == "COIN_DISPENSER"))).scalars().all()
        counts = {row.denomination: row.count for row in rows}
        limits = self._settings.coin_storage_capacities
        return all(f"PHP_{value}" in limits and counts.get(f"PHP_{value}", 0) + max(1, (remaining + value - 1) // value) <= limits[f"PHP_{value}"] for value in (1, 5, 10, 20))

    async def quote(self, *, provider, direction, amount, session_id):
        self._check_ready(direction)
        async with self._db_factory() as session:
            uncertain_bill = (await session.execute(select(EWalletIntake.id).where(EWalletIntake.state == "PREPARED").limit(1))).scalar_one_or_none()
            uncertain_coin = (await session.execute(select(EWalletCoinSession.id).where(EWalletCoinSession.state == "UNCERTAIN").limit(1))).scalar_one_or_none()
            if uncertain_bill or uncertain_coin:
                raise EWalletTransactionError("Unresolved cash intake requires operator reconciliation")
        if not self._settings.use_mock_hardware:
            await self._coin_controller.verify_intake_capabilities()
        if provider not in {"gcash", "maya"} or direction not in {"cash-in", "cash-out"}:
            raise EWalletTransactionError("Invalid e-wallet service")
        if not isinstance(amount, int) or not 1 <= amount <= 50_000:
            raise EWalletTransactionError("Amount must be between 1 and 50000")
        fee = self._calculate_fee(amount)
        if amount <= fee:
            raise EWalletTransactionError("Amount must be greater than the fee")
        bills, coins = await self._available()
        payload = dict(provider=provider, direction=direction, amount=amount, fee=fee,
                       transfer_amount=amount-fee, total_due=amount, policy_version=POLICY_VERSION)
        if direction == "cash-out":
            payload["dispense_plan"] = calculate_change(amount-fee, bills, coins).model_dump()
        else:
            options, _ = await self._safe_options(amount, coins)
            if not options["bills"] and not options["coins_enabled"]:
                raise EWalletTransactionError("No safe payment path for this amount; choose another amount")
            payload["allowed_intake"] = options
        quote_id = str(uuid.uuid4())
        expires = datetime.utcnow() + timedelta(minutes=5)
        async with self._db_factory() as session:
            session.add(EWalletQuote(id=quote_id, session_id=session_id, payload=payload, expires_at=expires))
            await session.commit()
        return dict(payload, quote_id=quote_id, expires_at=expires.isoformat()+"Z")

    @serialized
    async def start_transaction(self, *, provider, direction, amount, mobile_number=None,
                                account_name=None, session_id=None, request_key=None,
                                quote_id=None, policy_version=None):
        if request_key:
            async with self._db_factory() as session:
                prior = (await session.execute(select(Tx).where(Tx.request_key == request_key))).scalar_one_or_none()
                if prior:
                    if prior.session_id != session_id:
                        raise EWalletTransactionError("Request belongs to another session")
                    if (prior.provider, prior.direction, prior.amount, prior.mobile_number or "", prior.account_name or "") != (provider, direction, amount, mobile_number or "", (account_name or "").strip()):
                        raise EWalletTransactionError("The request key belongs to different transaction details", "IDEMPOTENCY_CONFLICT")
                    return await self.get_transaction(prior.id)
        self._check_ready(direction)
        if self.has_active_transaction:
            raise EWalletTransactionError("Another e-wallet transaction is already active")
        if direction == "cash-in":
            if not mobile_number or len(mobile_number) != 11 or not mobile_number.startswith("09") or not mobile_number.isascii() or not mobile_number.isdigit():
                raise EWalletTransactionError("Invalid mobile number")
            if not account_name or len(account_name.strip()) < 2:
                raise EWalletTransactionError("Account name is required")
        elif mobile_number is not None or account_name is not None:
            raise EWalletTransactionError("Cash-out does not accept account identity fields")
        fresh = await self.quote(provider=provider, direction=direction, amount=amount, session_id=session_id or "internal")
        if quote_id:
            async with self._db_factory() as session:
                quote = await session.get(EWalletQuote, quote_id)
                if not quote or quote.session_id != session_id or quote.expires_at <= datetime.utcnow():
                    raise EWalletTransactionError("Quote expired; enter the amount again", "QUOTE_EXPIRED")
                for key in ("provider", "direction", "amount", "fee", "allowed_intake", "dispense_plan"):
                    if quote.payload.get(key) != fresh.get(key):
                        raise EWalletTransactionError("Quote changed; review a new quote", "QUOTE_CHANGED")
        elif session_id:
            raise EWalletTransactionError("A confirmed quote is required")
        if direction == "cash-in" and session_id and policy_version != POLICY_VERSION:
            raise EWalletTransactionError("Accept the cash-in policy before inserting cash")
        tx_id = str(uuid.uuid4())
        if self._operation_mode:
            self._operation_mode.begin_transaction(tx_id)
        self._operation_owner = self._active_transaction_id = tx_id
        record = Tx(id=tx_id, provider=provider, direction=direction,
                    mobile_number=mobile_number or "", account_name=(account_name or "").strip(),
                    state="ACCEPTING_CASH" if direction == "cash-in" else "CREATED",
                    amount=amount, fee=fresh["fee"], transfer_amount=fresh["transfer_amount"],
                    total_due=amount, session_id=session_id, request_key=request_key,
                    policy_version=policy_version, heartbeat_at=datetime.utcnow(),
                    deadline=datetime.utcnow()+timedelta(seconds=120 if direction == "cash-in" else 300),
                    gateway_work={"qr_key": f"ewallet:{tx_id}:qr"} if direction == "cash-out" else {})
        try:
            async with self._db_factory() as session:
                session.add(record)
                await session.commit()
            if direction == "cash-out":
                plan = DispensePlan(**fresh["dispense_plan"])
                await self._hold(tx_id, plan)
                await self._save(tx_id, dispense_plan=plan.model_dump())
                await self._create_qr(tx_id)
            else:
                self._bill_acceptor.set_expected_currency("PHP")
                self._bill_acceptor.set_expected_denomination(None)
            await self._publish(tx_id)
            return await self.get_transaction(tx_id)
        except Exception:
            await self._clear_active(tx_id)
            raise

    async def _create_qr(self, tx_id):
        record = await self._record(tx_id)
        async def checkpoint(stage, data):
            current = await self._record(tx_id)
            work = dict(current.gateway_work or {})
            work[stage] = data
            values = {"gateway_work": work}
            if stage == "intent":
                values["gateway_payment_intent_id"] = data["id"]
            await self._save(tx_id, **values)
        try:
            result = await self._gateway.create_qr_payment(amount_centavos=record.amount*100,
                reference=tx_id, idempotency_key=f"ewallet:{tx_id}:qr", checkpoint=checkpoint)
            await self._save(tx_id, gateway_payment_intent_id=result.payment_intent_id,
                gateway_status=result.status, qr_image_url=result.qr_image_url, test_url=result.test_url,
                state="WAITING_FOR_PAYMENT")
        except Exception as exc:
            await self._save(tx_id, state="CANCELLATION_PENDING", customer_present=False,
                             error_message=str(exc))
            raise EWalletTransactionError("QR setup is being reconciled; please wait") from exc

    async def _save(self, tx_id, **values):
        async with self._db_factory() as session:
            record = await session.get(Tx, tx_id)
            next_state = values.get("state", record.state)
            if next_state != record.state and next_state not in TRANSITIONS.get(record.state, set()):
                raise EWalletTransactionError(f"Invalid transition from {record.state} to {next_state}")
            for key, value in values.items():
                setattr(record, key, value)
            await session.commit()

    async def _hold(self, tx_id, plan):
        if self._inventory:
            quantities = {f"{'COIN_DISPENSER' if i.denom_type == 'coin' else 'BILL_DISPENSER'}:{i.denom}": i.count for i in plan.items}
            await self._inventory.hold(tx_id, quantities)

    async def _prepare_change(self, record, value):
        options, changes = await self._options(record)
        remaining = record.total_due - record.inserted_amount
        if value > remaining:
            excess = value - remaining
            if excess > 20 or excess not in changes:
                raise EWalletTransactionError("This bill requires unavailable change; use a smaller bill")
            await self._hold(record.id, changes[excess])
        else:
            _, coins = await self._available(record.id)
            next_options, _ = await self._safe_options(remaining-value, coins, storing_bill=value)
            if value < remaining and not next_options["bills"] and not next_options["coins_enabled"]:
                raise EWalletTransactionError("This cash leaves no safe completion path")

    @serialized
    async def confirm_cash_in(self, transaction_id):
        record = await self._record(transaction_id)
        self._require_cash_in(record)
        if record.state != "CASH_ACCEPTED":
            if record.state in INTAKE:
                raise EWalletTransactionError("Required cash has not been accepted")
            return await self.get_transaction(transaction_id)
        try:
            self._check_ready("cash-in")
            await self._close_coins(transaction_id)
        except Exception as exc:
            return await self._mark_claim_required(transaction_id, "FUNDING_FAULT", str(exc), True)
        record = await self._record(transaction_id)
        if record.change_due <= 20:
            _, coins = await self._available(transaction_id)
            plan = calculate_change(record.change_due, {}, coins)
            await self._hold(transaction_id, plan)
            await self._save(transaction_id, dispense_plan=plan.model_dump())
        await self._save(transaction_id, state="SUBMISSION_UNKNOWN", submission_at=datetime.utcnow(),
                         deadline=datetime.utcnow()+timedelta(minutes=20),
                         gateway_work={"transfer_key": f"ewallet:{transaction_id}:transfer"})
        return await self._submit_transfer(transaction_id)

    async def _submit_transfer(self, tx_id):
        record = await self._record(tx_id)
        if record.submission_at and datetime.utcnow()-record.submission_at >= timedelta(hours=23):
            # Provider idempotency responses are retained for approximately 24h.
            # After the conservative cutoff, only read-based discovery is safe.
            found = await self._gateway.find_transfer(tx_id)
            attrs = (found or {}).get("attributes") or found or {}
            batch_id = attrs.get("batch_transfer_id") or attrs.get("batch_transaction_id")
            if found and batch_id:
                await self._save(tx_id, gateway_batch_transfer_id=batch_id, gateway_transfer_id=found["id"])
                return await self._verify_and_complete_cash_in(tx_id)
            return await self._mark_claim_required(tx_id, "SUBMISSION_RECONCILIATION", "Transfer must be reconciled by reference; automatic resubmission is disabled", True)
        try:
            result = await self._gateway.create_disbursement(provider=record.provider,
                account_number=record.mobile_number, account_name=record.account_name,
                amount_centavos=record.transfer_amount*100, reference=tx_id,
                idempotency_key=f"ewallet:{tx_id}:transfer")
        except Exception as exc:
            await self._save(tx_id, error_message=f"Transfer outcome is being reconciled: {exc}")
            return await self.get_transaction(tx_id)
        state = "CLAIM_REQUIRED" if record.state == "CLAIM_REQUIRED" else "DISBURSEMENT_PENDING"
        await self._save(tx_id, gateway_batch_transfer_id=result.batch_transfer_id,
            gateway_transfer_id=result.transfer_id, gateway_status=result.status, state=state)
        await self._publish(tx_id)
        if result.status in {"succeeded", "success", "paid", "failed", "rejected"}:
            return await self._verify_and_complete_cash_in(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def _verify_and_complete_cash_in(self, tx_id):
        record = await self._record(tx_id)
        if record.state in TERMINAL:
            return await self.get_transaction(tx_id)
        batch = await self._gateway.get_batch_transfer(record.gateway_batch_transfer_id)
        transfers = batch.get("transfers") or []
        raw = next((t for t in transfers if t.get("id") == record.gateway_transfer_id), None)
        transfer = {**(raw or {}), **((raw or {}).get("attributes") or {})}
        recipient = transfer.get("destination_account") or transfer.get("receiver") or {}
        if (batch.get("id") != record.gateway_batch_transfer_id
            or not raw or transfer.get("reference_number") != tx_id
            or transfer.get("amount") != record.transfer_amount*100
            or str(transfer.get("currency", "")).upper() != "PHP"
            or recipient.get("number", recipient.get("bank_account_number")) != record.mobile_number
            or recipient.get("bic", recipient.get("bank_code")) != PROVIDER_BICS[record.provider]):
            return await self._mark_claim_required(tx_id, "TRANSFER_VERIFICATION_FAILED", "Transfer identity or recipient mismatch", True)
        status = str(transfer.get("status", "")).lower()
        await self._save(tx_id, gateway_status=status)
        if status in {"succeeded", "success", "paid"}:
            await self._save(tx_id, wallet_credited=record.transfer_amount)
            return await self._complete_cash_in(tx_id)
        if status in {"failed", "rejected", "returned", "cancelled"}:
            await self._save(tx_id, refunded_fee=record.fee)
            return await self._mark_claim_required(tx_id, "TRANSFER_FAILED", "Wallet transfer failed")
        return await self.get_transaction(tx_id)

    async def _complete_cash_in(self, tx_id):
        record = await self._record(tx_id)
        if record.state == "COMPLETE":
            return await self.get_transaction(tx_id)
        if record.state == "CLAIM_REQUIRED" or not record.customer_present or self._active_transaction_id != tx_id:
            return await self._mark_claim_required(tx_id, "LATE_GATEWAY_SUCCESS", "Wallet credited; remaining excess requires operator settlement")
        if record.change_due > 20:
            return await self._mark_claim_required(tx_id, "EXCESS_CASH", "Excess above PHP 20 requires operator settlement")
        if record.change_due:
            try:
                self._check_ready("cash-in")
            except Exception as exc:
                return await self._mark_claim_required(tx_id, "CHANGE_UNAVAILABLE", str(exc))
            await self._save(tx_id, state="CHANGE_PENDING")
            result = await self._dispenser.execute_dispense(DispensePlan(**record.dispense_plan),
                reference_id=tx_id, source_kind="EWALLET_CHANGE")
            await self._save(tx_id, change_dispensed=result.total_dispensed, dispense_result=result.model_dump())
            if not result.success:
                return await self._mark_claim_required(tx_id, "CHANGE_SHORTFALL", result.error or "Change incomplete", bool(result.ambiguous_amount))
        await self._save(tx_id, state="COMPLETE", error_message=None, completed_at=datetime.utcnow())
        await self._finish(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def _verify_and_dispense_cash_out(self, tx_id, payment_id=None):
        record = await self._record(tx_id)
        if record.state in {"COMPLETE", "RESOLVED"}:
            return await self.get_transaction(tx_id)
        intent = await self._gateway.get_payment_intent(record.gateway_payment_intent_id)
        attrs = intent.get("attributes") or {}
        if attrs.get("status") != "succeeded":
            return await self.get_transaction(tx_id)
        payment = next((p for p in attrs.get("payments", []) if
            (payment_id is None or p.get("id") == payment_id)
            and (p.get("attributes") or {}).get("status") == "paid"), None)
        paid = (payment or {}).get("attributes") or {}
        valid = (intent.get("id") == record.gateway_payment_intent_id
            and attrs.get("amount") == record.amount*100
            and str(attrs.get("currency", "")).upper() == "PHP"
            and (attrs.get("metadata") or {}).get("coinnect_transaction_id") == tx_id
            and paid.get("amount") == record.amount*100
            and str(paid.get("currency", "")).upper() == "PHP"
            and (paid.get("source") or {}).get("type") == "qrph")
        if not valid:
            return await self._mark_claim_required(tx_id, "PAYMENT_VERIFICATION_FAILED", "Payment identity mismatch", True)
        await self._save(tx_id, gateway_status="paid")
        if not record.customer_present or record.state in {"CLAIM_REQUIRED", "CANCELLED", "CANCELLATION_PENDING"} or self._active_transaction_id != tx_id:
            return await self._mark_claim_required(tx_id, "LATE_PAYMENT", "Payment verified after the customer session ended")
        if record.state not in {"WAITING_FOR_PAYMENT", "PAYMENT_CONFIRMED", "DISPENSING"}:
            return await self.get_transaction(tx_id)
        await self._save(tx_id, state="PAYMENT_CONFIRMED", deadline=None)
        return await self._dispense_paid_cash_out(tx_id)

    async def _dispense_paid_cash_out(self, tx_id):
        record = await self._record(tx_id)
        if self._active_transaction_id != tx_id or not record.customer_present:
            return await self._mark_claim_required(tx_id, "PAYOUT_RECOVERY", "Unattended payout blocked", True)
        try:
            self._check_ready("cash-out")
            plan = DispensePlan(**record.dispense_plan)
            await self._save(tx_id, state="DISPENSING")
            result = await self._dispenser.execute_dispense(plan, reference_id=tx_id, source_kind="EWALLET")
        except Exception as exc:
            return await self._mark_claim_required(tx_id, "PAYOUT_FAULT", str(exc), True)
        await self._save(tx_id, dispensed_amount=result.total_dispensed, dispense_result=result.model_dump())
        if not result.success:
            await self._save(tx_id, refunded_fee=record.fee)
            return await self._mark_claim_required(tx_id, "PARTIAL_DISPENSE", result.error or "Cash payout incomplete", bool(result.ambiguous_amount))
        await self._save(tx_id, state="COMPLETE", completed_at=datetime.utcnow())
        await self._finish(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def cancel_transaction(self, transaction_id):
        record = await self._record(transaction_id)
        if record.state == "CANCELLED":
            return await self.get_transaction(transaction_id)
        if record.inserted_amount or record.gateway_status in {"paid", "succeeded"}:
            raise EWalletTransactionError("Money received; cancellation is unavailable", "TRANSACTION_NOT_CANCELLABLE")
        if record.state not in {"ACCEPTING_CASH", "CREATED", "WAITING_FOR_PAYMENT", "CANCELLATION_PENDING"}:
            raise EWalletTransactionError("Transaction is not cancellable", "TRANSACTION_NOT_CANCELLABLE")
        await self._close_coins(transaction_id)
        record = await self._record(transaction_id)
        if record.inserted_amount:
            return await self._after_intake(transaction_id)
        if record.direction == "cash-out":
            # Session closure is durable; a racing payment becomes a refund claim.
            await self._save(transaction_id, state="CANCELLATION_PENDING", customer_present=False, qr_image_url=None)
            return await self._reconcile_cancel(transaction_id)
        await self._save(transaction_id, state="CANCELLED", completed_at=datetime.utcnow(), customer_present=False)
        await self._finish(transaction_id)
        return await self.get_transaction(transaction_id)

    async def _reconcile_cancel(self, tx_id):
        record = await self._record(tx_id)
        try:
            if not record.gateway_payment_intent_id:
                # Repeating the same QR operation retrieves a lost creation response.
                await self._create_qr(tx_id)
                await self._save(tx_id, state="CANCELLATION_PENDING", customer_present=False, qr_image_url=None)
                record = await self._record(tx_id)
            intent = await self._gateway.get_payment_intent(record.gateway_payment_intent_id)
            if (intent.get("attributes") or {}).get("status") == "succeeded":
                return await self._verify_and_dispense_cash_out(tx_id)
            await self._gateway.cancel_payment_intent(record.gateway_payment_intent_id)
            intent = await self._gateway.get_payment_intent(record.gateway_payment_intent_id)
            status = (intent.get("attributes") or {}).get("status")
            if status == "succeeded":
                return await self._verify_and_dispense_cash_out(tx_id)
            if status not in {"cancelled", "canceled"}:
                raise EWalletTransactionError("External cancellation is not yet confirmed")
        except Exception as exc:
            await self._save(tx_id, error_message=f"Checking payment cancellation: {exc}")
            if self._inventory:
                await self._inventory.release_hold(tx_id)
            await self._clear_active(tx_id)
            return await self.get_transaction(tx_id)
        await self._save(tx_id, state="CANCELLED", completed_at=datetime.utcnow(), error_message=None)
        await self._finish(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def _mark_claim_required(self, transaction_id, error_code, error_message, provisional=False, drain_intake=True):
        record = await self._record(transaction_id)
        if record.state in {"COMPLETE", "RESOLVED", "ABANDONED_RETAINED"}:
            return await self.get_transaction(transaction_id)
        async with self._db_factory() as session:
            operations = (await session.execute(select(PhysicalOperation).where(PhysicalOperation.transaction_id == transaction_id))).scalars().all()
        if operations:
            confirmed = sum(op.confirmed_count * op.denomination_value for op in operations)
            provisional = provisional or any(op.state in {"PLANNED", "STARTED", "AMBIGUOUS"} for op in operations)
            field = "change_dispensed" if record.direction == "cash-in" else "dispensed_amount"
            if confirmed > getattr(record, field):
                await self._save(transaction_id, **{field: confirmed})
                record = await self._record(transaction_id)
        if record.direction == "cash-in":
            if drain_intake:
                try:
                    await self._close_coins(transaction_id, fault_claim=False)
                except Exception:
                    provisional = True
                record = await self._record(transaction_id)
            credited = record.wallet_credited or 0
            amount = max(0, record.inserted_amount - credited - (record.fee if credited else 0) - record.change_dispensed)
            kind = "INPUT_REFUND"
            async with self._db_factory() as session:
                prepared = (await session.execute(select(EWalletIntake).where(
                    EWalletIntake.transaction_id == transaction_id, EWalletIntake.state == "PREPARED"))).scalars().all()
                coins_uncertain = (await session.execute(select(EWalletCoinSession.id).where(
                    EWalletCoinSession.transaction_id == transaction_id, EWalletCoinSession.state != "CLOSED").limit(1))).scalar_one_or_none()
                provisional = provisional or bool(prepared) or coins_uncertain is not None
                amount += sum(operation.value for operation in prepared)
            if record.submission_at and not credited and record.gateway_status not in {"failed", "rejected", "returned", "cancelled"}:
                provisional = True
        else:
            amount = 0 if record.dispensed_amount >= record.transfer_amount else max(0, record.amount-record.dispensed_amount)
            kind = "OUTPUT_SHORTFALL"
        async with self._db_factory() as session:
            record = await session.get(Tx, transaction_id)
            record.customer_present = False
            record.refunded_fee = (record.fee if not record.wallet_credited else 0) if record.direction == "cash-in" else (record.fee if record.dispensed_amount < record.transfer_amount else 0)
            if self._claim_service:
                await self._claim_service.create(source_kind="EWALLET", transaction_id=transaction_id,
                    claim_kind=kind, amount=amount, currency="PHP", reason_code=error_code,
                    reason_message=error_message, confirmed_dispensed_amount=record.dispensed_amount+record.change_dispensed,
                    provisional=provisional, record=record, session=session)
            else:
                record.state, record.error_code, record.error_message = "CLAIM_REQUIRED", error_code, error_message
                record.claim_ticket_code = record.claim_ticket_code or secrets.token_hex(4).upper()
                record.completed_at = datetime.utcnow()
                await session.commit()
        if self._inventory:
            await self._inventory.release_hold(transaction_id)
        await self._publish(transaction_id)
        await self._clear_active(transaction_id)
        return await self.get_transaction(transaction_id)

    async def _finish(self, tx_id):
        if self._inventory:
            await self._inventory.release_hold(tx_id)
        record = await self._record(tx_id)
        if record.state == "COMPLETE" and self._receipt_service:
            await self._receipt_service.print_receipt(record)
        await self._publish(tx_id)
        await self._clear_active(tx_id)

    async def _clear_active(self, transaction_id):
        if self._active_transaction_id != transaction_id:
            return
        if self._coin_controller:
            try:
                await self._coin_controller.set_coin_acceptor_enabled(False)
            except Exception:
                self._status.set_inventory_consistent(False)
                logger.exception("Failed to disable coin intake; new money operations blocked")
        self._active_transaction_id = None
        if self._operation_mode:
            self._operation_mode.end_transaction(transaction_id)
        self._operation_owner = None

    async def touch(self, tx_id, continue_session=False):
        if tx_id != self._active_transaction_id:
            return await self.get_transaction(tx_id)
        # Presence must not queue behind a slow external payment request.
        self._heartbeats[tx_id] = datetime.utcnow()
        if continue_session:
            return await self._continue_session(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def _continue_session(self, tx_id):
        record = await self._record(tx_id)
        if record.state == "ACCEPTING_CASH":
            await self._save(tx_id, heartbeat_at=datetime.utcnow(),
                deadline=datetime.utcnow()+timedelta(seconds=120 if record.direction == "cash-in" else 300))
        return await self.get_transaction(tx_id)

    @serialized
    async def expire_transaction(self, tx_id, now=None):
        now = now or datetime.utcnow()
        record = await self._record(tx_id)
        if record.state in TERMINAL or record.state == "CLAIM_REQUIRED":
            return
        if record.state == "CASH_ACCEPTED":
            await self.confirm_cash_in(tx_id)
            return
        if record.state == "ACCEPTING_CASH":
            heartbeat = self._heartbeats.get(tx_id, record.heartbeat_at)
            healthy = bool(heartbeat and (now-heartbeat).total_seconds() <= 30)
            try:
                self._check_ready("cash-in")
            except Exception:
                healthy = False
            if not healthy:
                if record.inserted_amount:
                    await self._mark_claim_required(tx_id, "SESSION_INTERRUPTED", "Customer session or hardware unavailable", True)
                else:
                    await self.cancel_transaction(tx_id)
                return
            if record.deadline and now >= record.deadline:
                await self._close_coins(tx_id)
                record = await self._record(tx_id)
                if record.inserted_amount >= record.total_due:
                    await self._after_intake(tx_id)
                    return
                if record.inserted_amount and record.policy_version != POLICY_VERSION:
                    await self._mark_claim_required(tx_id, "LEGACY_TIMEOUT", "Legacy cash requires reconciliation")
                    return
                state = "ABANDONED_RETAINED" if record.inserted_amount else "CANCELLED"
                await self._save(tx_id, state=state, retained_amount=record.inserted_amount,
                                 customer_present=False, completed_at=now)
                await self._finish(tx_id)
        elif record.deadline and now >= record.deadline:
            if record.direction == "cash-out":
                await self.cancel_transaction(tx_id)
            elif record.state in {"SUBMISSION_UNKNOWN", "DISBURSEMENT_PENDING"}:
                await self._mark_claim_required(tx_id, "TRANSFER_PENDING", "Wallet result remains unconfirmed after twenty minutes", True)

    @serialized
    async def handle_tamper(self, sensor):
        tx_id = self._active_transaction_id
        if not tx_id:
            return
        record = await self._record(tx_id)
        if record.direction == "cash-in":
            await self._mark_claim_required(tx_id, "HARDWARE_INTERRUPTED", str(sensor), True)
        else:
            await self._save(tx_id, customer_present=False)
            if record.gateway_status == "paid":
                await self._mark_claim_required(tx_id, "HARDWARE_INTERRUPTED", str(sensor), True)
            else:
                await self._save(tx_id, state="CANCELLATION_PENDING", qr_image_url=None)
                await self._clear_active(tx_id)

    @serialized
    async def recover_pending_transactions(self):
        async with self._db_factory() as session:
            ids = list((await session.execute(select(Tx.id).where(~Tx.state.in_(TERMINAL)))).scalars())
        for tx_id in ids:
            record = await self._record(tx_id)
            await self._save(tx_id, customer_present=False)
            if record.direction == "cash-in" and record.state == "DISBURSEMENT_PENDING" and record.submission_at is None:
                submitted = record.updated_at or record.created_at
                await self._save(tx_id, submission_at=submitted, deadline=submitted + timedelta(minutes=20))
            async with self._db_factory() as session:
                uncertain = (await session.execute(select(EWalletIntake).where(
                    EWalletIntake.transaction_id == tx_id, EWalletIntake.state == "PREPARED"))).scalars().all()
            try:
                await self._close_coins(tx_id)
            except Exception:
                uncertain = True
            if uncertain:
                self._status.set_inventory_consistent(False)
                await self._mark_claim_required(tx_id, "INTAKE_RECOVERY", "Stored cash requires physical reconciliation", True)
            elif record.direction == "cash-in" and record.state in INTAKE:
                await self._mark_claim_required(tx_id, "CRASH_RECOVERY", "Interrupted cash intake requires reconciliation", True)
            elif record.direction == "cash-out" and record.state != "CLAIM_REQUIRED":
                await self._save(tx_id, state="CANCELLATION_PENDING", qr_image_url=None)
            elif record.state in {"CHANGE_PENDING", "DISPENSING", "PAYMENT_CONFIRMED"}:
                await self._mark_claim_required(tx_id, "CRASH_RECOVERY", "Interrupted payout requires reconciliation", True)
            elif record.direction == "cash-in" and record.state == "CLAIM_REQUIRED" and not record.submission_at and not record.gateway_batch_transfer_id:
                await self._mark_claim_required(tx_id, "LEGACY_RECOVERY", "Stored cash requires operator settlement")
        await self.reconcile_pending()

    async def start(self):
        self._worker = asyncio.create_task(self._run(), name="ewallet-reconciliation")

    async def stop(self):
        if self._worker:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)

    async def _run(self):
        cycle = 0
        while True:
            try:
                if self._active_transaction_id:
                    await self.expire_transaction(self._active_transaction_id)
                if cycle % 5 == 0:
                    await self.reconcile_pending()
                cycle += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("E-wallet maintenance cycle failed; will retry")
            await asyncio.sleep(1)

    @serialized
    async def reconcile_pending(self):
        async with self._db_factory() as session:
            ids = list((await session.execute(select(Tx.id).where(~Tx.state.in_(TERMINAL)))).scalars())
        for tx_id in ids:
            record = await self._record(tx_id)
            try:
                if record.state in {"SUBMISSION_UNKNOWN", "DISBURSEMENT_PENDING"} and record.deadline and datetime.utcnow() >= record.deadline:
                    await self._mark_claim_required(tx_id, "TRANSFER_PENDING", "Wallet result remains unconfirmed after twenty minutes", True)
                    record = await self._record(tx_id)
                if record.state == "CANCELLATION_PENDING":
                    await self._reconcile_cancel(tx_id)
                elif record.direction == "cash-out" and record.gateway_payment_intent_id:
                    await self._verify_and_dispense_cash_out(tx_id)
                elif record.direction == "cash-in":
                    if record.gateway_batch_transfer_id:
                        await self._verify_and_complete_cash_in(tx_id)
                    elif record.submission_at:
                        await self._submit_transfer(tx_id)
            except Exception:
                logger.exception("Reconciliation will retry transaction %s", tx_id)

    async def enqueue_gateway_event(self, event):
        event_id = str(event.get("id") or "")
        if not event_id:
            raise EWalletTransactionError("Gateway event ID is required")
        async with self._db_factory() as session:
            if await session.get(GatewayEventRecord, event_id):
                return {"accepted": True, "event_id": event_id, "duplicate": True}
            session.add(GatewayEventRecord(id=event_id, event_type=event.get("type", "unknown"),
                resource_id=event.get("resource_id"), payload=event, processed=False, status="RECEIVED"))
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                if await session.get(GatewayEventRecord, event_id):
                    return {"accepted": True, "event_id": event_id, "duplicate": True}
                raise
        return {"accepted": True, "event_id": event_id, "duplicate": False}

    @serialized
    async def process_gateway_event(self, event, persisted_event_id=None):
        if persisted_event_id is None:
            accepted = await self.enqueue_gateway_event(event)
            if accepted["duplicate"]:
                return {"duplicate": True}
        resource = event.get("resource_id")
        async with self._db_factory() as session:
            record = (await session.execute(select(Tx).where(or_(
                Tx.gateway_payment_intent_id == resource, Tx.gateway_transfer_id == resource,
                Tx.gateway_batch_transfer_id == resource)))).scalar_one_or_none() if resource else None
        if record is None:
            raise EWalletTransactionError("Gateway transaction is not committed yet", "TRANSACTION_NOT_FOUND")
        result = await self.get_transaction(record.id)
        if record.state not in {"COMPLETE", "RESOLVED", "ABANDONED_RETAINED"}:
            if record.direction == "cash-out":
                result = await self._verify_and_dispense_cash_out(record.id, event.get("payment_id"))
            else:
                result = await self._verify_and_complete_cash_in(record.id)
        async with self._db_factory() as session:
            row = await session.get(GatewayEventRecord, str(event["id"]))
            row.processed, row.status = True, "PROCESSED"
            row.processing_error = row.lease_expires_at = None
            row.processed_at = datetime.utcnow()
            await session.commit()
        return result

    async def escalate_gateway_event(self, event, error):
        # A reconciliation error is not evidence of a new debt; the deadline
        # worker escalates known funded transactions with the proper accounting.
        logger.error("Gateway event %s remains pending: %s", event.get("id"), error)

    async def get_transaction(self, transaction_id):
        record = await self._record(transaction_id)
        data = self._serialize(record)
        if record.state == "ACCEPTING_CASH":
            data["allowed_intake"], _ = await self._options(record)
        async with self._db_factory() as session:
            claims = (await session.execute(select(ClaimRecord).where(
                ClaimRecord.source_kind == "EWALLET", ClaimRecord.transaction_id == transaction_id))).scalars().all()
        data["claims"] = [self._claim_service.serialize(c) for c in claims] if self._claim_service else []
        if claims:
            data["shortfall"] = sum(c.amount for c in claims if c.status != "RESOLVED")
        return data

    async def _publish(self, tx_id):
        data = await self.get_transaction(tx_id)
        kind = WSEventType.EWALLET_STATE_CHANGED
        if data["state"] == "COMPLETE":
            kind = WSEventType.EWALLET_COMPLETE
        elif data["state"] == "CLAIM_REQUIRED":
            kind = WSEventType.EWALLET_CLAIM_REQUIRED
        record = await self._record(tx_id)
        await self._ws.broadcast(WSEvent(type=kind, payload=data), kiosk_session_id=record.session_id or "legacy-unavailable")

    def _calculate_fee(self, amount):
        for tier in sorted(self._settings.ewallet_fee_tiers, key=lambda item: item.min):
            if amount >= tier.min and (tier.max is None or amount <= tier.max):
                return tier.fee
        raise EWalletTransactionError("Amount is outside the configured e-wallet fee tiers")

    @staticmethod
    def _require_cash_in(record):
        if record is None or record.direction != "cash-in":
            raise EWalletTransactionError("Transaction is not cash-in")

    @staticmethod
    def _serialize(record):
        fields = ("provider", "direction", "mobile_number", "account_name", "state", "amount", "fee",
                  "transfer_amount", "total_due", "inserted_amount", "inserted_denominations",
                  "dispensed_amount", "dispense_plan", "dispense_result", "gateway_payment_intent_id",
                  "gateway_batch_transfer_id", "gateway_transfer_id", "gateway_status", "qr_image_url",
                  "test_url", "claim_ticket_code", "error_code", "error_message", "change_due",
                  "change_dispensed", "retained_amount", "wallet_credited", "refunded_fee", "intake_counts")
        data = {key: getattr(record, key) for key in fields}
        data.update(transaction_id=record.id, version=record.version,
                    session_closed=not record.customer_present,
                    can_cancel=record.state in {"ACCEPTING_CASH", "WAITING_FOR_PAYMENT"}
                    and record.inserted_amount == 0 and record.gateway_status not in {"paid", "succeeded"},
                    shortfall=None)
        for key in ("created_at", "updated_at", "completed_at", "deadline"):
            value = getattr(record, key)
            data[key] = value.isoformat()+"Z" if value else None
        return data
