-- 02_clean_layer.sql
-- Builds the analysis table for delivered orders.
-- Every delivered order gets a data-quality flag; only rows that pass all
-- checks go into fact_delivered. Failing rows are kept in dq_quarantine
-- with the reason, so nothing disappears silently.

DROP TABLE IF EXISTS dq_flags;
CREATE TABLE dq_flags AS
SELECT
    o.order_id,
    CASE
        WHEN o.order_delivered_customer_date IS NULL
            THEN 'delivered status but no delivery date'
        WHEN o.order_delivered_customer_date < o.order_purchase_timestamp
            THEN 'delivered before purchase'
        WHEN o.order_approved_at IS NULL
            THEN 'missing approval timestamp'
        WHEN o.order_delivered_carrier_date IS NULL
            THEN 'missing carrier handover timestamp'
        WHEN o.order_delivered_carrier_date < o.order_purchase_timestamp
            THEN 'handed to carrier before purchase'
        WHEN o.order_delivered_customer_date < o.order_delivered_carrier_date
            THEN 'delivered to customer before carrier handover'
        WHEN i.order_id IS NULL
            THEN 'order has no items'
        ELSE NULL
    END AS dq_issue
FROM orders o
LEFT JOIN v_order_items i ON i.order_id = o.order_id
WHERE o.order_status = 'delivered';

DROP TABLE IF EXISTS dq_quarantine;
CREATE TABLE dq_quarantine AS
SELECT o.*, f.dq_issue
FROM orders o
JOIN dq_flags f ON f.order_id = o.order_id
WHERE f.dq_issue IS NOT NULL;

DROP TABLE IF EXISTS fact_delivered;
CREATE TABLE fact_delivered AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_purchase_timestamp,
    DATE(o.order_purchase_timestamp)              AS purchase_date,
    STRFTIME('%Y-%m', o.order_purchase_timestamp) AS purchase_month,
    -- lead times in days
    ROUND(JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_purchase_timestamp), 2)   AS delivery_days,
    ROUND(JULIANDAY(o.order_approved_at)             - JULIANDAY(o.order_purchase_timestamp), 2)   AS approval_days,
    ROUND(JULIANDAY(o.order_delivered_carrier_date)  - JULIANDAY(o.order_approved_at), 2)          AS seller_handling_days,
    ROUND(JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_delivered_carrier_date), 2) AS carrier_transit_days,
    ROUND(JULIANDAY(o.order_estimated_delivery_date) - JULIANDAY(o.order_purchase_timestamp), 2)   AS promised_days,
    -- positive = days late, negative = days early (compared by calendar date)
    CAST(JULIANDAY(DATE(o.order_delivered_customer_date))
       - JULIANDAY(DATE(o.order_estimated_delivery_date)) AS INTEGER) AS days_vs_estimate,
    CASE WHEN DATE(o.order_delivered_customer_date) > DATE(o.order_estimated_delivery_date)
         THEN 1 ELSE 0 END AS is_late,
    i.n_items,
    i.n_sellers,
    i.items_value,
    i.freight_value,
    ROUND(i.items_value + i.freight_value, 2) AS order_value,
    r.review_score
FROM orders o
JOIN dq_flags f         ON f.order_id = o.order_id AND f.dq_issue IS NULL
JOIN customers c        ON c.customer_id = o.customer_id
JOIN v_order_items i    ON i.order_id = o.order_id
LEFT JOIN v_order_review r ON r.order_id = o.order_id;

CREATE INDEX IF NOT EXISTS ix_fact_order ON fact_delivered (order_id);
CREATE INDEX IF NOT EXISTS ix_fact_month ON fact_delivered (purchase_month);
CREATE INDEX IF NOT EXISTS ix_fact_state ON fact_delivered (customer_state);
