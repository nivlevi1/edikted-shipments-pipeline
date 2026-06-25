-- Union of all 6 raw sources (4 CSV, 2 JSON) with normalized column names and malformed rows removed.
-- All string null representations ('None', 'NaN', '') converted to SQL NULL via clean_str macro.
--
-- Fixes applied (evidence in notebooks/data_profile.ipynb):
--   Finding #1 (ERROR)  — Column drift: WHERE additional_handling_length_girth <> '' drops all 6
--                         drifted rows. Blank last col = drift; 'None' last col = clean row.
--   Finding #3 (ERROR)  — Artifact columns in edikted_1sa112 (\nwarehouse_invoice, __warehouse_invoice,
--                         iwarehouse_fees) excluded via explicit SELECT list in json_1sa112 CTE.
--   Finding #4 (WARN)   — Column name variants (inserdatetime, address, _warehouse_*) aliased to
--                         canonical names in per-source CTEs before UNION ALL.
--   Finding #5 (WARN)   — clean_str macro applies NULLIF x3 to all 92 columns.
--   Finding #6 (WARN)   — JSON sources had no ID; ROW_NUMBER() OVER () added as surrogate.

with csv_sources as (
    select *
    from (
        select * from {{ source('raw', 'edikted_112412') }}
        union all
        select * from {{ source('raw', 'edikted_212412') }}
        union all
        select * from {{ source('raw', 'edikted_212423') }}
        union all
        select * from {{ source('raw', 'background_image') }}
    ) all_csv
    -- unified column-drift filter:
    --   all drifted rows (regardless of shift boundary) leave the last column blank ('').
    --   normal rows always have additional_handling_length_girth = 'None'.
    --   this catches rows 7, 22, 38, 62 in background_image and rows 8, 13 in edikted_212423.
    where additional_handling_length_girth <> ''
),

json_1sa112 as (
    -- renames: inserdatetime, _warehouse_invoice, _warehouse_fees, address
    -- drops:   \nwarehouse_invoice, __warehouse_invoice, iwarehouse_fees (artifact columns)
    select
        row_number() over ()::text                      as "ID",
        source_file,
        inserdatetime                                   as insert_datetime,
        _warehouse_invoice                              as warehouse_invoice,
        carrier,
        carriers_fees,
        check_amount,
        check_num,
        check_reference,
        customer,
        customer_name,
        customer_num,
        date,
        extra_length_surcharge,
        invoice_date,
        invoice_num,
        invoice_number,
        non_standard_length,
        order_id,
        order_type,
        ordernum_ponum,
        oversize_charge,
        package_dimensions,
        pick_ticket,
        po_num,
        received,
        receiver_address1,
        receiver_address_1,
        receiver_address_2,
        receiver_city,
        receiver_company_name,
        receiver_country,
        receiver_name,
        receiver_postal_code,
        receiver_state,
        reference_1,
        reference_2,
        sender_company_name,
        sender_name,
        service,
        total_charge,
        total_credit,
        tracking_number,
        trackingnum,
        values,
        weight_billable,
        zone,
        ge_ordernum,
        parcel_codes,
        date_received_in_hub,
        is_replacement_order,
        count_parcels,
        shipping_paid_by_customer,
        shipping_subsidies,
        duties_paid_by_customer,
        weight_lbs,
        out_of_delivery_area_tier_b,
        clearance_end_use_fee,
        _warehouse_fees                                 as warehouse_fees,
        transportation_type,
        address                                         as main_address,
        customs,
        extra,
        dimensional,
        peak,
        das,
        fuel,
        transportation,
        shopify_order_date,
        join_order_id,
        order_name,
        order_date,
        otype,
        join_order_name,
        shopify_order_type,
        additional_tax_administration_duty_kor,
        addl_handling_weight,
        invalid_accountnum,
        additional_weight_charge_ground_shipmen,
        delivery_confirmation_signature,
        hst_harmonized_sales_tax_duty,
        returns_print_label,
        additional_handling_charge_weight,
        british_columbia_pst,
        not_previously_billed_remote_area_surcharge,
        same_day_pickup_alternate_address_web_request,
        delivery_area_surcharge_intra_hawaii_r,
        delivery_area_surcharge_alaska,
        declared_value,
        additional_handling_charge_dimensions,
        additional_handling_length_girth,
        _source_file
    from {{ source('raw', 'edikted_1sa112') }}
),

