-- 03_data_quality_checks.sql
-- Each block is one named query; scripts/run_sql.py saves the result to
-- outputs/sql_results/<name>.csv

-- name: dq_summary
-- One row per check: how many records fail it.
SELECT 'orders: duplicate order_id' AS check_name,
       COUNT(*) - COUNT(DISTINCT order_id) AS failing_rows
FROM orders
UNION ALL
SELECT 'order_items: item without matching order',
       COUNT(*) FROM order_items i
       WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = i.order_id)
UNION ALL
SELECT 'order_items: price <= 0', COUNT(*) FROM order_items WHERE price <= 0
UNION ALL
SELECT 'orders: payment total differs from items + freight by > 1 BRL',
       COUNT(*) FROM v_order_items i
       JOIN v_order_payments p ON p.order_id = i.order_id
       WHERE ABS(p.paid_value - (i.items_value + i.freight_value)) > 1
UNION ALL
SELECT 'order_reviews: orders with more than one review',
       COUNT(*) FROM (SELECT order_id FROM order_reviews
                      GROUP BY order_id HAVING COUNT(*) > 1)
UNION ALL
SELECT 'products: missing category', COUNT(*) FROM products
       WHERE product_category_name IS NULL
UNION ALL
SELECT 'delivered orders: ' || dq_issue, COUNT(*)
FROM dq_flags WHERE dq_issue IS NOT NULL
GROUP BY dq_issue;

-- name: dq_pipeline_counts
SELECT
    (SELECT COUNT(*) FROM orders)                                    AS all_orders,
    (SELECT COUNT(*) FROM orders WHERE order_status = 'delivered')   AS delivered_orders,
    (SELECT COUNT(*) FROM dq_quarantine)                             AS quarantined,
    (SELECT COUNT(*) FROM fact_delivered)                            AS clean_delivered_orders;
