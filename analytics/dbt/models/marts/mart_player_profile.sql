select
    cast(player as varchar) as player,
    cast(year as integer) as year,
    cast(month as integer) as month,
    cast(games_played as integer) as games_played,
    cast(wins as integer) as wins,
    cast(losses as integer) as losses,
    cast(draws as integer) as draws,
    cast(win_rate as double) as win_rate,
    cast(avg_elo as double) as avg_elo,
    cast(elo_change as double) as elo_change,
    cast(most_played_opening_white as varchar) as most_played_opening_white,
    cast(most_played_opening_black as varchar) as most_played_opening_black
from {{ source('lake', 'gold_player_monthly_stats') }}
where player is not null
