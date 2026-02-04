"""SQLコメント内パラメータの字句解析."""

from __future__ import annotations

import re
from dataclasses import dataclass

# パラメータパターン
# /* $name */'default' : 削除可能
# /* name */'default'  : 削除不可
PARAM_PATTERN = re.compile(
    r"/\*\s*(\$)?(\w+)\s*\*/\s*"
    r"("
    r"'[^']*'"  # 'string'
    r'|"[^"]*"'  # "string"
    r"|\d+(?:\.\d+)?"  # number
    r"|\w+"  # identifier
    r"|\([^)]*\)"  # (list)
    r"|NULL"  # NULL
    r")?"
)

# IN句パターン
IN_PATTERN = re.compile(
    r"\bIN\s*/\*\s*(\$)?(\w+)\s*\*/\s*\([^)]*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Token:
    """パラメータトークン."""

    name: str
    """パラメータ名."""

    removable: bool
    """$付き(Noneで行削除)."""

    default: str
    """デフォルト値文字列."""

    is_in_clause: bool
    """IN句パラメータか."""

    start: int
    """元文字列内の開始位置."""

    end: int
    """元文字列内の終了位置."""


def tokenize(line: str) -> list[Token]:
    """行からパラメータトークンを抽出する.

    IN句パターンを先にマッチし、その後通常パラメータパターンを
    重複しない範囲でマッチさせる。

    Args:
        line: SQL行文字列

    Returns:
        Token のリスト（出現順）

    """
    tokens: list[Token] = []
    used_ranges: list[tuple[int, int]] = []

    # IN句パターンを先にマッチ
    for m in IN_PATTERN.finditer(line):
        dollar = m.group(1)
        name = m.group(2)
        tokens.append(
            Token(
                name=name,
                removable=dollar is not None,
                default=_extract_in_default(m.group(0)),
                is_in_clause=True,
                start=m.start(),
                end=m.end(),
            )
        )
        used_ranges.append((m.start(), m.end()))

    # 通常パラメータパターン（IN句と重複しない範囲）
    for m in PARAM_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        dollar = m.group(1)
        name = m.group(2)
        default = m.group(3) or ""
        tokens.append(
            Token(
                name=name,
                removable=dollar is not None,
                default=default,
                is_in_clause=False,
                start=m.start(),
                end=m.end(),
            )
        )

    tokens.sort(key=lambda t: t.start)
    return tokens


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    """指定範囲が既存範囲と重複するか判定する."""
    return any(start < r_end and end > r_start for r_start, r_end in ranges)


def _extract_in_default(matched: str) -> str:
    """IN句マッチ文字列からデフォルトリスト部分を抽出する."""
    paren_start = matched.rfind("(")
    if paren_start >= 0:
        return matched[paren_start:]
    return ""
