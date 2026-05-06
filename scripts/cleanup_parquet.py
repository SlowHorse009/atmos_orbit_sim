"""Cleanup script: keep only the last N parquet files in output/.
Usage:
    python scripts/cleanup_parquet.py --n 3
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.simulation_service import _keep_last_n_parquet, KEEP_LAST_N

parser = argparse.ArgumentParser(description="Keep last N parquet files in output/")
parser.add_argument("--n", type=int, default=KEEP_LAST_N, help="Number of latest parquet files to keep")
args = parser.parse_args()

deleted = _keep_last_n_parquet(n=args.n)
print("deleted:", deleted)
