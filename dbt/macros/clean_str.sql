{% macro clean_str(col) %}
    NULLIF(NULLIF(NULLIF(NULLIF(NULLIF(NULLIF(
        CASE WHEN TRIM({{ col }}) ~ '^-+$' THEN NULL ELSE {{ col }} END,
    'None'), 'NaN'), ''), 'N/A'), 'n/a'), '"None"')
{% endmacro %}
