import pandas as pd
from src.market import (
    get_latest_price_for_purchased_stocks,
)


def add_simple_moving_avg(data: pd.DataFrame, days: int) -> pd.DataFrame:

    data["{days}_moving_avg".format(days=days)] = (
        data["Close"].rolling(window=days).mean()
    )
    return data


def get_stock_price_delta(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["delta"] = stock_data["Close"] - stock_data["avg_purchase_price"]
    stock_data["delta_pct"] = (
        stock_data["Close"] - stock_data["avg_purchase_price"]
    ) / stock_data["avg_purchase_price"]

    return stock_data


def get_total_return(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["total_return"] = (
        1.0
        * stock_data["delta_pct"]
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
    stock_data_copy = stock_data.copy()
    stock_data_copy["todays_change"] = (
        stock_data_copy["Close"] - stock_data_copy["Previous Close"]
    )
    stock_data_copy["todays_change_pct"] = (
        1.0
        * (stock_data_copy["Close"] - stock_data_copy["Previous Close"])
        / stock_data_copy["Previous Close"]
    )

    return stock_data_copy


def get_daily_return(stock_data: pd.DataFrame) -> pd.DataFrame:
    stock_data["daily_return"] = (
        1.0
        * stock_data["todays_change_pct"]
        * stock_data["total_quantity"]
        * stock_data["avg_purchase_price"]
    )
    return stock_data


def get_purchased_stocks_with_metrics(purchased_stocks: pd.DataFrame) -> pd.DataFrame:

    purchased_stocks_with_metrics = get_latest_price_for_purchased_stocks(
        purchased_stocks
    )
    purchased_stocks_with_metrics = get_stock_price_delta(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_total_return(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_daily_delta(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = get_daily_return(purchased_stocks_with_metrics)
    purchased_stocks_with_metrics = update_sort_stock_data_by_delta(
        purchased_stocks_with_metrics
    )

    return purchased_stocks_with_metrics
