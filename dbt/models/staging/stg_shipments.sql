with source as (
    select * from {{ source('raw', 'shipments') }}
)

select * from source
