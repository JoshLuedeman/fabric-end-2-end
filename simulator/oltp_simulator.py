"""
Contoso OLTP Transaction Simulator

Generates realistic POS transactions, customer interactions, and inventory
updates against the Fabric SQL Database at configurable rates.

Designed to run 24/7 as a container alongside the IoT sensor simulator,
making the OLTP database feel like a live running business.

Architecture
------------
This simulator is the SINGLE source of truth for POS transactions, customer
interactions, and inventory data.  POS transactions written here flow to
Eventhouse for real-time analytics via:

    OLTP Simulator  →  Fabric SQL Database  →  Change Event Streaming  →  Eventstream  →  Eventhouse / Lakehouse

Fabric SQL Database's built-in "Change Event Streaming" feature pushes CDC
events (inserts/updates on Transactions, TransactionItems, Inventory, and
CustomerInteractions) to an Eventstream automatically.  This eliminates the
need for a separate POS event generator — the Node.js streaming container
now handles only IoT sensor telemetry (temperature, humidity, foot traffic,
energy, door counters).

See also:
    src/eventstream/change_event_config.json   — Eventstream routing setup
    infra/modules/fabric-sql-database/main.tf  — Change Event Streaming TF config

Usage:
    python oltp_simulator.py              # Live mode (requires DB connection)
    python oltp_simulator.py --dry-run    # Console output only (testing)
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

import config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  [%(threadName)s]  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("oltp-simulator")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_shutdown_event = threading.Event()

# Cumulative counters (accessed from multiple threads)
_lock = threading.Lock()
_stats: Dict[str, int] = {
    "transactions": 0,
    "transaction_items": 0,
    "interactions": 0,
    "inventory_updates": 0,
    "errors": 0,
}
# Stores that had sales since last inventory cycle
_stores_with_sales: set = set()

# Pre-generated ID pools (populated once at startup)
_store_ids: List[str] = []
_product_ids: List[str] = []
_customer_ids: List[str] = []
_employee_ids: List[str] = []
_store_weights: Optional[np.ndarray] = None


# ===================================================================
# Database helpers
# ===================================================================
class DatabaseConnection:
    """Thin wrapper around a pyodbc connection for the OLTP database."""

    def __init__(self, connection_string: str) -> None:
        import pyodbc  # deferred so dry-run doesn't require the driver

        self._conn = pyodbc.connect(connection_string, autocommit=True)
        log.info("Connected to SQL Database")

    def call_sp_process_sale(
        self,
        customer_id: Optional[str],
        store_id: str,
        employee_id: str,
        payment_method: str,
        channel: str,
        line_items_json: str,
    ) -> Dict[str, Any]:
        """Execute sp_process_sale and return the result row."""
        cursor = self._conn.cursor()
        cursor.execute(
            "EXEC dbo.sp_process_sale "
            "  @customer_id=?, @store_id=?, @employee_id=?, "
            "  @payment_method=?, @channel=?, @line_items=?",
            customer_id,
            store_id,
            employee_id,
            payment_method,
            channel,
            line_items_json,
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return {
                "transaction_id": str(row[0]),
                "subtotal": float(row[1]),
                "tax_amount": float(row[2]),
                "discount_amount": float(row[3]),
                "total_amount": float(row[4]),
                "loyalty_points": int(row[5]),
            }
        return {}

    def insert_interaction(
        self,
        customer_id: str,
        interaction_type: str,
        channel: str,
        subject: str,
        resolution_status: str,
        agent_employee_id: str,
        satisfaction_score: Optional[int],
    ) -> str:
        """INSERT a row into CustomerInteractions; return the interaction_id."""
        interaction_id = str(uuid.uuid4())
        resolved_at = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            if resolution_status == "resolved"
            else None
        )
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.CustomerInteractions
                (interaction_id, customer_id, interaction_type, channel,
                 subject, resolution_status, agent_employee_id,
                 satisfaction_score, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETUTCDATE(), ?)
            """,
            interaction_id,
            customer_id,
            interaction_type,
            channel,
            subject,
            resolution_status,
            agent_employee_id,
            satisfaction_score,
            resolved_at,
        )
        cursor.close()
        return interaction_id

    def batch_replenish_inventory(
        self, updates: List[Dict[str, Any]]
    ) -> int:
        """Batch-update Inventory rows (replenishment shipments)."""
        cursor = self._conn.cursor()
        count = 0
        for u in updates:
            cursor.execute(
                """
                UPDATE dbo.Inventory
                SET quantity_on_hand  = quantity_on_hand + ?,
                    last_received_date = GETUTCDATE(),
                    updated_at         = GETUTCDATE()
                WHERE store_id = ? AND product_id = ?
                """,
                u["quantity"],
                u["store_id"],
                u["product_id"],
            )
            count += cursor.rowcount
        cursor.close()
        return count

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


