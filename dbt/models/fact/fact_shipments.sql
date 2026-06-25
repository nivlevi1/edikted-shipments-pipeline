-- Finding #2 (ERROR): join_order_id and join_order_name are 0% accurate in all 224k source rows.
-- The source system used an unknown formula — not coalesce(order_id, order_name).
-- Fix: add corrected columns. Original broken columns kept for lineage traceability.
-- All downstream joins on order ID must use the _fixed columns.
--
--   join_order_id_fixed   = coalesce(order_id, order_name)
--   join_order_name_fixed = coalesce(coalesce(order_id, order_name), '0000066600000')

with stg as (
    select * from {{ ref('stg_shipments') }}
)

select
    *,
    coalesce(order_id, order_name)                            as join_order_id_fixed,
    coalesce(coalesce(order_id, order_name), '0000066600000') as join_order_name_fixed
from stg
