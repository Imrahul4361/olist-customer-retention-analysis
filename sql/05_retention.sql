-- =====================================================================
-- 05_retention.sql
-- Q: How many customers come back, when, and what predicts it?
-- =====================================================================

-- name: retention_summary
SELECT
    COUNT(*)                                                    AS customers,
    SUM(is_repeat)                                              AS repeat_customers,
    ROUND(100.0 * AVG(is_repeat), 2)                            AS repeat_rate_pct,
    ROUND(SUM(CASE WHEN is_repeat = 1 THEN lifetime_value END)
          / SUM(is_repeat), 2)                                  AS avg_ltv_repeat,
    ROUND(SUM(CASE WHEN is_repeat = 0 THEN lifetime_value END)
          / SUM(1 - is_repeat), 2)                              AS avg_ltv_one_time
FROM dim_customers;

-- name: days_to_second_purchase
-- Gap between 1st and 2nd purchase DAY (same-day split baskets excluded)
WITH days AS (
    SELECT DISTINCT customer_id, purchase_date FROM fact_orders
),
seq AS (
    SELECT customer_id, purchase_date,
           LEAD(purchase_date) OVER (PARTITION BY customer_id ORDER BY purchase_date) AS next_date,
           ROW_NUMBER()        OVER (PARTITION BY customer_id ORDER BY purchase_date) AS rn
    FROM days
)
, buckets AS (
    SELECT
        CASE
            WHEN DATE_DIFF('day', purchase_date, next_date) <=  30 THEN '1. within 30 days'
            WHEN DATE_DIFF('day', purchase_date, next_date) <=  90 THEN '2. 31-90 days'
            WHEN DATE_DIFF('day', purchase_date, next_date) <= 180 THEN '3. 91-180 days'
            WHEN DATE_DIFF('day', purchase_date, next_date) <= 365 THEN '4. 181-365 days'
            ELSE '5. over 1 year'
        END              AS gap_bucket,
        COUNT(*)         AS customers
    FROM seq
    WHERE rn = 1 AND next_date IS NOT NULL
    GROUP BY 1
)
SELECT gap_bucket, customers,
       ROUND(100.0 * customers / SUM(customers) OVER (), 1)                          AS pct,
       ROUND(100.0 * SUM(customers) OVER (ORDER BY gap_bucket ROWS UNBOUNDED PRECEDING)
             / SUM(customers) OVER (), 1)                                            AS cumulative_pct
FROM buckets
ORDER BY gap_bucket;

-- name: repeat_by_first_order_experience
-- Does a bad FIRST experience stop people coming back?
-- Only first orders before 2018-03-01 so everyone has a full 180-day window.
SELECT
    CASE WHEN first_order_late = 1 THEN 'Late' ELSE 'On time / early' END AS first_order_delivery,
    COUNT(*)                                    AS customers,
    SUM(repeat_180d)                            AS came_back_180d,
    ROUND(100.0 * AVG(repeat_180d), 2)          AS repeat_180d_pct
FROM dim_customers
WHERE first_purchase_date < '2018-03-01'
GROUP BY 1
ORDER BY 1;

-- name: repeat_by_first_review
SELECT
    CASE WHEN first_order_review >= 4 THEN '4-5 stars'
         WHEN first_order_review >= 3 THEN '3 stars'
         ELSE '1-2 stars' END                   AS first_order_rating,
    COUNT(*)                                    AS customers,
    ROUND(100.0 * AVG(repeat_180d), 2)          AS repeat_180d_pct
FROM dim_customers
WHERE first_purchase_date < '2018-03-01' AND first_order_review IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- name: repeat_by_first_category
SELECT
    first_order_category                        AS category,
    COUNT(*)                                    AS customers,
    SUM(repeat_180d)                            AS came_back_180d,
    ROUND(100.0 * AVG(repeat_180d), 2)          AS repeat_180d_pct
FROM dim_customers
WHERE first_purchase_date < '2018-03-01'
  AND first_order_category <> 'unknown'
GROUP BY 1
HAVING COUNT(*) >= 1000
ORDER BY repeat_180d_pct DESC, category;

-- name: cohort_retention
-- Monthly acquisition cohorts: % of customers buying again in month +1..+6
WITH cohort AS (
    SELECT customer_id, DATE_TRUNC('month', first_purchase_date) AS cohort_month, first_purchase_date
    FROM dim_customers
),
activity AS (
    SELECT DISTINCT f.customer_id, c.cohort_month,
           DATE_DIFF('month', c.cohort_month, f.purchase_month) AS month_n
    FROM fact_orders f
    JOIN cohort c USING (customer_id)
    WHERE f.purchase_date > c.first_purchase_date          -- a later purchase day
)
SELECT
    c.cohort_month,
    COUNT(DISTINCT c.customer_id)                                         AS cohort_size,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 1 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m1,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 2 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m2,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 3 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m3,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 4 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m4,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 5 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m5,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN a.month_n = 6 THEN a.customer_id END) / COUNT(DISTINCT c.customer_id), 2) AS m6
FROM cohort c
LEFT JOIN activity a USING (customer_id)
WHERE c.cohort_month BETWEEN '2017-01-01' AND '2018-02-01'
GROUP BY c.cohort_month
ORDER BY c.cohort_month;
