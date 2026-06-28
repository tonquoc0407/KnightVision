select
    player,
    year,
    month,
    games_played,
    wins,
    losses,
    draws,
    win_rate,
    avg_elo,
    elo_change,
    most_played_opening_white,
    most_played_opening_black
from analytics.player_profiles
where lower(player) = lower(?)
order by year, month;