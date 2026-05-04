select *
from {{ ref('stg_games') }}
where game_id is null
