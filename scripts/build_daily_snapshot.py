from datetime import date
from src.db import get_transaction_events, upsert_daily_snapshot, create_tables
from src.metrics import build_daily_holdings_snapshot

if __name__ == '__main__':
    create_tables()
    
    events = get_transaction_events()
    if events.empty:
        print("No transaction events, nothing to snapshot")
    else:
        print(f"Found {len(events)} transaction events")
        print(f"Date range: {events['event_time'].min()} to {events['event_time'].max()}")
        
        # build snapshots for all dates from first event to today
        # full history replay keeps avg override forever logic
        snapshot_df = build_daily_holdings_snapshot(
            events_df=events,
            start_date=events["event_time"].min().date(),
            end_date=date.today()
        )
        
        if snapshot_df.empty:
            print("No snapshots built, check price fetch")
        else:
            print(f"Built {len(snapshot_df)} snapshot rows")
            print(snapshot_df.head())
            upsert_daily_snapshot(snapshot_df)
            print("Upserted to daily_holdings_snapshot")
            
            # show portfolio total over time
            daily_total = snapshot_df.groupby("report_date")["market_value"].sum().reset_index()
            print("\nPortfolio total over time:")
            print(daily_total.tail(10))
