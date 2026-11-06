"""Rebuild the entire project from scratch, step by step.

    python src/run_all.py

1. download raw data      2. SQL model + analysis outputs   3. chart PNGs
4. executed notebook      5. HTML dashboard                 6. slide deck
7. Power BI project (PBIP)
"""
from pathlib import Path
import subprocess
import sys

SRC = Path(__file__).resolve().parent
STEPS = [
    "download_data.py",
    "run_sql.py",
    "charts.py",
    "build_notebook.py",   # re-runs run_sql + charts inside the notebook too
    "build_dashboard.py",
    "build_deck.py",
    "build_powerbi.py",
]


def main() -> None:
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        subprocess.run([sys.executable, str(SRC / step)], check=True)
    print("\nAll outputs rebuilt.")


if __name__ == "__main__":
    main()
