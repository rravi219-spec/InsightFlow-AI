WITH customer_metrics AS (
    SELECT *, CAST(JULIANDAY(:analysis_date) - JULIANDAY(last_purchase_date) AS INTEGER) AS recency_days
    FROM retail_purchasers
), ranks AS (
    SELECT *, COUNT(*) OVER () AS n,
        RANK() OVER (ORDER BY recency_days DESC) AS rr,
        COUNT(*) OVER (PARTITION BY recency_days) AS rt,
        RANK() OVER (ORDER BY frequency) AS fr,
        COUNT(*) OVER (PARTITION BY frequency) AS ft,
        RANK() OVER (ORDER BY monetary_micros) AS mr,
        COUNT(*) OVER (PARTITION BY monetary_micros) AS mt
    FROM customer_metrics
), scored AS (
    SELECT customer_key, first_purchase_date, last_purchase_date, recency_days,
        frequency, monetary_micros,
        CASE WHEN n=1 THEN 3 ELSE MIN(5, 1 + CAST(5.0*(rr-1+(rt-1)/2.0)/(n-1) AS INTEGER)) END AS r_score,
        CASE WHEN n=1 THEN 3 ELSE MIN(5, 1 + CAST(5.0*(fr-1+(ft-1)/2.0)/(n-1) AS INTEGER)) END AS f_score,
        CASE WHEN n=1 THEN 3 ELSE MIN(5, 1 + CAST(5.0*(mr-1+(mt-1)/2.0)/(n-1) AS INTEGER)) END AS m_score
    FROM ranks
)
SELECT *, CASE
    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
    WHEN r_score >= 3 AND f_score >= 4 THEN 'Loyal'
    WHEN r_score >= 4 AND frequency = 1 THEN 'New Customers'
    WHEN r_score >= 3 THEN 'Potential Loyalists'
    WHEN f_score >= 3 THEN 'At Risk'
    ELSE 'Hibernating'
END AS segment
FROM scored
