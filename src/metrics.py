import pandas as pd
from datetime import datetime, date
from src.market import get_latest_price_for_purchased_stocks, get_stock_price_data


def add_simple_moving_avg(data: pd.DataFrame, days: int) -> pd.DataFrame:
    # keep your original style but using assign for safety
    col_name = f"{days}_moving_avg"
    data[col_name] = data["Close"].rolling(window=days).mean()
    return data


def get_stock_price_delta(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["delta"] = stock_data["Close"] - stock_data["avg_purchase_price"]
    stock_data["delta_pct"] = (
        stock_data["Close"] - stock_data["avg_purchase_price"]
    ) / stock_data["avg_purchase_price"]
    return stock_data


def get_total_return(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["total_return"] = (
        stock_data["delta_pct"]
        * stock_data["total_quantity"]
        * stock_data["avg_purchase_price"]
    )
    return stock_data


def update_sort_stock_data_by_delta(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data_sorted = stock_data.copy()
    stock_data_sorted = stock_data_sorted.sort_values(
        by=["total_return"], ascending=False
    )
    return stock_data_sorted


def get_daily_delta(stock_data: pd.DataFrame) -> pd.DataFrame:
    # keep copy pattern from before
    stock_data_copy = stock_data.copy()
    stock_data_copy["todays_change"] = (
        stock_data_copy["Close"] - stock_data_copy["Previous Close"]
    )
    stock_data_copy["todays_change_pct"] = (
        stock_data_copy["Close"] - stock_data_copy["Previous Close"]
    ) / stock_data_copy["Previous Close"]
    return stock_data_copy


def get_daily_return(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["daily_return"] = (
        stock_data["todays_change_pct"]
        * stock_data["total_quantity"]
        * stock_data["avg_purchase_price"]
    )
    return stock_data


# --- new event-sourcing logic with manual override forever ---

def get_current_holdings_from_events(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes stock_transaction_event DataFrame and returns current holdings per ticker.
    Keeps your simple pandas style, full history replay.

    Columns expected: event_time, ticker, quantity, price_per_share, event_type, manual_avg_override
    manual_avg_override: if NOT NULL, that becomes avg_cost going forward forever.
    """
    if events_df.empty:
        return pd.DataFrame(columns=["ticker", "quantity", "avg_cost", "cost_basis"])

    events_df = events_df.copy()
    events_df["event_time"] = pd.to_datetime(events_df["event_time"])
    events_df = events_df.sort_values(["ticker", "event_time"])

    holdings = {}

    for _, row in events_df.iterrows():
        ticker = str(row["ticker"]).upper()
        qty_event = float(row["quantity"])
        price = float(row["price_per_share"])
        event_type = str(row["event_type"]).upper()
        override = row.get("manual_avg_override")
        has_override = pd.notna(override) and override != ""

        if ticker not in holdings:
            holdings[ticker] = {"quantity": 0.0, "avg_cost": 0.0}

        prev_qty = holdings[ticker]["quantity"]
        prev_avg = holdings[ticker]["avg_cost"]

        if event_type == "BUY":
            if has_override:
                # override becomes new avg after this buy, applies forever
                new_qty = prev_qty + qty_event
                new_avg = float(override)
                holdings[ticker]["quantity"] = new_qty
                holdings[ticker]["avg_cost"] = new_avg
            else:
                new_qty = prev_qty + qty_event
                if new_qty == 0:
                    new_avg = 0.0
                else:
                    total_cost = prev_qty * prev_avg + qty_event * price
                    new_avg = total_cost / new_qty
                holdings[ticker]["quantity"] = new_qty
                holdings[ticker]["avg_cost"] = new_avg
        elif event_type == "SELL":
            new_qty = prev_qty - qty_event
            if new_qty < 0:
                new_qty = 0.0
            if has_override:
                holdings[ticker]["avg_cost"] = float(override)
            else:
                holdings[ticker]["avg_cost"] = prev_avg
            holdings[ticker]["quantity"] = new_qty
        elif event_type == "ADJUST":
            # pure manual override forever, no qty change
            if has_override:
                holdings[ticker]["avg_cost"] = float(override)
            # qty stays same
            holdings[ticker]["quantity"] = prev_qty

    # convert to DataFrame, filter out zero qty unless you want to keep history
    rows = []
    for ticker, vals in holdings.items():
        if vals["quantity"] <= 0:
            continue
        rows.append({
            "ticker": ticker,
            "quantity": vals["quantity"],
            "avg_cost": vals["avg_cost"],
            "cost_basis": vals["quantity"] * vals["avg_cost"]
        })

    if not rows:
        return pd.DataFrame(columns=["ticker", "quantity", "avg_cost", "cost_basis"])

    holdings_df = pd.DataFrame(rows)
    # align with old naming for metrics pipeline
    holdings_df["avg_purchase_price"] = holdings_df["avg_cost"]
    holdings_df["total_quantity"] = holdings_df["quantity"]
    holdings_df["purchase_price"] = holdings_df["avg_cost"]
    return holdings_df


def get_current_holdings_snapshot(events_df: pd.DataFrame, as_of_date=None) -> pd.DataFrame:
    """
    Holdings as of a specific date (inclusive). If as_of_date is None, use all events.
    This is used to build daily snapshots day-by-day.
    """
    if events_df.empty:
        return pd.DataFrame(columns=["ticker", "quantity", "avg_cost"])
    
    if as_of_date is not None:
        as_of_date = pd.to_datetime(as_of_date).date()
        events_df = events_df[pd.to_datetime(events_df["event_time"]).dt.date <= as_of_date].copy()
    
    return get_current_holdings_from_events(events_df)


def get_purchased_stocks_with_metrics(purchased_stocks: pd.DataFrame) -> pd.DataFrame:
    """
    Supports both old format (stock_purchase_history) and new format (holdings from events).
    purchased_stocks can be:
    - old: purchase_date, quantity, purchase_price, ticker
    - new: ticker, quantity, avg_cost (from get_current_holdings_from_events)
    """
    if purchased_stocks.empty:
        return pd.DataFrame()

    # if already has avg_cost/quantity from new logic, skip aggregation in market.py will handle
    purchased_stocks_with_metrics = get_latest_price_for_purchased_stocks(
        purchased_stocks
    )
    
    # normalize column names for downstream calcs
    if "avg_purchase_price" not in purchased_stocks_with_metrics.columns:
        if "avg_cost" in purchased_stocks_with_metrics.columns:
            purchased_stocks_with_metrics["avg_purchase_price"] = purchased_stocks_with_metrics["avg_cost"]
    
    if "total_quantity" not in purchased_stocks_with_metrics.columns:
        if "quantity" in purchased_stocks_with_metrics.columns:
            purchased_stocks_with_metrics["total_quantity"] = purchased_stocks_with_metrics["quantity"]

    # if price data missing, return what we have
    if "Close" not in purchased_stocks_with_metrics.columns:
        return purchased_stocks_with_metrics

    purchased_stocks_with_metrics = get_stock_price_delta(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_total_return(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_daily_delta(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_daily_return(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = update_sort_stock_data_by_delta(
        purchased_stocks_with_metrics
    )

    return purchased_stocks_with_metrics


def build_daily_holdings_snapshot(events_df: pd.DataFrame, start_date=None, end_date=None, price_history_df=None):
    """
    Builds daily_holdings_snapshot for charting total portfolio value over time.
    Simple style: replay events day-by-day, fetch close price for each day.

    price_history_df optional: pre-fetched close prices DataFrame with Date index and ticker columns
    If None, will fetch via yfinance inside (batch).

    Returns DataFrame report_date, ticker, quantity, avg_cost, close_price, market_value, cost_basis
    """
    if events_df.empty:
        return pd.DataFrame(columns=["report_date", "ticker", "quantity", "avg_cost", "close_price", "market_value", "cost_basis"])

    import yfinance as yf

    events_df = events_df.copy()
    events_df["event_time"] = pd.to_datetime(events_df["event_time"])
    
    if start_date is None:
        start_date = events_df["event_time"].min().date()
    if end_date is None:
        end_date = date.today()

    # unique report dates: trading days between start and end where we have holdings
    # for POC, use all dates where events happened + today, plus daily for last 1mo for chart smoothness
    # simplest: generate all trading days via yfinance for tickers
    all_tickers = events_df["ticker"].unique().tolist()
    all_tickers = [t.upper() for t in all_tickers]
    # sanitize for yfinance (BRK/B -> BRK-B)
    sanitized_map = {orig: orig.replace("/", "-") for orig in all_tickers}
    sanitized_tickers = list(sanitized_map.values())

    # fetch batch price history for range
    try:
        if price_history_df is None:
            # yf download for range using sanitized tickers
            hist = yf.download(sanitized_tickers, start=start_date, end=end_date, group_by="ticker", progress=False, auto_adjust=False)
            price_history_df = hist
    except Exception as e:
        print(f"build_daily_holdings_snapshot price fetch failed: {e}")
        price_history_df = pd.DataFrame()

    # determine report dates: use trading days from price history or event dates
    report_dates = sorted(events_df["event_time"].dt.date.unique().tolist())
    # ensure today included
    if date.today() not in report_dates:
        report_dates.append(date.today())
    report_dates = sorted(set(report_dates))

    snapshot_rows = []
    for rpt_date in report_dates:
        # holdings as of this date
        holdings_as_of = get_current_holdings_snapshot(events_df, as_of_date=rpt_date)
        if holdings_as_of.empty:
            continue
        
        for _, h_row in holdings_as_of.iterrows():
            ticker = h_row["ticker"]
            qty = h_row["quantity"]
            avg_cost = h_row["avg_cost"]
            
            close_price = None
            yf_ticker = sanitized_map.get(ticker, ticker.replace("/", "-"))
            try:
                # try to get close for that date from price_history_df (which uses sanitized tickers)
                if price_history_df is not None and not price_history_df.empty:
                    # handle MultiIndex
                    if isinstance(price_history_df.columns, pd.MultiIndex):
                        # try to extract using sanitized ticker
                        if yf_ticker in price_history_df.columns.get_level_values(0):
                            series = price_history_df[yf_ticker]["Close"]
                        elif ticker in price_history_df.columns.get_level_values(0):
                            series = price_history_df[ticker]["Close"]
                        else:
                            # try Close level
                            if "Close" in price_history_df.columns.get_level_values(0):
                                try:
                                    series = price_history_df["Close"][yf_ticker] if yf_ticker in price_history_df["Close"].columns else price_history_df["Close"][ticker]
                                except Exception:
                                    series = None
                            else:
                                series = None
                        if series is not None:
                            series = series.dropna()
                            series.index = pd.to_datetime(series.index).date
                            avail = series[series.index <= rpt_date]
                            if not avail.empty:
                                close_price = float(avail.iloc[-1])
                    else:
                        if "Close" in price_history_df.columns:
                            series = price_history_df["Close"]
                            series = series.dropna()
                            series.index = pd.to_datetime(series.index).date
                            avail = series[series.index <= rpt_date]
                            if not avail.empty:
                                close_price = float(avail.iloc[-1])
                # fallback single
                if close_price is None:
                    # fetch 5d around date
                    single = get_stock_price_data(ticker, "5d")
                    if not single.empty:
                        single["Date"] = pd.to_datetime(single["Date"]).dt.date
                        avail = single[single["Date"] <= rpt_date]
                        if not avail.empty:
                            close_price = float(avail["Close"].iloc[-1])
            except Exception as e:
                print(f"close lookup failed for {ticker} on {rpt_date}: {e}")
                close_price = None

            if close_price is None:
                continue

            snapshot_rows.append({
                "report_date": rpt_date,
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
                "close_price": close_price,
                "market_value": qty * close_price,
                "cost_basis": qty * avg_cost
            })

    if not snapshot_rows:
        return pd.DataFrame(columns=["report_date", "ticker", "quantity", "avg_cost", "close_price", "market_value", "cost_basis"])

    return pd.DataFrame(snapshot_rows)