json_1sa122 as (
    -- rename: address -> main_address
    select
        row_number() over ()::text                      as "ID",
        source_file,
        insert_datetime,
        warehouse_invoice,
        carrier,
        carriers_fees,
        check_amount,
        check_num,
        check_reference,
        customer,
        customer_name,
        customer_num,
        date,
        extra_length_surcharge,
        invoice_date,
        invoice_num,
        invoice_number,
        non_standard_length,
        order_id,
        order_type,
        ordernum_ponum,
        oversize_charge,
        package_dimensions,
        pick_ticket,
        po_num,
        received,
        receiver_address1,
        receiver_address_1,
        receiver_address_2,
        receiver_city,
        receiver_company_name,
        receiver_country,
        receiver_name,
        receiver_postal_code,
        receiver_state,
        reference_1,
        reference_2,
        sender_company_name,
        sender_name,
        service,
        total_charge,
        total_credit,
        tracking_number,
        trackingnum,
        values,
        weight_billable,
        zone,
        ge_ordernum,
        parcel_codes,
        date_received_in_hub,
        is_replacement_order,
        count_parcels,
        shipping_paid_by_customer,
        shipping_subsidies,
        duties_paid_by_customer,
        weight_lbs,
        out_of_delivery_area_tier_b,
        clearance_end_use_fee,
        warehouse_fees,
        transportation_type,
        address                                         as main_address,
        customs,
        extra,
        dimensional,
        peak,
        das,
        fuel,
        transportation,
        shopify_order_date,
        join_order_id,
        order_name,
        order_date,
        otype,
        join_order_name,
        shopify_order_type,
        additional_tax_administration_duty_kor,
        addl_handling_weight,
        invalid_accountnum,
        additional_weight_charge_ground_shipmen,
        delivery_confirmation_signature,
        hst_harmonized_sales_tax_duty,
        returns_print_label,
        additional_handling_charge_weight,
        british_columbia_pst,
        not_previously_billed_remote_area_surcharge,
        same_day_pickup_alternate_address_web_request,
        delivery_area_surcharge_intra_hawaii_r,
        delivery_area_surcharge_alaska,
        declared_value,
        additional_handling_charge_dimensions,
        additional_handling_length_girth,
        _source_file
    from {{ source('raw', 'edikted_1sa122') }}
),

unioned as (
    select * from csv_sources
    union all
    select * from json_1sa112
    union all
    select * from json_1sa122
)

