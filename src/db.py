import duckdb
import pandas as pd
from src.config import DB_PATH
from pathlib import Path


def create_tables():
    # simple init, keep your style
    db_sql_path = Path(__file__).parent.parent / "scripts" / "db.sql"
    with duckdb.connect(DB_PATH) as con:
        if db_sql_path.exists():
            sql_text = db_sql_path.read_text()
            # split by ; and exec one by one, duckdb doesn't like multi statements with ENUM sometimes
            for stmt in sql_text.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    con.sql(stmt)
                except Exception as e:
                    # ENUM type already exists or other idempotent error, ignore for POC
                    print(f"create_tables warning: {e} for stmt: {stmt[:50]}")
        else:
            # fallback inline
            con.sql("""
                CREATE TABLE IF NOT EXISTS stock_transaction_event (
                    id UUID DEFAULT uuid(),
                    event_time TIMESTAMP NOT NULL,
                    ticker VARCHAR NOT NULL,
                    quantity DOUBLE NOT NULL,
                    price_per_share DOUBLE NOT NULL,
                    event_type VARCHAR NOT NULL,
                    manual_avg_override DOUBLE,
                    notes VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            con.sql("""
                CREATE TABLE IF NOT EXISTS daily_holdings_snapshot (
                    report_date DATE NOT NULL,
                    ticker VARCHAR NOT NULL,
                    quantity DOUBLE NOT NULL,
                    avg_cost DOUBLE NOT NULL,
                    close_price DOUBLE,
                    market_value DOUBLE,
                    cost_basis DOUBLE,
                    PRIMARY KEY (report_date, ticker)
                )
            """)


def insert_transaction_event(event_dict: dict):
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        query = """
            INSERT INTO stock_transaction_event 
            (event_time, ticker, quantity, price_per_share, event_type, manual_avg_override, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        con.execute(
            query,
            (
                event_dict["event_time"],
                event_dict["ticker"].upper(),
                float(event_dict["quantity"]),
                float(event_dict["price_per_share"]),
                event_dict["event_type"],
                event_dict.get("manual_avg_override"),
                event_dict.get("notes"),
            ),
        )


def get_transaction_events() -> pd.DataFrame:
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        df = con.sql("""
            SELECT 
                id,
                event_time,
                ticker,
                quantity,
                price_per_share,
                event_type,
                manual_avg_override,
                notes,
                created_at
            FROM stock_transaction_event
            ORDER BY event_time ASC
        """).df()
    return df


def get_latest_snapshot_date():
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        row = con.sql("SELECT MAX(report_date) as max_date FROM daily_holdings_snapshot").df()
        if row.empty or pd.isna(row.iloc[0]["max_date"]):
            return None
        return row.iloc[0]["max_date"]


def upsert_daily_snapshot(snapshot_df: pd.DataFrame):
    create_tables()
    if snapshot_df.empty:
        return
    # ensure columns
    snapshot_df = snapshot_df.copy()
    snapshot_df["report_date"] = pd.to_datetime(snapshot_df["report_date"]).dt.date
    snapshot_df["market_value"] = snapshot_df["quantity"] * snapshot_df["close_price"]
    snapshot_df["cost_basis"] = snapshot_df["quantity"] * snapshot_df["avg_cost"]
    
    with duckdb.connect(DB_PATH) as con:
        # delete existing for those dates/tickers to make idempotent
        for report_date in snapshot_df["report_date"].unique():
            con.execute("DELETE FROM daily_holdings_snapshot WHERE report_date = ?", [report_date])
        
        query = """
            INSERT INTO daily_holdings_snapshot 
            (report_date, ticker, quantity, avg_cost, close_price, market_value, cost_basis)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        for row in snapshot_df.itertuples(index=False):
            con.execute(
                query,
                (
                    row.report_date,
                    row.ticker,
                    float(row.quantity),
                    float(row.avg_cost),
                    float(row.close_price) if row.close_price is not None else None,
                    float(row.market_value) if row.market_value is not None else None,
                    float(row.cost_basis) if row.cost_basis is not None else None,
                ),
            )


def get_daily_holdings_snapshot(report_date=None) -> pd.DataFrame:
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        if report_date is None:
            df = con.sql("SELECT * FROM daily_holdings_snapshot ORDER BY report_date DESC, ticker").df()
        else:
            df = con.sql(
                "SELECT * FROM daily_holdings_snapshot WHERE report_date = ? ORDER BY ticker",
                [report_date],
            ).df()
    return df


def get_latest_holdings_snapshot() -> pd.DataFrame:
    latest_date = get_latest_snapshot_date()
    if latest_date is None:
        return pd.DataFrame()
    return get_daily_holdings_snapshot(latest_date)


# legacy support for old code, will be removed
def insert_stock_purchase(stock_purchase_history: pd.DataFrame):
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        con.sql("""
                CREATE TABLE IF NOT EXISTS stock_purchase_history (purchase_date DATE, quantity DOUBLE, purchase_price DOUBLE, ticker VARCHAR)
            """)
        query = """
            INSERT INTO stock_purchase_history (purchase_date, quantity, purchase_price, ticker)
            VALUES (?, ?, ?, ?)
        """
        for row in stock_purchase_history.itertuples(index=False):
            con.execute(
                query, (row.purchase_date, row.quantity, row.purchase_price, row.ticker)
            )


def get_stock_purchase_history() -> pd.DataFrame:
    create_tables()
    with duckdb.connect(DB_PATH) as con:
        try:
            df = con.sql("""
                SELECT * FROM stock_purchase_history
                WHERE purchase_date = (SELECT MAX(purchase_date) FROM stock_purchase_history)
            """).df()
            if not df.empty:
                return df
        except Exception:
            pass
        # fallback to events if old table empty
        events = get_transaction_events()
        if events.empty:
            return pd.DataFrame(columns=["purchase_date", "quantity", "purchase_price", "ticker"])
        # convert events to old format for backward compat
        buys = events[events["event_type"] == "BUY"].copy()
        buys["purchase_date"] = pd.to_datetime(buys["event_time"]).dt.date
        buys["purchase_price"] = buys["price_per_share"]
        return buys[["purchase_date", "quantity", "purchase_price", "ticker"]]
