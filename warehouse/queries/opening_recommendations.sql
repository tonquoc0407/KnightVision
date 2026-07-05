select
    eco_code,
    opening_family,
    elo_bucket,
    time_control_type,
    games_count,
    white_win_rate,
    black_win_rate,
    draw_rate,
    avg_game_length,
    most_common_response
from analytics.opening_stats
where (? is null or elo_bucket = ?)
  and (? is null or time_control_type = ?)
  and games_count >= 5
order by
    case when ? = 'draw' then draw_rate else white_win_rate end desc,
    games_count desc
limit ?;
