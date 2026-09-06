"""Durable forex lifecycle. Monetary totals are always scoped to a currency."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from sqlalchemy import select, text

from app.core.errors import TransactionError
from app.models.db_models import (TransactionRecord, ForexSession, ForexQuoteRecord,
    ForexIntake, DispenseExecution, PhysicalOperation, InventoryHold)
from app.models.forex import ForexQuote
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import DispensePlan, calculate_change
from app.services.forex_change_calculator import calculate_forex_dispense

logger = logging.getLogger(__name__)
TERMINAL = {"COMPLETE", "CANCELLED", "ERROR", "CLAIM_REQUIRED", "RESOLVED"}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def durable(method):
    @wraps(method)
    async def call(self, *args, **kwargs):
        task = asyncio.create_task(method(self, *args, **kwargs))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Finish accounting even when the initiating HTTP request disappears.
            return await task
    return call


class ForexTransactionOrchestrator:
    def __init__(self, bill_acceptor, dispense_orchestrator, machine_status, ws_manager,
                 forex_rate_service, db_session_factory, operation_mode=None,
                 receipt_service=None, claim_service=None, inventory_service=None):
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispense_orchestrator
        self._status = machine_status
        self._ws = ws_manager
        self._forex = forex_rate_service
        self._db_factory = db_session_factory
        self._operation_mode = operation_mode
        self._receipt_service = receipt_service
        self._claim_service = claim_service
        self._inventory = inventory_service
        self._lock = asyncio.Lock()
        self._active_id = None
        self._timer = None
        self._accounting_fault = False

    @property
    def has_active_transaction(self):
        return self._active_id is not None

    @property
    def active_transaction_id(self):
        return self._active_id

    def _require_active(self, expected_id=None):
        if not self._active_id or (expected_id is not None and expected_id != self._active_id):
            raise TransactionError("", "No active forex transaction")
        return self._active_id

    @staticmethod
    def _quantities(plan):
        return {( "BILL_DISPENSER" if i.denom_type == "bill" else "COIN_DISPENSER") + ":" + i.denom: i.count for i in plan.items}

    async def _hold(self, session, tx_id, leg, plan):
        if self._inventory is None:
            raise TransactionError(tx_id, "Durable inventory service is required")
        await self._inventory.hold_in_session(session, tx_id + ":" + leg, self._quantities(plan))

    async def _publish(self, tx_id):
        state = await self.get_transaction_state(tx_id)
        try:
            await self._ws.broadcast(WSEvent(type=WSEventType.TRANSACTION_STATE_CHANGED, payload=state))
        except Exception:
            logger.exception("Forex snapshot broadcast failed: %s", tx_id)
        return state

    async def _transition(self, session, record, meta, state, reset=False):
        record.state = state
        record.updated_at = now()
        meta.revision += 1
        if state in TERMINAL:
            record.completed_at = now()
            meta.deadline = None
        elif reset:
            meta.deadline = now() + timedelta(seconds=180)
        await session.commit()

    @durable
    async def start_transaction(self, service_type=None, selected_amount=None,
                                selected_dispense_denoms=None, *, quote_id=None, idempotency_key=None):
        async with self._lock:
            if not quote_id or not idempotency_key:
                raise ValueError("A reviewed quote_id and idempotency_key are required")
            async with self._db_factory() as session:
                existing = (await session.execute(select(ForexSession).where(ForexSession.idempotency_key == idempotency_key))).scalar_one_or_none()
                if existing:
                    if existing.quote_id != quote_id:
                        raise ValueError("Idempotency key belongs to a different quote")
                    return await self.get_transaction_state(existing.id)
                used = (await session.execute(select(ForexSession.id).where(ForexSession.quote_id == quote_id))).scalar_one_or_none()
                if used:
                    raise ValueError("Quote already used; retry with the original idempotency key")
                if self._active_id:
                    raise TransactionError(self._active_id, "A transaction is already in progress")
                if self._accounting_fault:
                    raise ValueError("Forex accounting reconciliation is required")
                saved = await session.get(ForexQuoteRecord, quote_id)
                if not saved or saved.expires_at <= now():
                    raise ValueError("QUOTE_EXPIRED: review a fresh quote")
                quote = ForexQuote(**saved.data)
                if not await self._forex.check_forex_available():
                    raise ValueError("Online connectivity and valid rates are required")
                snapshot = self._status.snapshot()
                if snapshot.security.tamper_active or self._status.should_block_dispensing_for_inventory_reconciliation():
                    raise ValueError("Machine requires security/inventory reconciliation")
                tx_id = str(uuid.uuid4())
                owned = False
                configured = False
                try:
                    if self._operation_mode:
                        self._operation_mode.begin_transaction(tx_id)
                        owned = True
                    plan = calculate_forex_dispense(quote, snapshot.consumables.bill_dispenser_counts,
                                                    snapshot.consumables.coin_counts)
                    await self._hold(session, tx_id, "EXCHANGE", plan)
                    record = TransactionRecord(id=tx_id, type="forex-" + quote.service_type,
                        state="WAITING_FOR_BILL", target_amount=int(quote.output_amount),
                        total_due=int(quote.input_amount), fee=int(quote.fee_amount),
                        from_currency=quote.from_currency, to_currency=quote.to_currency,
                        exchange_rate=quote.rate, rate_locked_at=now(),
                        forex_fee_percentage=quote.fee_percentage, converted_amount=int(quote.converted_amount))
                    meta = ForexSession(id=tx_id, quote_id=quote_id, idempotency_key=idempotency_key,
                        quote=quote.model_dump(mode="json"), revision=1, deadline=now()+timedelta(seconds=180),
                        legs={"EXCHANGE": {"currency": quote.to_currency, "plan": plan.model_dump()}})
                    session.add_all([record, meta])
                    configured = True
                    self._bill_acceptor.set_expected_currency(quote.from_currency)
                    self._bill_acceptor.set_expected_denomination(None if quote.from_currency == "PHP" else f"{quote.from_currency}_{quote.selected_amount}")
                    await session.commit()
                except BaseException:
                    await session.rollback()
                    try:
                        if configured:
                            self._bill_acceptor.set_expected_currency("PHP")
                            self._bill_acceptor.set_expected_denomination(None)
                    except Exception:
                        logger.exception("Failed to reset forex acceptor configuration")
                    finally:
                        if owned:
                            self._operation_mode.end_transaction(tx_id)
                    raise
            self._active_id = tx_id
            self._timer = asyncio.create_task(self._watch(tx_id))
            await self._inventory.refresh_runtime()
            return await self._publish(tx_id)

    @durable
    async def handle_bill_inserted(self, transaction_id=None):
        tx_id = transaction_id or self._require_active()
        async with self._lock:
            if tx_id != self._active_id:
                return await self.get_transaction_state(tx_id)
            state = await self.get_transaction_state(tx_id)
            if state["state"] != "WAITING_FOR_BILL":
                return state
            if not await self._bill_acceptor.wait_for_bill(timeout=5.0):
                return state
            if state.get("deadline") and datetime.fromisoformat(state["deadline"].removesuffix("Z")) <= now():
                await self._settle(tx_id, "INACTIVITY_TIMEOUT")
                await self._cleanup(tx_id)
                return await self._publish(tx_id)
            op_id = str(uuid.uuid4())
            async with self._db_factory() as session:
                record = await session.get(TransactionRecord, tx_id)
                meta = await session.get(ForexSession, tx_id)
                await self._transition(session, record, meta, "AUTHENTICATING")
            await self._publish(tx_id)

            async def prepare(denomination, value):
                async with self._db_factory() as session:
                    record = await session.get(TransactionRecord, tx_id)
                    meta = await session.get(ForexSession, tx_id)
                    if self._status.snapshot().security.tamper_active:
                        raise ValueError("LOCKED_OUT")
                    if record.from_currency != "PHP" and record.inserted_amount + value != record.total_due:
                        raise ValueError("Insert the selected foreign bill only")
                    change = max(0, record.inserted_amount + value - record.total_due)
                    if change:
                        snapshot = self._status.snapshot()
                        plan = calculate_change(change, snapshot.consumables.bill_dispenser_counts,
                                                snapshot.consumables.coin_counts, currency="PHP")
                        await self._hold(session, tx_id, "CHANGE", plan)
                        meta.legs = {**meta.legs, "CHANGE": {"currency": "PHP", "plan": plan.model_dump()}}
                    session.add(ForexIntake(id=op_id, transaction_id=tx_id, denomination=denomination.value, value=value))
                    await session.commit()
                await self._inventory.refresh_runtime()

            async def retained(denomination, value):
                async with self._db_factory() as session:
                    op = await session.get(ForexIntake, op_id)
                    if not op or op.state == "RETAINED":
                        return
                    record = await session.get(TransactionRecord, tx_id)
                    storage = denomination.value if record.from_currency == "PHP" else record.from_currency
                    await self._inventory.adjust_in_session(session, "BILL_STORAGE", storage, 1,
                                                            "FOREX_BILL_ACCEPTED", reference_id=tx_id)
                    record.inserted_amount += value
                    counts = dict(record.inserted_denominations or {})
                    counts[denomination.value] = counts.get(denomination.value, 0) + 1
                    record.inserted_denominations = counts
                    op.state = "RETAINED"
                    meta = await session.get(ForexSession, tx_id)
                    meta.revision += 1
                    await session.commit()
                await self._inventory.refresh_runtime()

            try:
                result = await asyncio.wait_for(self._bill_acceptor.accept_bill(skip_entry_wait=True,
                    on_authenticated=prepare, custom_store_and_record=retained), timeout=70)
            except Exception:
                logger.exception("Forex intake failed")
                result = None
            async with self._db_factory() as session:
                record = await session.get(TransactionRecord, tx_id)
                meta = await session.get(ForexSession, tx_id)
                op = await session.get(ForexIntake, op_id)
                if op is not None and op.state == "PREPARED" and getattr(result, "retention", None) == "EJECTED":
                    op.state = "EJECTED"
                    await session.commit()
                    await self._inventory.release_hold(tx_id + ":CHANGE")
                    meta.legs = {name: leg for name, leg in meta.legs.items() if name != "CHANGE"}
                    await session.commit()
                uncertain = op is not None and op.state not in {"RETAINED", "EJECTED"}
                fatal = result is None or getattr(result, "retention", "UNCERTAIN") == "UNCERTAIN"
                if fatal:
                    self._accounting_fault = True
                if uncertain:
                    op.state = "UNCERTAIN"
                    await session.commit()
                    self._accounting_fault = True
                    self._status.set_inventory_consistent(False)
                if uncertain or fatal or self._status.snapshot().security.tamper_active:
                    await self._settle(tx_id, "INTAKE_FAULT")
                    await self._cleanup(tx_id)
                else:
                    accepted = op is not None and op.state == "RETAINED"
                    record.error_message = None if accepted else getattr(result, "error", "Bill rejected")
                    await self._transition(session, record, meta,
                        "WAITING_FOR_CONFIRMATION" if record.inserted_amount >= record.total_due else "WAITING_FOR_BILL", reset=accepted)
            return await self._publish(tx_id)

    @durable
    async def confirm_transaction(self, transaction_id=None):
        tx_id = transaction_id or self._require_active()
        async with self._lock:
            if tx_id != self._active_id:
                return await self.get_transaction_state(tx_id)
            async with self._db_factory() as session:
                record = await session.get(TransactionRecord, tx_id)
                meta = await session.get(ForexSession, tx_id)
                if record.state != "WAITING_FOR_CONFIRMATION":
                    return await self.get_transaction_state(tx_id)
                if meta.deadline and meta.deadline <= now():
                    await self._settle(tx_id, "INACTIVITY_TIMEOUT")
                    await self._cleanup(tx_id)
                    return await self._publish(tx_id)
                meta.payout_started = True
                meta.deadline = None
                await self._transition(session, record, meta, "DISPENSING")
                legs = meta.legs
            await self._publish(tx_id)
            try:
                for leg in ("EXCHANGE", "CHANGE"):
                    if leg not in legs:
                        continue
                    result = await self._dispenser.execute_dispense(DispensePlan(**legs[leg]["plan"]),
                        reference_id=tx_id, source_kind="FOREX_" + leg)
                    if not result.success:
                        break
            except Exception:
                logger.exception("Forex payout interrupted: %s", tx_id)
            await self._settle(tx_id, "PAYOUT_RESULT")
            await self._cleanup(tx_id)
            return await self._publish(tx_id)

    async def _settle(self, tx_id, reason):
        async with self._db_factory() as session:
            record = await session.get(TransactionRecord, tx_id)
            meta = await session.get(ForexSession, tx_id)
            if record.state in {"COMPLETE", "RESOLVED", "CANCELLED"}:
                return
            old_ticket = record.claim_ticket_code
            items = []
            if not meta.payout_started:
                uncertain = (await session.execute(select(ForexIntake).where(ForexIntake.transaction_id == tx_id,
                    ForexIntake.state.in_(["PREPARED", "UNCERTAIN"])))).scalars().all()
                amount = record.inserted_amount + sum(op.value for op in uncertain)
                if amount:
                    items.append(dict(kind="INPUT_REFUND", currency=record.from_currency, amount=amount,
                                      status="PROVISIONAL" if uncertain else "OPEN"))
            else:
                legs = dict(meta.legs)
                for leg, data in legs.items():
                    execution = (await session.execute(select(DispenseExecution).where(
                        DispenseExecution.transaction_id == tx_id, DispenseExecution.source_kind == "FOREX_" + leg))).scalar_one_or_none()
                    operations = [] if not execution else (await session.execute(select(PhysicalOperation).where(PhysicalOperation.execution_id == execution.id))).scalars().all()
                    confirmed = sum(o.confirmed_count * o.denomination_value for o in operations)
                    ambiguous = sum((o.requested_count-o.confirmed_count)*o.denomination_value for o in operations
                                    if o.state in {"STARTED", "AMBIGUOUS"})
                    owed = max(0, data["plan"]["total_amount"] - confirmed)
                    legs[leg] = {**data, "confirmed": confirmed, "ambiguous": ambiguous, "owed": owed}
                    if owed:
                        items.append(dict(kind="OUTPUT_SHORTFALL" if leg == "EXCHANGE" else "PHP_CHANGE",
                            currency=data["currency"], amount=owed, status="PROVISIONAL" if ambiguous else "OPEN"))
                exchange = legs["EXCHANGE"]
                if exchange["owed"] and record.fee:
                    items.append(dict(kind="FEE_REFUND", currency="PHP", amount=record.fee,
                                      status="PROVISIONAL" if exchange["ambiguous"] else "OPEN"))
                meta.legs = legs
                record.dispensed_amount = exchange["confirmed"]
            if items or old_ticket:
                if self._claim_service is None:
                    raise RuntimeError("Durable claim service is required")
                ticket = await self._claim_service.create_forex(session, record, items, reason)
                record.claim_ticket_code = ticket
            await self._transition(session, record, meta,
                "CLAIM_REQUIRED" if items or old_ticket else "COMPLETE" if meta.payout_started else "CANCELLED")
        await self._release_holds(tx_id)
        state = await self.get_transaction_state(tx_id)
        if self._receipt_service:
            try:
                if items and not old_ticket:
                    await self._receipt_service.print_forex_claim(state)
                elif state["state"] == "COMPLETE":
                    await self._receipt_service.print_receipt(state)
            except Exception:
                logger.exception("Forex receipt failed after durable settlement: %s", tx_id)

    async def _release_holds(self, tx_id):
        if self._inventory:
            for leg in ("EXCHANGE", "CHANGE"):
                await self._inventory.release_hold(tx_id + ":" + leg)

    async def _cleanup(self, tx_id):
        if self._active_id == tx_id:
            self._active_id = None
            try:
                self._bill_acceptor.set_expected_currency("PHP")
                self._bill_acceptor.set_expected_denomination(None)
            except Exception:
                self._accounting_fault = True
                logger.exception("Failed to restore forex acceptor configuration")
            finally:
                if self._operation_mode:
                    self._operation_mode.end_transaction(tx_id)
                if self._timer and self._timer is not asyncio.current_task():
                    self._timer.cancel()
                self._timer = None

    @durable
    async def cancel_transaction(self, transaction_id=None):
        tx_id = transaction_id or self._require_active()
        async with self._lock:
            if tx_id != self._active_id:
                return await self.get_transaction_state(tx_id)
            state = await self.get_transaction_state(tx_id)
            if state["inserted_amount"]:
                raise TransactionError(tx_id, "CASH_ALREADY_ACCEPTED: cancellation is disabled")
            await self._settle(tx_id, "CANCELLED_BY_CUSTOMER")
            await self._cleanup(tx_id)
            return await self._publish(tx_id)

    @durable
    async def continue_transaction(self, transaction_id=None):
        tx_id = transaction_id or self._require_active()
        async with self._lock:
            self._require_active(tx_id)
            async with self._db_factory() as session:
                record = await session.get(TransactionRecord, tx_id)
                meta = await session.get(ForexSession, tx_id)
                if record.state not in {"WAITING_FOR_BILL", "WAITING_FOR_CONFIRMATION"}:
                    raise ValueError("Cannot extend this transaction")
                if meta.deadline and meta.deadline <= now():
                    await self._settle(tx_id, "INACTIVITY_TIMEOUT")
                    await self._cleanup(tx_id)
                    return await self._publish(tx_id)
                await self._transition(session, record, meta, record.state, reset=True)
            return await self._publish(tx_id)

    async def _watch(self, tx_id):
        while self._active_id == tx_id:
            await asyncio.sleep(1)
            async with self._lock:
                if self._active_id != tx_id:
                    return
                async with self._db_factory() as session:
                    meta = await session.get(ForexSession, tx_id)
                    expired = meta.deadline and meta.deadline <= now()
                if expired:
                    await self._settle(tx_id, "INACTIVITY_TIMEOUT")
                    await self._cleanup(tx_id)
                    await self._publish(tx_id)
                    return

    async def stop(self):
        if self._timer:
            self._timer.cancel()
            await asyncio.gather(self._timer, return_exceptions=True)
            self._timer = None

    async def handle_tamper(self, sensor):
        async with self._lock:
            if self._active_id:
                tx_id = self._active_id
                await self._settle(tx_id, "TAMPER: " + str(sensor))
                await self._cleanup(tx_id)
                await self._publish(tx_id)

    async def get_transaction_state(self, transaction_id):
        async with self._db_factory() as session:
            if session.bind.dialect.name == "sqlite":
                await session.execute(text("BEGIN"))
            record = await session.get(TransactionRecord, transaction_id)
            if not record or not record.type.startswith("forex-"):
                raise TransactionError(transaction_id, "Transaction not found")
            meta = await session.get(ForexSession, transaction_id)
            state = {key: getattr(record, key) for key in ("type", "state", "target_amount", "fee", "total_due",
                "inserted_amount", "dispensed_amount", "inserted_denominations", "from_currency", "to_currency",
                "exchange_rate", "forex_fee_percentage", "converted_amount", "claim_ticket_code", "error_code", "error_message")}
            state.update(transaction_id=transaction_id, revision=meta.revision if meta else 0,
                quote=meta.quote if meta else None, payout_legs=meta.legs if meta else {},
                deadline=meta.deadline.isoformat()+"Z" if meta and meta.deadline else None,
                legacy_review_required=meta is None)
            state.update({key: getattr(record, key).isoformat() + "Z" if getattr(record, key) else None
                          for key in ("created_at", "updated_at", "completed_at")})
            if meta:
                # Progress is reconstructed from durable per-currency evidence.
                legs = {}
                for name, leg in meta.legs.items():
                    execution = (await session.execute(select(DispenseExecution).where(
                        DispenseExecution.transaction_id == transaction_id,
                        DispenseExecution.source_kind == "FOREX_" + name))).scalar_one_or_none()
                    ops = [] if execution is None else (await session.execute(select(PhysicalOperation).where(
                        PhysicalOperation.execution_id == execution.id))).scalars().all()
                    confirmed = sum(o.confirmed_count * o.denomination_value for o in ops)
                    legs[name] = {**leg, "confirmed": confirmed}
                state["payout_legs"] = legs
            if self._claim_service:
                state["claim"] = await self._claim_service.get_forex(transaction_id=transaction_id, session=session)
            return state

    async def recover_pending_transactions(self):
        async with self._db_factory() as session:
            rows = (await session.execute(select(TransactionRecord).where(TransactionRecord.type.like("forex-%")))).scalars().all()
            pending = []
            finalized = []
            for record in rows:
                meta = await session.get(ForexSession, record.id)
                if meta and record.state not in {"COMPLETE", "CANCELLED", "RESOLVED"}:
                    pending.append(record.id)
                elif meta:
                    finalized.append(record.id)
                elif not meta and record.state not in TERMINAL:
                    self._accounting_fault = True
            uncertain = (await session.execute(select(ForexIntake.id).where(ForexIntake.state.in_(["PREPARED", "UNCERTAIN"])))).first()
            self._accounting_fault = self._accounting_fault or bool(uncertain)
        for tx_id in finalized:
            # A crash can occur after the terminal commit but before hold cleanup.
            # release_hold only releases HELD inventory, never consumed stock.
            await self._release_holds(tx_id)
        for tx_id in pending:
            await self._settle(tx_id, "STARTUP_RECOVERY")

    async def reconcile_intake(self, operation_id, retained, operator, notes):
        async with self._lock:
            if self._active_id:
                raise ValueError("Finish the active forex session before reconciliation")
            async with self._db_factory() as session:
                op = await session.get(ForexIntake, operation_id)
                if not op or op.state not in {"PREPARED", "UNCERTAIN"}:
                    raise ValueError("Intake is not awaiting reconciliation")
                record = await session.get(TransactionRecord, op.transaction_id)
                if retained:
                    await self._inventory.adjust_in_session(session, "BILL_STORAGE",
                        op.denomination if record.from_currency == "PHP" else record.from_currency,
                        1, "FOREX_INTAKE_RECONCILED", reference_id=record.id)
                    record.inserted_amount += op.value
                    counts = dict(record.inserted_denominations or {})
                    counts[op.denomination] = counts.get(op.denomination, 0) + 1
                    record.inserted_denominations = counts
                op.state = "RETAINED" if retained else "EJECTED"
                op.resolved_by = operator
                op.resolution_notes = notes
                await session.commit()
                tx_id = record.id
            await self._inventory.refresh_runtime()
            await self._settle(tx_id, "INTAKE_RECONCILED")
            self._accounting_fault = False
            await self.recover_pending_transactions()
            return await self._publish(tx_id)

    async def reconcile_payout(self, tx_id):
        async with self._lock:
            if self._active_id:
                raise ValueError("Finish the active forex session before reconciliation")
            await self._settle(tx_id, "PAYOUT_RECONCILED")
            return await self._publish(tx_id)

    async def availability(self):
        snapshot = self._status.snapshot()
        result = {}
        for service, amounts in {"usd-to-php": [10, 50], "php-to-usd": [10, 50], "eur-to-php": [5, 10], "php-to-eur": [5, 10]}.items():
            result[service] = []
            for amount in amounts:
                reason = None
                try:
                    if not self._forex.enabled or not self._forex.is_online or not self._forex.rates_valid:
                        raise ValueError("Online connectivity and valid rates are required")
                    quote = self._forex.get_quote(service, amount)
                    calculate_forex_dispense(quote, snapshot.consumables.bill_dispenser_counts, snapshot.consumables.coin_counts)
                except Exception as exc:
                    reason = str(exc)
                result[service].append(dict(amount=amount, available=reason is None, reason=reason))
        return result
