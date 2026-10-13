"""Hidden acceptance tests for splitter.py (FairShare).

Every test names the SPEC.md clause it checks in a ``# SPEC x.y`` comment.
The module under test is imported from PYTHONPATH.
"""
import dataclasses
import random
from decimal import Decimal as D

import pytest

import splitter
from splitter import (
    Expense,
    SplitError,
    compute_balances,
    parse_expenses,
    settle_up,
    split_equal,
    split_exact,
    split_percent,
    split_shares,
)

HEADER = "payer,amount,mode,participants\n"


def assert_money(value):
    assert isinstance(value, D)
    assert value.as_tuple().exponent == -2, value
    if value == 0:
        assert not value.is_signed(), value


def assert_money_dict(result):
    assert list(result) == sorted(result)
    for v in result.values():
        assert_money(v)


def line_error(text):
    with pytest.raises(SplitError) as info:
        parse_expenses(text)
    return str(info.value)


# ----------------------------------------------------------------- section 1


def test_public_api_exists():  # SPEC 1.2
    assert splitter.MODES == ("equal", "shares", "percent", "exact")
    for name in ("split_equal", "split_shares", "split_percent", "split_exact",
                 "parse_expenses", "compute_balances", "settle_up"):
        assert callable(getattr(splitter, name))


def test_split_error_is_value_error():  # SPEC 1.3
    assert issubclass(SplitError, ValueError)


@pytest.mark.parametrize("bad", [10, 10.0, "10", True, None])
def test_amount_must_be_decimal(bad):  # SPEC 1.6
    with pytest.raises(SplitError):
        split_equal(bad, ["A"])


