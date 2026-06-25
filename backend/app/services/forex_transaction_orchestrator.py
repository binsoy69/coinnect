"""Forex transaction orchestrator.

Coordinates forex-specific transaction lifecycle:
rate fetching, rate locking, multi-currency bill acceptance,
conversion calculation, and dispensing in the target currency.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.ws import ConnectionManager
from app.core.constants import (
    BILL_DENOM_VALUES,
    ForexServiceType,
    FOREX_PAIRS,
)
from app.core.errors import ConnectivityError, ForexError, TransactionError
from app.models.db_models import (
    TransactionRecord,
    TransactionState,
    WALAction,
    WALEntry,
    WALStatus,
)
from app.models.events import WSEvent, WSEventType
from app.models.forex import ForexQuote
from app.services.bill_acceptor import BillAcceptor
from app.services.dispense_orchestrator import DispenseOrchestrator
from app.services.forex_change_calculator import calculate_forex_dispense
from app.services.forex_rate_service import ForexRateService
from app.services.machine_status import MachineStatus
from app.services.transaction_state_machine import TransactionStateMachine
from app.services.operation_mode import OperationModeManager

logger = logging.getLogger(__name__)


class ForexTransactionOrchestrator:
    """Manages forex transaction lifecycles.

    Key differences from TransactionOrchestrator:
    - Requires online connectivity check before starting
    - Locks exchange rate at transaction start
    - Configures bill acceptor for the expected input currency
    - Uses forex-specific dispense calculation
    - Records forex metadata (rate, currency pair, fee %)
    """

    def __init__(
        self,
        bill_acceptor: BillAcceptor,
        dispense_orchestrator: DispenseOrchestrator,
        machine_status: MachineStatus,
        ws_manager: ConnectionManager,
        forex_rate_service: ForexRateService,
        db_session_factory: async_sessionmaker,
        operation_mode: OperationModeManager | None = None,
    ):
        self._bill_acceptor = bill_acceptor
        self._dispenser = dispense_orchestrator
        self._status = machine_status
        self._ws = ws_manager
        self._forex = forex_rate_service
        self._db_factory = db_session_factory
        self._active_tx: Optional[TransactionStateMachine] = None
        self._active_session: Optional[AsyncSession] = None
        self._active_quote: Optional[ForexQuote] = None
        self._operation_mode = operation_mode
        self._operation_owner: Optional[str] = None

    @property
    def has_active_transaction(self) -> bool:
        return self._active_tx is not None

    @property
    def active_transaction_id(self) -> Optional[str]:
        return self._active_tx.transaction_id if self._active_tx else None

    async def start_transaction(
        self,
        service_type: str,
        selected_amount: int,
        selected_dispense_denoms: list = None,
    ) -> dict:
        """Start a forex transaction.

        Args:
            service_type: e.g., "usd-to-php"
            selected_amount: Foreign currency amount (for both directions)
            selected_dispense_denoms: User-selected output denominations

        Returns:
            Transaction state dict.

        Raises:
            ConnectivityError: If kiosk is offline.
            ForexError: If rates unavailable or dispense not possible.
            TransactionError: If another transaction is active.
        """
        if self._active_tx is not None:
            raise TransactionError(
                self._active_tx.transaction_id,
                "A transaction is already in progress",
            )

        # 1. Connectivity check
        if not await self._forex.check_forex_available():
            raise ConnectivityError("Forex requires internet connectivity")

        # 2. Validate machine state
        snapshot = self._status.snapshot()
        if snapshot.security.tamper_active:
            raise TransactionError("", "Machine is in lockdown mode")
        if not snapshot.consumables.inventory_consistent:
            raise TransactionError("", "Inventory reconciliation is required")

        # 3. Get quote (locks rate)
        try:
            self._active_quote = self._forex.get_quote(service_type, selected_amount)
        except Exception as e:
            raise ForexError(f"Cannot calculate conversion: {e}")

        quote = self._active_quote
        pair = FOREX_PAIRS[ForexServiceType(service_type)]
        from_currency, to_currency = pair

        # 4. Determine amounts
        total_due = int(quote.input_amount)
        target_amount = int(quote.output_amount)
        fee = int(quote.fee_amount)

        # 5. Pre-check dispense capability
        try:
            calculate_forex_dispense(
                quote,
                snapshot.consumables.bill_dispenser_counts,
                snapshot.consumables.coin_counts,
                preferred_denoms=selected_dispense_denoms or [],
            )
        except Exception as e:
            self._active_quote = None
            raise ForexError(f"Cannot dispense target amount: {e}")

        # 6. Configure bill acceptor for expected currency
        self._bill_acceptor.set_expected_currency(from_currency.value)

        # 7. Create DB record
        tx_type = f"forex-{service_type}"
        tx_id = str(uuid.uuid4())
        if self._operation_mode:
            self._operation_mode.begin_transaction(tx_id)
            self._operation_owner = tx_id
        session = self._db_factory()
        self._active_session = session

        record = TransactionRecord(
            id=tx_id,
            type=tx_type,
            state=TransactionState.IDLE.value,
            target_amount=target_amount,
            fee=fee,
            total_due=total_due,
            selected_dispense_denoms=selected_dispense_denoms or [],
            from_currency=from_currency.value,
            to_currency=to_currency.value,
            exchange_rate=quote.rate,
            rate_locked_at=quote.locked_at,
            forex_fee_percentage=quote.fee_percentage,
            converted_amount=int(quote.converted_amount),
        )
        session.add(record)

        # WAL: rate locked
        wal_entry = WALEntry(
            transaction_id=tx_id,
            action=WALAction.FOREX_RATE_LOCKED.value,
            data={
                "rate": quote.rate,
                "from": from_currency.value,
                "to": to_currency.value,
                "amount": selected_amount,
            },
        )
        session.add(wal_entry)
        await session.commit()

        # 8. Create state machine
        self._active_tx = TransactionStateMachine(
            transaction_id=tx_id,
            transaction_type=tx_type,
            ws_manager=self._ws,
            db_session=session,
        )

        await self._active_tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # Broadcast rate locked event
        await self._ws.broadcast(WSEvent(
            type=WSEventType.FOREX_RATE_LOCKED,
            payload={
                "transaction_id": tx_id,
                "rate": quote.rate,
                "from_currency": from_currency.value,
                "to_currency": to_currency.value,
                "fee_percentage": quote.fee_percentage,
            },
        ))

        logger.info(
            f"Forex transaction started: {tx_id} type={service_type} "
            f"rate={quote.rate} amount={selected_amount} fee={fee}"
        )

        return await self.get_transaction_state(tx_id)

    async def handle_bill_inserted(self) -> dict:
        """Handle a bill acceptance cycle during a forex transaction."""
        tx = self._require_active()

        if not tx.is_in_state(TransactionState.WAITING_FOR_BILL):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot accept bill in state {tx.state.value}",
            )

        await tx.transition_to(TransactionState.AUTHENTICATING)

        result = await self._bill_acceptor.accept_bill()

        if not result.success:
            await tx.transition_to(
                TransactionState.WAITING_FOR_BILL,
                {"last_rejection": result.error},
            )
            tx.reset_timeout()
            return await self.get_transaction_state(tx.transaction_id)

        # Bill accepted
        await tx.transition_to(
            TransactionState.SORTING,
            {"denomination": result.denomination.value, "value": result.value},
        )

        # Update DB
        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if db_record:
            db_record.inserted_amount += result.value
            inserted = dict(db_record.inserted_denominations or {})
            denom_key = str(result.value)
            inserted[denom_key] = inserted.get(denom_key, 0) + 1
            db_record.inserted_denominations = inserted
            await session.commit()

        await tx.transition_to(TransactionState.WAITING_FOR_BILL)

        # Check if enough money inserted
        if db_record and db_record.inserted_amount >= db_record.total_due:
            await tx.transition_to(TransactionState.WAITING_FOR_CONFIRMATION)
        else:
            tx.reset_timeout()

        return await self.get_transaction_state(tx.transaction_id)

    async def confirm_transaction(self) -> dict:
        """Confirm the forex transaction and trigger dispensing."""
        tx = self._require_active()

        if not tx.is_in_state(TransactionState.WAITING_FOR_CONFIRMATION):
            raise TransactionError(
                tx.transaction_id,
                f"Cannot confirm in state {tx.state.value}",
            )

        session = self._active_session
        db_record = await self._get_db_record(session, tx.transaction_id)
        if not db_record:
            raise TransactionError(tx.transaction_id, "Transaction record not found")

        # Calculate dispense plan using locked quote
        snapshot = self._status.snapshot()
        plan = calculate_forex_dispense(
            self._active_quote,
            snapshot.consumables.bill_dispenser_counts,
            snapshot.consumables.coin_counts,
            preferred_denoms=db_record.selected_dispense_denoms,
        )

        db_record.dispense_plan = {
            "items": [item.model_dump() for item in plan.items],
            "total_amount": plan.total_amount,
        }
        await session.commit()

        await tx.transition_to(TransactionState.DISPENSING)

        result = await self._dispenser.execute_dispense(
            plan, reference_id=tx.transaction_id
        )

        db_record.dispensed_amount = result.total_dispensed
        db_record.dispense_result = result.model_dump()
        await session.commit()

        if result.success:
            await tx.transition_to(
                TransactionState.COMPLETE,
                {"dispensed_amount": result.total_dispensed},
            )
        else:
            await tx.transition_to(
                TransactionState.ERROR,
                {
                    "error_code": "PARTIAL_DISPENSE",
                    "error_message": result.error,
                    "dispensed_amount": result.total_dispensed,
                    "shortfall": result.shortfall,
                    "claim_ticket_code": result.claim_ticket_code,
                },
            )

        state = await self.get_transaction_state(tx.transaction_id)
        await self._cleanup()
        return state

    async def cancel_transaction(self) -> dict:
        """Cancel the active forex transaction."""
        tx = self._require_active()
        await tx.cancel()
        state = await self.get_transaction_state(tx.transaction_id)
        await self._cleanup()
        return state

    async def get_transaction_state(self, transaction_id: str) -> dict:
        """Get full state including forex-specific fields."""
        session = self._active_session or self._db_factory()
        db_record = await self._get_db_record(session, transaction_id)
        if not db_record:
            raise TransactionError(transaction_id, "Transaction not found")

        result = {
            "transaction_id": db_record.id,
            "type": db_record.type,
            "state": db_record.state,
            "target_amount": db_record.target_amount,
            "fee": db_record.fee,
            "total_due": db_record.total_due,
            "inserted_amount": db_record.inserted_amount,
            "dispensed_amount": db_record.dispensed_amount,
            "inserted_denominations": db_record.inserted_denominations or {},
            "dispense_plan": db_record.dispense_plan,
            "dispense_result": db_record.dispense_result,
            "selected_dispense_denoms": db_record.selected_dispense_denoms or [],
            "error_code": db_record.error_code,
            "error_message": db_record.error_message,
            "created_at": db_record.created_at.isoformat() if db_record.created_at else None,
            "updated_at": db_record.updated_at.isoformat() if db_record.updated_at else None,
            "completed_at": db_record.completed_at.isoformat() if db_record.completed_at else None,
            # Forex-specific
            "from_currency": db_record.from_currency,
            "to_currency": db_record.to_currency,
            "exchange_rate": db_record.exchange_rate,
            "rate_locked_at": db_record.rate_locked_at.isoformat() if db_record.rate_locked_at else None,
            "forex_fee_percentage": db_record.forex_fee_percentage,
            "converted_amount": db_record.converted_amount,
        }

        if session != self._active_session:
            await session.close()

        return result

    def _require_active(self) -> TransactionStateMachine:
        if self._active_tx is None:
            raise TransactionError("", "No active forex transaction")
        return self._active_tx

    async def _get_db_record(
        self, session: AsyncSession, transaction_id: str
    ) -> Optional[TransactionRecord]:
        result = await session.execute(
            select(TransactionRecord).where(TransactionRecord.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def _cleanup(self) -> None:
        if self._active_session:
            await self._active_session.close()
            self._active_session = None
        self._active_tx = None
        self._active_quote = None
        if self._operation_mode and self._operation_owner:
            self._operation_mode.end_transaction(self._operation_owner)
            self._operation_owner = None
        # Reset bill acceptor to PHP
        self._bill_acceptor.set_expected_currency("PHP")
