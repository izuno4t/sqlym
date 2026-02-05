"""SQLコメント内パラメータの字句解析."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 修飾記号:
#   $ - removable (negative時に行削除)
#   & - bind-less (negative時に行削除、positive時はプレースホルダなし)
#   @ - required (negative時に例外)
#   ? - fallback (negative時は次のパラメータを使用)
#   ! - negation (negative/positive を反転)
#
# 例:
#   /* $name */     - 削除可能
#   /* &flag */     - バインドなし行削除
#   /* $!name */    - 否定付き削除可能
#   /* @id */       - 必須パラメータ
#   /* ?a ?b */     - フォールバック

# パラメータパターン
# /* $name */'default' : 削除可能
# /* name */'default'  : 削除不可
PARAM_PATTERN = re.compile(
    r"/\*\s*([$&@?!]+)?(\w+)\s*\*/\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r"|\d+(?:\.\d+)?"  # number
    r"|\w+"  # identifier
    r"|\([^)]*\)"  # (list)
    r"|NULL"  # NULL
    r")?"
)

# フォールバックパターン（複数 ?param を含むコメント）
# /* ?a ?b ?c */'default' : a が negative なら b、b も negative なら c、全て negative ならデフォルト
FALLBACK_PATTERN = re.compile(
    r"/\*\s*((?:\?\w+\s*)+)\*/\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r"|\d+(?:\.\d+)?"  # number
    r"|\w+"  # identifier
    r"|NULL"  # NULL
    r")"
)

# IN句パターン
IN_PATTERN = re.compile(
    r"\bIN\s*/\*\s*([$&@?!]+)?(\w+)\s*\*/\s*\([^)]*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Token:
    """パラメータトークン."""

    name: str
    """パラメータ名."""

    removable: bool
    """$付き(negative時に行削除)."""

    default: str
    """デフォルト値文字列."""

    is_in_clause: bool
    """IN句パラメータか."""

    start: int
    """元文字列内の開始位置."""

    end: int
    """元文字列内の終了位置."""

    bindless: bool = False
    """&付き(negative時に行削除、positive時はプレースホルダなし)."""

    negated: bool = False
    """!付き(negative/positive判定を反転)."""

    required: bool = False
    """@付き(negative時に例外)."""

    fallback: bool = False
    """?付き(negative時は次のパラメータを使用)."""

    fallback_names: tuple[str, ...] = ()
    """フォールバックチェーン（?a ?b ?c の場合 ('a', 'b', 'c')）."""


def _parse_modifiers(modifiers: str | None) -> dict[str, bool]:
    """修飾記号文字列をパースしてフラグ辞書を返す."""
    if not modifiers:
        return {
            "removable": False,
            "bindless": False,
            "negated": False,
            "required": False,
            "fallback": False,
        }
    return {
        "removable": "$" in modifiers,
        "bindless": "&" in modifiers,
        "negated": "!" in modifiers,
        "required": "@" in modifiers,
        "fallback": "?" in modifiers,
    }


def tokenize(line: str) -> list[Token]:
    """行からパラメータトークンを抽出する.

    IN句パターンを先にマッチし、次にフォールバックパターン、
    最後に通常パラメータパターンを重複しない範囲でマッチさせる。

    Args:
        line: SQL行文字列

    Returns:
        Token のリスト（出現順）

    """
    tokens: list[Token] = []
    used_ranges: list[tuple[int, int]] = []

    # IN句パターンを先にマッチ
    for m in IN_PATTERN.finditer(line):
        modifiers = m.group(1)
        name = m.group(2)
        flags = _parse_modifiers(modifiers)
        tokens.append(
            Token(
                name=name,
                removable=flags["removable"],
                default=_extract_in_default(m.group(0)),
                is_in_clause=True,
                start=m.start(),
                end=m.end(),
                bindless=flags["bindless"],
                negated=flags["negated"],
                required=flags["required"],
                fallback=flags["fallback"],
            )
        )
        used_ranges.append((m.start(), m.end()))

    # フォールバックパターン（/* ?a ?b ?c */'default' 形式）
    for m in FALLBACK_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        params_str = m.group(1)  # "?a ?b ?c " のような文字列
        default = m.group(2)
        # ?name 形式のパラメータ名を抽出
        names = tuple(re.findall(r"\?(\w+)", params_str))
        if names:
            tokens.append(
                Token(
                    name=names[0],  # 最初のパラメータ名をメイン名とする
                    removable=True,  # フォールバックは全て negative 時に行削除
                    default=default,
                    is_in_clause=False,
                    start=m.start(),
                    end=m.end(),
                    bindless=False,
                    negated=False,
                    required=False,
                    fallback=True,
                    fallback_names=names,
                )
            )
            used_ranges.append((m.start(), m.end()))

    # 通常パラメータパターン（IN句・フォールバックと重複しない範囲）
    for m in PARAM_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        modifiers = m.group(1)
        name = m.group(2)
        default = m.group(3) or ""
        flags = _parse_modifiers(modifiers)
        tokens.append(
            Token(
                name=name,
                removable=flags["removable"],
                default=default,
                is_in_clause=False,
                start=m.start(),
                end=m.end(),
                bindless=flags["bindless"],
                negated=flags["negated"],
                required=flags["required"],
                fallback=flags["fallback"],
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
