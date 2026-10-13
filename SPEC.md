# FairShare — `splitter.py` Specification

This document is the complete, self-contained specification of the Python
module `splitter.py`. Every behaviour you must implement is stated in a
numbered clause. Where a clause says "raise `SplitError`", no other exception
type is acceptable.

---

## 1. General

**1.1 Module.** The module is a single file named `splitter.py`. It must use
the Python standard library only and must run on Python 3.12. Importing it
must have no side effects (no printing, no file or network access).

**1.2 Public names.** The module must define, at top level, exactly these
public names (it may define additional private helpers whose names start with
`_`, and may define other public names, but these must exist with these
exact names and signatures):

| Name | Kind |
|---|---|
| `SplitError` | exception class |
| `Expense` | frozen dataclass |
| `MODES` | the tuple `("equal", "shares", "percent", "exact")` |
| `split_equal(amount, people)` | function |
| `split_shares(amount, shares)` | function |
| `split_percent(amount, percents)` | function |
| `split_exact(amount, parts)` | function |
| `parse_expenses(csv_text)` | function |
| `compute_balances(expenses)` | function |
| `settle_up(balances)` | function |

All function parameters are positional-or-keyword and have exactly the names
shown above.

**1.3 `SplitError`.** `class SplitError(ValueError)`. It is the *only*
exception type raised by any public function for invalid input. Every
validation failure described in this document raises `SplitError` (never
`TypeError`, `KeyError`, `decimal.InvalidOperation`, `ZeroDivisionError`,
etc.). The message text is free-form, except for the `parse_expenses`
line-number prefix defined in 6.10.

**1.4 Money representation.** One rupee = 100 paise. Internally all
computation should be done in integer paise so that no rounding error can
occur. Money values crossing the public API are `decimal.Decimal` rupee
values.

**1.5 Returned money values.** Every money value *returned* by any public
function (dict values, tuple amounts, `Expense.amount`, `Expense.split`
values) is a `decimal.Decimal` with exactly two decimal places, i.e.
`value.as_tuple().exponent == -2` (for example `Decimal("5.00")`,
`Decimal("0.00")`, `Decimal("-3.10")`). Every returned zero is unsigned:
it is `Decimal("0.00")`, never `Decimal("-0.00")`, i.e.
`value.is_signed()` is `False` for every returned zero value.

**1.6 Accepted money values (the "money rule").** Wherever this document says
a value must satisfy the *money rule*, the value must be:

* (a) an instance of `decimal.Decimal` — `int`, `float`, `str`, `bool` and
  every other type raise `SplitError`;
* (b) finite — `Decimal("NaN")`, `Decimal("sNaN")`, `Decimal("Infinity")`,
  `Decimal("-Infinity")` raise `SplitError`;
* (c) a whole number of paise — the *value* times 100 must be an integer.
  The check is on the numeric value, not the written form:
  `Decimal("10.5")`, `Decimal("10.50")`, `Decimal("10.500")`, `Decimal("1E+1")`
  are all accepted; `Decimal("10.505")` and `Decimal("0.001")` raise
  `SplitError` ("more than 2 decimal places").

A *positive money value* additionally must be strictly greater than zero;
`Decimal("0")`, `Decimal("0.00")`, `Decimal("-0")` and negatives raise
`SplitError`.

**1.7 Names.** Wherever a person's name is accepted:

* (a) it must be a `str`, otherwise `SplitError`;
* (b) leading and trailing whitespace is removed with `str.strip()`; the
  stripped form is the person's name from then on (it is the form used in
  every output);
* (c) a name that is empty after stripping raises `SplitError`;
* (d) names are case-sensitive: `"asha"` and `"Asha"` are different people;
* (e) within one collection of names (one `people` list, the keys of one
  `shares`/`percents`/`parts`/`balances` dict, or the participants of one CSV
  row), two names that are equal *after stripping* raise `SplitError`
  ("duplicate name"). Example: `["Asha", " Asha"]` is rejected.

Exception: `compute_balances` uses the names stored in `Expense` objects
exactly as stored (see 7.2).

**1.8 Ordering ("alphabetical").** "Alphabetical order" and "sorted by name"
always mean Python's default `str` ordering, i.e. `sorted(names)`
(Unicode code point order; therefore `"B" < "a"` and `"Z" < "b"`).

**1.9 Returned dicts.** Every dict returned by a public function has its keys
in alphabetical order (1.8) — i.e. `list(result) == sorted(result)` — and
contains exactly the keys stated for that function.