class DryRunConnection:
    """Mock connection that prints to console instead of touching a DB."""

    def call_sp_process_sale(
        self,
        customer_id: Optional[str],
        store_id: str,
        employee_id: str,
        payment_method: str,
        channel: str,
        line_items_json: str,
    ) -> Dict[str, Any]:
        items = json.loads(line_items_json)
        subtotal = sum(
            i["quantity"] * i["unit_price"] * (1 - i.get("discount_pct", 0) / 100)
            for i in items
        )
        tax = round(subtotal * 0.0825, 2)
        total = round(subtotal + tax, 2)
        result = {
            "transaction_id": str(uuid.uuid4()),
            "subtotal": round(subtotal, 2),
            "tax_amount": tax,
            "discount_amount": round(
                sum(
                    i["quantity"] * i["unit_price"] * i.get("discount_pct", 0) / 100
                    for i in items
                ),
                2,
            ),
            "total_amount": total,
            "loyalty_points": int(subtotal),
        }
        log.info(
            "DRY-RUN  sp_process_sale  store=%s  customer=%s  items=%d  total=$%.2f  channel=%s",
            store_id,
            customer_id or "WALK-IN",
            len(items),
            total,
            channel,
        )
        return result

    def insert_interaction(
        self,
        customer_id: str,
        interaction_type: str,
        channel: str,
        subject: str,
        resolution_status: str,
        agent_employee_id: str,
        satisfaction_score: Optional[int],
    ) -> str:
        iid = str(uuid.uuid4())
        log.info(
            "DRY-RUN  interaction  customer=%s  type=%s  channel=%s  subject='%s'  score=%s",
            customer_id,
            interaction_type,
            channel,
            subject[:50],
            satisfaction_score,
        )
        return iid

    def batch_replenish_inventory(
        self, updates: List[Dict[str, Any]]
    ) -> int:
        for u in updates:
            log.info(
                "DRY-RUN  inventory replenish  store=%s  product=%s  +%d units",
                u["store_id"],
                u["product_id"],
                u["quantity"],
            )
        return len(updates)

    def close(self) -> None:
        pass


# ===================================================================
# Rate helpers
# ===================================================================
def _current_rate_multiplier() -> float:
    """Return the combined time-of-day × weekend × global multiplier."""
    now = datetime.now(timezone.utc)
    hour_mult = config.TIME_OF_DAY_MULTIPLIER.get(now.hour, 1.0)
    weekend_mult = config.WEEKEND_MULTIPLIER if now.weekday() >= 5 else 1.0
    return hour_mult * weekend_mult * config.RATE_MULTIPLIER


def _sleep_for_rate(base_rate: float) -> None:
    """Sleep long enough to achieve *base_rate* events/sec (adjusted)."""
    effective = base_rate * _current_rate_multiplier()
    if effective <= 0:
        time.sleep(1.0)
        return
    # Poisson-ish jitter: exponential inter-arrival
    interval = np.random.exponential(1.0 / effective)
    # Cap so we never sleep more than 30 s even at 0.1× overnight
    interval = min(interval, 30.0)
    # Use the shutdown event as a cancellable sleep
    _shutdown_event.wait(timeout=interval)


# ===================================================================
# ID helpers
# ===================================================================
def _pick_store() -> str:
    """Pick a weighted-random store ID (Flagship stores get more traffic)."""
    return str(np.random.choice(_store_ids, p=_store_weights))


