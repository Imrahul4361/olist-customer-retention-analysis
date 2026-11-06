-- =====================================================================
-- 03_kpi_overview.sql  -  headline KPIs and monthly trend
-- =====================================================================

-- name: kpi_headline
SELECT
    COUNT(*)                                             AS delivered_orders,
    COUNT(DISTINCT customer_id)                          AS customers,
    COUNT(DISTINCT seller_id)                            AS sellers,
    ROUND(SUM(order_value), 0)                           AS revenue_brl,
    ROUND(AVG(order_value), 2)                           AS avg_order_value_brl,
    ROUND(AVG(review_score), 2)                          AS avg_review_score,
    ROUND(100.0 * AVG(is_late), 2)                       AS late_rate_pct,
    ROUND(AVG(delivery_days), 1)                         AS avg_delivery_days,
    MEDIAN(days_vs_promise)                              AS median_days_vs_promise,
    (SELECT ROUND(100.0 * AVG(is_repeat), 2) FROM dim_customers)          AS repeat_customer_pct,
    (SELECT ROUND(100.0 * SUM(CASE WHEN is_repeat = 1 THEN lifetime_value END)
                      / SUM(lifetime_value), 2) FROM dim_customers)       AS repeat_revenue_share_pct
FROM fact_orders;

-- name: kpi_monthly
SELECT
    purchase_month,
    COUNT(*)                                    AS orders,
    ROUND(SUM(order_value), 0)                  AS revenue_brl,
    ROUND(100.0 * AVG(is_late), 2)              AS late_rate_pct,
    ROUND(AVG(review_score), 2)                 AS avg_review_score,
    ROUND(100.0 * AVG(is_negative_review), 2)   AS negative_review_pct
FROM fact_orders
WHERE purchase_month BETWEEN '2017-01-01' AND '2018-08-01'
GROUP BY purchase_month
ORDER BY purchase_month;