@pytest.mark.parametrize("bad", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_amount_must_be_finite(bad):  # SPEC 1.6
    with pytest.raises(SplitError):
        split_equal(D(bad), ["A"])


@pytest.mark.parametrize("bad", ["10.505", "0.001", "1.999"])
def test_amount_more_than_two_places_rejected(bad):  # SPEC 1.6
    with pytest.raises(SplitError):
        split_equal(D(bad), ["A", "B"])


@pytest.mark.parametrize("ok", ["10.500", "1E+1", "10.5"])
def test_amount_two_places_by_value_accepted(ok):  # SPEC 1.6
    result = split_equal(D(ok), ["A"])
    assert result == {"A": D(ok)}
    assert_money(result["A"])


@pytest.mark.parametrize("bad", ["0", "0.00", "-0", "-5", "-0.01"])
def test_amount_must_be_positive(bad):  # SPEC 1.6
    for call in (lambda: split_equal(D(bad), ["A"]),
                 lambda: split_shares(D(bad), {"A": 1}),
                 lambda: split_percent(D(bad), {"A": D("100")}),
                 lambda: split_exact(D(bad), {"A": D(bad)})):
        with pytest.raises(SplitError):
            call()


def test_smallest_amount_accepted():  # SPEC 1.6
    assert split_equal(D("0.01"), ["A"]) == {"A": D("0.01")}
    assert split_exact(D("0.01"), {"A": D("0.01")}) == {"A": D("0.01")}


def test_names_stripped_and_case_sensitive():  # SPEC 1.7
    result = split_equal(D("3"), ["  asha", "Asha  ", "\tBALA\n"])
    assert list(result) == ["Asha", "BALA", "asha"]


@pytest.mark.parametrize("people", [["A", ""], ["A", "   "], ["A", 5], ["A", None]])
def test_bad_names_rejected(people):  # SPEC 1.7
    with pytest.raises(SplitError):
        split_equal(D("10"), people)


def test_duplicate_after_strip_rejected_everywhere():  # SPEC 1.7
    with pytest.raises(SplitError):
        split_equal(D("10"), ["Asha", " Asha"])
    with pytest.raises(SplitError):
        split_shares(D("10"), {"Asha": 1, "Asha ": 1})
    with pytest.raises(SplitError):
        split_percent(D("10"), {"Asha": D("50"), " Asha": D("50")})
    with pytest.raises(SplitError):
        split_exact(D("10"), {"Asha": D("5"), "Asha\t": D("5")})
    with pytest.raises(SplitError):
        settle_up({"A": D("1"), " A": D("-1")})


def test_code_point_ordering():  # SPEC 1.8
    result = split_equal(D("0.02"), ["b", "a", "B"])
    assert list(result) == ["B", "a", "b"]
    assert result == {"B": D("0.01"), "a": D("0.01"), "b": D("0.00")}


def test_inputs_not_mutated():  # SPEC 1.10
    people = [" B", "A"]
    shares = {" B": 1, "A": 2}
    bal = {"A": D("5"), "B": D("-5")}
    split_equal(D("10"), people)
    split_shares(D("10"), shares)
    settle_up(bal)
    assert people == [" B", "A"]
    assert shares == {" B": 1, "A": 2}
    assert bal == {"A": D("5"), "B": D("-5")}


# ----------------------------------------------------------------- section 2


def test_split_equal_example():  # SPEC 2.5
    result = split_equal(D("100"), ["Chen", "Asha", "Bala"])
    assert result == {"Asha": D("33.34"), "Bala": D("33.33"), "Chen": D("33.33")}
    assert_money_dict(result)


def test_split_equal_zero_shares_included():  # SPEC 2.4
    result = split_equal(D("0.02"), ["b", "a", "c"])
    assert result == {"a": D("0.01"), "b": D("0.01"), "c": D("0.00")}
    assert_money_dict(result)


def test_split_equal_exact_division():  # SPEC 2.3
    assert split_equal(D("9"), ["X", "Y", "Z"]) == {"X": D("3"), "Y": D("3"), "Z": D("3")}


def test_split_equal_remainder_to_alphabetical_first():  # SPEC 2.3
    # 1.03 among 4 -> 25 each + 3 leftover paise to A, B, C
    result = split_equal(D("1.03"), ["D", "C", "B", "A"])
    assert result == {"A": D("0.26"), "B": D("0.26"), "C": D("0.26"), "D": D("0.25")}


def test_split_equal_single_person():  # SPEC 2.4
    assert split_equal(D("12.34"), ["Solo"]) == {"Solo": D("12.34")}


@pytest.mark.parametrize("people", [("A", "B"), {"A", "B"}, "AB", {"A": 1}, None])
def test_split_equal_people_must_be_list(people):  # SPEC 2.1
    with pytest.raises(SplitError):
        split_equal(D("10"), people)


def test_split_equal_empty_people():  # SPEC 2.2
    with pytest.raises(SplitError):
        split_equal(D("10"), [])


# ----------------------------------------------------------------- section 3


def test_split_shares_examples():  # SPEC 3.5
    assert split_shares(D("10"), {"A": 1, "B": 2}) == {"A": D("3.33"), "B": D("6.67")}
    assert split_shares(D("90.50"), {"Asha": 1, "Bala": 2}) == {
        "Asha": D("30.17"), "Bala": D("60.33")}
    result = split_shares(D("1.00"), {"C": 1, "B": 1, "A": 1})
    assert result == {"A": D("0.34"), "B": D("0.33"), "C": D("0.33")}
    assert_money_dict(result)


def test_split_shares_largest_remainder_not_alphabetical():  # SPEC 3.3
    # P=100, weights Z:1 Y:1 X:5 (W=7): X 71 r3, Y 14 r2, Z 14 r2; L=1 -> X
    assert split_shares(D("1.00"), {"Z": 1, "Y": 1, "X": 5}) == {
        "X": D("0.72"), "Y": D("0.14"), "Z": D("0.14")}
    # P=200, weights A:1 B:1 C:1 D:4 (W=7): A,B,C 28 r4, D 114 r2; L=2 -> A, B
    assert split_shares(D("2.00"), {"D": 4, "C": 1, "B": 1, "A": 1}) == {
        "A": D("0.29"), "B": D("0.29"), "C": D("0.28"), "D": D("1.14")}


def test_split_shares_remainder_ties_alphabetical():  # SPEC 3.3
    # P=5, weights 2,2,1 (W=5): each exact -> no leftover
    assert split_shares(D("0.05"), {"a": 2, "b": 2, "c": 1}) == {
        "a": D("0.02"), "b": D("0.02"), "c": D("0.01")}
    # P=7, weights b:2, a:2, c:1: a 2 r4, b 2 r4, c 1 r2; L=2 -> a, b
    assert split_shares(D("0.07"), {"b": 2, "a": 2, "c": 1}) == {
        "a": D("0.03"), "b": D("0.03"), "c": D("0.01")}


def test_split_shares_large_weights():  # SPEC 3.3
    assert split_shares(D("100"), {"A": 1000, "B": 3000}) == {"A": D("25.00"), "B": D("75.00")}


@pytest.mark.parametrize("weight", [0, -1, True, False, 1.0, D("1"), "1", None])
def test_split_shares_bad_weights(weight):  # SPEC 3.2
    with pytest.raises(SplitError):
        split_shares(D("10"), {"A": 1, "B": weight})


@pytest.mark.parametrize("shares", [{}, [("A", 1)], None])
def test_split_shares_bad_container(shares):  # SPEC 3.1
    with pytest.raises(SplitError):
        split_shares(D("10"), shares)


def test_split_shares_keys_stripped():  # SPEC 3.4
    assert split_shares(D("3"), {" B ": 2, "A": 1}) == {"A": D("1.00"), "B": D("2.00")}


# ----------------------------------------------------------------- section 4


def test_split_percent_examples():  # SPEC 4.6
    result = split_percent(D("10"), {"A": D("33.33"), "B": D("33.33"), "C": D("33.34")})
    assert result == {"A": D("3.33"), "B": D("3.33"), "C": D("3.34")}
    assert_money_dict(result)
    assert split_percent(D("0.01"), {"A": D("50"), "B": D("50")}) == {
        "A": D("0.01"), "B": D("0.00")}


def test_split_percent_uses_largest_remainder():  # SPEC 4.4
    # P=101, A 10% -> 10.1, B 90% -> 90.9 ; L=1 goes to B (rem 9000 > 1000)
    assert split_percent(D("1.01"), {"A": D("10"), "B": D("90")}) == {
        "A": D("0.10"), "B": D("0.91")}
    # fractional percents: P=1000, A 12.5 -> 125, B 87.5 -> 875
    assert split_percent(D("10"), {"B": D("87.5"), "A": D("12.5")}) == {
        "A": D("1.25"), "B": D("8.75")}


def test_split_percent_single_100():  # SPEC 4.3
    assert split_percent(D("7.77"), {"A": D("100.00")}) == {"A": D("7.77")}


@pytest.mark.parametrize("percents", [
    {"A": D("33.33"), "B": D("33.33"), "C": D("33.33")},
    {"A": D("60"), "B": D("50")},
    {"A": D("99.99")},
    {"A": D("100.01")},
])
def test_split_percent_must_sum_to_100(percents):  # SPEC 4.3
    with pytest.raises(SplitError):
        split_percent(D("10"), percents)


@pytest.mark.parametrize("a, b", [
    (D("100"), D("0")),
    (D("110"), D("-10")),
    (D("66.667"), D("33.333")),
    (D("50"), 50),
    (D("50"), 50.0),
    (D("50"), "50"),
    (D("50"), D("NaN")),
    (D("50"), None),
])
def test_split_percent_bad_values(a, b):  # SPEC 4.2
    with pytest.raises(SplitError):
        split_percent(D("10"), {"A": a, "B": b})


def test_split_percent_negative_with_compensation_rejected():  # SPEC 4.2
    with pytest.raises(SplitError):
        split_percent(D("10"), {"A": D("110"), "B": D("-10")})
    with pytest.raises(SplitError):
        split_percent(D("10"), {"A": D("100"), "B": D("0")})


@pytest.mark.parametrize("percents", [{}, None, [("A", D("100"))]])
def test_split_percent_bad_container(percents):  # SPEC 4.1
    with pytest.raises(SplitError):
        split_percent(D("10"), percents)


# ----------------------------------------------------------------- section 5


def test_split_exact_example():  # SPEC 5.5
    result = split_exact(D("10"), {"B": D("6.5"), "A": D("3.5")})
    assert result == {"A": D("3.50"), "B": D("6.50")}
    assert list(result) == ["A", "B"]
    assert_money_dict(result)


@pytest.mark.parametrize("parts", [
    {"A": D("3"), "B": D("6.99")},
    {"A": D("3"), "B": D("7.01")},
    {"A": D("10.00"), "B": D("0.01")},
])
def test_split_exact_must_sum(parts):  # SPEC 5.3
    with pytest.raises(SplitError):
        split_exact(D("10"), parts)


@pytest.mark.parametrize("value", [D("0"), D("-1"), D("1.001"), 5, "5", D("Infinity")])
def test_split_exact_bad_parts(value):  # SPEC 5.2
    with pytest.raises(SplitError):
        split_exact(D("10"), {"A": D("10"), "B": value})


@pytest.mark.parametrize("parts", [{}, None, [("A", D("10"))]])
def test_split_exact_bad_container(parts):  # SPEC 5.1
    with pytest.raises(SplitError):
        split_exact(D("10"), parts)


def test_split_exact_keys_stripped():  # SPEC 5.4
    assert split_exact(D("1"), {" Z ": D("0.4"), "Y": D("0.6")}) == {"Y": D("0.60"), "Z": D("0.40")}


# ----------------------------------------------------------------- section 6

EXAMPLE_CSV = (
    "payer,amount,mode,participants\n"
    "Asha,300,equal,Asha;Bala;Chen\n"
    "\n"
    "Bala, 90.50 ,shares,Asha:1;Bala:2\n"
    "Chen,100,percent,Asha:50;Chen:50\n"
)
EXAMPLE_EXPENSES = [
    Expense("Asha", D("300.00"), "equal",
            {"Asha": D("100.00"), "Bala": D("100.00"), "Chen": D("100.00")}),
    Expense("Bala", D("90.50"), "shares", {"Asha": D("30.17"), "Bala": D("60.33")}),
    Expense("Chen", D("100.00"), "percent", {"Asha": D("50.00"), "Chen": D("50.00")}),
]


def test_expense_is_frozen_dataclass():  # SPEC 6.1
    assert dataclasses.is_dataclass(Expense)
    assert [f.name for f in dataclasses.fields(Expense)] == ["payer", "amount", "mode", "split"]
    e = Expense("A", D("1.00"), "exact", {"A": D("1.00")})
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.payer = "B"
    assert e == Expense(payer="A", amount=D("1.00"), mode="exact", split={"A": D("1.00")})


def test_parse_example():  # SPEC 6.12
    result = parse_expenses(EXAMPLE_CSV)
    assert result == EXAMPLE_EXPENSES
    for e in result:
        assert type(e.payer) is str
        assert_money(e.amount)
        assert_money_dict(e.split)


def test_parse_each_mode():  # SPEC 6.7
    text = HEADER + (
        "A,10,equal,C;B\n"
        "B,10,shares,A:3;C:1\n"
        "C,10,percent,A:25.5;B:74.5\n"
        "A,10.25,exact,B:10;C:0.25\n"
    )
    assert parse_expenses(text) == [
        Expense("A", D("10.00"), "equal", {"B": D("5.00"), "C": D("5.00")}),
        Expense("B", D("10.00"), "shares", {"A": D("7.50"), "C": D("2.50")}),
        Expense("C", D("10.00"), "percent", {"A": D("2.55"), "B": D("7.45")}),
        Expense("A", D("10.25"), "exact", {"B": D("10.00"), "C": D("0.25")}),
    ]


def test_parse_mode_recorded():  # SPEC 6.1
    modes = [e.mode for e in parse_expenses(HEADER + "A,1,exact,A:1\nA,1,equal,A\n")]
    assert modes == ["exact", "equal"]


def test_parse_whitespace_and_crlf():  # SPEC 6.3
    text = " payer , amount ,mode,participants \r\n  \r\n Asha , 10 , equal , Bala ; Chen \r\n"
    assert parse_expenses(text) == [
        Expense("Asha", D("10.00"), "equal", {"Bala": D("5.00"), "Chen": D("5.00")})]


def test_parse_plain_crlf():  # SPEC 6.3
    text = "payer,amount,mode,participants\r\nA,10,equal,B;C\r\nB,1,exact,A:1\r\n"
    assert parse_expenses(text) == [
        Expense("A", D("10.00"), "equal", {"B": D("5.00"), "C": D("5.00")}),
        Expense("B", D("1.00"), "exact", {"A": D("1.00")})]


def test_parse_only_one_cr_removed():  # SPEC 6.3
    # a lone CR not at the end of a line is ordinary data, so this is one
    # line with 7 fields -> malformed header on line 1
    assert line_error("payer,amount,mode,participants\rA,1,equal,A\n").startswith("line 1: ")
    # only one trailing CR is removed: "B;C" + CR + CR leaves "C" + CR, which strips
    assert parse_expenses("payer,amount,mode,participants\nA,2,equal,B;C\r\r") == [
        Expense("A", D("2.00"), "equal", {"B": D("1.00"), "C": D("1.00")})]


def test_parse_shares_value_whitespace_and_leading_zero():  # SPEC 6.7
    assert parse_expenses(HEADER + "A,3,shares, B : 02 ; C:1\n") == [
        Expense("A", D("3.00"), "shares", {"B": D("2.00"), "C": D("1.00")})]


def test_parse_header_only_returns_empty():  # SPEC 6.5
    assert parse_expenses(HEADER) == []
    assert parse_expenses("\n\npayer,amount,mode,participants") == []


@pytest.mark.parametrize("text", ["", "\n", "  \n\t\n"])
def test_parse_no_header(text):  # SPEC 6.5
    assert line_error(text).startswith("line 1: ")


def test_parse_bad_header_line_number():  # SPEC 6.5
    assert line_error("Payer,amount,mode,participants\nA,1,equal,A\n").startswith("line 1: ")
    assert line_error("\n\npayer,amount,mode\nA,1,equal,A\n").startswith("line 3: ")
    assert line_error("A,1,equal,A\n").startswith("line 1: ")


def test_parse_repeated_header_is_data_row():  # SPEC 6.5
    assert line_error(HEADER + "A,1,equal,A\n" + HEADER).startswith("line 3: ")


def test_parse_line_numbers_count_blank_lines():  # SPEC 6.10
    text = HEADER + "\n\nA,10,foo,B\n"
    assert line_error(text).startswith("line 4: ")


def test_parse_stops_at_first_bad_line():  # SPEC 6.10
    text = HEADER + "A,10,equal,B\nA,10,bogus,B\nA,-1,equal,B\n"
    assert line_error(text).startswith("line 3: ")


@pytest.mark.parametrize("row", [
    "A,10,equal",                       # 3 fields
    "A,10,equal,B,C",                   # 5 fields
    '"A",10,equal,B',                   # quotes not allowed
    ",10,equal,B",                      # empty payer
    "   ,10,equal,B",                   # blank payer
    "A,,equal,B",                       # empty amount
    "A,10.,equal,B",                    # bad amount format
    "A,.5,equal,B",
    "A,10.505,equal,B",                 # 3 decimals
    "A,-5,equal,B",                     # sign
    "A,+5,equal,B",
    "A,1e3,equal,B",                    # exponent
    "A,0,equal,B",                      # zero amount
    "A,0.00,equal,B",
    "A,10,EQUAL,B",                     # mode case-sensitive
    "A,10,split,B",                     # unknown mode
    "A,10,split,B:10",                  # unknown mode, valid-looking entries
    "A,10,Exact,B:10",
    "A,10,equal,",                      # no participants
    "A,10,equal,B;;C",                  # empty entry
    "A,10,equal,B;",                    # trailing separator
    "A,10,equal,B:1",                   # weight in equal mode
    "A,10,equal,B;B",                   # duplicate
    "A,10,equal,B; B ",                 # duplicate after strip
    "A,10,shares,B",                    # missing weight
    "A,10,shares,B:1:2",                # too many colons
    "A,10,shares,:1",                   # empty name
    "A,10,shares,B:1.5",                # non-int share
    "A,10,shares,B:-1",                 # negative share
    "A,10,shares,B:0;C:1",              # zero share
    "A,10,shares,B:x",
    "A,10,shares,B:",
    "A,10,shares,B:1;B:2",              # duplicate
    "A,10,percent,B:50;C:49",           # not 100
    "A,10,percent,B:100;C:0",           # zero percent
    "A,10,percent,B:33.333;C:66.667",   # 3 decimals
    "A,10,percent,B:50;C:-50",
    "A,10,percent,B:50;B:50",           # duplicate
    "A,10,exact,B:5;C:4.99",            # wrong sum
    "A,10,exact,B:10;C:0",              # zero part
    "A,10,exact,B:10.001",              # 3 decimals
    "A,10,exact,B:5;B:5",               # duplicate
    "A,10,exact,B",                     # missing value
])
def test_parse_malformed_rows(row):  # SPEC 6.6
    text = HEADER + "X,1,equal,X\n" + row + "\n"
    msg = line_error(text)
    assert msg.startswith("line 3: "), msg


def test_parse_quote_in_participants_rejected():  # SPEC 6.4
    assert line_error(HEADER + 'A,10,equal,"B"\n').startswith("line 2: ")


def test_parse_non_str():  # SPEC 6.2
    for bad in (None, b"payer,amount,mode,participants\n", ["payer,amount,mode,participants"]):
        with pytest.raises(SplitError):
            parse_expenses(bad)


def test_parse_payer_not_participant_and_repeat_payer():  # SPEC 6.9
    result = parse_expenses(HEADER + "Z,4,equal,A;B\nZ,1,exact,A:1\n")
    assert [e.payer for e in result] == ["Z", "Z"]
    assert result[0].split == {"A": D("2.00"), "B": D("2.00")}


def test_parse_line_number_large():  # SPEC 6.10
    rows = "".join(f"P{i},1,equal,Q\n" for i in range(11))
    msg = line_error(HEADER + rows + "P,1,equal,Q:1\n")
    assert msg.startswith("line 13: "), msg


# ----------------------------------------------------------------- section 7


def test_balances_example():  # SPEC 7.6
    result = compute_balances(EXAMPLE_EXPENSES)
    assert result == {"Asha": D("119.83"), "Bala": D("-69.83"), "Chen": D("-50.00")}
    assert list(result) == ["Asha", "Bala", "Chen"]
    assert_money_dict(result)


def test_balances_zero_included():  # SPEC 7.4
    result = compute_balances([Expense("A", D("5.00"), "exact", {"A": D("5.00")})])
    assert result == {"A": D("0.00")}
    assert_money(result["A"])


def test_balances_payer_not_in_split_and_zero_share():  # SPEC 7.4
    exps = [Expense("Z", D("0.02"), "equal", {"b": D("0.01"), "a": D("0.01"), "c": D("0.00")})]
    result = compute_balances(exps)
    assert result == {"Z": D("0.02"), "a": D("-0.01"), "b": D("-0.01"), "c": D("0.00")}
    assert list(result) == ["Z", "a", "b", "c"]
    assert_money_dict(result)


def test_balances_accumulate():  # SPEC 7.3
    exps = [
        Expense("A", D("10"), "exact", {"B": D("10")}),
        Expense("B", D("4"), "exact", {"A": D("4")}),
        Expense("A", D("6"), "exact", {"A": D("3"), "C": D("3")}),
    ]
    assert compute_balances(exps) == {"A": D("9.00"), "B": D("-6.00"), "C": D("-3.00")}


def test_balances_empty():  # SPEC 7.1
    assert compute_balances([]) == {}


@pytest.mark.parametrize("bad", [None, (), "x"])
def test_balances_not_list(bad):  # SPEC 7.1
    with pytest.raises(SplitError):
        compute_balances(bad)


@pytest.mark.parametrize("exp", [
    "not an expense",
    {"payer": "A"},
    Expense("A", D("10"), "exact", {"B": D("9.99")}),          # sum mismatch
    Expense("A", D("10"), "exact", {"B": D("10.01")}),
    Expense("A", D("10"), "exact", {"B": D("11"), "C": D("-1")}),  # negative value
    Expense("A", D("0"), "exact", {"B": D("0")}),              # non-positive amount
    Expense("A", D("-5"), "exact", {"B": D("-5")}),
    Expense("A", 10, "exact", {"B": D("10")}),                 # amount not Decimal
    Expense("A", D("10"), "exact", {"B": 10}),                 # value not Decimal
    Expense("A", D("10"), "exact", {"B": D("10.001")}),
    Expense("A", D("10"), "exact", {}),                        # empty split
    Expense("A", D("10"), "exact", [("B", D("10"))]),          # not a dict
    Expense("", D("10"), "exact", {"B": D("10")}),             # empty payer
    Expense(None, D("10"), "exact", {"B": D("10")}),
    Expense("A", D("10"), "exact", {"": D("10")}),             # empty key
    Expense("A", D("10"), "exact", {5: D("10")}),
])
def test_balances_invalid_expense(exp):  # SPEC 7.2
    with pytest.raises(SplitError):
        compute_balances([Expense("Q", D("1"), "exact", {"Q": D("1")}), exp])


def test_balances_mode_not_inspected_and_names_not_stripped():  # SPEC 7.2
    result = compute_balances([Expense("A ", D("2"), "whatever", {"A": D("2")})])
    assert result == {"A": D("-2.00"), "A ": D("2.00")}


# ----------------------------------------------------------------- section 8


def test_settle_examples():  # SPEC 8.5
    out = settle_up({"Asha": D("119.83"), "Bala": D("-69.83"), "Chen": D("-50.00")})
    assert out == [("Bala", "Asha", D("69.83")), ("Chen", "Asha", D("50.00"))]
    assert settle_up({"A": D("10"), "B": D("10"), "C": D("-20")}) == [
        ("C", "A", D("10.00")), ("C", "B", D("10.00"))]
    assert settle_up({"A": D("-30"), "B": D("-10"), "C": D("25"), "D": D("15")}) == [
        ("A", "C", D("25.00")), ("B", "D", D("10.00")), ("A", "D", D("5.00"))]


def test_settle_result_types():  # SPEC 8.4
    out = settle_up({"A": D("-1.5"), "B": D("1.5")})
    assert out == [("A", "B", D("1.50"))]
    assert type(out) is list and type(out[0]) is tuple
    assert_money(out[0][2])


def test_settle_debtor_ties_alphabetical():  # SPEC 8.3
    assert settle_up({"Y": D("-5"), "X": D("-5"), "Z": D("10")}) == [
        ("X", "Z", D("5.00")), ("Y", "Z", D("5.00"))]


def test_settle_largest_debtor_first():  # SPEC 8.3
    # B owes most -> pays first, to the largest creditor C
    assert settle_up({"A": D("-1"), "B": D("-9"), "C": D("7"), "D": D("3")}) == [
        ("B", "C", D("7.00")), ("B", "D", D("2.00")), ("A", "D", D("1.00"))]


def test_settle_creditor_exceeds_debt():  # SPEC 8.3
    assert settle_up({"A": D("-2"), "B": D("-3"), "C": D("5")}) == [
        ("B", "C", D("3.00")), ("A", "C", D("2.00"))]


def test_returned_zeros_unsigned():  # SPEC 1.5
    for v in split_equal(D("0.01"), ["A", "B", "C"]).values():
        assert_money(v)
    bal = compute_balances([Expense("A", D("1"), "exact", {"A": D("1")}),
                            Expense("B", D("2"), "exact", {"C": D("2")}),
                            Expense("C", D("2"), "exact", {"B": D("2")})])
    assert bal == {"A": D("0"), "B": D("0"), "C": D("0")}
    for v in bal.values():
        assert_money(v)


def test_settle_zero_balances_skipped():  # SPEC 8.4
    assert settle_up({"A": D("0"), "B": D("-1"), "C": D("1"), "D": D("0.00")}) == [
        ("B", "C", D("1.00"))]
    assert settle_up({"A": D("0"), "B": D("0")}) == []
    assert settle_up({}) == []


def test_settle_one_paisa():  # SPEC 8.3
    assert settle_up({"A": D("-0.01"), "B": D("0.01")}) == [("A", "B", D("0.01"))]
    assert settle_up({"A": D("-0.02"), "B": D("0.01"), "C": D("0.01")}) == [
        ("A", "B", D("0.01")), ("A", "C", D("0.01"))]


def test_settle_keys_stripped():  # SPEC 8.1
    assert settle_up({" A ": D("-1"), "B\t": D("1")}) == [("A", "B", D("1.00"))]


@pytest.mark.parametrize("bal", [
    {"A": D("1"), "B": D("-0.99")},
    {"A": D("0.01")},
    {"A": D("-0.01")},
    {"A": D("5"), "B": D("-4"), "C": D("-2")},
])
def test_settle_sum_must_be_zero(bal):  # SPEC 8.2
    with pytest.raises(SplitError):
        settle_up(bal)


@pytest.mark.parametrize("bal", [
    None, [("A", D("1"))],
    {"A": 1, "B": -1},
    {"A": D("0.001"), "B": D("-0.001")},
    {"A": D("NaN"), "B": D("1")},
    {"": D("1"), "B": D("-1")},
    {5: D("1"), "B": D("-1")},
])
def test_settle_invalid(bal):  # SPEC 8.1
    with pytest.raises(SplitError):
        settle_up(bal)


# ------------------------------------------------- property-style checks


def _rand_names(rng, k):
    pool = ["Asha", "Bala", "Chen", "Dev", "Esha", "Farid", "gita", "Hari", "Ivan", "jo"]
    return rng.sample(pool, k)


def test_property_splits_sum_to_amount():  # SPEC 2.4
    rng = random.Random(42)
    for _ in range(300):
        paise = rng.randint(1, 1_000_000)
        amount = D(paise).scaleb(-2)
        names = _rand_names(rng, rng.randint(1, 7))
        results = [split_equal(amount, names),
                   split_shares(amount, {n: rng.randint(1, 50) for n in names})]
        cuts = sorted(rng.sample(range(1, 10000), len(names) - 1)) if len(names) > 1 else []
        bounds = [0] + cuts + [10000]
        results.append(split_percent(amount, {
            n: D(bounds[i + 1] - bounds[i]).scaleb(-2) for i, n in enumerate(names)}))
        for r in results:
            assert sum(r.values()) == amount
            assert set(r) == set(names)
            assert_money_dict(r)
            assert all(v >= 0 for v in r.values())


def test_property_shares_fair():  # SPEC 3.3
    rng = random.Random(42)
    for _ in range(300):
        paise = rng.randint(1, 100_000)
        names = _rand_names(rng, rng.randint(1, 6))
        weights = {n: rng.randint(1, 20) for n in names}
        result = split_shares(D(paise).scaleb(-2), weights)
        total_w = sum(weights.values())
        for n in names:
            exact = D(paise * weights[n]) / D(total_w)
            got = result[n].scaleb(2)
            assert exact - 1 < got < exact + 1


def test_property_equal_spread_at_most_one_paisa():  # SPEC 2.3
    rng = random.Random(42)
    for _ in range(300):
        paise = rng.randint(1, 100_000)
        names = _rand_names(rng, rng.randint(1, 8))
        result = split_equal(D(paise).scaleb(-2), names)
        values = [result[n] for n in sorted(names)]
        assert max(values) - min(values) <= D("0.01")
        assert values == sorted(values, reverse=True)


def test_property_balances_sum_zero_and_settle_clears():  # SPEC 7.5
    rng = random.Random(42)
    for _ in range(150):
        lines = [HEADER.strip()]
        for _ in range(rng.randint(1, 6)):
            names = _rand_names(rng, rng.randint(1, 5))
            payer = _rand_names(rng, 1)[0]
            amount = D(rng.randint(1, 500_000)).scaleb(-2)
            mode = rng.choice(["equal", "shares", "exact"])
            if mode == "equal":
                parts = ";".join(names)
            elif mode == "shares":
                parts = ";".join(f"{n}:{rng.randint(1, 9)}" for n in names)
            else:
                split = split_equal(amount, names)
                if any(v == 0 for v in split.values()):
                    # a 0.00 exact part would be a malformed row (5.2); use equal
                    mode = "equal"
                    parts = ";".join(names)
                else:
                    parts = ";".join(f"{n}:{v}" for n, v in split.items())
            lines.append(f"{payer},{amount},{mode},{parts}")
        expenses = parse_expenses("\n".join(lines))
        balances = compute_balances(expenses)
        assert sum(balances.values()) == 0
        assert_money_dict(balances)
        transfers = settle_up(balances)
        assert len(transfers) <= max(0, sum(1 for v in balances.values() if v) - 1)
        remaining = dict(balances)
        for frm, to, amt in transfers:
            assert amt > 0
            assert_money(amt)
            assert remaining[frm] < 0 < remaining[to]
            remaining[frm] += amt
            remaining[to] -= amt
        assert all(v == 0 for v in remaining.values())


def test_property_deterministic():  # SPEC 8.3
    rng = random.Random(42)
    for _ in range(100):
        names = _rand_names(rng, rng.randint(2, 6))
        vals = [rng.randint(-5000, 5000) for _ in names[:-1]]
        vals.append(-sum(vals))
        bal = {n: D(v).scaleb(-2) for n, v in zip(names, vals)}
        rev = dict(reversed(list(bal.items())))
        assert settle_up(bal) == settle_up(rev)
