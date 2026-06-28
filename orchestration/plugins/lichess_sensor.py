from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from airflow.sensors.base import BaseSensorOperator
from airflow.utils.context import Context


@dataclass(frozen=True)
class LichessDumpLocation:
    month: str
    variant: str = "rated"

    @property
    def url(self) -> str:
        filename = f"lichess_db_standard_{self.variant}_{self.month}.pgn.zst"
        return f"https://database.lichess.org/standard/{filename}"

class LichessDumpSensor(BaseSensorOperator):
    """Wait until the expected monthly Lichess dump is reachable."""

    template_fields = ("month", "variant")

    def __init__(self, *, month: str, variant: str = "rated", **kwargs) -> None:
        super().__init__(**kwargs)
        self.month = month
        self.variant = variant

    def poke(self, context: Context) -> bool:
        location = LichessDumpLocation(month=self.month, variant=self.variant)
        request = Request(location.url, method="HEAD", headers={"User-Agent": "KnightVision-Airflow/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                available = 200 <= response.status < 400
                if available:
                    self.log.info("Found Lichess dump: %s", location.url)
                return available
        except HTTPError as exc:
            if exc.code == 404:
                self.log.info("Lichess dump not available yet: %s", location.url)
                return False
            raise
        except URLError as exc:
            self.log.warning("Could not check Lichess dump %s: %s", location.url, exc)
            return False