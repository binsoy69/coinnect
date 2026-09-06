"""Durable intake operations for the e-wallet orchestrator."""
import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.models.db_models import EWalletTransactionRecord as Tx, EWalletIntake, EWalletCoinSession, ConverterCoinSession
from app.services.inventory_service import InventoryLocation
from app.services.ewallet_policy import INTAKE, serialized
from app.core.errors import EWalletTransactionError


class EWalletIntakeMixin:
    async def _credit(self, tx_id, value, medium, operation_id, denomination, session=None):
        if session is None:
            async with self._db_factory() as db:
                await self._credit(tx_id, value, medium, operation_id, denomination, db)
                await db.commit()
            if self._inventory:
                await self._inventory.refresh_runtime()
            return
        operation = await session.get(EWalletIntake, operation_id)
        if operation and operation.state == "STORED":
            return
        record = await session.get(Tx, tx_id)
        if operation is None:
            operation = EWalletIntake(id=operation_id, transaction_id=tx_id, medium=medium,
                                      denomination=denomination, value=value)
            session.add(operation)
        if self._inventory and medium != "SIMULATED":
            location = InventoryLocation.BILL_STORAGE if medium == "BILL" else InventoryLocation.COIN_DISPENSER
            await self._inventory.adjust_in_session(session, location, denomination, 1, "EWALLET_INTAKE", tx_id)
        operation.state = "STORED"
        record.inserted_amount += value
        counts = dict(record.intake_counts or {})
        key = f"{medium}:{value}"
        counts[key] = counts.get(key, 0) + 1
        record.intake_counts = counts
        denoms = dict(record.inserted_denominations or {})
        denoms[str(value)] = denoms.get(str(value), 0) + 1
        record.inserted_denominations = denoms
        record.change_due = max(0, record.inserted_amount - record.total_due)
        if record.state in INTAKE:
            record.state = "CASH_ACCEPTED" if record.inserted_amount >= record.total_due else "ACCEPTING_CASH"
            record.deadline = datetime.utcnow() + timedelta(seconds=120)

    @serialized
    async def record_cash_insert(self, transaction_id, denomination):
        if not self._settings.use_mock_hardware or self._settings.environment == "production":
            raise EWalletTransactionError("Simulated intake is disabled")
        record = await self._record(transaction_id)
        self._require_intake(record)
        if denomination not in {1, 5, 10, 20, 50, 100, 200, 500, 1000}:
            raise EWalletTransactionError("Invalid PHP denomination")
        await self._prepare_change(record, denomination)
        await self._credit(transaction_id, denomination, "SIMULATED", str(uuid.uuid4()), f"PHP_{denomination}")
        return await self._after_intake(transaction_id)

    @serialized
    async def accept_bill(self, transaction_id):
        record = await self._record(transaction_id)
        self._require_intake(record)
        self._check_ready("cash-in")
        await self._close_coins(transaction_id)
        record = await self._record(transaction_id)
        if record.inserted_amount >= record.total_due:
            return await self._after_intake(transaction_id)
        operation_id = str(uuid.uuid4())
        prepared = False
        async def prepare(denom, value):
            nonlocal prepared
            current = await self._record(transaction_id)
            self._require_intake(current)
            if not denom.value.startswith("PHP_"):
                raise EWalletTransactionError("PHP bills only")
            await self._prepare_change(current, value)
            async with self._db_factory() as session:
                session.add(EWalletIntake(id=operation_id, transaction_id=transaction_id,
                            medium="BILL", denomination=denom.value, value=value))
                await session.commit()
            prepared = True
        async def stored(denom, value):
            await self._credit(transaction_id, value, "BILL", operation_id, denom.value)
        result = await self._bill_acceptor.accept_bill(on_authenticated=prepare, custom_store_and_record=stored)
        if not result.success:
            if prepared:
                self._status.set_inventory_consistent(False)
                return await self._mark_claim_required(transaction_id, "INTAKE_UNCERTAIN", result.error or "Bill intake interrupted", True)
            if result.error not in {"NO_BILL_DETECTED", "NOT_GENUINE", "UNKNOWN_DENOMINATION", "STORAGE_FULL"} and not str(result.error).startswith("PREPARATION_FAILED"):
                return await self._mark_claim_required(transaction_id, "INTAKE_FAULT", result.error or "Intake unavailable", True)
            raise EWalletTransactionError(result.error or "Bill rejected")
        return await self._after_intake(transaction_id)

    async def _after_intake(self, tx_id):
        record = await self._record(tx_id)
        if record.inserted_amount >= record.total_due:
            await self._close_coins(tx_id)
            return await self.confirm_cash_in(tx_id)
        await self._publish(tx_id)
        return await self.get_transaction(tx_id)

    @serialized
    async def open_coins(self, tx_id):
        record = await self._record(tx_id)
        self._require_intake(record)
        self._check_ready("cash-in")
        options, changes = await self._options(record)
        if not options["coins_enabled"] or self._coin_controller is None:
            raise EWalletTransactionError("Coin intake unavailable; use the displayed bills")
        if self._inventory:
            envelope = {}
            for plan in changes.values():
                for item in plan.items:
                    key = f"COIN_DISPENSER:{item.denom}"
                    envelope[key] = max(envelope.get(key, 0), item.count)
            await self._inventory.hold(tx_id, envelope)
        async with self._db_factory() as session:
            existing = (await session.execute(select(EWalletCoinSession).where(
                EWalletCoinSession.transaction_id == tx_id, EWalletCoinSession.state != "CLOSED"))).scalar_one_or_none()
            if existing:
                report = await self._coin_controller.coin_session_status()
                if report.session_state in {"CLOSED", "UNCERTAIN"}:
                    await self._close_coins(tx_id)
                    return await self._after_intake(tx_id)
                return await self.get_transaction(tx_id)
            standard_max = (await session.execute(select(func.max(ConverterCoinSession.session_id)))).scalar() or 0
            wallet_max = (await session.execute(select(func.max(EWalletCoinSession.sid)))).scalar() or 0
            sid = max(standard_max, wallet_max) + 1
            session.add(EWalletCoinSession(transaction_id=tx_id, sid=sid, counts={}))
            await session.commit()
        await self._coin_controller.verify_intake_capabilities()
        await self._coin_controller.coin_session_start(sid, max_value=20)
        return await self.get_transaction(tx_id)

    @serialized
    async def handle_coin_session_pulse(self, sid, seq, denom, count):
        async with self._db_factory() as session:
            row = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.sid == sid))).scalar_one_or_none()
            if row is None:
                return False
            if row.state == "CLOSED":
                return True
            tx_id = row.transaction_id
        await self._close_coins(tx_id)
        record = await self._record(tx_id)
        if record.state in INTAKE:
            await self._after_intake(tx_id)
        return True

    async def handle_coin_inserted(self, denomination):
        # Unscoped legacy events must never create customer credit.
        if self.has_active_transaction:
            self._status.set_inventory_consistent(False)
            await self.handle_tamper("UNSCOPED_COIN_EVENT")

    async def _close_coins(self, tx_id, fault_claim=True):
        async with self._db_factory() as session:
            row = (await session.execute(select(EWalletCoinSession).where(
                EWalletCoinSession.transaction_id == tx_id, EWalletCoinSession.state != "CLOSED"))).scalar_one_or_none()
            if row is None:
                return
            sid = row.sid
        try:
            await self._coin_controller.coin_session_stop(sid)
            stop = asyncio.get_running_loop().time() + self._settings.coin_session_timeout_ms / 1000 + 1
            while True:
                report = await self._coin_controller.coin_session_status()
                if report.sid != sid:
                    raise EWalletTransactionError("Coin intake requires physical reconciliation")
                if report.session_state in {"CLOSED", "UNCERTAIN"}:
                    break
                if asyncio.get_running_loop().time() >= stop:
                    raise EWalletTransactionError("Coin drain timed out")
                await asyncio.sleep(.1)
            async with self._db_factory() as session:
                row = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.sid == sid))).scalar_one()
                counts = dict(row.counts or {})
                for denom in (1, 5, 10, 20):
                    final = getattr(report, f"count_{denom}")
                    previous = counts.get(str(denom), 0)
                    if final < previous:
                        raise EWalletTransactionError("Coin count regressed")
                    for index in range(previous, final):
                        await self._credit(tx_id, denom, "COIN", f"coin:{sid}:{denom}:{index}", f"PHP_{denom}", session)
                    counts[str(denom)] = final
                row.counts, row.state = counts, report.session_state
                await session.commit()
            if self._inventory:
                await self._inventory.refresh_runtime()
            if report.session_state == "UNCERTAIN":
                raise EWalletTransactionError("Coin intake requires physical reconciliation")
            await self._coin_controller.coin_session_ack(sid)
        except Exception:
            async with self._db_factory() as session:
                row = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.sid == sid))).scalar_one()
                row.state = "UNCERTAIN"
                await session.commit()
            self._status.set_inventory_consistent(False)
            if fault_claim:
                await self._mark_claim_required(tx_id, "COIN_SESSION_UNCERTAIN", "Coin intake requires operator reconciliation", True, drain_intake=False)
            raise

    def _require_intake(self, record):
        self._require_cash_in(record)
        if record.id != self._active_transaction_id or record.state != "ACCEPTING_CASH":
            raise EWalletTransactionError("Cash intake is closed")

    @serialized
    async def reconcile_intake(self, operation_id, retained, notes):
        async with self._db_factory() as session:
            operation = await session.get(EWalletIntake, operation_id)
            if not operation:
                raise EWalletTransactionError("Intake operation not found")
            if operation.state != "PREPARED":
                return await self.get_transaction(operation.transaction_id)
            tx_id = operation.transaction_id
            if retained:
                await self._credit(tx_id, operation.value, "BILL", operation.id, operation.denomination, session)
            else:
                operation.state = "RETURNED"
            operation.resolution_notes = notes
            await session.commit()
        if self._inventory:
            await self._inventory.refresh_runtime()
        return await self._mark_claim_required(tx_id, "INTAKE_RECONCILED", notes)

    @serialized
    async def reconcile_coin_session(self, sid, counts, notes):
        async with self._db_factory() as session:
            row = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.sid == sid))).scalar_one()
            if row.state == "CLOSED":
                return await self.get_transaction(row.transaction_id)
            tx_id = row.transaction_id
            previous = row.counts or {}
            for denomination in (1, 5, 10, 20):
                total = counts.get(str(denomination), 0)
                if total < previous.get(str(denomination), 0):
                    raise EWalletTransactionError("Confirmed coin credits cannot be removed")
                for index in range(previous.get(str(denomination), 0), total):
                    await self._credit(tx_id, denomination, "COIN", f"coin:{sid}:{denomination}:{index}", f"PHP_{denomination}", session)
            row.counts = counts
            row.resolution_notes = notes
            await session.commit()
        await self._coin_controller.reconcile_coin_session(sid)
        async with self._db_factory() as session:
            row = (await session.execute(select(EWalletCoinSession).where(EWalletCoinSession.sid == sid))).scalar_one()
            row.state = "CLOSED"
            await session.commit()
        await self._coin_controller.coin_session_ack(sid)
        if self._inventory:
            await self._inventory.refresh_runtime()
        return await self._mark_claim_required(tx_id, "INTAKE_RECONCILED", notes)
