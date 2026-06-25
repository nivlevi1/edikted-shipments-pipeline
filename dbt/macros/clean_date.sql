{% macro clean_date(col, cast_type='date') %}
    CASE WHEN TRIM({{ col }}) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
         THEN TRIM({{ col }})::{{ cast_type }}
    END
{% endmacro %}
