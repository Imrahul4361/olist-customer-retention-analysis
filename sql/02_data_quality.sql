-- =====================================================================
-- 02_data_quality.sql  -  checks run BEFORE trusting any number
-- Each "-- name:" block is executed by src/run_sql.py and saved to
-- data/processed/<name>.csv
-- =====================================================================

-- name: dq_row_counts
SELECT 'raw_orders'    AS table_name, COUNT(*) AS n_rows FROM raw_orders    UNION ALL
SELECT 'raw_customers',              COUNT(*)            FROM raw_customers UNION ALL
SELECT 'raw_items',                  COUNT(*)            FROM raw_items     UNION ALL
SELECT 'raw_payments',               COUNT(*)            FROM raw_payments  UNION ALL
SELECT 'raw_reviews',                COUNT(*)            FROM raw_reviews   UNION ALL
SELECT 'raw_products',               COUNT(*)            FROM raw_products  UNION ALL
SELECT 'raw_sellers',                COUNT(*)            FROM raw_sellers   UNION ALL
SELECT 'fact_orders (delivered)',    COUNT(*)            FROM fact_orders   UNION ALL
SELECT 'dim_customers (people)',     COUNT(*)            FROM dim_customers;

-- name: dq_order_status
SELECT order_status, COUNT(*) AS n_orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM raw_orders
GROUP BY order_status
ORDER BY n_orders DESC, order_status;

-- name: dq_issues
-- Known issues and how the model handles them
SELECT 'customer_id is per ORDER, not per person' AS issue,
       COUNT(DISTINCT customer_id) - COUNT(DISTINCT customer_unique_id) AS affected_rows,
       'use customer_unique_id as the real customer key' AS handling
FROM raw_customers
UNION ALL
SELECT 'orders with more than one review',
       (SELECT COUNT(*) FROM (SELECT order_id FROM raw_reviews GROUP BY 1 HAVING COUNT(*) > 1)),
       'average the scores'
UNION ALL
SELECT 'delivered orders missing delivery date',
       (SELECT COUNT(*) FROM raw_orders WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL),
       'excluded from fact_orders'
UNION ALL
SELECT 'delivered orders without a review',
       (SELECT COUNT(*) FROM fact_orders WHERE review_score IS NULL),
       'kept; excluded only from rating metrics'
UNION ALL
SELECT 'orders with more than one seller',
       (SELECT COUNT(*) FROM fact_orders WHERE n_sellers > 1),
       'excluded from seller-level metrics only'
UNION ALL
SELECT 'same-day "repeat" orders (split baskets)',
       (SELECT COUNT(*) - COUNT(DISTINCT customer_id || CAST(purchase_date AS VARCHAR)) FROM fact_orders),
       'repeat customer = purchases on 2+ different days'
UNION ALL
SELECT 'sparse months (2016-09..12, 2018-09..10)',
       (SELECT COUNT(*) FROM raw_orders WHERE order_purchase_timestamp < '2017-01-01' OR order_purchase_timestamp >= '2018-09-01'),
       'excluded from monthly trend charts';
