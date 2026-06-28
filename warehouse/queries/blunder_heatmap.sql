select
    square,
    count(*) as evaluated_positions,
    sum(case when is_blunder then 1 else 0 end) as blunders,
    round(avg(cp_loss), 1) as avg_cp_loss,
    max(cp_loss) as max_cp_loss
from analytics.blunder_positions
where cp_loss is not null
  and (? is null or year = ?)
group by 1
order by blunders desc, avg_cp_loss desc;
