-- =====================================================================
-- 06_sellers_and_routes.sql
-- Q: Where do late deliveries come from? (sellers, routes, months)
-- Seller metrics use single-seller orders only (98.7% of orders).
-- =====================================================================

-- name: seller_pareto
-- How concentrated are late deliveries? (Pareto / 80-20 analysis)
WITH s AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(is_late) AS late_orders
    FROM fact_orders
    WHERE n_sellers = 1
    GROUP BY seller_id
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY late_orders DESC, orders DESC, seller_id)               AS seller_rank,
           SUM(late_orders) OVER (ORDER BY late_orders DESC, orders DESC, seller_id
                                  ROWS UNBOUNDED PRECEDING)                         AS cum_late,
           SUM(late_orders) OVER ()                                                 AS total_late,
           COUNT(*) OVER ()                                                         AS total_sellers
    FROM s
)
SELECT seller_rank, seller_id, orders, late_orders,
       ROUND(100.0 * seller_rank / total_sellers, 2)  AS pct_of_sellers,
       ROUND(100.0 * cum_late / total_late, 2)        AS cum_pct_of_late_orders
FROM ranked
ORDER BY seller_rank;

-- name: seller_watchlist
-- "Chronic late" sellers: 30+ orders and a late rate >= 15% (~2x the average)
SELECT seller_id, seller_state,
       COUNT(*)                              AS orders,
       SUM(is_late)                          AS late_orders,
       ROUND(100.0 * AVG(is_late), 1)        AS late_rate_pct,
       ROUND(AVG(review_score), 2)           AS avg_review,
       ROUND(SUM(order_value), 0)            AS revenue_brl
FROM fact_orders
WHERE n_sellers = 1
GROUP BY seller_id, seller_state
HAVING COUNT(*) >= 30 AND AVG(is_late) >= 0.15
ORDER BY late_orders DESC, seller_id;

-- name: route_performance
-- Seller state -> customer state lanes with 500+ orders
SELECT route,
       COUNT(*)                              AS orders,
       SUM(is_late)                          AS late_orders,
       ROUND(100.0 * AVG(is_late), 1)        AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)          AS avg_delivery_days,
       ROUND(AVG(review_score), 2)           AS avg_review,
       ROUND(100.0 * SUM(is_late) / (SELECT SUM(is_late) FROM fact_orders WHERE n_sellers = 1), 1)
                                             AS pct_of_all_late
FROM fact_orders
WHERE n_sellers = 1
GROUP BY route
HAVING COUNT(*) >= 500
ORDER BY late_orders DESC, route;

-- name: late_by_customer_state
SELECT customer_state,
       COUNT(*)                              AS orders,
       ROUND(100.0 * AVG(is_late), 1)        AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)          AS avg_delivery_days,
       ROUND(AVG(review_score), 2)           AS avg_review
FROM fact_orders
GROUP BY customer_state
ORDER BY orders DESC, customer_state;
