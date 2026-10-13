"""CLI: python -m fairshare expenses.csv  -> balances table and settlement list."""
import argparse
import sys
from decimal import Decimal

from .splitter import SplitError, compute_balances, parse_expenses, settle_up


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m fairshare", description="Split group expenses and settle up.")
    ap.add_argument("csv", help="CSV file with columns payer,amount,mode,participants")
    args = ap.parse_args(argv)
    try:
        with open(args.csv, encoding="utf-8", newline="") as f:
            text = f.read()
        expenses = parse_expenses(text)
        balances = compute_balances(expenses)
        transfers = settle_up(balances)
    except (OSError, SplitError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    total = sum((e.amount for e in expenses), Decimal("0.00"))
    print(f"{len(expenses)} expenses, total Rs {total}\n")
    width = max([len(n) for n in balances] + [6])
    print(f"{'Person':<{width}}  {'Balance':>10}")
    print("-" * (width + 12))
    for name, bal in balances.items():
        print(f"{name:<{width}}  {bal:>10}")
    print("\n(positive = is owed money)\n\nSettlement:")
    if not transfers:
        print("  nothing to settle")
    for frm, to, amt in transfers:
        print(f"  {frm} pays {to}  Rs {amt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