**1.10 Purity.** No public function mutates its arguments.

**1.11 Validation order.** When an input has several problems, any one
`SplitError` may be raised; tests only check that `SplitError` is raised
(and, for `parse_expenses`, the line-number prefix of 6.10).

---

## 2. `split_equal(amount, people) -> dict[str, Decimal]`

**2.1 Arguments.** `amount` must be a positive money value (1.6). `people`
must be a `list` (a `tuple`, `set`, `str`, `dict` or anything else raises
`SplitError`). Its elements are names (1.7).

**2.2 Validation.** An empty list raises `SplitError`. Each element is
validated and stripped per 1.7; non-`str`, empty-after-strip and duplicate
(after strip) names raise `SplitError`.

**2.3 Algorithm.** Let `P` be the amount in paise and `n = len(people)`.
Everybody receives `P // n` paise. The remaining `r = P % n` paise are given,
one paisa each, to the first `r` people in alphabetical order (1.8).

**2.4 Result.** A dict mapping every (stripped) person to their share
(1.5), keys in alphabetical order. People whose share is zero are included
with `Decimal("0.00")`. The values always sum exactly to `amount`.

**2.5 Examples.**

```python
split_equal(Decimal("100"), ["Chen", "Asha", "Bala"])
# {"Asha": Decimal("33.34"), "Bala": Decimal("33.33"), "Chen": Decimal("33.33")}

split_equal(Decimal("0.02"), ["b", "a", "c"])
# {"a": Decimal("0.01"), "b": Decimal("0.01"), "c": Decimal("0.00")}

split_equal(Decimal("10"), [" Asha "])      # {"Asha": Decimal("10.00")}
split_equal(Decimal("10"), ["Asha", "Asha "])  # SplitError (duplicate)
split_equal(10, ["Asha"])                    # SplitError (not a Decimal)
```

---

## 3. `split_shares(amount, shares) -> dict[str, Decimal]`

**3.1 Arguments.** `amount` must be a positive money value (1.6). `shares`
must be a non-empty `dict` (otherwise `SplitError`) mapping names (1.7) to
integer weights.

**3.2 Weights.** Each weight must be an `int` that is not a `bool`
(`True`/`False`, `float`, `Decimal`, `str` raise `SplitError`) and must be
`>= 1` (zero and negative weights raise `SplitError`).

**3.3 Algorithm (largest remainder).** Let `P` be the amount in paise, `w_i`
the weights and `W = sum(w_i)`.

1. Each person gets `base_i = (P * w_i) // W` paise.
2. Each person's *remainder* is `rem_i = (P * w_i) % W`.
3. The leftover `L = P - sum(base_i)` paise (always `0 <= L < number of
   people`) are given one paisa each to the `L` people ranked first when
   people are sorted by `rem_i` **descending**, ties broken by name
   **alphabetically ascending** (1.8).

**3.4 Result.** Same form as 2.4: every person, alphabetical keys, values sum
exactly to `amount`.

**3.5 Examples.**

```python
split_shares(Decimal("10"), {"A": 1, "B": 2})
# P=1000, W=3: base A=333 rem 1, B=666 rem 2, L=1 -> B
# {"A": Decimal("3.33"), "B": Decimal("6.67")}

split_shares(Decimal("90.50"), {"Asha": 1, "Bala": 2})
# P=9050: Asha 3016 rem 2, Bala 6033 rem 1, L=1 -> Asha
# {"Asha": Decimal("30.17"), "Bala": Decimal("60.33")}

split_shares(Decimal("1.00"), {"C": 1, "B": 1, "A": 1})
# all rems equal (1), L=1 -> alphabetical -> A
# {"A": Decimal("0.34"), "B": Decimal("0.33"), "C": Decimal("0.33")}

split_shares(Decimal("10"), {"A": 0, "B": 1})    # SplitError
split_shares(Decimal("10"), {"A": True})         # SplitError
```

---

## 4. `split_percent(amount, percents) -> dict[str, Decimal]`

**4.1 Arguments.** `amount` must be a positive money value (1.6). `percents`
must be a non-empty `dict` (otherwise `SplitError`) mapping names (1.7) to
percentages.

**4.2 Percent values.** Each percentage must be a `Decimal` that is strictly
positive and has at most two decimal places — i.e. exactly the *positive
money value* rule of 1.6 applied to the percentage. So `int`/`float`/`str`
values, zero, negatives, NaN/Infinity and `Decimal("33.333")` raise
`SplitError`.

