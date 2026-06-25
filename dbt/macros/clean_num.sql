{% macro clean_num(col) %}
    CASE WHEN TRIM({{ col }}) ~ '^-?[0-9]+(\.[0-9]+)?$'
         THEN TRIM({{ col }})::numeric
    END
{% endmacro %}
