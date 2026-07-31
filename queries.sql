SELECT * FROM stock_purchase_history;

-- Modify
ALTER TABLE stock_purchase_history ADD COLUMN quantity DOUBLE;

-- NEVER USE THE BELOW COMMAND
DELETE FROM stock_purchase_history WHERE 1=1;