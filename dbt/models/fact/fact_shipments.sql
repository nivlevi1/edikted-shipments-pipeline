-- TODO: apply join_order_id / join_order_name fix on top of stg_shipments
select * from {{ ref('stg_shipments') }}
