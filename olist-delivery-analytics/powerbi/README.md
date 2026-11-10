# Power BI model

`python scripts/analysis.py` writes a star schema to `powerbi/model/` (not committed because of file size):

| Table | Grain | Key columns |
|---|---|---|
| `fact_orders.csv` | one row per clean delivered order | order_id, purchase_date, customer_state, is_late, delivery_days, review_score, order_value |
| `fact_order_items.csv` | one row per order × seller × product line | order_id, seller_id, seller_state, category, price, freight_value |
| `dim_date.csv` | one row per calendar day | date, year, month, year_month, weekday |
| `dim_state.csv` | one row per Brazilian state | customer_state |

## Relationships

- `dim_date[date]` 1 → * `fact_orders[purchase_date]`
- `dim_state[customer_state]` 1 → * `fact_orders[customer_state]`
- `fact_orders[order_id]` 1 → * `fact_order_items[order_id]` (single direction)

## DAX measures

```DAX
Orders = COUNTROWS ( fact_orders )

Revenue = SUM ( fact_orders[order_value] )

Late Orders = CALCULATE ( [Orders], fact_orders[is_late] = 1 )

Late Rate % = DIVIDE ( [Late Orders], [Orders] )

Avg Delivery Days = AVERAGE ( fact_orders[delivery_days] )

Avg Promised Days = AVERAGE ( fact_orders[promised_days] )

Avg Review = AVERAGE ( fact_orders[review_score] )

Negative Review % =
DIVIDE (
    CALCULATE ( [Orders], fact_orders[review_score] <= 2 ),
    CALCULATE ( [Orders], NOT ISBLANK ( fact_orders[review_score] ) )
)

Late Rate % (3M Rolling) =
VAR _end = MAX ( dim_date[date] )
VAR _start = EDATE ( _end, -3 ) + 1
RETURN
    CALCULATE ( [Late Rate %], DATESBETWEEN ( dim_date[date], _start, _end ) )

Late Rate vs Avg (pp) =
[Late Rate %] - CALCULATE ( [Late Rate %], ALL ( dim_state ) )
```

## Suggested report page

- KPI cards: Orders, Revenue, Avg Delivery Days, Late Rate %, Avg Review, Negative Review %
- Line and column chart: Orders (columns) and Late Rate % (line) by `year_month`
- Bar chart: Late Rate % by `customer_state`, coloured with conditional formatting (≥ 10% red)
- Clustered bar: Negative Review % by delivery outcome (late vs on time)
- Slicers: year_month, customer_state, category
