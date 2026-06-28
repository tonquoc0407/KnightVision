with players as (
    select white_player as player, white_elo as elo, game_date from {{ ref('stg_games') }}
    union all
    select black_player as player, black_elo as elo, game_date from {{ ref('stg_games') }}
)

select
    player,
    min(game_date) as first_seen_date,
    max(game_date) as last_seen_date,
    count(*) as games_seen,
    avg(elo) as avg_elo
from players
where player is not null
group by 1
