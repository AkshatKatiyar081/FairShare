# FairShare prototype

A small group bill splitter with a command-line interface. The module `fairshare/splitter.py` is the
implementation written by the Claude Opus 5.5 contestant run `opus_r2` in the bake-off (chosen because
every run scored 100% on the hidden acceptance tests, and opus_r2 had the highest reference mutation
score). The CLI wrapper `fairshare/__main__.py` was added for the demo. Standard library only; Python 3.11+.

## Usage

```
python -m fairshare sample_expenses.csv
```

CSV columns: `payer,amount,mode,participants`, where mode is `equal|shares|percent|exact` and
participants look like `A;B` (equal) or `A:2;B:1` (other modes). Amounts are rupees with at most two
decimal places. See `SPEC.md` for the full rules.

## Tests

The hidden acceptance suite from the experiment (204 test items) is included:

```
python -m pip install pytest
python -m pytest tests -q
```
