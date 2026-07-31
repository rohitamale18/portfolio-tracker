
from src.metrics import get_purchased_stocks_with_metrics
from src.ui import get_stock_portfolio_table, get_top_daily_movers
import streamlit as st
import pandas as pd
from src.db import get_stock_purchase_history

if __name__ == '__main__':
    st.set_page_config(page_title="Rohit's Portfolio", layout="wide")
    st.title("Rohit's Portfolio")
    
    stock_purchase_history = get_stock_purchase_history()
    purchased_stocks_with_metrics = get_purchased_stocks_with_metrics(stock_purchase_history)
    
    get_top_daily_movers(purchased_stocks_with_metrics, 'gainer')
    get_top_daily_movers(purchased_stocks_with_metrics, 'loser')
    
    get_stock_portfolio_table(purchased_stocks_with_metrics)