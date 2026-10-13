"""FairShare expense splitter (see SPEC.md). Standard library only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "SplitError",
    "Expense",
    "MODES",
    "split_equal",
    "split_shares",
    "split_percent",
    "split_exact",
    "parse_expenses",
    "compute_balances",
    "settle_up",
]

MODES = ("equal", "shares", "percent", "exact")

_AMOUNT_RE = re.compile(r"[0-9]+(\.[0-9]{1,2})?")
_INT_RE = re.compile(r"[0-9]+")


class SplitError(ValueError):
    """Raised for every invalid input to a public function."""


@dataclass(frozen=True)
class Expense:
    payer: str
    amount: Decimal
    mode: str
    split: dict


# ---------------------------------------------------------------- helpers


def _to_paise(value, what="amount"):
    """Validate the money rule (1.6) and return the value in integer paise."""
    if not isinstance(value, Decimal):
        raise SplitError(f"{what} must be a Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise SplitError(f"{what} must be finite")
    num, den = value.as_integer_ratio()
    scaled = num * 100
    if scaled % den != 0:
        raise SplitError(f"{what} has more than 2 decimal places")
    return scaled // den


def _positive_paise(value, what="amount"):
    p = _to_paise(value, what)
    if p <= 0:
        raise SplitError(f"{what} must be positive")
    return p


def _from_paise(paise):
    """Integer paise -> Decimal with exponent -2, never negative zero."""
    return Decimal(f"{int(paise)}E-2")


def _name(name):
    if not isinstance(name, str):
        raise SplitError(f"name must be a str, got {type(name).__name__}")
    stripped = name.strip()
    if not stripped:
        raise SplitError("name must not be empty")
    return stripped


def _names(names):
    out = []
    seen = set()
    for n in names:
        s = _name(n)
        if s in seen:
            raise SplitError(f"duplicate name {s!r}")
        seen.add(s)
        out.append(s)
    return out


def _check_dict(d, what):
    if not isinstance(d, dict):
        raise SplitError(f"{what} must be a dict")
    if not d:
        raise SplitError(f"{what} must not be empty")


def _result(paise_by_name):
    return {k: _from_paise(paise_by_name[k]) for k in sorted(paise_by_name)}


def _largest_remainder(total, weights):
    """weights: dict name -> positive int. Returns dict name -> paise."""
    W = sum(weights.values())
    base = {}
    rem = {}
    for n, w in weights.items():
        base[n], rem[n] = divmod(total * w, W)
    leftover = total - sum(base.values())
    order = sorted(weights, key=lambda n: (-rem[n], n))
    for n in order[:leftover]:
        base[n] += 1
    return base


# ---------------------------------------------------------------- splits


def split_equal(amount, people):
    total = _positive_paise(amount)
    if not isinstance(people, list):
        raise SplitError("people must be a list")
    if not people:
        raise SplitError("people must not be empty")
    names = _names(people)
    n = len(names)
    q, r = divmod(total, n)
    shares = {}
    for i, name in enumerate(sorted(names)):
        shares[name] = q + (1 if i < r else 0)
    return _result(shares)


def _weights_from_shares(shares):
    _check_dict(shares, "shares")
    names = _names(list(shares.keys()))
    weights = {}
    for key, name in zip(shares.keys(), names):
        w = shares[key]
        if not isinstance(w, int) or isinstance(w, bool):
            raise SplitError(f"weight for {name!r} must be an int")
        if w < 1:
            raise SplitError(f"weight for {name!r} must be >= 1")
        weights[name] = w
    return weights


def split_shares(amount, shares):
    total = _positive_paise(amount)
    weights = _weights_from_shares(shares)
    return _result(_largest_remainder(total, weights))


def split_percent(amount, percents):
    total = _positive_paise(amount)
    _check_dict(percents, "percents")
    names = _names(list(percents.keys()))
    weights = {}
    for key, name in zip(percents.keys(), names):
        weights[name] = _positive_paise(percents[key], f"percent for {name!r}")
    if sum(weights.values()) != 10000:
        raise SplitError("percentages must sum to exactly 100")
    return _result(_largest_remainder(total, weights))


def split_exact(amount, parts):
    total = _positive_paise(amount)
    _check_dict(parts, "parts")
    names = _names(list(parts.keys()))
    out = {}
    for key, name in zip(parts.keys(), names):
        out[name] = _positive_paise(parts[key], f"part for {name!r}")
    if sum(out.values()) != total:
        raise SplitError("exact parts must sum to the amount")
    return _result(out)


# ---------------------------------------------------------------- parsing


def _parse_row(fields):
    payer_f, amount_f, mode_f, parts_f = fields
    payer = _name(payer_f)
    if not _AMOUNT_RE.fullmatch(amount_f):
        raise SplitError(f"bad amount {amount_f!r}")
    amount = Decimal(amount_f)
    if amount <= 0:
        raise SplitError(f"amount must be positive: {amount_f!r}")
    if mode_f not in MODES:
        raise SplitError(f"unknown mode {mode_f!r}")
    entries = [e.strip() for e in parts_f.split(";")]
    for e in entries:
        if not e:
            raise SplitError("empty participant entry")
    if mode_f == "equal":
        names = []
        for e in entries:
            if ":" in e:
                raise SplitError(f"unexpected ':' in equal participant {e!r}")
            names.append(e)
        split = split_equal(amount, names)
    else:
        mapping = {}
        for e in entries:
            if e.count(":") != 1:
                raise SplitError(f"participant entry must be NAME:VALUE: {e!r}")
            raw_name, raw_val = e.split(":")
            name = _name(raw_name)
            val = raw_val.strip()
            if name in mapping:
                raise SplitError(f"duplicate name {name!r}")
            if mode_f == "shares":
                if not _INT_RE.fullmatch(val):
                    raise SplitError(f"bad share value {val!r}")
                mapping[name] = int(val)
            else:
                if not _AMOUNT_RE.fullmatch(val):
                    raise SplitError(f"bad value {val!r}")
                mapping[name] = Decimal(val)
        if mode_f == "shares":
            split = split_shares(amount, mapping)
        elif mode_f == "percent":
            split = split_percent(amount, mapping)
        else:
            split = split_exact(amount, mapping)
    return Expense(payer, _from_paise(_to_paise(amount)), mode_f, split)


def _fields(line):
    if '"' in line:
        raise SplitError("quote character not allowed")
    fields = line.split(",")
    if len(fields) != 4:
        raise SplitError(f"expected 4 fields, got {len(fields)}")
    return [f.strip() for f in fields]


def parse_expenses(csv_text):
    if not isinstance(csv_text, str):
        raise SplitError("csv_text must be a str")
    lines = csv_text.split("\n")
    result = []
    header_seen = False
    for idx, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip():
            continue
        try:
            fields = _fields(line)
            if not header_seen:
                if fields != ["payer", "amount", "mode", "participants"]:
                    raise SplitError("bad header")
                header_seen = True
                continue
            result.append(_parse_row(fields))
        except SplitError as exc:
            raise SplitError(f"line {idx}: {exc}") from None
    if not header_seen:
        raise SplitError("line 1: missing header")
    return result


# ---------------------------------------------------------------- balances


def compute_balances(expenses):
    if not isinstance(expenses, list):
        raise SplitError("expenses must be a list")
    bal = {}
    for exp in expenses:
        if not isinstance(exp, Expense):
            raise SplitError("each element must be an Expense")
        payer = exp.payer
        if not isinstance(payer, str) or not payer:
            raise SplitError("payer must be a non-empty str")
        amount = _positive_paise(exp.amount)
        split = exp.split
        if not isinstance(split, dict) or not split:
            raise SplitError("split must be a non-empty dict")
        parts = {}
        for k, v in split.items():
            if not isinstance(k, str) or not k:
                raise SplitError("split keys must be non-empty str")
            p = _to_paise(v, f"split value for {k!r}")
            if p < 0:
                raise SplitError("split values must be >= 0")
            parts[k] = p
        if sum(parts.values()) != amount:
            raise SplitError("split values must sum to the amount")
        bal[payer] = bal.get(payer, 0) + amount
        for k, p in parts.items():
            bal[k] = bal.get(k, 0) - p
    return _result(bal)


def settle_up(balances):
    if not isinstance(balances, dict):
        raise SplitError("balances must be a dict")
    names = _names(list(balances.keys()))
    bal = {}
    for key, name in zip(balances.keys(), names):
        bal[name] = _to_paise(balances[key], f"balance for {name!r}")
    if sum(bal.values()) != 0:
        raise SplitError("balances must sum to zero")
    transfers = []
    while True:
        debtors = [n for n in bal if bal[n] < 0]
        if not debtors:
            break
        debtor = min(debtors, key=lambda n: (bal[n], n))
        creditors = [n for n in bal if bal[n] > 0]
        creditor = min(creditors, key=lambda n: (-bal[n], n))
        t = min(-bal[debtor], bal[creditor])
        transfers.append((debtor, creditor, _from_paise(t)))
        bal[debtor] += t
        bal[creditor] -= t
    return transfers
