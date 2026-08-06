import streamlit as st
from src.db import get_transaction_events, get_stock_purchase_history, get_daily_holdings_snapshot
from src.metrics import get_current_holdings_from_events, get_purchased_stocks_with_metrics
from src.ui import (
    get_total_portfolio_value,
    get_top_daily_movers,
    render_portfolio_table,
    render_stock_controls,
    render_stock_chart,
    render_log_transaction_form,
    render_portfolio_snapshot_chart,
)

st.set_page_config(page_title="Rohit's Portfolio", layout="wide")
st.title("Rohit's Portfolio")

# sidebar form for manual logging
render_log_transaction_form()

# try new event-sourcing path first
events = get_transaction_events()

if not events.empty:
    # new flow: holdings from events with manual avg override forever logic
    holdings = get_current_holdings_from_events(events)
    if holdings.empty:
        st.info("No current holdings after processing events. Log a BUY in sidebar.")
        st.stop()
    purchased_stocks_with_metrics = get_purchased_stocks_with_metrics(holdings)
else:
    # fallback to old table for backward compat
    st.caption("No transaction events found, falling back to old stock_purchase_history table. Log a trade in sidebar to use new model.")
    stock_purchase_history = get_stock_purchase_history()
    if stock_purchase_history.empty:
        st.info("No holdings yet. Log a trade in sidebar to get started.")
        st.stop()
    purchased_stocks_with_metrics = get_purchased_stocks_with_metrics(stock_purchase_history)

if purchased_stocks_with_metrics.empty:
    st.warning("No metrics computed. Check data.")
    st.stop()

get_total_portfolio_value(purchased_stocks_with_metrics)
get_top_daily_movers(purchased_stocks_with_metrics, "gainer")
get_top_daily_movers(purchased_stocks_with_metrics, "loser")

# portfolio snapshot chart if exists
snapshot_df = get_daily_holdings_snapshot()
if not snapshot_df.empty:
    render_portfolio_snapshot_chart(snapshot_df)

# table returns selected ticker
selected_ticker = render_portfolio_table(purchased_stocks_with_metrics)

if not selected_ticker:
    st.info("Click a row in the table above to see the chart.")
    st.stop()

# detail view
period, sma_days = render_stock_controls()
render_stock_chart(selected_ticker, period, sma_days)
