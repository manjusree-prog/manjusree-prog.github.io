-- 01_views.sql
-- Order-level helper views. Several tables are at a finer grain than the order
-- (items, payments, reviews), so they are aggregated to one row per order first.

DROP VIEW IF EXISTS v_order_items;
CREATE VIEW v_order_items AS
SELECT
    order_id,
    COUNT(*)                   AS n_items,
    COUNT(DISTINCT seller_id)  AS n_sellers,
    ROUND(SUM(price), 2)         AS items_value,
    ROUND(SUM(freight_value), 2) AS freight_value
FROM order_items
GROUP BY order_id;

DROP VIEW IF EXISTS v_order_payments;
CREATE VIEW v_order_payments AS
SELECT order_id, ROUND(SUM(payment_value), 2) AS paid_value
FROM order_payments
GROUP BY order_id;

-- An order can have more than one review row; keep the latest answer.
DROP VIEW IF EXISTS v_order_review;
CREATE VIEW v_order_review AS
SELECT order_id, review_score
FROM (
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (PARTITION BY order_id
                              ORDER BY review_answer_timestamp DESC) AS rn
    FROM order_reviews
)
WHERE rn = 1;
