-- =====================================================================
-- 07_customer_segments.sql
-- RFM-style segmentation for CRM targeting.
-- Because 98% of customers buy once, classic RFM collapses on F.
-- So we segment on Recency x Value, and flag Frequency separately.
-- Snapshot date = day after the last order in the data.
-- =====================================================================

-- name: customer_segments
WITH snap AS (SELECT MAX(purchase_date) + INTERVAL 1 DAY AS d FROM fact_orders),
base AS (
    SELECT c.customer_id,
           DATE_DIFF('day', c.last_purchase_date, (SELECT d FROM snap)) AS recency_days,
           c.n_purchase_days                                            AS frequency,
           c.lifetime_value                                             AS monetary,
           NTILE(4) OVER (ORDER BY c.lifetime_value)                    AS value_quartile   -- 4 = top 25%
    FROM dim_customers c
)
SELECT
    CASE
        WHEN frequency >= 2 AND recency_days <= 180           THEN '1. Loyal (repeat, active)'
        WHEN frequency >= 2                                   THEN '2. Lapsed repeat buyers'
        WHEN recency_days <= 120 AND value_quartile = 4       THEN '3. New high-value (win 2nd order)'
        WHEN recency_days <= 120                              THEN '4. New standard (win 2nd order)'
        WHEN value_quartile = 4                               THEN '5. Dormant high-value'
        ELSE                                                       '6. Dormant one-time'
    END                                         AS segment,
    COUNT(*)                                    AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)          AS pct_customers,
    ROUND(SUM(monetary), 0)                     AS revenue_brl,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1) AS pct_revenue,
    ROUND(AVG(monetary), 0)                     AS avg_value_brl,
    ROUND(AVG(recency_days), 0)                 AS avg_recency_days
FROM base
GROUP BY 1
ORDER BY 1;
