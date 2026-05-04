select
    eco_code,
    opening_family,
    opening_variation,
    count(*) as games_seen,
    avg(game_length) as avg_game_length
from {{ ref('stg_games') }}
where eco_code is not null
group by 1, 2, 3
