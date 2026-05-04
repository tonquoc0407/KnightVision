with player_games as (
    select
        white_player as player,
        game_date,
        year,
        month,
        white_elo as elo,
        case when result = 'white_win' then 1 else 0 end as win,
        case when result = 'black_win' then 1 else 0 end as loss,
        case when result = 'draw' then 1 else 0 end as draw
    from {{ ref('stg_games') }}
    union all
    select
        black_player as player,
        game_date,
        year,
        month,
        black_elo as elo,
        case when result = 'black_win' then 1 else 0 end as win,
        case when result = 'white_win' then 1 else 0 end as loss,
        case when result = 'draw' then 1 else 0 end as draw
    from {{ ref('stg_games') }}
)

select
    player,
    year,
    month,
    count(*) as games_played,
    sum(win) as wins,
    sum(loss) as losses,
    sum(draw) as draws,
    avg(win) as win_rate,
    avg(elo) as avg_elo,
    avg(elo) - lag(avg(elo)) over (partition by player order by year, month) as elo_change
from player_games
where player is not null
group by 1, 2, 3
