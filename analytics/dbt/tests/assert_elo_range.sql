select *
from {{ ref('stg_games') }}
where (white_elo is not null and (white_elo < 400 or white_elo > 3500))
   or (black_elo is not null and (black_elo < 400 or black_elo > 3500))
