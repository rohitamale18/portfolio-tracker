import pandas as pd
import yfinance as yf
from datetime import date


def get_stock_price_data(ticker: str, period: str) -> pd.DataFrame:
    try:
        base_stock_data = yf.Ticker(ticker)
        historic_stock_data = base_stock_data.history(period=period)[
            ["Close"]
        ].reset_index()
    except Exception as e:
        print(f"Failed to get stock price from yfinance for {ticker}")
        historic_stock_data = pd.DataFrame(
            data=[[date.today(), ticker, None]], columns=["Date", "ticker", "Close"]
        )
    return historic_stock_data


def get_latest_price_for_purchased_stocks(
    purchased_stocks: pd.DataFrame,
) -> pd.DataFrame:
    purchased_stocks = (
        purchased_stocks.groupby("ticker")
        .agg(
            avg_purchase_price=("purchase_price", "mean"),
            total_quantity=("quantity", "sum"),
        )
        .reset_index()
    )

    rows = []
    for ticker in purchased_stocks["ticker"]:
        hist = get_stock_price_data(ticker, "2d")
        if hist.empty:
            print(f"Warning: no price data for {ticker}, skipping")
            continue
        hist = hist.sort_values("Date")
        # Ensure Close is numeric
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            continue
        latest = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest
        rows.append({"ticker": ticker, "Close": latest, "Previous Close": prev})

    last_price = pd.DataFrame(rows)
    if last_price.empty:
        return purchased_stocks  # fallback, no price data
    purchased_stocks_with_last_price = pd.merge(
        purchased_stocks, last_price, on="ticker", how="left"
    )
    return purchased_stocks_with_last_price
