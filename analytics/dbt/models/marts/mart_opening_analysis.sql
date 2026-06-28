select
    cast(eco_code as varchar) as eco_code,
    cast(opening_family as varchar) as opening_family,
    cast(elo_bucket as varchar) as elo_bucket,
    cast(time_control_type as varchar) as time_control_type,
    cast(year as integer) as year,
    cast(games_count as integer) as games_count,
    cast(white_win_rate as double) as white_win_rate,
    cast(black_win_rate as double) as black_win_rate,
    cast(draw_rate as double) as draw_rate,
    cast(avg_game_length as double) as avg_game_length,
    cast(most_common_response as varchar) as most_common_response
from {{ source('lake', 'gold_opening_performance') }}
where eco_code is not null
