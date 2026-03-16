"""
Top-level entry point — starts both API and UI in parallel.

Usage:
    uv run python main.py

Or use the individual scripts:
    bash scripts/run_api.sh   # API only  (http://localhost:8000)
    bash scripts/run_ui.sh    # UI only   (http://localhost:8501)
    bash scripts/run_all.sh   # both
"""

import subprocess
import signal
import sys


def main() -> None:
    api = subprocess.Popen(
        ["uv", "run", "uvicorn", "api.main:app", "--reload",
         "--host", "0.0.0.0", "--port", "8000"]
    )
    ui = subprocess.Popen(
        ["uv", "run", "streamlit", "run", "ui/main.py",
         "--server.port=8501", "--server.address=0.0.0.0"]
    )

    def _stop(*_):
        api.terminate()
        ui.terminate()
        api.wait()
        ui.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("API:  http://localhost:8000")
    print("UI:   http://localhost:8501")
    print("Docs: http://localhost:8000/docs")
    print("Press Ctrl+C to stop.")

    api.wait()
    ui.wait()


if __name__ == "__main__":
    main()
