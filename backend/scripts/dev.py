from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    commands = [
        ["uv", "run", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        ["pnpm", "--dir", "frontend", "dev", "--host", "127.0.0.1", "--port", "5173"],
    ]
    processes = [subprocess.Popen(command, cwd=ROOT) for command in commands]

    def stop(_signum: int, _frame: object) -> None:
        for process in processes:
            process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        return max(process.wait() for process in processes)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    sys.exit(main())
