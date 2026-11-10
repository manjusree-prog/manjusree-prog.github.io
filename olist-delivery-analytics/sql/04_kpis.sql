-- 04_kpis.sql
-- Business KPIs on the clean delivered-orders table.
-- The analysis window is Jan 2017 - Aug 2018: the months before and after
-- have too few orders to be reliable.

-- name: kpi_overview
SELECT
    COUNT(*)                                        AS delivered_orders,
    COUNT(DISTINCT customer_unique_id)              AS customers,
    ROUND(SUM(order_value), 0)                      AS revenue_brl,
    ROUND(AVG(order_value), 2)                      AS avg_order_value,
    ROUND(AVG(delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(promised_days), 1)                    AS avg_promised_days,
    ROUND(100.0 * AVG(is_late), 1)                  AS late_rate_pct,
    ROUND(AVG(review_score), 2)                     AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0 END), 1) AS negative_review_pct
FROM fact_delivered
WHERE purchase_month BETWEEN '2017-01' AND '2018-08';

-- name: monthly_trend
-- Orders, revenue and late rate per month, plus a 3-month rolling late rate.
WITH m AS (
    SELECT purchase_month,
           COUNT(*)                 AS orders,
           ROUND(SUM(order_value),0) AS revenue_brl,
           SUM(is_late)             AS late_orders,
           ROUND(AVG(delivery_days),1) AS avg_delivery_days,
           ROUND(AVG(review_score),2)  AS avg_review
    FROM fact_delivered
    WHERE purchase_month BETWEEN '2017-01' AND '2018-08'
    GROUP BY purchase_month
)
SELECT purchase_month, orders, revenue_brl, late_orders,
       ROUND(100.0 * late_orders / orders, 1) AS late_rate_pct,
       ROUND(100.0 * SUM(late_orders) OVER w / SUM(orders) OVER w, 1) AS late_rate_3m_pct,
       avg_delivery_days, avg_review
FROM m
WINDOW w AS (ORDER BY purchase_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
ORDER BY purchase_month;

-- name: review_by_delivery_outcome
-- How satisfaction changes with delivery performance against the promised date.
SELECT
    CASE
        WHEN days_vs_estimate <= -8 THEN '1. 8+ days early'
        WHEN days_vs_estimate <= -1 THEN '2. 1-7 days early'
        WHEN days_vs_estimate  = 0 THEN '3. on the promised day'
        WHEN days_vs_estimate <= 3 THEN '4. 1-3 days late'
        WHEN days_vs_estimate <= 7 THEN '5. 4-7 days late'
        ELSE                            '6. 8+ days late'
    END AS delivery_outcome,
    COUNT(*)                                   AS orders,
    ROUND(AVG(review_score), 2)                AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0 END), 1) AS negative_review_pct,
    ROUND(100.0 * AVG(CASE WHEN review_score = 5 THEN 1.0 ELSE 0 END), 1)  AS five_star_pct
FROM fact_delivered
WHERE review_score IS NOT NULL
  AND purchase_month BETWEEN '2017-01' AND '2018-08'
GROUP BY delivery_outcome
ORDER BY delivery_outcome;

-- name: late_rate_by_state
-- States ranked by late rate (states with at least 500 orders).
WITH s AS (
    SELECT customer_state,
           COUNT(*)                      AS orders,
           ROUND(100.0 * AVG(is_late),1) AS late_rate_pct,
           ROUND(AVG(delivery_days),1)   AS avg_delivery_days,
           ROUND(AVG(promised_days),1)   AS avg_promised_days,
           ROUND(AVG(review_score),2)    AS avg_review
    FROM fact_delivered
    WHERE purchase_month BETWEEN '2017-01' AND '2018-08'
    GROUP BY customer_state
    HAVING COUNT(*) >= 500
)
SELECT RANK() OVER (ORDER BY late_rate_pct DESC) AS late_rank, *
FROM s
ORDER BY late_rank;