**4.3 Sum.** The percentages must sum to exactly `100`
(`Decimal("33.33") + Decimal("33.33") + Decimal("33.34")` is fine;
`33.33 * 3 = 99.99` raises `SplitError`; so does any sum above 100).

**4.4 Algorithm.** Exactly the largest-remainder algorithm of 3.3, using as
the integer weight of each person their percentage multiplied by 100 (so the
weights are hundredths of a percent and `W = 10000`).

**4.5 Result.** Same form as 2.4.

**4.6 Examples.**

```python
split_percent(Decimal("10"), {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.34")})
# weights 3333, 3333, 3334; P=1000:
# A 333 rem 3300, B 333 rem 3300, C 333 rem 4000, L=1 -> C
# {"A": Decimal("3.33"), "B": Decimal("3.33"), "C": Decimal("3.34")}

split_percent(Decimal("0.01"), {"A": Decimal("50"), "B": Decimal("50")})
# {"A": Decimal("0.01"), "B": Decimal("0.00")}

split_percent(Decimal("10"), {"A": Decimal("60"), "B": Decimal("50")})   # SplitError
split_percent(Decimal("10"), {"A": Decimal("100"), "B": Decimal("0")})   # SplitError
```

---

## 5. `split_exact(amount, parts) -> dict[str, Decimal]`

**5.1 Arguments.** `amount` must be a positive money value (1.6). `parts`
must be a non-empty `dict` (otherwise `SplitError`) mapping names (1.7) to
money amounts.

**5.2 Part values.** Each part must be a *positive* money value (1.6): zero,
negative, non-`Decimal`, non-finite and sub-paisa values raise `SplitError`.

**5.3 Sum.** The parts must sum exactly to `amount` (compared as values, e.g.
`Decimal("10")` equals `Decimal("10.00")`); otherwise `SplitError`.

**5.4 Result.** A dict with every (stripped) name mapped to its part,
quantized per 1.5, keys alphabetical.

**5.5 Examples.**

```python
split_exact(Decimal("10"), {"B": Decimal("6.5"), "A": Decimal("3.5")})
# {"A": Decimal("3.50"), "B": Decimal("6.50")}
split_exact(Decimal("10"), {"A": Decimal("3"), "B": Decimal("6.99")})   # SplitError
split_exact(Decimal("10"), {"A": Decimal("10"), "B": Decimal("0")})     # SplitError
```

---

## 6. `parse_expenses(csv_text) -> list[Expense]`

**6.1 `Expense`.** A dataclass declared with `@dataclass(frozen=True)` and
exactly these four fields, in this order:

| Field | Type | Meaning |
|---|---|---|
| `payer` | `str` | the stripped name of the person who paid |
| `amount` | `Decimal` | the amount paid, quantized per 1.5 |
| `mode` | `str` | one of `MODES` |
| `split` | `dict[str, Decimal]` | **the computed split**: the dict returned by the split function for this mode (rupee amounts per person, keys alphabetical) — *not* the raw weights |

It is constructed positionally or by keyword:
`Expense(payer, amount, mode, split)`. Equality is the default dataclass
field-wise equality. The dataclass performs no validation of its own
(no `__post_init__` checks); `compute_balances` validates (7.2).

**6.2 Argument.** `csv_text` must be a `str`, otherwise `SplitError`.

**6.3 Lines and line numbers.** The text is split into lines with
`csv_text.split("\n")`. If a line ends with `"\r"`, that single `"\r"` is
removed (so `"\r\n"` line endings work). Only `"\n"` separates lines: a
`"\r"` anywhere else, `"\x0b"`, `"\x0c"`, `"\u2028"` etc. are ordinary
characters inside a line, so `str.splitlines()` is **not** a correct way to
split the text. Line numbers are 1-based indexes
into this list. Blank lines (lines that are empty or contain only whitespace)
are skipped but still count for numbering. A trailing newline at the end of
the text therefore just produces a final blank line, which is skipped.

**6.4 Fields.** A non-blank line is split on every `","` and must produce
exactly 4 fields; each field is stripped with `str.strip()`. Any other field
count is a malformed line. There is **no quoting**: a line that contains a
double-quote character `"` anywhere is malformed. These rules apply to
every non-blank line regardless of its position, **including the header
line**: a header line with the wrong number of fields or containing `"` is a
malformed header and the error refers to its line number (e.g. a text whose
first non-blank line, on line 3, is `payer,amount,mode` raises
`"line 3: ..."`).

