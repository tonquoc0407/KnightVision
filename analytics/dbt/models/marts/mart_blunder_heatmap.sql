select
    cast(square as varchar) as square,
    count(*) as blunders,
    avg(cast(cp_loss as double)) as avg_cp_loss
from {{ source('lake', 'gold_blunder_positions') }}
where cast(is_blunder as boolean) = true
group by 1
