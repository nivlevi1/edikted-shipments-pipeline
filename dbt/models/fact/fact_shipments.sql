with stg as (
    select * from {{ ref('stg_shipments') }}
),

fixed as (
    select
        *,
        coalesce(order_id, order_name)                          as join_order_id,
        coalesce(coalesce(order_id, order_name), '0000066600000') as join_order_name
    from stg
)

select * from fixed
