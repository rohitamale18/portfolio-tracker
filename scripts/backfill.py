from datetime import date, datetime

import pandas as pd
import duckdb

if __name__ == '__main__':
    
    # Read CSV
    path = "stock_data/schwab_2026_07_30.csv"
    raw_stock_data = pd.read_csv(path, delimiter=',', skiprows=2)
    
    # Cleaning
    # Cost basis contains a $ sign and ,
    raw_stock_data['cost_basis_cleaned'] = raw_stock_data['Cost Basis'].str.replace('[^0-9.]', "", regex=True)
    staging_data = raw_stock_data.iloc[:-3, :].copy()
    # Get the avg_purchase_price
    staging_data.loc[:, 'avg_purchase_price'] = 1.0 * staging_data['cost_basis_cleaned'].astype('float') / staging_data['Qty (Quantity)'].astype('float')
    # Final data
    output_data = staging_data.loc[:, ['Symbol', 'avg_purchase_price', 'Qty (Quantity)']]
    output_data.loc[:, 'purchase_date'] = datetime.strptime('2026-07-30', '%Y-%m-%d') 
    output_data.columns = ['ticker', 'purchase_price', 'quantity', 'purchase_date']

    # Initialize connection
    with duckdb.connect("portfolio.db") as con:
        # If table does not exist
        con.sql("""
                CREATE TABLE IF NOT EXISTS stock_purchase_history (purchase_date DATE, quantity DOUBLE, purchase_price DOUBLE, ticker VARCHAR)
            """
        )
        print("Table created")
        query = """
            INSERT INTO stock_purchase_history (purchase_date, quantity, purchase_price, ticker)
            VALUES (?, ?, ?, ?)
        """
        for row in output_data.itertuples(index=False):
            con.execute(query, (row.purchase_date, row.quantity, row.purchase_price, row.ticker))

    