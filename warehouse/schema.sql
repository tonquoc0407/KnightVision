create schema if not exists analytics;

create or replace view analytics.opening_stats as
select
    eco_code,
    opening_family,
    elo_bucket,
    time_control_type,
    year,
    games_count,
    white_win_rate,
    black_win_rate,
    draw_rate,
    avg_game_length,
    most_common_response
from gold_opening_performance;

create or replace view analytics.player_profiles as
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
from gold_player_monthly_stats;

create or replace view analytics.time_pressure as
select
    time_remaining_bucket,
    game_phase,
    time_control_type,
    year,
    games_count,
    evaluated_positions,
    blunder_count,
    avg_cp_loss,
    blunder_rate
from gold_time_pressure_analysis;

create or replace view analytics.blunder_positions as
select
    game_id,
    ply_number,
    fen,
    move_uci,
    square,
    game_phase,
    time_control_type,
    year,
    player_elo,
    time_remaining_seconds,
    material_balance,
    is_in_check,
    eval_before_cp,
    eval_after_cp,
    cp_loss,
    is_blunder
from gold_blunder_positions;
