"""CLI to print backtest run statistics and equity curve.

Usage:
    python scripts/backtest_summary.py <run_id>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import get_backtest_summary, get_equity_curve
from app.config import settings
from app.db import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description="Print backtest summary")
    parser.add_argument("run_id", type=int, help="Backtest run ID")
    args = parser.parse_args()

    conn = get_connection(settings.db_path)

    run_row = conn.execute(
        "SELECT * FROM backtest_runs WHERE id = ?", (args.run_id,)
    ).fetchone()
    if run_row is None:
        print(f"No backtest run found with id={args.run_id}", file=sys.stderr)
        sys.exit(1)

    summary = get_backtest_summary(conn, args.run_id)
    curve = get_equity_curve(conn, args.run_id)

    params = json.loads(run_row["strategy_params"])

    print(f"\n{'=' * 50}")
    print(f"  Backtest Run: {run_row['name']} (id={args.run_id})")
    print(f"{'=' * 50}")
    print(f"  Period:     {run_row['date_range_start']} to {run_row['date_range_end']}")
    print(f"  Frequency:  {run_row['scan_frequency']}")
    print(f"  Started:    {run_row['started_at']}")
    print(f"  Completed:  {run_row['completed_at'] or 'IN PROGRESS'}")
    print()
    print(f"  Total scans:    {summary['total_scans']}")
    print(f"  Total trades:   {summary['total_trades']}")
    print(f"  Resolved:       {summary['total_resolved']}")

    if summary["win_rate"] is not None:
        print(f"  Win rate:       {summary['win_rate']:.1f}%")
        print(f"  Avg P&L:        {summary['avg_pnl_pct']:.2f}%")
        print()
        best = summary["best_trade"]
        worst = summary["worst_trade"]
        print(f"  Best trade:     {best['symbol']} {best['snapshot_date']} → {best['pnl_pct']:+.2f}%")
        print(f"  Worst trade:    {worst['symbol']} {worst['snapshot_date']} → {worst['pnl_pct']:+.2f}%")
    else:
        print("  (no resolved trades yet)")

    if curve:
        print(f"\n  {'Equity Curve':^30}")
        print(f"  {'—' * 30}")
        for point in curve:
            bar_len = int(abs(point["cumulative_pnl"]) * 5)
            bar_char = "+" if point["cumulative_pnl"] >= 0 else "-"
            bar = bar_char * min(bar_len, 20)
            print(f"  {point['date']}  {point['cumulative_pnl']:+7.2f}%  {bar}")

    print()
    print(f"  Strategy params: {json.dumps(params, indent=2)}")
    print()


if __name__ == "__main__":
    main()