**6.5 Header.** The first non-blank line must be the header: its four
stripped fields must be exactly `payer`, `amount`, `mode`, `participants`
in that order (case-sensitive; e.g. `payer, amount ,mode,participants` is
accepted, `Payer,amount,mode,participants` is not). If it is not, the error
refers to that line's number. If the text contains no non-blank line at all
(e.g. `""` or `"\n  \n"`), raise `SplitError` with the prefix `"line 1: "`.
A header followed by no data rows returns `[]`. Any later line that looks like
the header is just a data row (and will normally be malformed, since
`amount` is not a valid amount).

**6.6 Data row fields.** Each subsequent non-blank line is one expense:

* `payer` — a name (1.7); empty → malformed.
* `amount` — must fully match the regular expression `[0-9]+(\.[0-9]{1,2})?`
  (ASCII digits only; no sign, no exponent, no thousands separators; `"10"`,
  `"10.5"`, `"10.50"`, `"0.75"` match; `"10."`, `".5"`, `"10.505"`, `"-5"`,
  `"1e3"`, `"₹10"` do not). It is converted with `Decimal(text)`. It must be
  positive: `"0"` / `"0.00"` are malformed.
* `mode` — exactly one of `equal`, `shares`, `percent`, `exact`
  (case-sensitive); anything else is malformed ("unknown mode").
* `participants` — see 6.7.

**6.7 Participants field.** The field is split on every `";"` and each entry
is stripped. Empty entries (from an empty field, `"A;;B"`, or a trailing
`";"`) are malformed (they are empty names).

* `equal` mode: each entry is a bare name. An entry containing `":"` is
  malformed. Example: `Asha;Bala;Chen`.
* `shares`, `percent`, `exact` modes: each entry must have the form
  `NAME:VALUE` with exactly one `":"`. `NAME` and `VALUE` are each stripped.
  `NAME` must be a valid name (1.7). An entry without `":"` or with more than
  one `":"` is malformed.
  * `shares`: `VALUE` must fully match `[0-9]+` and is converted with
    `int(VALUE)` (`"02"` is 2). Example: `Asha:2;Bala:1`.
  * `percent`: `VALUE` must fully match `[0-9]+(\.[0-9]{1,2})?` and is
    converted with `Decimal(VALUE)`. Example: `Asha:50;Bala:25.5;Chen:24.5`.
  * `exact`: same as `percent`. Example: `Asha:100;Bala:50.25`.
* Duplicate names within one row's participants (after stripping) are
  malformed, in every mode.

**6.8 Computing the split.** The row's split is computed by calling the
mode's split function: `split_equal(amount, names)` for `equal` (with the
list of names in the order written), `split_shares(amount, {name: int})`,
`split_percent(amount, {name: Decimal})`, `split_exact(amount, {name:
Decimal})`. Every rule of sections 2–5 therefore applies (zero shares, zero
percent, percents not summing to 100, exact parts not summing to the amount,
zero exact parts, ...); any such failure makes the row malformed.

**6.9 Payer.** The payer need not appear among the participants. The same
person may pay several expenses.

**6.10 Error messages.** Every `SplitError` raised for a malformed or missing
header or a malformed data row has a message (i.e. `str(exc)`) that **starts
with** `"line N: "` where `N` is the line number of 6.3 (e.g. `"line 3:
unknown mode 'foo'"`). Parsing stops at the first malformed line. The
non-`str` argument error of 6.2 has no required prefix.

**6.11 Result.** A list with one `Expense` per data row, in file order.

**6.12 Example.**

```text
payer,amount,mode,participants
Asha,300,equal,Asha;Bala;Chen

Bala, 90.50 ,shares,Asha:1;Bala:2
Chen,100,percent,Asha:50;Chen:50
```

parses to

```python
[
  Expense("Asha", Decimal("300.00"), "equal",
          {"Asha": Decimal("100.00"), "Bala": Decimal("100.00"), "Chen": Decimal("100.00")}),
  Expense("Bala", Decimal("90.50"), "shares",
          {"Asha": Decimal("30.17"), "Bala": Decimal("60.33")}),
  Expense("Chen", Decimal("100.00"), "percent",
          {"Asha": Decimal("50.00"), "Chen": Decimal("50.00")}),
]
```

Errors (each text starts with the header line):

