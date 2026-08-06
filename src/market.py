import pandas as pd
import yfinance as yf
from datetime import date


def _sanitize_ticker_for_yf(ticker: str) -> str:
    t = ticker.strip().upper()
    if "/" in t:
        t = t.replace("/", "-")
    return t


def get_stock_price_data(ticker: str, period: str) -> pd.DataFrame:
    yf_ticker = _sanitize_ticker_for_yf(ticker)
    try:
        base_stock_data = yf.Ticker(yf_ticker)
        historic_stock_data = base_stock_data.history(period=period)[
            ["Close"]
        ].reset_index()
        if "ticker" not in historic_stock_data.columns:
            historic_stock_data["ticker"] = ticker
    except Exception as e:
        print(f"Failed to get stock price from yfinance for {ticker} (yf: {yf_ticker}): {e}")
        historic_stock_data = pd.DataFrame(
            data=[[date.today(), ticker, None]], columns=["Date", "ticker", "Close"]
        )
    return historic_stock_data


def get_batch_close_prices(tickers: list, period: str = "2d") -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame(columns=["ticker", "Close", "Previous Close"])
    
    original_tickers = [t.upper() for t in tickers]
    sanitized_map = {orig: _sanitize_ticker_for_yf(orig) for orig in original_tickers}
    # reverse map sanitized -> original (if duplicate sanitized, keep first)
    reverse_map = {}
    for orig, san in sanitized_map.items():
        if san not in reverse_map:
            reverse_map[san] = orig
    sanitized_tickers = list(sanitized_map.values())

    try:
        # batch download using sanitized tickers
        data = yf.download(sanitized_tickers, period=period, group_by="ticker", progress=False, auto_adjust=False)
        if data.empty:
            return pd.DataFrame(columns=["ticker", "Close", "Previous Close"])
        
        rows = []
        if len(sanitized_tickers) == 1:
            hist = data[["Close"]].dropna()
            if hist.empty:
                return pd.DataFrame(columns=["ticker", "Close", "Previous Close"])
            hist = hist.sort_index()
            latest = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest
            rows.append({"ticker": original_tickers[0], "Close": latest, "Previous Close": prev})
        else:
            for orig in original_tickers:
                san = sanitized_map[orig]
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        # try san in level 0 or 1
                        close_series = pd.Series(dtype=float)
                        if san in data.columns.get_level_values(0):
                            close_series = data[san]["Close"].dropna()
                        elif san in data.columns.get_level_values(1):
                            close_series = data["Close"][san].dropna()
                        else:
                            # try alternative extraction
                            try:
                                close_series = data.xs("Close", axis=1, level=0)[san].dropna()
                            except Exception:
                                close_series = pd.Series(dtype=float)
                    else:
                        close_series = data["Close"].dropna()
                    
                    if close_series.empty:
                        continue
                    close_series = close_series.sort_index()
                    latest = float(close_series.iloc[-1])
                    prev = float(close_series.iloc[-2]) if len(close_series) >= 2 else latest
                    rows.append({"ticker": orig, "Close": latest, "Previous Close": prev})
                except Exception as inner_e:
                    print(f"Batch price failed for {orig} (san {san}): {inner_e}")
                    try:
                        single = get_stock_price_data(orig, period)
                        single = single.dropna(subset=["Close"]).sort_values("Date")
                        if not single.empty:
                            latest = float(single["Close"].iloc[-1])
                            prev = float(single["Close"].iloc[-2]) if len(single) >= 2 else latest
                            rows.append({"ticker": orig, "Close": latest, "Previous Close": prev})
                    except Exception as e2:
                        print(f"Single fallback failed for {orig}: {e2}")
                        continue
        
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Batch download failed: {e}, falling back to loop")
        rows = []
        for orig in original_tickers:
            try:
                hist = get_stock_price_data(orig, period)
                hist = hist.dropna(subset=["Close"]).sort_values("Date")
                if hist.empty:
                    continue
                latest = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest
                rows.append({"ticker": orig, "Close": latest, "Previous Close": prev})
            except Exception as inner:
                print(f"Fallback loop failed for {orig}: {inner}")
                continue
        return pd.DataFrame(rows)


def get_latest_price_for_purchased_stocks(
    purchased_stocks: pd.DataFrame,
) -> pd.DataFrame:
    if purchased_stocks.empty:
        return purchased_stocks
    
    price_col = "avg_purchase_price" if "avg_purchase_price" in purchased_stocks.columns else "avg_cost" if "avg_cost" in purchased_stocks.columns else "purchase_price"
    qty_col = "total_quantity" if "total_quantity" in purchased_stocks.columns else "quantity"
    
    if "ticker" in purchased_stocks.columns and price_col in purchased_stocks.columns:
        if len(purchased_stocks) == purchased_stocks["ticker"].nunique():
            agg_df = purchased_stocks.copy()
            if price_col != "avg_purchase_price" and "avg_purchase_price" not in agg_df.columns:
                agg_df["avg_purchase_price"] = agg_df[price_col]
            if qty_col != "total_quantity" and "total_quantity" not in agg_df.columns:
                agg_df["total_quantity"] = agg_df[qty_col]
        else:
            agg_df = (
                purchased_stocks.groupby("ticker")
                .agg(
                    avg_purchase_price=(price_col, "mean"),
                    total_quantity=(qty_col, "sum"),
                )
                .reset_index()
            )
    else:
        agg_df = purchased_stocks.copy()

    tickers = agg_df["ticker"].tolist()
    last_price = get_batch_close_prices(tickers, "2d")
    
    if last_price.empty:
        return agg_df
    
    merged = pd.merge(agg_df, last_price, on="ticker", how="left")
    return merged
