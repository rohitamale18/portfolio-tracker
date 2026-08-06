import pandas as pd
import streamlit as st
from datetime import datetime, date
from src.market import get_stock_price_data
from src.metrics import add_simple_moving_avg
from src.db import insert_transaction_event


def get_total_portfolio_value(stock_data: pd.DataFrame):
    if stock_data.empty:
        st.subheader("Total Portfolio Holdings: $0.00")
        return
    # support both old and new column names
    if "total_quantity" in stock_data.columns and "Close" in stock_data.columns:
        total = (stock_data["Close"] * stock_data["total_quantity"]).sum()
    elif "quantity" in stock_data.columns and "Close" in stock_data.columns:
        total = (stock_data["Close"] * stock_data["quantity"]).sum()
    else:
        total = 0
    st.subheader(f"Total Portfolio Holdings: ${total:,.2f}")


def get_top_daily_movers(
    stock_data: pd.DataFrame, move_type: str = "gainer", threshold: int = 3
):
    if stock_data.empty:
        return
    is_gainer = move_type == "gainer"
    ordered_data = stock_data.sort_values(
        by="daily_return", ascending=not is_gainer
    ).head(threshold)

    bg_color = "#d4edda" if is_gainer else "#f8d7da"
    text_color = "#155724" if is_gainer else "#721c24"

    st.subheader("Top Gainers" if is_gainer else "Top Losers")
    cols = st.columns(threshold)

    for i, col in enumerate(cols):
        if i >= len(ordered_data):
            break
        row = ordered_data.iloc[i]
        with col:
            # single div card, no outer container gap
            st.markdown(
                f"""
            <div style="background-color:{bg_color}; color:{text_color}; 
                        padding:12px; border-radius:8px; text-align:center; border:1px solid #ccc">
                <div style="font-weight:700; font-size:18px">{row['ticker']}</div>
                <div style="font-size:14px">Change: {row['daily_return']:+.2f}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def render_log_transaction_form():
    st.sidebar.header("Log Trade")
    st.sidebar.caption("Simple manual entry. Override avg applies forever.")

    with st.sidebar.form("log_trade_form"):
        ticker = st.text_input("Ticker", placeholder="AAPL").upper().strip()
        event_type = st.selectbox("Event", ["BUY", "SELL", "ADJUST (manual avg override only)"])
        # clean event_type value
        event_type_clean = event_type.split(" ")[0]

        quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.1, help="0 allowed for ADJUST")
        price_per_share = st.number_input("Price per share", min_value=0.0, value=100.0, step=0.5)
        event_date = st.date_input("Event Date", value=date.today())
        event_time_input = st.time_input("Event Time", value=datetime.now().time())

        override_check = st.checkbox("Override avg cost forever? (simple fix for lot issues)", value=(event_type_clean=="ADJUST"))
        manual_avg_override = None
        if override_check:
            manual_avg_override = st.number_input(
                "Manual Avg Override", min_value=0.0, value=price_per_share, step=0.1,
                help="If set, this becomes avg_cost going forward forever for this ticker"
            )

        notes = st.text_input("Notes (optional)", placeholder="e.g. correction for split, sold lot A")

        submitted = st.form_submit_button("Log Transaction")

        if submitted:
            if not ticker:
                st.sidebar.error("Ticker required")
                return None
            
            # combine date + time
            event_time = datetime.combine(event_date, event_time_input)

            # for ADJUST, quantity can be 0
            if event_type_clean == "ADJUST" and quantity == 0:
                quantity = 0.0

            event_dict = {
                "event_time": event_time,
                "ticker": ticker,
                "quantity": float(quantity),
                "price_per_share": float(price_per_share),
                "event_type": event_type_clean,
                "manual_avg_override": float(manual_avg_override) if override_check else None,
                "notes": notes.strip() if notes else None
            }

            try:
                insert_transaction_event(event_dict)
                st.sidebar.success(f"Logged {event_type_clean} {quantity} {ticker} @ {price_per_share}. Override: {manual_avg_override}")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Failed to log: {e}")
                return None

    # also show recent transactions
    from src.db import get_transaction_events
    events = get_transaction_events()
    if not events.empty:
        st.sidebar.subheader("Recent Transactions")
        st.sidebar.dataframe(
            events.tail(10).sort_values("event_time", ascending=False)[["event_time", "ticker", "event_type", "quantity", "price_per_share", "manual_avg_override"]],
            hide_index=True,
            width='stretch'
        )


def render_portfolio_table(purchased_stocks_with_metrics: pd.DataFrame):
    # pure render, returns selected ticker or None, no st.stop() inside
    st.subheader("Overview")
    
    if purchased_stocks_with_metrics.empty:
        st.info("No holdings yet. Log a trade in sidebar.")
        return None

    with st.container(border=True):
        stock_selection = st.dataframe(
            purchased_stocks_with_metrics,
            column_config={
                "ticker": "Ticker",
                "avg_purchase_price": "Average Purchase Price",
                "avg_cost": "Average Cost",
                "total_quantity": "Quantity",
                "quantity": "Quantity",
                "Close": st.column_config.NumberColumn("Last Price", format="$%.2f"),
                "total_return": st.column_config.NumberColumn(
                    "Total Gain", format="$%.2f"
                ),
                "delta": st.column_config.NumberColumn(
                    "Total Price Change", format="$%.2f"
                ),
                "delta_pct": st.column_config.NumberColumn(
                    "Gain (%)", format="percent"
                ),
                "todays_change": st.column_config.NumberColumn(
                    "Today's Change", format="$%.2f"
                ),
                "todays_change_pct": st.column_config.NumberColumn(
                    "Today's Gain (%)", format="percent"
                ),
                "daily_return": st.column_config.NumberColumn(
                    "Daily Gain", format="$%.2f"
                ),
            },
            on_select="rerun",
            selection_mode="single-row",
            key="ticker",
            hide_index=True,
            width="stretch",
            column_order=(
                "ticker",
                "Close",
                "total_quantity",
                "daily_return",
                "total_return",
                "delta",
                "todays_change",
                "todays_change_pct",
                "delta_pct",
                "avg_purchase_price",
            ),
        )
        rows = stock_selection.selection.rows
        if not rows:
            return None
        
        selected_index = rows[0]
        ticker_selection = purchased_stocks_with_metrics.iloc[selected_index]["ticker"]
        return ticker_selection


def render_stock_controls():
    st.write("Stock Detail")
    period_selection = st.selectbox(
        label="Select Period", options=("1mo", "3mo", "12mo", "60mo")
    )
    mapper = {
        "50 Day": 50,
        "100 Day": 100,
        "200 Day": 200,
    }
    with st.container(border=True):
        sma_selection = st.radio(
            "SMA",
            ["50 Day", "100 Day", "200 Day"],
            index=None,
        )
    sma_days = mapper.get(sma_selection) if sma_selection else None
    return period_selection, sma_days


def render_stock_chart(ticker: str, period: str, sma_days: int = None):
    st.write(f"Showing details for: **{ticker}**")
    data = get_stock_price_data(ticker, period)
    if data.empty:
        st.warning(f"No price data for {ticker}")
        return
    
    data["Date"] = pd.to_datetime(data["Date"]).dt.date

    if sma_days is not None:
        data = add_simple_moving_avg(data, sma_days)

    with st.container(border=True):
        st.line_chart(
            data.set_index("Date"), height=400, x_label="Date", y_label="Price"
        )


def render_portfolio_snapshot_chart(snapshot_df: pd.DataFrame):
    # new chart for total portfolio over time using daily_holdings_snapshot
    if snapshot_df.empty:
        return
    st.subheader("Portfolio Value Over Time")
    # aggregate total market value per report_date
    daily_total = snapshot_df.groupby("report_date")["market_value"].sum().reset_index()
    daily_total["report_date"] = pd.to_datetime(daily_total["report_date"])
    daily_total = daily_total.sort_values("report_date")
    with st.container(border=True):
        st.line_chart(daily_total.set_index("report_date"), y="market_value", height=300, x_label="Date", y_label="Total Value")


# legacy wrapper to keep old app.py working, but new code should use split functions
def get_stock_portfolio_table(purchased_stocks_with_metrics: pd.DataFrame):
    ticker = render_portfolio_table(purchased_stocks_with_metrics)
    
    if not ticker:
        st.info("Click a row in the table above to see the chart.")
        st.stop()

    period, sma_days = render_stock_controls()
    render_stock_chart(ticker, period, sma_days)
