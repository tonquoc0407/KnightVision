select
    md5(player) as player_key,
    player,
    first_seen_date,
    last_seen_date,
    games_seen,
    avg_elo
from {{ ref('stg_players') }}
