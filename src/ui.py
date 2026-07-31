import pandas as pd
import streamlit as st
from src.market import get_stock_price_data
from src.metrics import add_simple_moving_avg


def get_top_daily_movers(
    stock_data: pd.DataFrame, move_type: str = "gainer", threshold: int = 3
):
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
            # border=False - we draw our own colored background
            st.markdown(
                f"""
            <div style="background-color:{bg_color}; color:{text_color}; 
                        padding:12px; border-radius:8px; text-align:center">
                <div style="font-weight:700; font-size:18px">{row['ticker']}</div>
                <div style="font-size:14px">Change: {row['daily_return']:+.2f}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )


def get_stock_portfolio_table(purchased_stocks_with_metrics: pd.DataFrame):

    st.subheader("Overview")
    with st.container(border=True):
        stock_selection = st.dataframe(
            purchased_stocks_with_metrics,
            column_config={
                "ticker": "Ticker",
                "avg_purchase_price": "Average Purchase Price",
                "total_quantity": "Quantity",
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
        selected_stock = stock_selection.selection.rows

        if not selected_stock:
            st.info("Click a row in the table above to see the chart.")
            st.stop()  # halts the script here — nothing below runs

        # From here on, we know a row is selected
        selected_index = selected_stock[0]
        ticker_selection = purchased_stocks_with_metrics.iloc[selected_index]["ticker"]
        st.write(f"Showing details for: **{ticker_selection}**")

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

        data = get_stock_price_data(ticker_selection, period_selection)
        data["Date"] = pd.to_datetime(data["Date"]).dt.date

        output_columns = ["Close"]
        if sma_selection is not None:
            output_columns.append("{day}_moving_avg".format(day=mapper[sma_selection]))
            data = add_simple_moving_avg(data, mapper[sma_selection])

        with st.container(border=True):
            st.line_chart(
                data.set_index("Date"), height=400, x_label="Date", y_label="Price"
            )
