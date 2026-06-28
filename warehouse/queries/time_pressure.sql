select
    time_remaining_bucket,
    game_phase,
    time_control_type,
    sum(games_count) as games_count,
    sum(evaluated_positions) as evaluated_positions,
    sum(blunder_count) as blunder_count,
    round(
        sum(coalesce(avg_cp_loss, 0) * coalesce(evaluated_positions, 0))
        / nullif(sum(coalesce(evaluated_positions, 0)), 0),
        1
    ) as avg_cp_loss,
    round(
        sum(coalesce(blunder_count, 0))::double
        / nullif(sum(coalesce(evaluated_positions, 0)), 0),
        4
    ) as blunder_rate
from analytics.time_pressure
where (? is null or year = ?)
group by 1, 2, 3
order by time_control_type, game_phase, time_remaining_bucket;
