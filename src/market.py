import pandas as pd
import yfinance as yf
from datetime import date, timedelta

def get_stock_price_data(ticker: str, period: str) -> pd.DataFrame:
    try:
        base_stock_data = yf.Ticker(ticker)
        historic_stock_data = base_stock_data.history(period=period)[['Close']].reset_index() 
    except Exception as e:
        print(f"Failed to get stock price from yfinance for {ticker}")
        historic_stock_data = pd.DataFrame(data=[[date.today(), ticker, None]], columns=['Date', 'ticker', 'Close'])
    return historic_stock_data

def get_previous_day_stock_price(ticker: str) -> float:
    base_stock_data = get_stock_price_data(ticker, "2d").reset_index()
    yesterday = date.today() - timedelta(days=1)
    base_stock_data['Date'] = pd.to_datetime(base_stock_data['Date']).dt.date

    return base_stock_data[base_stock_data['Date'] == yesterday]['Close']

def get_latest_price_for_purchased_stocks(purchased_stocks: pd.DataFrame) -> pd.DataFrame:
    purchased_stocks = purchased_stocks.groupby('ticker').agg(avg_purchase_price=('purchase_price', 'mean'), total_quantity=('quantity', 'sum')).reset_index()
        
    purchased_stocks_with_last_price = pd.DataFrame()
    last_price = pd.DataFrame()
    for purchased_stock in purchased_stocks.reset_index()['ticker']:
        tmp = {
            "ticker": purchased_stock,
            "Close": get_stock_price_data(purchased_stock, "1d")['Close'],
            "Previous Close": get_previous_day_stock_price(purchased_stock)
        }
        last_price = pd.concat([last_price, pd.DataFrame(tmp)], ignore_index=True)
    purchased_stocks_with_last_price = pd.merge(purchased_stocks, last_price)
    return purchased_stocks_with_last_price