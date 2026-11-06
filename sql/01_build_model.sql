-- =====================================================================
-- 01_build_model.sql
-- Builds a clean analytical model from the 8 raw Olist tables.
-- Engine: DuckDB (standard SQL; notes mark the few MySQL/PostgreSQL differences)
--
-- Output tables
--   fact_orders     one row per DELIVERED order, enriched with customer,
--                   delivery performance, review score, payment, seller, category
--   dim_customers   one row per real person (customer_unique_id)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Reviews: a few orders have >1 review -> average them
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_reviews AS
SELECT
    order_id,
    AVG(review_score)                          AS review_score,
    MAX(review_comment_message)                AS review_text
FROM raw_reviews
GROUP BY order_id;

-- ---------------------------------------------------------------------
-- 2. Payments: one order can be paid with several methods -> sum value
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_payments AS
SELECT
    order_id,
    ROUND(SUM(payment_value), 2)               AS order_value,
    MAX(payment_installments)                  AS installments,
    -- main payment method = the one carrying the largest amount (ties -> first sequence)
    FIRST(payment_type ORDER BY payment_value DESC, payment_sequential)
                                               AS payment_type   -- MySQL: use a ROW_NUMBER() subquery instead
FROM raw_payments
GROUP BY order_id;

-- ---------------------------------------------------------------------
-- 3. Items: roll up to order level, keep seller + category
--    98.7% of orders have exactly one seller; multi-seller orders are
--    flagged so seller-level analysis can exclude them.
--    Seller and category come from the most expensive item (deterministic).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE stg_items AS
SELECT
    i.order_id,
    COUNT(*)                                   AS n_items,
    COUNT(DISTINCT i.seller_id)                AS n_sellers,
    FIRST(i.seller_id    ORDER BY i.price DESC, i.order_item_id) AS seller_id,
    FIRST(s.seller_state ORDER BY i.price DESC, i.order_item_id) AS seller_state,
    FIRST(COALESCE(t.product_category_name_english,
                   p.product_category_name, 'unknown')
          ORDER BY i.price DESC, i.order_item_id)                AS category,
    ROUND(SUM(i.price), 2)                     AS items_price,
    ROUND(SUM(i.freight_value), 2)             AS freight_value
FROM raw_items i
JOIN raw_sellers s           ON s.seller_id = i.seller_id
LEFT JOIN raw_products p     ON p.product_id = i.product_id
LEFT JOIN raw_category_translation t
                             ON t.product_category_name = p.product_category_name
GROUP BY i.order_id;

-- ---------------------------------------------------------------------
-- 4. Fact table: delivered orders only (96,470 rows)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_orders AS
SELECT
    o.order_id,
    c.customer_unique_id                                           AS customer_id,
    c.customer_state,
    o.order_purchase_timestamp                                     AS purchased_at,
    CAST(o.order_purchase_timestamp AS DATE)                       AS purchase_date,
    DATE_TRUNC('month', o.order_purchase_timestamp)                AS purchase_month,
    o.order_delivered_customer_date                                AS delivered_at,
    o.order_estimated_delivery_date                                AS promised_at,
    DATE_DIFF('day', o.order_purchase_timestamp,
                     o.order_delivered_customer_date)              AS delivery_days,
    DATE_DIFF('day', o.order_estimated_delivery_date,
                     o.order_delivered_customer_date)              AS days_vs_promise,   -- negative = early
    CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
         THEN 1 ELSE 0 END                                         AS is_late,
    r.review_score,
    CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END                AS is_negative_review,
    r.review_text,
    p.order_value,
    p.payment_type,
    p.installments,
    i.n_items,
    i.n_sellers,
    i.seller_id,
    i.seller_state,
    i.category,
    i.items_price,
    i.freight_value,
    i.seller_state || ' -> ' || c.customer_state                   AS route
FROM raw_orders o
JOIN raw_customers c       ON c.customer_id = o.customer_id
LEFT JOIN stg_reviews r    ON r.order_id = o.order_id
LEFT JOIN stg_payments p   ON p.order_id = o.order_id
LEFT JOIN stg_items i      ON i.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL;

-- ---------------------------------------------------------------------
-- 5. Customer dimension
--    "Repeat customer" = bought on 2+ DIFFERENT days.
--    (28% of raw "second orders" are placed the same day = one basket
--     split into several orders; counting them would overstate loyalty.)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_customers AS
WITH first_order AS (
    SELECT *
    FROM fact_orders
    QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY purchased_at, order_id) = 1
),
agg AS (
    SELECT
        customer_id,
        COUNT(*)                         AS n_orders,
        COUNT(DISTINCT purchase_date)    AS n_purchase_days,
        ROUND(SUM(order_value), 2)       AS lifetime_value,
        MIN(purchase_date)               AS first_purchase_date,
        MAX(purchase_date)               AS last_purchase_date
    FROM fact_orders
    GROUP BY customer_id
)
SELECT
    a.*,
    CASE WHEN a.n_purchase_days > 1 THEN 1 ELSE 0 END             AS is_repeat,
    -- did they come back (different day) within 180 days of first purchase?
    CASE WHEN EXISTS (
        SELECT 1 FROM fact_orders x
        WHERE x.customer_id = a.customer_id
          AND x.purchase_date >  a.first_purchase_date
          AND x.purchase_date <= a.first_purchase_date + INTERVAL 180 DAY
    ) THEN 1 ELSE 0 END                                            AS repeat_180d,
    f.is_late              AS first_order_late,
    f.review_score         AS first_order_review,
    f.category             AS first_order_category,
    f.customer_state,
    f.payment_type         AS first_payment_type,
    f.order_value          AS first_order_value
FROM agg a
JOIN first_order f USING (customer_id);
