select
    md5(coalesce(eco_code, '') || '|' || coalesce(opening_family, '') || '|' || coalesce(opening_variation, '')) as opening_key,
    eco_code,
    opening_family,
    opening_variation,
    games_seen,
    avg_game_length
from {{ ref('stg_openings') }}