-- Clean string nulls then cast to proper types.
-- Numeric columns → numeric, date columns → date/timestamp, rest → varchar.
select
    -- identity
    {{ clean_str('"ID"') }}                                                          as "ID",
    {{ clean_str('source_file') }}                                                   as source_file,
    {{ clean_str('_source_file') }}                                                  as _source_file,

    -- dates
    {{ clean_date('insert_datetime', 'timestamp') }}                                 as insert_datetime,
    {{ clean_date('date') }}                                                         as date,
    {{ clean_date('invoice_date') }}                                                 as invoice_date,
    {{ clean_date('date_received_in_hub') }}                                         as date_received_in_hub,
    {{ clean_date('shopify_order_date') }}                                           as shopify_order_date,
    {{ clean_date('order_date') }}                                                   as order_date,

    -- carrier / service
    {{ clean_str('carrier') }}                                                       as carrier,
    {{ clean_str('service') }}                                                       as service,
    {{ clean_str('transportation_type') }}                                           as transportation_type,
    {{ clean_str('transportation') }}                                                as transportation,

    -- financials (numeric)
    {{ clean_num('total_charge') }}                                                  as total_charge,
    {{ clean_num('total_credit') }}                                                  as total_credit,
    {{ clean_num('carriers_fees') }}                                                 as carriers_fees,
    {{ clean_num('weight_billable') }}                                               as weight_billable,
    {{ clean_num('weight_lbs') }}                                                    as weight_lbs,
    {{ clean_num('count_parcels') }}                                                 as count_parcels,
    {{ clean_num('warehouse_invoice') }}                                             as warehouse_invoice,
    {{ clean_num('warehouse_fees') }}                                                as warehouse_fees,
    {{ clean_num('check_amount') }}                                                  as check_amount,
    {{ clean_num('shipping_subsidies') }}                                            as shipping_subsidies,
    {{ clean_num('duties_paid_by_customer') }}                                       as duties_paid_by_customer,
    {{ clean_num('declared_value') }}                                                as declared_value,
    {{ clean_num('zone') }}                                                          as zone,

    -- surcharges (numeric)
    {{ clean_num('extra_length_surcharge') }}                                        as extra_length_surcharge,
    {{ clean_num('oversize_charge') }}                                               as oversize_charge,
    {{ clean_num('out_of_delivery_area_tier_b') }}                                   as out_of_delivery_area_tier_b,
    {{ clean_num('clearance_end_use_fee') }}                                         as clearance_end_use_fee,
    {{ clean_num('customs') }}                                                       as customs,
    {{ clean_num('dimensional') }}                                                   as dimensional,
    {{ clean_num('peak') }}                                                          as peak,
    {{ clean_num('das') }}                                                           as das,
    {{ clean_num('fuel') }}                                                          as fuel,
    {{ clean_num('additional_tax_administration_duty_kor') }}                        as additional_tax_administration_duty_kor,
    {{ clean_num('addl_handling_weight') }}                                          as addl_handling_weight,
    {{ clean_num('additional_weight_charge_ground_shipmen') }}                       as additional_weight_charge_ground_shipmen,
    {{ clean_num('hst_harmonized_sales_tax_duty') }}                                 as hst_harmonized_sales_tax_duty,
    {{ clean_num('additional_handling_charge_weight') }}                             as additional_handling_charge_weight,
    {{ clean_num('british_columbia_pst') }}                                          as british_columbia_pst,
    {{ clean_num('not_previously_billed_remote_area_surcharge') }}                   as not_previously_billed_remote_area_surcharge,
    {{ clean_num('delivery_area_surcharge_intra_hawaii_r') }}                        as delivery_area_surcharge_intra_hawaii_r,
    {{ clean_num('delivery_area_surcharge_alaska') }}                                as delivery_area_surcharge_alaska,
    {{ clean_num('additional_handling_charge_dimensions') }}                         as additional_handling_charge_dimensions,

    -- invoice references (numeric IDs)
    {{ clean_num('invoice_num') }}                                                   as invoice_num,
    {{ clean_num('invoice_number') }}                                                as invoice_number,

    -- order
    {{ clean_str('order_id') }}                                                      as order_id,
    {{ clean_str('order_name') }}                                                    as order_name,
    {{ clean_str('order_type') }}                                                    as order_type,
    {{ clean_str('otype') }}                                                         as otype,
    {{ clean_str('ordernum_ponum') }}                                                as ordernum_ponum,
    {{ clean_str('po_num') }}                                                        as po_num,
    {{ clean_str('ge_ordernum') }}                                                   as ge_ordernum,
    {{ clean_str('shopify_order_type') }}                                            as shopify_order_type,
    {{ clean_str('join_order_id') }}                                                 as join_order_id,
    {{ clean_str('join_order_name') }}                                               as join_order_name,
    {{ clean_str('is_replacement_order') }}                                          as is_replacement_order,

    -- tracking
    {{ clean_str('tracking_number') }}                                               as tracking_number,
    {{ clean_str('trackingnum') }}                                                   as trackingnum,
    {{ clean_str('reference_1') }}                                                   as reference_1,
    {{ clean_str('reference_2') }}                                                   as reference_2,
    {{ clean_str('pick_ticket') }}                                                   as pick_ticket,
    {{ clean_str('parcel_codes') }}                                                  as parcel_codes,
    {{ clean_str('package_dimensions') }}                                            as package_dimensions,
    {{ clean_str('non_standard_length') }}                                           as non_standard_length,
    {{ clean_str('invalid_accountnum') }}                                            as invalid_accountnum,

    -- receiver
    {{ clean_str('receiver_name') }}                                                 as receiver_name,
    {{ clean_str('receiver_company_name') }}                                         as receiver_company_name,
    {{ clean_str('receiver_address1') }}                                             as receiver_address1,
    {{ clean_str('receiver_address_1') }}                                            as receiver_address_1,
    {{ clean_str('receiver_address_2') }}                                            as receiver_address_2,
    {{ clean_str('receiver_city') }}                                                 as receiver_city,
    {{ clean_str('receiver_state') }}                                                as receiver_state,
    {{ clean_str('receiver_postal_code') }}                                          as receiver_postal_code,
    {{ clean_str('receiver_country') }}                                              as receiver_country,
    {{ clean_str('main_address') }}                                                  as main_address,

    -- sender
    {{ clean_str('sender_name') }}                                                   as sender_name,
    {{ clean_str('sender_company_name') }}                                           as sender_company_name,

    -- customer
    {{ clean_str('customer') }}                                                      as customer,
    {{ clean_str('customer_name') }}                                                 as customer_name,
    {{ clean_str('customer_num') }}                                                  as customer_num,

    -- payment
    {{ clean_str('check_num') }}                                                     as check_num,
    {{ clean_str('check_reference') }}                                               as check_reference,
    {{ clean_str('shipping_paid_by_customer') }}                                     as shipping_paid_by_customer,
    {{ clean_str('returns_print_label') }}                                           as returns_print_label,
    {{ clean_str('delivery_confirmation_signature') }}                               as delivery_confirmation_signature,

    -- misc
    {{ clean_str('received') }}                                                      as received,
    {{ clean_str('values') }}                                                        as values,
    {{ clean_str('extra') }}                                                         as extra,
    {{ clean_str('additional_handling_length_girth') }}                              as additional_handling_length_girth
from unioned
