"""Persistent PayMongo-backed e-wallet transaction orchestration."""

from __future__ import annotations

import logging
import secrets
import string
import uuid
from datetime import datetime

from sqlalchemy import or_, select
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
    ):
        self._settings = settings
        self._gateway = gateway
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispenser
        self._status = machine_status
        self._ws = ws_manager
        self._db_factory = db_session_factory
        self._active_transaction_id: str | None = None
        self._operation_mode = operation_mode
        self._operation_owner: str | None = None

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
            self._clear_active()
            raise
        self._active_transaction_id = tx_id

        if direction == "cash-out":
            try:
                qr = await self._gateway.create_qr_payment(
                    amount_centavos=amount * 100,
                    reference=tx_id,
                    idempotency_key=f"ewallet:{tx_id}:qr",
                )
            except Exception:
                self._clear_active()
                async with self._db_factory() as session:
                    failed = await session.get(EWalletTransactionRecord, tx_id)
                    failed.state = "FAILED"
                    failed.error_code = "QR_CREATION_FAILED"
                    failed.completed_at = datetime.utcnow()
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
            await session.commit()
            event = (
                WSEventType.EWALLET_CASH_ACCEPTED
                if record.state == "CASH_ACCEPTED"
                else WSEventType.EWALLET_STATE_CHANGED
            )
            await self._broadcast(record, event)
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
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            self._require_cash_in(record)
            if record.state == "DISBURSEMENT_PENDING":
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
            async with self._db_factory() as session:
                record = await session.get(
                    EWalletTransactionRecord, transaction_id
                )
                record.state = "CLAIM_REQUIRED"
                record.claim_ticket_code = record.claim_ticket_code or _claim_ticket()
                record.error_code = "DISBURSEMENT_FAILED"
                record.error_message = str(exc)
                await session.commit()
                await self._broadcast(
                    record, WSEventType.EWALLET_CLAIM_REQUIRED
                )
                self._clear_active()
            return await self.get_transaction(transaction_id)

        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            record.gateway_batch_transfer_id = result.batch_transfer_id
            record.gateway_transfer_id = result.transfer_id
            record.gateway_status = result.status
            record.state = "DISBURSEMENT_PENDING"
            await session.commit()
            await self._broadcast(record, WSEventType.EWALLET_GATEWAY_PENDING)
        return await self.get_transaction(transaction_id)

    async def process_gateway_event(self, event: dict) -> dict:
        event_id = str(event["id"])
        async with self._db_factory() as session:
            existing_event = await session.get(GatewayEventRecord, event_id)
            if existing_event and existing_event.processed:
                return {"duplicate": True}
            if existing_event is None:
                session.add(
                    GatewayEventRecord(
                        id=event_id,
                        event_type=str(event.get("type", "unknown")),
                        resource_id=event.get("resource_id"),
                        payload=event,
                    )
                )
                await session.flush()
            resource_id = event.get("resource_id")
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
                stored_event = await session.get(GatewayEventRecord, event_id)
                stored_event.processed = True
                await session.commit()
                return {"processed": False, "reason": "transaction_not_found"}
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
            elif status in {"failed", "cancelled", "expired", "returned"}:
                async with self._db_factory() as session:
                    record = await session.get(
                        EWalletTransactionRecord, record.id
                    )
                    if record.direction == "cash-in":
                        record.state = "CLAIM_REQUIRED"
                        record.claim_ticket_code = (
                            record.claim_ticket_code or _claim_ticket()
                        )
                    else:
                        record.state = "FAILED"
                    record.error_code = "GATEWAY_FAILED"
                    record.error_message = f"PayMongo status: {status}"
                    await session.commit()
                    await self._broadcast(
                        record,
                        WSEventType.EWALLET_CLAIM_REQUIRED
                        if record.claim_ticket_code
                        else WSEventType.EWALLET_GATEWAY_FAILED,
                    )
                    self._clear_active()
                result_payload = await self.get_transaction(record.id)
            else:
                result_payload = {"processed": True, "status": status}
        except Exception as exc:
            async with self._db_factory() as session:
                stored_event = await session.get(GatewayEventRecord, event_id)
                stored_event.processing_error = str(exc)
                await session.commit()
            raise

        async with self._db_factory() as session:
            stored_event = await session.get(GatewayEventRecord, event_id)
            stored_event.processed = True
            stored_event.processing_error = None
            stored_event.processed_at = datetime.utcnow()
            await session.commit()
        return result_payload

    async def process_transfer_callback(
        self, batch_transfer_id: str
    ) -> dict:
        async with self._db_factory() as session:
            result = await session.execute(
                select(EWalletTransactionRecord).where(
                    EWalletTransactionRecord.gateway_batch_transfer_id
                    == batch_transfer_id
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return {"processed": False, "reason": "transaction_not_found"}
            transaction_id = record.id
            transfer_id = record.gateway_transfer_id

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
            if record.inserted_amount > 0 or record.gateway_status in {
                "succeeded",
                "paid",
            }:
                raise EWalletTransactionError(
                    "Transaction requires operator reconciliation"
                )
            record.state = "CANCELLED"
            record.completed_at = datetime.utcnow()
            await session.commit()
            await self._broadcast(record, WSEventType.EWALLET_STATE_CHANGED)
            self._clear_active()
            return self._serialize(record)

    async def recover_pending_transactions(self) -> None:
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
            for record in result.scalars():
                if record.inserted_amount > 0 or record.gateway_status in {
                    "succeeded",
                    "paid",
                }:
                    record.state = "CLAIM_REQUIRED"
                    record.claim_ticket_code = (
                        record.claim_ticket_code or _claim_ticket()
                    )
                    record.error_code = "CRASH_RECOVERY"
            await session.commit()
        self._clear_active()

    async def _dispense_paid_cash_out(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record.state in {"COMPLETE", "CLAIM_REQUIRED", "DISPENSING"}:
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
            plan, reference_id=transaction_id
        )
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            record.dispensed_amount = result.total_dispensed
            record.dispense_result = result.model_dump()
            record.completed_at = datetime.utcnow()
            if result.success:
                record.state = "COMPLETE"
                event_type = WSEventType.EWALLET_COMPLETE
            else:
                record.state = "CLAIM_REQUIRED"
                record.claim_ticket_code = (
                    result.claim_ticket_code or _claim_ticket()
                )
                record.error_code = "PARTIAL_DISPENSE"
                record.error_message = result.error
                event_type = WSEventType.EWALLET_CLAIM_REQUIRED
            await session.commit()
            await self._broadcast(record, event_type)
            self._clear_active()
            return self._serialize(record)

    async def _complete_cash_in(self, transaction_id: str) -> dict:
        async with self._db_factory() as session:
            record = await session.get(EWalletTransactionRecord, transaction_id)
            if record.state == "COMPLETE":
                return self._serialize(record)
            record.state = "COMPLETE"
            record.completed_at = datetime.utcnow()
            await session.commit()
            await self._broadcast(record, WSEventType.EWALLET_COMPLETE)
            self._clear_active()
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
            record = await session.get(
                EWalletTransactionRecord, transaction_id
            )
            record.gateway_status = "paid"
            record.state = "PAYMENT_CONFIRMED"
            await session.commit()
        return await self._dispense_paid_cash_out(transaction_id)

    async def _mark_claim_required(
        self,
        transaction_id: str,
        error_code: str,
        error_message: str,
    ) -> dict:
        async with self._db_factory() as session:
            record = await session.get(
                EWalletTransactionRecord, transaction_id
            )
            record.state = "CLAIM_REQUIRED"
            record.claim_ticket_code = (
                record.claim_ticket_code or _claim_ticket()
            )
            record.error_code = error_code
            record.error_message = error_message
            record.completed_at = datetime.utcnow()
            await session.commit()
            await self._broadcast(
                record,
                WSEventType.EWALLET_CLAIM_REQUIRED,
            )
            self._clear_active()
            return self._serialize(record)

    def _clear_active(self) -> None:
        self._active_transaction_id = None
        if self._operation_mode and self._operation_owner:
            self._operation_mode.end_transaction(self._operation_owner)
            self._operation_owner = None

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
            "error_code": record.error_code,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "completed_at": (
                record.completed_at.isoformat() if record.completed_at else None
            ),
        }
