SELECT * FROM stock_purchase_history;

-- New Select
SELECT * FROM stock_purchase_history
WHERE purchase_date = (
    SELECT MAX(purchase_date) FROM stock_purchase_history
);

-- Modify
ALTER TABLE stock_purchase_history ADD COLUMN quantity DOUBLE;

-- NEVER USE THE BELOW COMMAND
DELETE FROM stock_purchase_history WHERE 1=1;