select
    cast(time_remaining_bucket as varchar) as time_remaining_bucket,
    cast(game_phase as varchar) as game_phase,
    cast(time_control_type as varchar) as time_control_type,
    cast(year as integer) as year,
    cast(games_count as integer) as games_count,
    cast(evaluated_positions as integer) as evaluated_positions,
    cast(blunder_count as integer) as blunder_count,
    cast(avg_cp_loss as double) as avg_cp_loss,
    cast(blunder_rate as double) as blunder_rate
from {{ source('lake', 'gold_time_pressure_analysis') }}