def _pick_products(channel: str) -> List[Dict[str, Any]]:
    """Build a random basket of line items."""
    lo, hi = config.BASKET_SIZE_BY_CHANNEL.get(channel, (1, 5))
    size = int(np.random.randint(lo, hi + 1))
    chosen = np.random.choice(_product_ids, size=size, replace=False)
    items = []
    for pid in chosen:
        qty = int(np.random.randint(1, 4))
        # Deterministic-ish price by product index (matches seed data approach)
        idx = int(pid.split("-")[1])
        base_price = round(5.0 + (idx * 7.97) % 190, 2)  # $5 – $195
        discount_pct = 0.0
        if np.random.random() < config.DISCOUNT_PROBABILITY:
            discount_pct = round(float(np.random.uniform(5, config.MAX_DISCOUNT_PCT)), 2)
        items.append(
            {
                "product_id": str(pid),
                "quantity": qty,
                "unit_price": base_price,
                "discount_pct": discount_pct,
            }
        )
    return items


def _pick_customer() -> Optional[str]:
    """Pick a customer ID or None for a walk-in."""
    if np.random.random() < config.ANONYMOUS_CUSTOMER_PCT:
        return None
    return str(np.random.choice(_customer_ids))


def _pick_employee() -> str:
    return str(np.random.choice(_employee_ids))


# ===================================================================
# Worker threads
# ===================================================================
def _transaction_worker(db: Any) -> None:
    """Continuously generate POS transactions at the configured rate."""
    log.info("Transaction worker started (base rate: %.1f/s)", config.TRANSACTION_RATE)
    while not _shutdown_event.is_set():
        try:
            store_id = _pick_store()
            channel = str(
                np.random.choice(config.CHANNELS, p=config.CHANNEL_WEIGHTS)
            )
            items = _pick_products(channel)
            customer_id = _pick_customer()
            employee_id = _pick_employee()
            payment = str(
                np.random.choice(
                    config.PAYMENT_METHODS, p=config.PAYMENT_WEIGHTS
                )
            )
            line_items_json = json.dumps(items)

            result = db.call_sp_process_sale(
                customer_id=customer_id,
                store_id=store_id,
                employee_id=employee_id,
                payment_method=payment,
                channel=channel,
                line_items_json=line_items_json,
            )

            with _lock:
                _stats["transactions"] += 1
                _stats["transaction_items"] += len(items)
                _stores_with_sales.add(store_id)

        except Exception:
            log.exception("Transaction worker error")
            with _lock:
                _stats["errors"] += 1
            time.sleep(1)  # back off on error

        _sleep_for_rate(config.TRANSACTION_RATE)


def _interaction_worker(db: Any) -> None:
    """Continuously generate customer-service interactions."""
    log.info("Interaction worker started (base rate: %.1f/s)", config.INTERACTION_RATE)
    while not _shutdown_event.is_set():
        try:
            itype = str(
                np.random.choice(
                    config.INTERACTION_TYPES, p=config.INTERACTION_WEIGHTS
                )
            )
            channel = config.INTERACTION_CHANNELS[itype]
            subject = str(np.random.choice(config.INTERACTION_SUBJECTS[itype]))
            customer_id = str(np.random.choice(_customer_ids))
            agent_id = _pick_employee()
            resolution = str(
                np.random.choice(
                    config.RESOLUTION_STATUSES, p=config.RESOLUTION_WEIGHTS
                )
            )
            score: Optional[int] = None
            if resolution == "resolved":
                score = int(np.random.choice([1, 2, 3, 4, 5], p=[0.02, 0.05, 0.13, 0.35, 0.45]))

            db.insert_interaction(
                customer_id=customer_id,
                interaction_type=itype,
                channel=channel,
                subject=subject,
                resolution_status=resolution,
                agent_employee_id=agent_id,
                satisfaction_score=score,
            )

            with _lock:
                _stats["interactions"] += 1

        except Exception:
            log.exception("Interaction worker error")
            with _lock:
                _stats["errors"] += 1
            time.sleep(1)

        _sleep_for_rate(config.INTERACTION_RATE)


