import duckdb
import pandas as pd
from src.config import DB_PATH


def insert_stock_purchase(stock_purchase_history: pd.DataFrame):

    # Initialize connection
    with duckdb.connect(DB_PATH) as con:
        # If table does not exist
        con.sql("""
                CREATE TABLE IF NOT EXISTS stock_purchase_history (purchase_date DATE, quantity DOUBLE, purchase_price DOUBLE, ticker VARCHAR)
            """)
        query = """
            INSERT INTO stock_purchase_history (purchase_date, quantity, purchase_price, ticker)
            VALUES (?, ?, ?, ?)
        """
        for row in stock_purchase_history.itertuples(index=False):
            con.execute(
                query, (row.purchase_date, row.quantity, row.purchase_price, row.ticker)
            )


def get_stock_purchase_history() -> pd.DataFrame:
    with duckdb.connect(DB_PATH) as con:
        purchase_history = con.sql("""
            SELECT * FROM stock_purchase_history
            WHERE purchase_date = (
                SELECT MAX(purchase_date) FROM stock_purchase_history
            )
            """).df()

    return purchase_history
