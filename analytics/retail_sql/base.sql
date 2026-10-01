-- Connection-local views: no changes to the validated dimensional database.
CREATE TEMP VIEW retail_known_lines AS
SELECT f.*, d.calendar_date,
       CASE WHEN f.quantity > 0 AND f.is_cancelled = 0 THEN 1 ELSE 0 END AS is_purchase
FROM fact_transaction f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_date d ON d.date_key = f.date_key;

CREATE TEMP VIEW retail_orders AS
SELECT customer_key, invoice, MIN(invoice_timestamp) AS order_timestamp,
       MIN(calendar_date) AS order_date, SUM(amount_micros) AS gross_purchase_micros,
       COUNT(*) AS purchase_lines
FROM retail_known_lines WHERE is_purchase = 1
GROUP BY customer_key, invoice;

CREATE TEMP VIEW retail_purchasers AS
SELECT customer_key, COUNT(*) AS frequency,
       MIN(order_date) AS first_purchase_date, MAX(order_date) AS last_purchase_date,
       SUM(gross_purchase_micros) AS monetary_micros
FROM retail_orders GROUP BY customer_key;

CREATE TEMP VIEW retail_ledger AS
SELECT customer_key, COUNT(*) AS eligible_lines,
       SUM(CASE WHEN is_purchase=1 THEN amount_micros ELSE 0 END) AS gross_purchase_micros,
       SUM(CASE WHEN is_purchase=0 THEN amount_micros ELSE 0 END) AS return_signed_micros,
       SUM(amount_micros) AS net_value_micros
FROM retail_known_lines GROUP BY customer_key;

CREATE TEMP VIEW retail_order_intervals AS
SELECT *, ROW_NUMBER() OVER (
           PARTITION BY customer_key ORDER BY order_timestamp, invoice) AS order_number,
       JULIANDAY(order_timestamp) - JULIANDAY(LAG(order_timestamp) OVER (
           PARTITION BY customer_key ORDER BY order_timestamp, invoice)) AS interval_days
FROM retail_orders;
