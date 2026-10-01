WITH RECURSIVE
acquisition AS (
    SELECT customer_key, SUBSTR(first_purchase_date,1,7) AS cohort_month
    FROM retail_purchasers
), sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size FROM acquisition GROUP BY cohort_month
), activity AS (
    SELECT a.cohort_month, SUBSTR(o.order_date,1,7) AS activity_month,
           COUNT(DISTINCT o.customer_key) AS active_customers
    FROM retail_orders o JOIN acquisition a USING(customer_key)
    GROUP BY a.cohort_month, SUBSTR(o.order_date,1,7)
), grid(cohort_month, cohort_size, activity_month, month_offset) AS (
    SELECT cohort_month, cohort_size, cohort_month, 0 FROM sizes
    UNION ALL
    SELECT cohort_month, cohort_size, STRFTIME('%Y-%m', activity_month || '-01', '+1 month'), month_offset+1
    FROM grid WHERE activity_month < SUBSTR(:observation_end,1,7)
)
SELECT g.*, COALESCE(a.active_customers,0) AS active_customers,
       100.0 * COALESCE(a.active_customers,0) / g.cohort_size AS retention_pct,
       CASE WHEN g.activity_month = SUBSTR(:observation_end,1,7)
                 AND :observation_end < DATE(:observation_end,'start of month','+1 month','-1 day')
            THEN 1 ELSE 0 END AS is_partial_month
FROM grid g LEFT JOIN activity a
    ON g.cohort_month=a.cohort_month AND g.activity_month=a.activity_month
ORDER BY g.cohort_month, g.month_offset