-- name: delivery_stage_breakdown
-- Where the time goes: approval -> seller handling -> carrier transit.
SELECT
    CASE is_late WHEN 1 THEN 'late' ELSE 'on time / early' END AS outcome,
    COUNT(*)                            AS orders,
    ROUND(AVG(approval_days), 1)        AS approval_days,
    ROUND(AVG(seller_handling_days), 1) AS seller_handling_days,
    ROUND(AVG(carrier_transit_days), 1) AS carrier_transit_days,
    ROUND(AVG(delivery_days), 1)        AS total_delivery_days,
    ROUND(AVG(promised_days), 1)        AS promised_days
FROM fact_delivered
WHERE purchase_month BETWEEN '2017-01' AND '2018-08'
GROUP BY is_late;

-- name: seller_late_concentration
-- Are late deliveries spread out or concentrated in a few sellers?
-- Each (order, seller) pair counts once.
WITH order_seller AS (
    SELECT DISTINCT f.order_id, i.seller_id, f.is_late
    FROM fact_delivered f
    JOIN order_items i ON i.order_id = f.order_id
    WHERE f.purchase_month BETWEEN '2017-01' AND '2018-08'
),
per_seller AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(is_late) AS late_orders
    FROM order_seller
    GROUP BY seller_id
),
ranked AS (
    SELECT seller_id, orders, late_orders,
           ROW_NUMBER() OVER (ORDER BY late_orders DESC, orders DESC) AS rn,
           COUNT(*) OVER ()                    AS n_sellers,
           SUM(late_orders) OVER ()            AS total_late,
           SUM(late_orders) OVER (ORDER BY late_orders DESC, orders DESC
                                  ROWS UNBOUNDED PRECEDING) AS cum_late
    FROM per_seller
)
SELECT rn AS seller_rank, seller_id, orders, late_orders,
       ROUND(100.0 * late_orders / orders, 1)      AS seller_late_rate_pct,
       ROUND(100.0 * rn / n_sellers, 2)            AS pct_of_sellers,
       ROUND(100.0 * cum_late / total_late, 1)     AS cum_pct_of_late_orders
FROM ranked
ORDER BY rn;

-- name: category_performance
-- Top 15 categories by revenue with their delivery and review performance.
WITH cat AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           f.order_id, f.is_late, f.review_score, f.delivery_days,
           i.price + i.freight_value AS line_value
    FROM fact_delivered f
    JOIN order_items i ON i.order_id = f.order_id
    LEFT JOIN products p ON p.product_id = i.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE f.purchase_month BETWEEN '2017-01' AND '2018-08'
)
SELECT category,
       COUNT(DISTINCT order_id)          AS orders,
       ROUND(SUM(line_value), 0)         AS revenue_brl,
       ROUND(100.0 * AVG(is_late), 1)    AS late_rate_pct,
       ROUND(AVG(delivery_days), 1)      AS avg_delivery_days,
       ROUND(AVG(review_score), 2)       AS avg_review
FROM cat
GROUP BY category
ORDER BY revenue_brl DESC
LIMIT 15;

-- name: repeat_customers
-- Do customers whose first order arrived late come back less often?
WITH first_order AS (
    SELECT customer_unique_id, is_late,
           ROW_NUMBER() OVER (PARTITION BY customer_unique_id
                              ORDER BY order_purchase_timestamp) AS rn,
           COUNT(*) OVER (PARTITION BY customer_unique_id)       AS n_orders
    FROM fact_delivered
)
SELECT CASE is_late WHEN 1 THEN 'first order late' ELSE 'first order on time' END AS first_delivery,
       COUNT(*)                                                     AS customers,
       ROUND(100.0 * AVG(CASE WHEN n_orders > 1 THEN 1.0 ELSE 0 END), 2) AS repeat_purchase_pct
FROM first_order
WHERE rn = 1
GROUP BY is_late;
