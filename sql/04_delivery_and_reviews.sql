-- =====================================================================
-- 04_delivery_and_reviews.sql
-- Q: How much does delivery performance drive customer ratings?
-- =====================================================================

-- name: reviews_by_delivery_status
SELECT
    CASE WHEN is_late = 1 THEN 'Late' ELSE 'On time / early' END    AS delivery_status,
    COUNT(*)                                                        AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)              AS pct_of_orders,
    ROUND(AVG(review_score), 2)                                     AS avg_review,
    ROUND(100.0 * AVG(is_negative_review), 1)                       AS negative_review_pct,
    SUM(is_negative_review)                                         AS negative_reviews,
    ROUND(100.0 * SUM(is_negative_review)
          / SUM(SUM(is_negative_review)) OVER (), 1)                AS pct_of_all_negative_reviews
FROM fact_orders
WHERE review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- name: reviews_by_days_vs_promise
-- Dose-response: the later the parcel, the worse the rating
SELECT
    CASE
        WHEN days_vs_promise <= -10 THEN '1. 10+ days early'
        WHEN days_vs_promise <=  -1 THEN '2. 1-9 days early'
        WHEN days_vs_promise  =   0 THEN '3. On promised day'
        WHEN days_vs_promise <=   3 THEN '4. 1-3 days late'
        WHEN days_vs_promise <=   7 THEN '5. 4-7 days late'
        ELSE                             '6. 8+ days late'
    END                                          AS delivery_bucket,
    COUNT(*)                                     AS orders,
    ROUND(AVG(review_score), 2)                  AS avg_review,
    ROUND(100.0 * AVG(is_negative_review), 1)    AS negative_review_pct
FROM fact_orders
WHERE review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- name: negative_review_themes
-- Keyword scan of Portuguese review text (1-2 star reviews with a comment)
WITH neg AS (
    SELECT LOWER(review_text) AS t
    FROM fact_orders
    WHERE is_negative_review = 1 AND review_text IS NOT NULL
)
SELECT theme, COUNT(*) AS reviews_mentioning,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM neg), 1) AS pct_of_negative_comments
FROM (
    SELECT 'Delivery / not received / delay' AS theme FROM neg
        WHERE REGEXP_MATCHES(t, 'receb|entreg|cheg|prazo|atras|demor')
    UNION ALL
    SELECT 'Wrong / different product'            FROM neg
        WHERE REGEXP_MATCHES(t, 'errad|diferente|outro produto|n.o era|nao era')
    UNION ALL
    SELECT 'Damaged / defective / poor quality'   FROM neg
        WHERE REGEXP_MATCHES(t, 'quebr|danific|defeit|qualidade|estragad|rasgad')
    UNION ALL
    SELECT 'Partial order (missing items)'        FROM neg
        WHERE REGEXP_MATCHES(t, 's. recebi|apenas um|apenas 1|faltou|faltando|um dos')
    UNION ALL
    SELECT 'Refund / cancellation'                FROM neg
        WHERE REGEXP_MATCHES(t, 'reembols|estorno|devolu|cancel')
) x
GROUP BY theme
ORDER BY reviews_mentioning DESC, theme;
