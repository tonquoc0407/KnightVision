select
    eco_code,
    opening_family,
    elo_bucket,
    time_control_type,
    year,
    sum(games_count) as games_count,
    round(avg(white_win_rate), 4) as white_win_rate,
    round(avg(black_win_rate), 4) as black_win_rate,
    round(avg(draw_rate), 4) as draw_rate,
    round(avg(avg_game_length), 1) as avg_game_length,
    any_value(most_common_response) as most_common_response
from analytics.opening_stats
where (? is null or eco_code = ?)
  and (? is null or lower(opening_family) like '%' || lower(?) || '%')
  and (? is null or year = ?)
group by 1, 2, 3, 4, 5
order by games_count desc, eco_code
limit ?;
