"""Run the custom dashboard API and React frontend together."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "dashboard_web"


def main() -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    dashboard_host = env.get("DASHBOARD_HOST", "127.0.0.1")
    dashboard_port = env.get("DASHBOARD_PORT", "3636")
    api_port = env.get("API_PORT", env.get("VITE_API_PORT", "3637"))
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dashboard_api.app:app", "--host", dashboard_host, "--port", api_port],
        cwd=ROOT,
        env=env,
    )
    web = subprocess.Popen(["npm", "run", "dev", "--", "--host", dashboard_host, "--port", dashboard_port], cwd=WEB_ROOT, env=env)
    try:
        return web.wait()
    finally:
        for process in [web, api]:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        api.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