def _inventory_worker(db: Any) -> None:
    """Periodically batch-replenish inventory for stores with recent sales."""
    log.info(
        "Inventory worker started (interval: %ds)", config.INVENTORY_UPDATE_INTERVAL
    )
    while not _shutdown_event.is_set():
        _shutdown_event.wait(timeout=config.INVENTORY_UPDATE_INTERVAL)
        if _shutdown_event.is_set():
            break

        try:
            # Collect stores that had sales
            with _lock:
                stores = list(_stores_with_sales)
                _stores_with_sales.clear()

            # Also pick some random stores to simulate receiving shipments
            extra_count = max(1, int(len(_store_ids) * config.REPLENISHMENT_STORE_PCT))
            extra_stores = list(np.random.choice(_store_ids, size=extra_count, replace=False))
            all_stores = list(set(stores + extra_stores))

            updates: List[Dict[str, Any]] = []
            for sid in all_stores:
                # Each store gets 1-3 products replenished
                n_products = int(np.random.randint(1, 4))
                products = list(np.random.choice(_product_ids, size=n_products, replace=False))
                for pid in products:
                    qty = int(
                        np.random.randint(
                            config.REPLENISHMENT_QTY_RANGE[0],
                            config.REPLENISHMENT_QTY_RANGE[1] + 1,
                        )
                    )
                    updates.append(
                        {"store_id": str(sid), "product_id": str(pid), "quantity": qty}
                    )

            if updates:
                rows_updated = db.batch_replenish_inventory(updates)
                with _lock:
                    _stats["inventory_updates"] += rows_updated
                log.info(
                    "Inventory replenishment: %d updates across %d stores",
                    len(updates),
                    len(all_stores),
                )

        except Exception:
            log.exception("Inventory worker error")
            with _lock:
                _stats["errors"] += 1


def _stats_worker() -> None:
    """Periodically print throughput stats."""
    log.info("Stats reporter started (interval: %ds)", config.STATS_REPORT_INTERVAL)
    prev: Dict[str, int] = dict(_stats)
    prev_time = time.monotonic()

    while not _shutdown_event.is_set():
        _shutdown_event.wait(timeout=config.STATS_REPORT_INTERVAL)
        if _shutdown_event.is_set():
            break

        now = time.monotonic()
        elapsed = now - prev_time
        if elapsed <= 0:
            continue

        with _lock:
            current = dict(_stats)

        txn_delta = current["transactions"] - prev["transactions"]
        item_delta = current["transaction_items"] - prev["transaction_items"]
        int_delta = current["interactions"] - prev["interactions"]
        inv_delta = current["inventory_updates"] - prev["inventory_updates"]
        err_delta = current["errors"] - prev["errors"]

        txn_per_min = txn_delta / elapsed * 60
        int_per_min = int_delta / elapsed * 60
        avg_basket = item_delta / txn_delta if txn_delta else 0

        mult = _current_rate_multiplier()

        log.info(
            "STATS  txn=%.1f/min  interactions=%.1f/min  "
            "avg_basket=%.1f  inv_updates=%d  errors=%d  "
            "rate_mult=%.2fx  | cumulative: txn=%d  int=%d  inv=%d  err=%d",
            txn_per_min,
            int_per_min,
            avg_basket,
            inv_delta,
            err_delta,
            mult,
            current["transactions"],
            current["interactions"],
            current["inventory_updates"],
            current["errors"],
        )

        prev = current
        prev_time = now


