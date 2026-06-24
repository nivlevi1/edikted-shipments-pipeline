-- TODO: union all raw sources + normalize column names
select * from {{ source('raw', 'edikted_112412') }} limit 0