```text
...\nAsha,10,foo,Bala          -> SplitError "line 2: ..."  (unknown mode)
...\n\nAsha,10.505,equal,Bala  -> SplitError "line 3: ..."  (bad amount)
...\nAsha,10,equal             -> SplitError "line 2: ..."  (3 fields)
Payer,amount,mode,participants -> SplitError "line 1: ..."  (bad header)
```

---

## 7. `compute_balances(expenses) -> dict[str, Decimal]`

**7.1 Argument.** `expenses` must be a `list` (otherwise `SplitError`); an
empty list returns `{}`.

**7.2 Validation of each element.** Each element must be an `Expense`
instance, otherwise `SplitError`. Its fields are used exactly as stored (names
are *not* stripped again) and validated as follows, each failure raising
`SplitError`:

* (a) `payer` is a non-empty `str`;
* (b) `amount` is a positive money value (1.6);
* (c) `split` is a non-empty `dict`; each key is a non-empty `str`; each value
  satisfies the money rule (1.6) and is `>= 0` (zero allowed, since
  `split_equal` can produce `0.00` shares; negative values rejected);
* (d) the `split` values sum exactly to `amount`.

`mode` is not inspected.

**7.3 Semantics.** For every expense, the payer is credited `amount` and each
person in `split` is debited their `split` value. A person's balance is
(total paid) − (total owed). **Positive = the person is owed money**;
negative = the person owes money.

**7.4 Result keys.** Every name that appears as a payer or as a `split` key
in any expense appears in the result — including people whose balance is
exactly zero (`Decimal("0.00")`). No other keys. Keys in alphabetical order
(1.8). Values per 1.5.

**7.5 Invariant.** The values always sum to exactly `0`.

**7.6 Example.** For the three expenses of 6.12:

```python
{"Asha": Decimal("119.83"), "Bala": Decimal("-69.83"), "Chen": Decimal("-50.00")}
```

and `compute_balances([Expense("A", Decimal("5.00"), "exact", {"A": Decimal("5.00")})])`
is `{"A": Decimal("0.00")}`.

---

## 8. `settle_up(balances) -> list[tuple[str, str, Decimal]]`

**8.1 Argument.** `balances` must be a `dict` (otherwise `SplitError`)
mapping names to balances. An empty dict returns `[]`. Keys are names per 1.7
(non-`str`, empty or duplicate-after-strip keys raise `SplitError`; the
stripped form is used in the output). Each value must satisfy the money rule
(1.6); values may be negative, zero or positive.

**8.2 Sum.** The balances must sum to exactly zero; otherwise `SplitError`.

**8.3 Algorithm (greedy).** Work in paise. Repeat while any balance is
negative:

1. The *debtor* is the person with the most negative balance; ties broken by
   name alphabetically (1.8), first wins.
2. The *creditor* is the person with the most positive balance; ties broken
   by name alphabetically, first wins.
3. `t = min(-debtor_balance, creditor_balance)`.
4. Emit the transfer `(debtor, creditor, t)`; add `t` to the debtor's
   balance and subtract `t` from the creditor's balance.

**8.4 Result.** The list of transfers in the order emitted. Each transfer is
a 3-tuple `(from_name, to_name, amount)` where `amount` is a positive
`Decimal` per 1.5. A person whose initial balance is zero never appears in
any transfer. Applying all transfers
(`from` += amount, `to` −= amount) brings every balance to exactly zero. All
balances zero (or `{}`) gives `[]`. The number of transfers is at most
`(number of non-zero balances) − 1`.

**8.5 Examples.**

```python
settle_up({"Asha": Decimal("119.83"), "Bala": Decimal("-69.83"), "Chen": Decimal("-50.00")})
# [("Bala", "Asha", Decimal("69.83")), ("Chen", "Asha", Decimal("50.00"))]

settle_up({"A": Decimal("10"), "B": Decimal("10"), "C": Decimal("-20")})
# creditors tie at 10 -> A first:
# [("C", "A", Decimal("10.00")), ("C", "B", Decimal("10.00"))]

settle_up({"A": Decimal("-30"), "B": Decimal("-10"), "C": Decimal("25"), "D": Decimal("15")})
# step 1: A(-30) pays C(25) 25  -> A -5, C 0
# step 2: B(-10) pays D(15) 10  -> B 0, D 5
# step 3: A(-5)  pays D(5)   5
# [("A","C",Decimal("25.00")), ("B","D",Decimal("10.00")), ("A","D",Decimal("5.00"))]

settle_up({"A": Decimal("1"), "B": Decimal("-0.99")})   # SplitError (sum != 0)
```
