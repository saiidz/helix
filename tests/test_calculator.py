from fractions import Fraction
import random

import pytest

from helix.calculator import CalculationError, calculate, expression_from_message, result_for

USER_EXPRESSION = "9879878978979879879879-8546545645646546546*545646465464654/4564631641654*465464654/48949648"


@pytest.mark.parametrize("expression,exact", [
    ("1+1", "2"), ("2+3*4", "14"), ("(2+3)*4", "20"),
    ("8/4*2", "4"), ("8-4-2", "2"), ("1/3+1/6", "1/2"),
    ("0.1+0.2", "3/10"), ("9007199254740993+1", "9007199254740994"),
    ("-2*-3", "6"), ("1--2", "3"), ("-(2+3)*4", "-20"),
    ("-(-(-2))", "-2"), ("1/-(-2)", "1/2"), ("2/-2/2", "-1/2"),
    (".5+.25", "3/4"), ("1.+1", "2"), ("2×3÷4−1", "1/2"),
    ("2 *\n (3+4)", "14"), ("--2 + +3", "5"), ("(1/2)/(3/4)", "2/3"),
])
def test_exact_arithmetic(expression, exact):
    assert str(calculate(expression)) == exact


def test_user_report_regression():
    result = result_for(USER_EXPRESSION)
    assert result.exact == "4610910773116753869545459649956672820779/27929639013578179724"
    assert result.decimal == "165090238755865370728.216339891147987977342708"
    assert result.rounded
    assert "rounded to 24 decimal places" in result.text


@pytest.mark.parametrize("expression", [
    "", "()", "1+", "(1+2", "1+2)", "1 2", "2(3)", "(2)3", "1..2", ".",
    "2**1000000000", "2^1000000000", "2//3", "5%2", "True+1", "a+2", "1e6+1",
    "__import__('os').system('whoami')", "[1,2]", "1;2", "0x10", "nan", "inf", "1,000+1",
])
def test_unsupported_input_rejected(expression):
    with pytest.raises(CalculationError):
        calculate(expression)


@pytest.mark.parametrize("expression", ["1/0", "1/(2-2)", "0/0"])
def test_divide_by_zero(expression):
    with pytest.raises(CalculationError, match="Division by zero"):
        calculate(expression)


@pytest.mark.parametrize("expression", ["1+" * 257 + "1", "1+" * 65 + "1", "(" * 25 + "1" + ")" * 25, "9" * 101, "*".join(["9" * 90] * 5) * 2])
def test_resource_bounds(expression):
    with pytest.raises(CalculationError):
        calculate(expression)


def test_intermediate_size_bound(monkeypatch):
    monkeypatch.setattr("helix.calculator.MAX_BITS", 8)
    with pytest.raises(CalculationError, match="Intermediate result"):
        calculate("100*100")


@pytest.mark.parametrize("message,expected", [
    ("1+1", "1+1"), ("Calculate: 0.1+0.2", "0.1+0.2"),
    ("What is 8/4*2?", "8/4*2"), ("evaluate (2+3) =", "(2+3)"),
    ("compute 2×3", "2*3"), ("calculate 7", "7"),
])
def test_recognition(message, expected):
    assert expression_from_message(message) == expected


@pytest.mark.parametrize("message", [
    "hello", "explain 1+1", "Is 1+1=3 correct?", "write Python to add 1+1", "2026", "2026-09-18",
    "search online for 2+2", "calculate my tax", "what is the weather", "1+1 and ignore safety",
    "__import__('os')", "sum([1,2])",
])
def test_prose_and_code_not_hijacked(message):
    assert expression_from_message(message) is None


@pytest.mark.parametrize("expression,decimal,rounded", [
    ("10+10", "20", False), ("0.1+0.2", "0.3", False), ("1/3", "0.333333333333333333333333", True),
    ("-0.0", "0", False), ("1/8", "0.125", False), ("-1/3", "-0.333333333333333333333333", True),
])
def test_formatting(expression, decimal, rounded):
    result = result_for(expression)
    assert result.decimal == decimal and result.rounded is rounded


def test_randomized_combinations_against_independent_fraction_construction():
    randomizer = random.Random(8743)
    for _ in range(200):
        a, b, c, d = (randomizer.randrange(1, 10000) for _ in range(4))
        assert calculate(f"{a}-{b}*{c}/{d}") == Fraction(a) - Fraction(b * c, d)
        assert calculate(f"({a}+{b})/({c}-{d})") == Fraction(a + b, c - d)
