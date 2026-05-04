select
    game_id,
    white_player,
    black_player,
    white_elo,
    black_elo,
    result,
    case
        when result = 'white_win' then white_player
        when result = 'black_win' then black_player
        else null
    end as winner,
    case
        when white_elo is not null and black_elo is not null
            then floor(((white_elo + black_elo) / 2) / 200) * 200
        else null
    end as elo_bucket,
    eco_code,
    opening_family,
    opening_variation,
    time_control_type,
    game_date,
    year,
    month,
    game_length,
    has_clock_data
from {{ ref('stg_games') }}