# ===================================================================
# Startup / shutdown
# ===================================================================
def _build_store_weights() -> np.ndarray:
    """Build a probability array for weighted store selection.

    Stores whose type is not in STORE_TYPE_WEIGHTS get a weight of 1.0.
    Since we don't query the DB for store_type at startup (that would
    require a live connection even in dry-run), we use a deterministic
    mapping based on the seed data pattern:
        S-0001, S-0008          → Flagship
        S-0002, S-0005, S-0007  → Standard
        S-0003, S-0006, S-0009  → Express
        S-0004                  → Outlet
        S-0010                  → Online
    For IDs beyond the seed set, default to 'Standard'.
    """
    seed_types: Dict[str, str] = {
        "S-0001": "Flagship",
        "S-0002": "Standard",
        "S-0003": "Express",
        "S-0004": "Outlet",
        "S-0005": "Standard",
        "S-0006": "Express",
        "S-0007": "Standard",
        "S-0008": "Flagship",
        "S-0009": "Express",
        "S-0010": "Online",
    }
    weights = []
    for sid in _store_ids:
        stype = seed_types.get(sid, "Standard")
        weights.append(config.STORE_TYPE_WEIGHTS.get(stype, 1.0))
    arr = np.array(weights)
    return arr / arr.sum()


def _setup_signal_handlers() -> None:
    """Register SIGINT / SIGTERM to trigger graceful shutdown."""

    def _handler(signum: int, _frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        log.info("Received %s — shutting down gracefully …", sig_name)
        _shutdown_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Contoso OLTP Transaction Simulator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=config.DRY_RUN,
        help="Log to console instead of writing to the database",
    )
    parser.add_argument(
        "--rate-multiplier",
        type=float,
        default=config.RATE_MULTIPLIER,
        help="Global rate multiplier (default: 1.0)",
    )
    args = parser.parse_args()

    # Apply CLI overrides
    config.DRY_RUN = args.dry_run
    config.RATE_MULTIPLIER = args.rate_multiplier

    # Populate ID pools
    global _store_ids, _product_ids, _customer_ids, _employee_ids, _store_weights
    _store_ids = config.store_ids()
    _product_ids = config.product_ids()
    _customer_ids = config.customer_ids()
    _employee_ids = config.employee_ids()
    _store_weights = _build_store_weights()

    log.info("=" * 70)
    log.info("Contoso OLTP Simulator starting")
    log.info(
        "  mode=%s  rate_mult=%.1fx  stores=%d  products=%d  customers=%d",
        "DRY-RUN" if config.DRY_RUN else "LIVE",
        config.RATE_MULTIPLIER,
        len(_store_ids),
        len(_product_ids),
        len(_customer_ids),
    )
    log.info(
        "  txn_rate=%.1f/s  interaction_rate=%.1f/s  inv_interval=%ds",
        config.TRANSACTION_RATE,
        config.INTERACTION_RATE,
        config.INVENTORY_UPDATE_INTERVAL,
    )
    log.info("=" * 70)

    # Connect (or mock)
    db: Any
    if config.DRY_RUN:
        db = DryRunConnection()
    else:
        if not config.SQL_CONNECTION_STRING:
            log.error("SQL_CONNECTION_STRING is required when DRY_RUN is false")
            sys.exit(1)
        db = DatabaseConnection(config.SQL_CONNECTION_STRING)

    _setup_signal_handlers()

    # Launch worker threads
    threads: List[threading.Thread] = [
        threading.Thread(
            target=_transaction_worker, args=(db,), name="txn-worker", daemon=True
        ),
        threading.Thread(
            target=_interaction_worker, args=(db,), name="int-worker", daemon=True
        ),
        threading.Thread(
            target=_inventory_worker, args=(db,), name="inv-worker", daemon=True
        ),
        threading.Thread(target=_stats_worker, name="stats-worker", daemon=True),
    ]
    for t in threads:
        t.start()
        log.info("Started thread: %s", t.name)

    # Block main thread until shutdown is signalled
    try:
        while not _shutdown_event.is_set():
            _shutdown_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        _shutdown_event.set()

    log.info("Waiting for workers to finish …")
    for t in threads:
        t.join(timeout=5.0)

    db.close()

    with _lock:
        log.info(
            "Final stats — transactions=%d  interactions=%d  "
            "inventory_updates=%d  errors=%d",
            _stats["transactions"],
            _stats["interactions"],
            _stats["inventory_updates"],
            _stats["errors"],
        )
    log.info("Simulator stopped.")


if __name__ == "__main__":
    main()
