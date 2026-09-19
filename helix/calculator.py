"""Bounded exact arithmetic, with no Python evaluation or external capabilities."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction

MAX_CHARS = 512
MAX_TOKENS = 128
MAX_DEPTH = 24
MAX_DIGITS = 100
MAX_BITS = 2048
DECIMAL_PLACES = 24
_NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")
_PREFIX = re.compile(r"^(?:what\s+is|calculate|compute|evaluate)\s*:?[ \t]*", re.I)
_CHARS = re.compile(r"[0-9\s.+\-*/()^%=]+\Z", re.ASCII)
_TRANSLATE = str.maketrans({"×": "*", "÷": "/", "−": "-"})
_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "u+": 3, "u-": 3}


class CalculationError(ValueError):
    """A public, non-sensitive rejection of unsupported or excessive input."""


def expression_from_message(message: str) -> str | None:
    """Only self-contained arithmetic; never extract expressions from prose/code."""
    text = message.strip().translate(_TRANSLATE)
    prefix = _PREFIX.match(text)
    if prefix:
        text = text[prefix.end():].strip()
    if text.endswith("?"):
        text = text[:-1].rstrip()
    if text.endswith("="):
        text = text[:-1].rstrip()
    if not text or not _CHARS.fullmatch(text) or not re.search(r"[0-9]", text):
        return None
    # A bare number or ISO date is context, not an implicit calculation request.
    if not prefix and (not re.search(r"[+*/^%()\-]", text) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text)):
        return None
    return text


def _bounded(value: Fraction) -> Fraction:
    if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > MAX_BITS:
        raise CalculationError("Intermediate result exceeds the calculator's size limit.")
    return value


def calculate(expression: str) -> Fraction:
    """Evaluate +, -, *, / and parentheses, including unary signs and decimals.

    An iterative operator/value stack preserves precedence and left-associative
    multiplication/division. No eval, exec, AST compiler, subprocess, or network.
    Length, token, nesting, operand, and intermediate-size bounds are mandatory.
    """
    if not isinstance(expression, str):
        raise CalculationError("Supply an arithmetic expression as text.")
    expression = expression.strip().translate(_TRANSLATE)
    if not expression or len(expression) > MAX_CHARS:
        raise CalculationError(f"Use between 1 and {MAX_CHARS} characters.")
    values: list[Fraction] = []
    operators: list[str] = []
    offset = depth = tokens = 0
    expecting_value = True

    def apply() -> None:
        operator = operators.pop()
        if operator in {"u+", "u-"}:
            if not values:
                raise CalculationError("A sign must be followed by a number or parentheses.")
            values[-1] = _bounded(-values[-1] if operator == "u-" else values[-1])
            return
        if len(values) < 2:
            raise CalculationError("An operator is missing an operand.")
        right, left = values.pop(), values.pop()
        if operator == "/" and not right:
            raise CalculationError("Division by zero is undefined.")
        if operator == "+":
            value = left + right
        elif operator == "-":
            value = left - right
        elif operator == "*":
            value = left * right
        else:
            value = left / right
        values.append(_bounded(value))

    while offset < len(expression):
        if expression[offset].isspace():
            offset += 1
            continue
        tokens += 1
        if tokens > MAX_TOKENS:
            raise CalculationError(f"Use at most {MAX_TOKENS} numbers and operators.")
        match = _NUMBER.match(expression, offset)
        token = expression[offset]
        if match:
            if not expecting_value:
                raise CalculationError("Use an explicit operator between numbers or parentheses.")
            literal = match.group()
            if sum(c.isdigit() for c in literal) > MAX_DIGITS:
                raise CalculationError(f"Each number may have at most {MAX_DIGITS} digits.")
            values.append(_bounded(Fraction(literal)))
            offset = match.end()
            expecting_value = False
            continue
        offset += 1
        if token == "(":
            if not expecting_value:
                raise CalculationError("Implicit multiplication is not supported; write '*'.")
            depth += 1
            if depth > MAX_DEPTH:
                raise CalculationError(f"Use at most {MAX_DEPTH} nested parentheses.")
            operators.append(token)
        elif token == ")":
            if expecting_value or not depth:
                raise CalculationError("Mismatched or empty parentheses.")
            while operators and operators[-1] != "(":
                apply()
            operators.pop()
            depth -= 1
            expecting_value = False
        elif token in "+-*/":
            if expecting_value:
                if token not in "+-":
                    raise CalculationError("An operator is missing an operand; powers are not supported.")
                operators.append("u" + token)
            else:
                while operators and operators[-1] != "(" and _PRECEDENCE[operators[-1]] >= _PRECEDENCE[token]:
                    apply()
                operators.append(token)
                expecting_value = True
        else:
            raise CalculationError("Supported arithmetic: numbers, decimals, +, -, *, /, and parentheses only.")
    if expecting_value or depth:
        raise CalculationError("Incomplete expression or mismatched parentheses.")
    while operators:
        apply()
    if len(values) != 1:
        raise CalculationError("Invalid arithmetic expression.")
    return values[0]


@dataclass(frozen=True)
class Calculation:
    exact: str
    decimal: str
    rounded: bool

    @property
    def text(self) -> str:
        if "/" not in self.exact:
            answer = f"{self.exact} (exact)."
        elif self.rounded:
            answer = (f"Approximately {self.decimal} (rounded to {DECIMAL_PLACES} decimal places)."
                      f"\n\nExact value: {self.exact}.")
        else:
            answer = f"{self.decimal} (exact).\n\nExact fraction: {self.exact}."
        return answer + "\n\nCalculated locally using exact arithmetic; no language-model or web call."


def result_for(expression: str) -> Calculation:
    value = calculate(expression)
    exact = str(value)
    with localcontext() as context:
        # More than enough for both MAX_BITS-bounded operands and decimal output.
        context.prec = MAX_BITS + DECIMAL_PLACES + 10
        decimal = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            Decimal(1).scaleb(-DECIMAL_PLACES), rounding=ROUND_HALF_EVEN
        )
    rendered = format(decimal, "f").rstrip("0").rstrip(".")
    if rendered in {"", "-0"}:
        rendered = "0"
    return Calculation(exact, rendered, Fraction(rendered) != value)
