select distinct
    md5(coalesce(time_control_type, '') || '|' || coalesce(base_time_seconds::varchar, '') || '|' || coalesce(increment_seconds::varchar, '')) as time_control_key,
    time_control_type,
    base_time_seconds,
    increment_seconds
from {{ ref('stg_games') }}
where time_control_type is not null
