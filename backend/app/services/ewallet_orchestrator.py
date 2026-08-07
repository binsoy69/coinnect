"""Persistent PayMongo-backed e-wallet transaction orchestration."""

from __future__ import annotations

import asyncio
import logging
import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.config import Settings
from app.core.errors import EWalletTransactionError
from app.models.db_models import (
    EWalletTransactionRecord,
    GatewayEventRecord,
)
from app.models.events import WSEvent, WSEventType
from app.services.change_calculator import calculate_change
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.machine_status import MachineStatus
from app.services.paymongo_client import PayMongoClient
from app.services.operation_mode import OperationModeManager
from app.services.receipt_service import ReceiptService
from app.drivers.coin_security_controller import CoinSecurityController

logger = logging.getLogger(__name__)


def _claim_ticket() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class EWalletOrchestrator:
    def __init__(
        self,
        settings: Settings,
        gateway: PayMongoClient,
        bill_acceptor,
        dispenser: DispenseOrchestrator,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        db_session_factory: async_sessionmaker,
        operation_mode: OperationModeManager | None = None,
        receipt_service: ReceiptService | None = None,
        coin_controller: CoinSecurityController | None = None,
        claim_service=None,
    ):
        self._settings = settings
        self._gateway = gateway
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispenser
        self._coin_controller = coin_controller
        self._status = machine_status
        self._ws = ws_manager
        self._db_factory = db_session_factory
        self._active_transaction_id: str | None = None
        self._operation_mode = operation_mode
        self._operation_owner: str | None = None
        self._receipt_service = receipt_service
        self._confirm_lock = asyncio.Lock()
        self._claim_service = claim_service
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    async def enqueue_gateway_event(self, event: dict) -> dict:
        """Durably accept a verified gateway event before acknowledging it."""
        event_id = str(event.get("id") or "").strip()
        if not event_id:
            raise EWalletTransactionError("Gateway event ID is required", "INVALID_EVENT")
        async with self._db_factory() as session:
            if await session.get(GatewayEventRecord, event_id):
                return {"accepted": True, "event_id": event_id, "duplicate": True}
            session.add(GatewayEventRecord(
                id=event_id,
                event_type=str(event.get("type", "unknown")),
                resource_id=event.get("resource_id"),
                payload=event,
                processed=False,
                status="RECEIVED",
            ))
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                if await session.get(GatewayEventRecord, event_id):
                    return {"accepted": True, "event_id": event_id, "duplicate": True}
                raise
        return {"accepted": True, "event_id": event_id, "duplicate": False}

    @property
    def has_active_transaction(self) -> bool:
        return self._active_transaction_id is not None

    async def start_transaction(
        self,
        *,
        provider: str,
        direction: str,
        amount: int,
        mobile_number: str | None = None,
        account_name: str | None = None,
    ) -> dict:
        if not self._status.is_online:
            raise EWalletTransactionError("Kiosk is offline. E-wallet transactions are disabled.")
        provider = provider.lower()
        direction = direction.lower()

        if provider not in {"gcash", "maya"}:
            raise EWalletTransactionError("Provider must be gcash or maya")
        if direction not in {"cash-in", "cash-out"}:
            raise EWalletTransactionError("Direction must be cash-in or cash-out")
        if direction == "cash-in":
            if (
                not mobile_number
                or len(mobile_number) != 11
                or not mobile_number.startswith("09")
                or not mobile_number.isdigit()
            ):
                raise EWalletTransactionError("Invalid mobile number")
            if not account_name or not account_name.strip():
                raise EWalletTransactionError("Account name is required")
        elif mobile_number is not None or account_name is not None:
            raise EWalletTransactionError(
                "Cash-out does not accept account identity fields"
            )
        if self._active_transaction_id is not None:
            raise EWalletTransactionError(
                "Another e-wallet transaction is already active"
            )

        fee = self._calculate_fee(amount)
        if amount <= fee:
            raise EWalletTransactionError("Amount must be greater than the fee")
        transfer_amount = amount - fee
        snapshot = self._status.snapshot()
        if not snapshot.consumables.inventory_consistent:
            raise EWalletTransactionError(
                "Inventory reconciliation is required"
            )
        if direction == "cash-out":
            calculate_change(
                transfer_amount,
                snapshot.consumables.bill_dispenser_counts,
                snapshot.consumables.coin_counts,
            )

        tx_id = str(uuid.uuid4())
        if self._operation_mode:
            self._operation_mode.begin_transaction(tx_id)
            self._operation_owner = tx_id
        record = EWalletTransactionRecord(
            id=tx_id,
            provider=provider,
            direction=direction,
            mobile_number=mobile_number or "",
            account_name=account_name.strip() if account_name else "",
            state="ACCEPTING_CASH" if direction == "cash-in" else "CREATED",
            amount=amount,
            fee=fee,
            transfer_amount=transfer_amount,
            total_due=amount,
        )
        try:
            async with self._db_factory() as session:
                session.add(record)
                await session.commit()
        except Exception:
            await self._clear_active()
            raise
        self._active_transaction_id = tx_id

        if direction == "cash-in":
            try:
                await self._set_coin_acceptor_enabled(True, raise_on_error=True)
            except Exception:
                await self._clear_active()
                async with self._db_factory() as session:
                    failed = await session.get(EWalletTransactionRecord, tx_id)
                    failed.state = "FAILED"
                    failed.error_code = "COIN_ACCEPTOR_ERROR"
                    failed.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                raise

        if direction == "cash-out":
            try:
                qr = await self._gateway.create_qr_payment(
                    amount_centavos=amount * 100,
                    reference=tx_id,
                    idempotency_key=f"ewallet:{tx_id}:qr",
                )
            except Exception:
                await self._clear_active()
                async with self._db_factory() as session:
                    failed = await session.get(EWalletTransactionRecord, tx_id)
                    failed.state = "FAILED"
                    failed.error_code = "QR_CREATION_FAILED"
                    failed.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                raise
            async with self._db_factory() as session:
                record = await session.get(EWalletTransactionRecord, tx_id)
                record.gateway_payment_intent_id = qr.payment_intent_id
                record.gateway_status = qr.status
                record.qr_image_url = qr.qr_image_url
                record.test_url = qr.test_url
                record.state = "WAITING_FOR_PAYMENT"
                await session.commit()
            await self._broadcast(record, WSEventType.EWALLET_GATEWAY_PENDING)
        else:
            await self._broadcast(record, WSEventType.EWALLET_STATE_CHANGED)
        self._reset_timeout(tx_id)
        return await self.get_transaction(tx_id)

    async def record_cash_insert(
        self, transaction_id: str, denomination: int
    ) -> dict:
        if denomination not in {1, 5, 10, 20, 50, 100, 200, 500, 1000}:
            raise EWalletTransactionError("Invalid PHP denomination")
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            self._require_cash_in(record)
            if record.state not in {"ACCEPTING_CASH", "CASH_ACCEPTED"}:
                raise EWalletTransactionError(
                    f"Cannot accept cash in state {record.state}"
                )
            record.inserted_amount += denomination
            denoms = dict(record.inserted_denominations or {})
            key = str(denomination)
            denoms[key] = denoms.get(key, 0) + 1
            record.inserted_denominations = denoms
            if record.inserted_amount >= record.total_due:
                record.state = "CASH_ACCEPTED"
                await self._set_coin_acceptor_enabled(False)
            await session.commit()
            event = (
                WSEventType.EWALLET_CASH_ACCEPTED
                if record.state == "CASH_ACCEPTED"
                else WSEventType.EWALLET_STATE_CHANGED
            )
            await self._broadcast(record, event)
        self._reset_timeout(transaction_id)
        return await self.get_transaction(transaction_id)

    async def accept_bill(self, transaction_id: str) -> dict:
        result = await self._bill_acceptor.accept_bill()
        if not result.success:
            raise EWalletTransactionError(result.error or "Bill rejected")
        return await self.record_cash_insert(transaction_id, result.value)

    async def handle_coin_inserted(self, denomination: int) -> None:
        """Route a hardware coin event to the active cash-in, if any."""
        async with self._db_factory() as session:
            result = await session.execute(
                select(EWalletTransactionRecord)
                .where(
                    EWalletTransactionRecord.direction == "cash-in",
                    EWalletTransactionRecord.state == "ACCEPTING_CASH",
                )
                .order_by(EWalletTransactionRecord.created_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
            transaction_id = record.id if record else None
        if transaction_id:
            await self.record_cash_insert(transaction_id, denomination)

    async def confirm_cash_in(self, transaction_id: str) -> dict:
        async with self._confirm_lock:
            return await self._confirm_cash_in_once(transaction_id)

    async def _confirm_cash_in_once(self, transaction_id: str) -> dict:
        self._cancel_timeout(transaction_id)
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            self._require_cash_in(record)
            if record.state in {
                "DISBURSEMENT_PENDING",
                "COMPLETE",
                "CLAIM_REQUIRED",
                "FAILED",
            }:
                return self._serialize(record)
            if record.state != "CASH_ACCEPTED":
                raise EWalletTransactionError("Required cash has not been accepted")
            account_number = record.mobile_number
            provider = record.provider
            account_name = record.account_name
            transfer_amount = record.transfer_amount

        try:
            result = await self._gateway.create_disbursement(
                provider=provider,
                account_number=account_number,
                account_name=account_name,
                amount_centavos=transfer_amount * 100,
                reference=transaction_id,
                idempotency_key=f"ewallet:{transaction_id}:transfer",
            )
        except Exception as exc:
            return await self._mark_claim_required(
                transaction_id, "DISBURSEMENT_FAILED", str(exc)
            )

        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            record.gateway_batch_transfer_id = result.batch_transfer_id
            record.gateway_transfer_id = result.transfer_id
            record.gateway_status = result.status
            record.state = "DISBURSEMENT_PENDING"
            await session.commit()
            await self._broadcast(record, WSEventType.EWALLET_GATEWAY_PENDING)
        return await self.get_transaction(transaction_id)

    async def process_gateway_event(
        self, event: dict, persisted_event_id: str | None = None
    ) -> dict:
        event_id = str(event["id"])
        if persisted_event_id is None:
            accepted = await self.enqueue_gateway_event(event)
            if accepted["duplicate"]:
                return {"duplicate": True}

        resource_id = event.get("resource_id")
        if not resource_id:
            raise EWalletTransactionError("Gateway event resource_id is missing", "INVALID_EVENT")

        async with self._db_factory() as session:
            result = await session.execute(
                select(EWalletTransactionRecord).where(
                    or_(
                        EWalletTransactionRecord.gateway_payment_intent_id
                        == resource_id,
                        EWalletTransactionRecord.gateway_transfer_id
                        == resource_id,
                    )
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                raise EWalletTransactionError(
                    "Gateway transaction is not committed yet", "TRANSACTION_NOT_FOUND"
                )
            status = str(event.get("status") or "").lower()
            record.gateway_status = status
            await session.commit()


        try:
            if (
                record.direction == "cash-out"
                and event.get("type") == "payment.paid"
            ):
                result_payload = await self._verify_and_dispense_cash_out(
                    record.id,
                    event.get("payment_id"),
                )
            elif (
                record.direction == "cash-in"
                and event.get("type") in {"transfer.outward.successful", "transfer.outward.failed"}
            ):
                result_payload = await self._verify_and_complete_cash_in(record.id)
            elif status in {"failed", "cancelled", "expired", "returned"}:
                if record.direction == "cash-in":
                    result_payload = await self._mark_claim_required(
                        record.id,
                        "GATEWAY_FAILED",
                        f"PayMongo status: {status}",
                    )
                    record = None
                else:
                    async with self._db_factory() as session:
                        record = await session.get(EWalletTransactionRecord, record.id)
                        record.state = "FAILED"
                        record.error_code = "GATEWAY_FAILED"
                        record.error_message = f"PayMongo status: {status}"
                        await session.commit()
                        await self._broadcast(record, WSEventType.EWALLET_GATEWAY_FAILED)
                        await self._clear_active()
                    result_payload = await self.get_transaction(record.id)
            else:
                result_payload = {"processed": True, "status": status}
        except Exception as exc:
            logger.error(f"Error processing gateway event {event_id}: {exc}", exc_info=True)
            raise


        async with self._db_factory() as session:
            stored_event = await session.get(GatewayEventRecord, event_id)
            stored_event.processed = True
            stored_event.status = "PROCESSED"
            stored_event.processing_error = None
            stored_event.lease_expires_at = None
            stored_event.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
        return result_payload

    async def escalate_gateway_event(self, event: dict, error: str) -> None:
        """Issue a durable provisional claim after fast retries are exhausted."""
        event_type = str(event.get("type") or "")
        if event_type not in {
            "payment.paid",
            "payment_intent.succeeded",
            "transfer.outward.successful",
            "transfer.outward.failed",
        }:
            return
        resource_id = event.get("resource_id")
        async with self._db_factory() as session:
            record = (await session.execute(
                select(EWalletTransactionRecord).where(or_(
                    EWalletTransactionRecord.gateway_payment_intent_id == resource_id,
                    EWalletTransactionRecord.gateway_transfer_id == resource_id,
                ))
            )).scalar_one_or_none()
        if record is not None and record.state not in {"COMPLETE", "CLAIM_REQUIRED"}:
            await self._mark_claim_required(
                record.id,
                "GATEWAY_RECONCILIATION_PENDING",
                f"Gateway event remains unreconciled after fast retries: {error}",
                provisional=True,
            )

    async def _verify_and_complete_cash_in(
        self,
        transaction_id: str,
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record is None:
                raise EWalletTransactionError("Transaction not found")
            batch_transfer_id = record.gateway_batch_transfer_id
            transfer_id = record.gateway_transfer_id
            if not batch_transfer_id or not transfer_id:
                raise EWalletTransactionError("Missing transfer identifiers")

        try:
            batch = await self._gateway.get_batch_transfer(batch_transfer_id)
            transfers = batch.get("transfers") or []
            transfer = next(
                (
                    item
                    for item in transfers
                    if item.get("id") == transfer_id
                ),
                None,
            )
            if (
                batch.get("id") != batch_transfer_id
                or transfer is None
                or transfer.get("reference_number") != transaction_id
            ):
                raise EWalletTransactionError(
                    "PayMongo transfer reconciliation mismatch"
                )
            status = str(transfer.get("status") or "").lower()
            expected_amount = record.transfer_amount * 100
            if transfer.get("amount") != expected_amount:
                raise EWalletTransactionError("Transfer amount mismatch")
            if str(transfer.get("currency") or "").upper() != "PHP":
                raise EWalletTransactionError("Transfer currency mismatch")
        except Exception as exc:
            return await self._mark_claim_required(
                transaction_id,
                "TRANSFER_VERIFICATION_FAILED",
                str(exc),
            )

        async with self._db_factory() as session:
            record = await session.get(
                EWalletTransactionRecord, transaction_id
            )
            record.gateway_status = status
            await session.commit()
        if status in {"success", "succeeded", "paid"}:
            return await self._complete_cash_in(transaction_id)
        if status in {"failed", "cancelled", "returned", "rejected"}:
            return await self._mark_claim_required(
                transaction_id,
                "TRANSFER_FAILED",
                f"PayMongo transfer status: {status}",
            )
        return await self.get_transaction(transaction_id)

    async def get_transaction(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record is None:
                raise EWalletTransactionError("Transaction not found")
            return self._serialize(record)

    async def cancel_transaction(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record is None:
                raise EWalletTransactionError("Transaction not found")
            if record.state not in {"CREATED", "WAITING_FOR_PAYMENT", "ACCEPTING_CASH"}:
                raise EWalletTransactionError(
                    f"Transaction is not cancellable in state {record.state}",
                    "TRANSACTION_NOT_CANCELLABLE",
                )
            if record.inserted_amount > 0 or record.gateway_status in {
                "succeeded",
                "paid",
            }:
                raise EWalletTransactionError(
                    "CASH_ALREADY_ACCEPTED: transaction requires operator reconciliation",
                    "CASH_ALREADY_ACCEPTED",
                )
            if record.gateway_payment_intent_id:
                try:
                    intent = await self._gateway.get_payment_intent(record.gateway_payment_intent_id)
                    status = (intent.get("attributes") or {}).get("status")
                    if status in {"succeeded", "paid"}:
                        record.gateway_status = status
                        await session.commit()
                        raise EWalletTransactionError(
                            "Transaction cannot be cancelled because payment is already completed."
                        )
                except EWalletTransactionError:
                    raise
                except Exception as exc:
                    logger.warning(f"Failed to fetch live payment status during cancellation: {exc}")

            record.state = "CANCELLED"
            record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            
            # Spawn background cancel task for PayMongo QR Code
            if record.gateway_payment_intent_id:
                import asyncio
                asyncio.create_task(self._cancel_payment_intent_background(record.gateway_payment_intent_id))

            await self._broadcast(record, WSEventType.EWALLET_STATE_CHANGED)
            await self._clear_active()
            return self._serialize(record)

    async def _cancel_payment_intent_background(self, intent_id: str) -> None:
        try:
            logger.info(f"Cancelling Payment Intent {intent_id} in background...")
            await self._gateway.cancel_payment_intent(intent_id)
            logger.info(f"Payment Intent {intent_id} successfully cancelled.")
        except Exception as exc:
            logger.error(f"Failed to cancel Payment Intent {intent_id} in background: {exc}")

    async def recover_pending_transactions(self) -> None:
        pending_disbursements = []
        async with self._db_factory() as session:
            result = await session.execute(
                select(EWalletTransactionRecord).where(
                    EWalletTransactionRecord.state.in_(
                        {
                            "CASH_ACCEPTED",
                            "DISBURSEMENT_PENDING",
                            "PAYMENT_CONFIRMED",
                            "DISPENSING",
                        }
                    )
                )
            )
            records = list(result.scalars())
            for record in records:
                if record.state == "DISBURSEMENT_PENDING":
                    pending_disbursements.append(record.id)
                elif record.inserted_amount > 0 or record.gateway_status in {
                    "succeeded",
                    "paid",
                }:
                    if self._claim_service:
                        post_authorization = record.state in {"PAYMENT_CONFIRMED", "DISPENSING"}
                        await self._claim_service.create(
                            source_kind="EWALLET",
                            transaction_id=record.id,
                            claim_kind="OUTPUT_SHORTFALL" if post_authorization else "INPUT_REFUND",
                            amount=(
                                max(0, record.transfer_amount - record.dispensed_amount)
                                if post_authorization else record.inserted_amount
                            ),
                            currency="PHP",
                            reason_code="CRASH_RECOVERY",
                            reason_message="Recovered interrupted e-wallet transaction during startup",
                            confirmed_dispensed_amount=record.dispensed_amount,
                            provisional=post_authorization,
                            record=record,
                            session=session,
                        )
                    else:
                        record.state = "CLAIM_REQUIRED"
                        record.claim_ticket_code = record.claim_ticket_code or _claim_ticket()
                        record.error_code = "CRASH_RECOVERY"
            await session.commit()

        for tx_id in pending_disbursements:
            try:
                logger.info(f"Reconciling pending disbursement {tx_id} with PayMongo API...")
                await self.verify_cash_in_disbursement(tx_id)
            except Exception as e:
                logger.error(f"Failed to reconcile pending disbursement {tx_id} during recovery: {e}")
                # Fallback: mark as claim required if verification fails completely
                await self._mark_claim_required(
                    tx_id,
                    "TRANSFER_VERIFICATION_FAILED",
                    f"Recovery error: {e}",
                )

        await self._clear_active()


    async def _dispense_paid_cash_out(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record.state in {"COMPLETE", "CLAIM_REQUIRED", "DISPENSING"}:
                return self._serialize(record)
            if record.state == "CANCELLED":
                if self._claim_service:
                    await self._claim_service.create(
                        source_kind="EWALLET", transaction_id=record.id,
                        claim_kind="OUTPUT_SHORTFALL", amount=record.transfer_amount,
                        currency="PHP", reason_code="LATE_PAYMENT_ON_CANCELLED",
                        reason_message="Payment received after transaction was cancelled",
                        provisional=True, record=record, session=session,
                    )
                else:
                    record.state = "CLAIM_REQUIRED"
                    record.claim_ticket_code = record.claim_ticket_code or _claim_ticket()
                    record.error_code = "LATE_PAYMENT_ON_CANCELLED"
                    record.error_message = "Payment received after transaction was cancelled"
                    record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                await self._clear_active()
                return self._serialize(record)
            snapshot = self._status.snapshot()
            plan = calculate_change(
                record.transfer_amount,
                snapshot.consumables.bill_dispenser_counts,
                snapshot.consumables.coin_counts,
            )
            record.state = "DISPENSING"
            record.dispense_plan = {
                "items": [item.model_dump() for item in plan.items],
                "total_amount": plan.total_amount,
            }
            await session.commit()
        result = await self._dispenser.execute_dispense(
            plan, reference_id=transaction_id, source_kind="EWALLET"
        )
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            record.dispensed_amount = result.total_dispensed
            record.dispense_result = result.model_dump()
            record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if result.success:
                record.state = "COMPLETE"
                event_type = WSEventType.EWALLET_COMPLETE
                await session.commit()
            else:
                event_type = WSEventType.EWALLET_CLAIM_REQUIRED
                if self._claim_service:
                    await self._claim_service.create(
                        source_kind="EWALLET",
                        transaction_id=record.id,
                        claim_kind="OUTPUT_SHORTFALL",
                        amount=result.shortfall,
                        currency="PHP",
                        reason_code="AMBIGUOUS_DISPENSE" if result.ambiguous_amount else "PARTIAL_DISPENSE",
                        reason_message=result.error,
                        confirmed_dispensed_amount=result.total_dispensed,
                        ambiguous_amount=result.ambiguous_amount,
                        provisional=bool(result.ambiguous_amount),
                        record=record,
                        session=session,
                    )
                else:
                    record.state = "CLAIM_REQUIRED"
                    record.claim_ticket_code = result.claim_ticket_code or _claim_ticket()
                    record.error_code = "PARTIAL_DISPENSE"
                    record.error_message = result.error
                    await session.commit()
            if self._receipt_service:
                if result.success:
                    await self._receipt_service.print_receipt(record)
                elif not self._claim_service:
                    await self._receipt_service.print_claim_ticket(
                        record,
                        claim_code=record.claim_ticket_code,
                        shortfall=result.shortfall,
                        error_reason=result.error
                    )
            await self._broadcast(record, event_type)
            await self._clear_active()
            return self._serialize(record)

    async def _complete_cash_in(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record.state == "CLAIM_REQUIRED":
                await self._note_late_gateway_success(session, record)
                return self._serialize(record)
            if record.state == "COMPLETE":
                return self._serialize(record)
            record.state = "COMPLETE"
            record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            if self._receipt_service:
                await self._receipt_service.print_receipt(record)
            await self._broadcast(record, WSEventType.EWALLET_COMPLETE)
            await self._clear_active()
            return self._serialize(record)

    async def _verify_and_dispense_cash_out(
        self,
        transaction_id: str,
        payment_id: str | None,
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(
                EWalletTransactionRecord, transaction_id
            )
            if record.state == "CANCELLED":
                if self._claim_service:
                    await self._claim_service.create(
                        source_kind="EWALLET", transaction_id=record.id,
                        claim_kind="OUTPUT_SHORTFALL", amount=record.transfer_amount,
                        currency="PHP", reason_code="LATE_PAYMENT_ON_CANCELLED",
                        reason_message="Payment received after transaction was cancelled",
                        provisional=True, record=record, session=session,
                    )
                else:
                    record.state = "CLAIM_REQUIRED"
                    record.claim_ticket_code = record.claim_ticket_code or _claim_ticket()
                    record.error_code = "LATE_PAYMENT_ON_CANCELLED"
                    record.error_message = "Payment received after transaction was cancelled"
                    record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
                await self._clear_active()
                return self._serialize(record)
            intent_id = record.gateway_payment_intent_id
            expected_amount = record.amount * 100
        try:
            intent = await self._gateway.get_payment_intent(intent_id)
            attrs = intent.get("attributes") or {}
            payments = attrs.get("payments") or []
            payment = next(
                (
                    item
                    for item in payments
                    if payment_id is None or item.get("id") == payment_id
                ),
                None,
            )
            payment_attrs = (
                payment.get("attributes") or {} if payment else {}
            )
            metadata = attrs.get("metadata") or {}
            if intent.get("id") != intent_id:
                raise EWalletTransactionError("Payment Intent ID mismatch")
            if attrs.get("status") != "succeeded":
                raise EWalletTransactionError(
                    "Payment Intent is not succeeded"
                )
            if attrs.get("amount") != expected_amount:
                raise EWalletTransactionError("Payment amount mismatch")
            if str(attrs.get("currency") or "").upper() != "PHP":
                raise EWalletTransactionError("Payment currency mismatch")
            if metadata.get("coinnect_transaction_id") != transaction_id:
                raise EWalletTransactionError(
                    "Payment transaction metadata mismatch"
                )
            if payment is None:
                raise EWalletTransactionError("Paid Payment not found")
            if payment_attrs.get("status") != "paid":
                raise EWalletTransactionError("Payment is not paid")
            if payment_attrs.get("amount") != expected_amount:
                raise EWalletTransactionError("Paid amount mismatch")
            if str(payment_attrs.get("currency") or "").upper() != "PHP":
                raise EWalletTransactionError("Paid currency mismatch")
            if (payment_attrs.get("source") or {}).get("type") != "qrph":
                raise EWalletTransactionError("Payment source is not QR Ph")
        except Exception as exc:
            return await self._mark_claim_required(
                transaction_id,
                "PAYMENT_VERIFICATION_FAILED",
                str(exc),
            )

        async with self._db_factory() as session:
            claimed = await session.execute(
                update(EWalletTransactionRecord)
                .where(
                    EWalletTransactionRecord.id == transaction_id,
                    EWalletTransactionRecord.state == "WAITING_FOR_PAYMENT",
                )
                .values(gateway_status="paid", state="PAYMENT_CONFIRMED")
            )
            await session.commit()
            if claimed.rowcount != 1:
                record = await session.get(EWalletTransactionRecord, transaction_id)
                if record.state == "CLAIM_REQUIRED":
                    await self._note_late_gateway_success(session, record)
                return self._serialize(record)
        self._cancel_timeout(transaction_id)
        return await self._dispense_paid_cash_out(transaction_id)

    async def _mark_claim_required(
        self,
        transaction_id: str,
        error_code: str,
        error_message: str,
        provisional: bool = False,
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(
                EWalletTransactionRecord, transaction_id
            )
            if record.direction == "cash-in":
                amount = record.inserted_amount
                claim_kind = "INPUT_REFUND"
            else:
                amount = max(0, record.transfer_amount - record.dispensed_amount)
                claim_kind = "OUTPUT_SHORTFALL"
            if self._claim_service:
                await self._claim_service.create(
                    source_kind="EWALLET",
                    transaction_id=record.id,
                    claim_kind=claim_kind,
                    amount=amount,
                    currency="PHP",
                    reason_code=error_code,
                    reason_message=error_message,
                    confirmed_dispensed_amount=record.dispensed_amount,
                    provisional=provisional or "VERIFICATION" in error_code,
                    record=record,
                    session=session,
                )
            else:
                record.state = "CLAIM_REQUIRED"
                record.claim_ticket_code = record.claim_ticket_code or _claim_ticket()
                record.error_code = error_code
                record.error_message = error_message
                record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
                if self._receipt_service:
                    await self._receipt_service.print_claim_ticket(
                        record,
                        claim_code=record.claim_ticket_code,
                        shortfall=amount,
                        error_reason=record.error_message
                    )
            await self._broadcast(
                record,
                WSEventType.EWALLET_CLAIM_REQUIRED,
            )
            await self._clear_active()
            return self._serialize(record)

    async def _note_late_gateway_success(self, session, record) -> None:
        """Preserve an issued claim while flagging a late success for review."""
        from app.models.db_models import ClaimRecord
        claim = (await session.execute(
            select(ClaimRecord).where(
                ClaimRecord.source_kind == "EWALLET",
                ClaimRecord.transaction_id == record.id,
                ClaimRecord.status != "RESOLVED",
            ).limit(1)
        )).scalar_one_or_none()
        record.gateway_status = "late_success"
        record.error_code = "LATE_GATEWAY_SUCCESS"
        record.error_message = "Gateway later reported success; operator review is required"
        if claim:
            claim.reason_code = "LATE_GATEWAY_SUCCESS"
            claim.reason_message = record.error_message
            claim.status = "PROVISIONAL"
        await session.commit()

    async def _clear_active(self) -> None:
        if self._active_transaction_id:
            self._cancel_timeout(self._active_transaction_id)
        self._active_transaction_id = None
        if self._operation_mode and self._operation_owner:
            self._operation_mode.end_transaction(self._operation_owner)
            self._operation_owner = None
        await self._set_coin_acceptor_enabled(False)

    def _reset_timeout(self, transaction_id: str) -> None:
        self._cancel_timeout(transaction_id)
        self._timeout_tasks[transaction_id] = asyncio.create_task(
            self._timeout_transaction(transaction_id)
        )

    def _cancel_timeout(self, transaction_id: str) -> None:
        task = self._timeout_tasks.pop(transaction_id, None)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()

    async def _timeout_transaction(self, transaction_id: str) -> None:
        try:
            await asyncio.sleep(60)
            async with self._db_factory() as session:
                record = await session.get(EWalletTransactionRecord, transaction_id)
                if record is None or record.state not in {"ACCEPTING_CASH", "CASH_ACCEPTED", "WAITING_FOR_PAYMENT"}:
                    return
                has_cash = record.inserted_amount > 0
            if has_cash:
                await self._mark_claim_required(
                    transaction_id,
                    "TIMEOUT_AFTER_CASH",
                    "Cash acceptance timed out after customer funds were accepted",
                )
            else:
                async with self._db_factory() as session:
                    record = await session.get(EWalletTransactionRecord, transaction_id)
                    if record.state in {"ACCEPTING_CASH", "WAITING_FOR_PAYMENT"}:
                        record.state = "CANCELLED"
                        record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        await session.commit()
                        await self._broadcast(record, WSEventType.EWALLET_STATE_CHANGED)
                await self._clear_active()
        except asyncio.CancelledError:
            pass
        finally:
            self._timeout_tasks.pop(transaction_id, None)

    async def _set_coin_acceptor_enabled(self, enabled: bool, raise_on_error: bool = False) -> None:
        if self._coin_controller is None:
            return
        try:
            await self._coin_controller.set_coin_acceptor_enabled(enabled)
        except Exception as e:
            logger.warning(f"Failed to set coin acceptor enabled={enabled}: {e}")
            if raise_on_error:
                raise

    def _calculate_fee(self, amount: int) -> int:
        for tier in sorted(
            self._settings.ewallet_fee_tiers,
            key=lambda item: item.min,
        ):
            if amount >= tier.min and (
                tier.max is None or amount <= tier.max
            ):
                return tier.fee
        raise EWalletTransactionError(
            "Amount is outside the configured e-wallet fee tiers"
        )

    async def _broadcast(
        self, record: EWalletTransactionRecord, event_type: WSEventType
    ) -> None:
        await self._ws.broadcast(
            WSEvent(type=event_type, payload=self._serialize(record))
        )

    @staticmethod
    def _require_cash_in(record: EWalletTransactionRecord | None) -> None:
        if record is None:
            raise EWalletTransactionError("Transaction not found")
        if record.direction != "cash-in":
            raise EWalletTransactionError("Transaction is not cash-in")

    @staticmethod
    def _serialize(record: EWalletTransactionRecord) -> dict:
        return {
            "transaction_id": record.id,
            "provider": record.provider,
            "direction": record.direction,
            "mobile_number": record.mobile_number or None,
            "account_name": record.account_name or None,
            "state": record.state,
            "amount": record.amount,
            "fee": record.fee,
            "transfer_amount": record.transfer_amount,
            "total_due": record.total_due,
            "inserted_amount": record.inserted_amount,
            "inserted_denominations": record.inserted_denominations or {},
            "dispensed_amount": record.dispensed_amount,
            "dispense_plan": record.dispense_plan,
            "dispense_result": record.dispense_result,
            "gateway_payment_intent_id": record.gateway_payment_intent_id,
            "gateway_batch_transfer_id": record.gateway_batch_transfer_id,
            "gateway_transfer_id": record.gateway_transfer_id,
            "gateway_status": record.gateway_status,
            "qr_image_url": record.qr_image_url,
            "test_url": record.test_url,
            "claim_ticket_code": record.claim_ticket_code,
            "shortfall": (
                (record.dispense_result or {}).get("shortfall")
                if record.dispense_result
                else None
            ),
            "error_code": record.error_code,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "completed_at": (
                record.completed_at.isoformat() if record.completed_at else None
            ),
        }
