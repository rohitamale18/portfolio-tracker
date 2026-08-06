from datetime import datetime
import duckdb
import pandas as pd
from src.config import DB_PATH
from src.db import create_tables

if __name__ == '__main__':
    create_tables()
    
    # read old stock_purchase_history if exists
    with duckdb.connect(DB_PATH) as con:
        try:
            old_df = con.sql("SELECT * FROM stock_purchase_history").df()
            print(f"Found old stock_purchase_history: {len(old_df)} rows")
        except Exception as e:
            print(f"No old table: {e}")
            old_df = pd.DataFrame()

        if old_df.empty:
            print("No old data to migrate, done")
        else:
            # clear events for clean migration? For POC, delete then reinsert
            print("Migrating to stock_transaction_event...")
            con.sql("DELETE FROM stock_transaction_event WHERE 1=1")
            
            # convert each old row to BUY event
            for row in old_df.itertuples(index=False):
                # purchase_date may be date or datetime
                purchase_date = row.purchase_date
                if isinstance(purchase_date, pd.Timestamp):
                    event_time = purchase_date.to_pydatetime()
                else:
                    # assume date, set time to 09:30
                    event_time = datetime.combine(purchase_date, datetime.min.time()).replace(hour=9, minute=30)
                
                query = """
                    INSERT INTO stock_transaction_event 
                    (event_time, ticker, quantity, price_per_share, event_type, manual_avg_override, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                con.execute(query, (
                    event_time,
                    row.ticker,
                    float(row.quantity),
                    float(row.purchase_price),
                    "BUY",
                    None,
                    "migrated from stock_purchase_history"
                ))
            
            print(f"Migrated {len(old_df)} rows")
            cnt = con.sql("SELECT COUNT(*) as cnt FROM stock_transaction_event").df()
            print(cnt)
