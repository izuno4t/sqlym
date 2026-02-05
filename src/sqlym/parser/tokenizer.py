"""SQLコメント内パラメータの字句解析."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

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

# 補助関数パターン
# /* %concat('%', param, '%') */'default'
# /*%C '%' param '%' */'default'
CONCAT_PATTERN = re.compile(
    r"/\*\s*(?:%concat\s*\(|%C\s+)([^)]+?)(?:\)|)\s*\*/\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r")"
)

# /* %L '%' param '%' */'default' - LIKE エスケープ + escape 句付与
LIKE_ESCAPE_PATTERN = re.compile(
    r"/\*\s*%L\s+([^*]+?)\s*\*/\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r")"
)

# /* %STR(param) */default - 直接埋め込み
# /* %SQL(param) */default
STR_EMBED_PATTERN = re.compile(
    r"/\*\s*%(STR|SQL)\s*\(\s*(\w+)\s*\)\s*\*/\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r"|\w+"  # identifier
    r")"
)

# ブロックディレクティブパターン
# -- %IF condition
# -- %ELSEIF condition
# -- %ELSE
# -- %END
IF_DIRECTIVE_PATTERN = re.compile(
    r"^[ \t]*--[ \t]*%IF\s+(.+?)\s*$",
    re.IGNORECASE,
)
ELSEIF_DIRECTIVE_PATTERN = re.compile(
    r"^[ \t]*--[ \t]*%ELSEIF\s+(.+?)\s*$",
    re.IGNORECASE,
)
ELSE_DIRECTIVE_PATTERN = re.compile(
    r"^[ \t]*--[ \t]*%ELSE\s*$",
    re.IGNORECASE,
)
END_DIRECTIVE_PATTERN = re.compile(
    r"^[ \t]*--[ \t]*%END\s*$",
    re.IGNORECASE,
)


class DirectiveType(Enum):
    """ブロックディレクティブの種類."""

    IF = "IF"
    ELSEIF = "ELSEIF"
    ELSE = "ELSE"
    END = "END"


@dataclass(frozen=True)
class Directive:
    """ブロックディレクティブ."""

    type: DirectiveType
    """ディレクティブの種類."""

    condition: str | None
    """条件式（IF/ELSEIF のみ）."""


def parse_directive(line: str) -> Directive | None:
    """行からブロックディレクティブをパースする.

    Args:
        line: SQL行文字列

    Returns:
        Directive オブジェクト、またはディレクティブでない場合は None

    """
    # %IF condition
    m = IF_DIRECTIVE_PATTERN.match(line)
    if m:
        return Directive(type=DirectiveType.IF, condition=m.group(1))

    # %ELSEIF condition
    m = ELSEIF_DIRECTIVE_PATTERN.match(line)
    if m:
        return Directive(type=DirectiveType.ELSEIF, condition=m.group(1))

    # %ELSE
    m = ELSE_DIRECTIVE_PATTERN.match(line)
    if m:
        return Directive(type=DirectiveType.ELSE, condition=None)

    # %END
    m = END_DIRECTIVE_PATTERN.match(line)
    if m:
        return Directive(type=DirectiveType.END, condition=None)

    return None


# インライン条件分岐パターン
# /*%if cond */ value1 /*%elseif cond2 */ value2 /*%else */ value3 /*%end*/
INLINE_IF_PATTERN = re.compile(
    r"/\*\s*%if\s+([^*]+?)\s*\*/"  # %if condition
    r"(.*?)"  # if branch value
    r"(?:"
    r"/\*\s*%elseif\s+([^*]+?)\s*\*/"  # %elseif condition (optional)
    r"(.*?)"  # elseif branch value
    r")*"
    r"(?:"
    r"/\*\s*%else\s*\*/"  # %else (optional)
    r"(.*?)"  # else branch value
    r")?"
    r"/\*\s*%end\s*\*/",  # %end
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class InlineCondition:
    """インライン条件分岐トークン."""

    conditions: tuple[str, ...]
    """条件式のタプル（IF, ELSEIF, ... の順）."""

    values: tuple[str, ...]
    """各条件に対応する値のタプル（最後は ELSE 用）."""

    start: int
    """元文字列内の開始位置."""

    end: int
    """元文字列内の終了位置."""


def parse_inline_conditions(line: str) -> list[InlineCondition]:
    """行からインライン条件分岐をパースする.

    構文: /*%if cond1 */ val1 /*%elseif cond2 */ val2 /*%else */ val3 /*%end*/

    Args:
        line: SQL行文字列

    Returns:
        InlineCondition のリスト

    """
    results: list[InlineCondition] = []

    # 複数の %if...%end を検出するため、手動でパース
    i = 0
    while i < len(line):
        # /*%if を探す
        if_match = re.search(r"/\*\s*%if\s+", line[i:], re.IGNORECASE)
        if not if_match:
            break

        start = i + if_match.start()
        pos = i + if_match.end()

        # 条件を抽出（*/ まで）
        cond_end = line.find("*/", pos)
        if cond_end == -1:
            break
        conditions: list[str] = [line[pos:cond_end].strip()]
        pos = cond_end + 2

        values: list[str] = []

        # ブランチを順にパース
        while pos < len(line):
            # 次のディレクティブを探す
            next_directive = re.search(
                r"/\*\s*%(elseif|else|end)\b",
                line[pos:],
                re.IGNORECASE,
            )
            if not next_directive:
                # %end が見つからない
                break

            # 現在のブランチ値を抽出
            branch_value = line[pos : pos + next_directive.start()].strip()
            values.append(branch_value)

            directive_type = next_directive.group(1).lower()
            pos = pos + next_directive.end()

            if directive_type == "elseif":
                # 条件を抽出
                cond_end = line.find("*/", pos)
                if cond_end == -1:
                    break
                conditions.append(line[pos:cond_end].strip())
                pos = cond_end + 2
            elif directive_type == "else":
                # */ まで進める
                close = line.find("*/", pos)
                if close == -1:
                    break
                pos = close + 2
            elif directive_type == "end":
                # */ まで進める
                close = line.find("*/", pos)
                if close == -1:
                    break
                end = close + 2
                results.append(
                    InlineCondition(
                        conditions=tuple(conditions),
                        values=tuple(values),
                        start=start,
                        end=end,
                    )
                )
                i = end
                break
        else:
            # ループが正常に終了しなかった
            break
        i = pos

    return results


# インクルードディレクティブパターン
# /* %include "relative/path.sql" */
# -- %include "relative/path.sql"
INCLUDE_PATTERN = re.compile(
    r"(?:"
    r"/\*\s*%include\s+[\"']([^\"']+)[\"']\s*\*/"
    r"|"
    r"--\s*%include\s+[\"']([^\"']+)[\"']"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IncludeDirective:
    """インクルードディレクティブ."""

    path: str
    """インクルードする SQL ファイルのパス."""

    start: int
    """元文字列内の開始位置."""

    end: int
    """元文字列内の終了位置."""


def parse_includes(line: str) -> list[IncludeDirective]:
    """行からインクルードディレクティブをパースする.

    Args:
        line: SQL行文字列

    Returns:
        IncludeDirective のリスト

    """
    results: list[IncludeDirective] = []
    for m in INCLUDE_PATTERN.finditer(line):
        # group(1) は /* */ 形式、group(2) は -- 形式
        path = m.group(1) or m.group(2)
        results.append(
            IncludeDirective(
                path=path,
                start=m.start(),
                end=m.end(),
            )
        )
    return results


# 比較演算子パターン（/* param */= 形式）
# col /* param */= 'default' : 値に応じて =, IS NULL, IN に自動変換
# col /* param */<> 'default' : 値に応じて <>, IS NOT NULL, NOT IN に自動変換
OPERATOR_PATTERN = re.compile(
    r"/\*\s*([$&@?!]+)?(\w+)\s*\*/\s*"
    r"(=|<>|!=)"  # 比較演算子
    r"\s*"
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r"|\d+(?:\.\d+)?"  # number
    r"|\w+"  # identifier
    r"|\([^)]*\)"  # (list)
    r"|NULL"  # NULL
    r")"
)

# LIKE パターン（/* param */LIKE 形式）
# col /* param */LIKE 'pattern' : リスト値の場合 OR 展開
# col /* param */NOT LIKE 'pattern' : リスト値の場合 AND 展開（NOT LIKE ... AND NOT LIKE ...）
LIKE_PATTERN = re.compile(
    r"/\*\s*([$&@?!]+)?(\w+)\s*\*/\s*"
    r"(NOT\s+)?LIKE\s+"  # LIKE or NOT LIKE
    r"("
    r"'(?:''|[^'])*'"  # 'string' (SQL escape: '')
    r'|"(?:\"\"|[^"])*"'  # "string" (SQL escape: "")
    r")",
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

    operator: str | None = None
    """比較演算子（=, <>, != など）。自動変換対象の場合に設定."""

    is_partial_in: bool = False
    """IN句内の部分パラメータか（固定値 + パラメータ混在）."""

    is_like: bool = False
    """LIKE パターンか（リスト値で OR 展開）."""

    is_not_like: bool = False
    """NOT LIKE パターンか（リスト値で AND 展開）."""

    helper_func: str | None = None
    """補助関数名（concat, L, STR, SQL）."""

    helper_args: tuple[str, ...] = ()
    """補助関数の引数リスト."""


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

    マッチ優先順位:
    1. IN句パターン
    2. 比較演算子パターン（/* param */= 形式）
    3. フォールバックパターン
    4. 通常パラメータパターン

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

    # 比較演算子パターン（/* param */= 形式）
    for m in OPERATOR_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        modifiers = m.group(1)
        name = m.group(2)
        operator = m.group(3)  # =, <>, !=
        default = m.group(4)
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
                operator=operator,
            )
        )
        used_ranges.append((m.start(), m.end()))

    # LIKE パターン（/* param */LIKE 形式）
    for m in LIKE_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        modifiers = m.group(1)
        name = m.group(2)
        not_prefix = m.group(3)  # "NOT " or None
        default = m.group(4)
        flags = _parse_modifiers(modifiers)
        is_not = not_prefix is not None
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
                is_like=not is_not,
                is_not_like=is_not,
            )
        )
        used_ranges.append((m.start(), m.end()))

    # %concat / %C パターン
    for m in CONCAT_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        args_str = m.group(1)
        default = m.group(2)
        args = _parse_helper_args(args_str)
        # 最初のパラメータ名を抽出（識別子のみ、文字列リテラル以外）
        param_names = [a for a in args if not a.startswith("'") and not a.startswith('"')]
        name = param_names[0] if param_names else "_concat"
        tokens.append(
            Token(
                name=name,
                removable=False,
                default=default,
                is_in_clause=False,
                start=m.start(),
                end=m.end(),
                helper_func="concat",
                helper_args=tuple(args),
            )
        )
        used_ranges.append((m.start(), m.end()))

    # %L パターン（LIKE エスケープ）
    for m in LIKE_ESCAPE_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        args_str = m.group(1)
        default = m.group(2)
        args = _parse_helper_args(args_str)
        param_names = [a for a in args if not a.startswith("'") and not a.startswith('"')]
        name = param_names[0] if param_names else "_like_escape"
        tokens.append(
            Token(
                name=name,
                removable=False,
                default=default,
                is_in_clause=False,
                start=m.start(),
                end=m.end(),
                helper_func="L",
                helper_args=tuple(args),
            )
        )
        used_ranges.append((m.start(), m.end()))

    # %STR / %SQL パターン（直接埋め込み）
    for m in STR_EMBED_PATTERN.finditer(line):
        if _overlaps(m.start(), m.end(), used_ranges):
            continue
        func_name = m.group(1)  # STR or SQL
        name = m.group(2)
        default = m.group(3)
        tokens.append(
            Token(
                name=name,
                removable=False,
                default=default,
                is_in_clause=False,
                start=m.start(),
                end=m.end(),
                helper_func=func_name,
                helper_args=(name,),
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
        # IN 句内の部分パラメータか判定
        is_partial = _is_inside_in_clause(line, m.start(), m.end())
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
                is_partial_in=is_partial,
            )
        )

    tokens.sort(key=lambda t: t.start)
    return tokens


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    """指定範囲が既存範囲と重複するか判定する."""
    return any(start < r_end and end > r_start for r_start, r_end in ranges)


def _parse_helper_args(args_str: str) -> list[str]:
    """補助関数の引数文字列をパースしてリストで返す.

    引数はカンマまたは空白で区切られる。
    文字列リテラル('...', "...")は1つの引数として扱う。

    Args:
        args_str: 引数文字列（例: "'%', param, '%'" または "'%' param '%'"）

    Returns:
        引数のリスト

    """
    args: list[str] = []
    current = ""
    in_single = False
    in_double = False
    i = 0

    while i < len(args_str):
        ch = args_str[i]

        if ch == "'" and not in_double:
            if in_single and i + 1 < len(args_str) and args_str[i + 1] == "'":
                # エスケープされた引用符
                current += "''"
                i += 2
                continue
            in_single = not in_single
            current += ch
        elif ch == '"' and not in_single:
            if in_double and i + 1 < len(args_str) and args_str[i + 1] == '"':
                current += '""'
                i += 2
                continue
            in_double = not in_double
            current += ch
        elif (ch == "," or ch.isspace()) and not in_single and not in_double:
            if current.strip():
                args.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1

    if current.strip():
        args.append(current.strip())

    return args


def _is_inside_in_clause(line: str, start: int, end: int) -> bool:
    """パラメータが IN 句の括弧内にあるか判定する.

    IN ('a', 'b', /* param */'c') のような場合に True を返す。
    IN (/* p1 */1, /* p2 */2) のような複数パラメータも True。
    IN /* param */(...) のような完全な IN 句パラメータは False（IN_PATTERN で処理）。

    Args:
        line: SQL行文字列
        start: パラメータの開始位置
        end: パラメータの終了位置

    Returns:
        IN 句内の部分パラメータなら True

    """
    prefix = line[:start]

    # prefix の末尾から開き括弧を探す（括弧のネストを考慮）
    # IN ( の後にいるかどうかを判定
    paren_depth = 0
    in_found = False
    i = len(prefix) - 1

    while i >= 0:
        ch = prefix[i]
        if ch == ")":
            paren_depth += 1
        elif ch == "(":
            if paren_depth > 0:
                paren_depth -= 1
            else:
                # 対応する開き括弧を見つけた
                # この前に IN があるか確認
                before_paren = prefix[:i].rstrip()
                if re.search(r"\bIN\s*$", before_paren, re.IGNORECASE):
                    in_found = True
                break
        i -= 1

    if not in_found:
        return False

    # パラメータの後に ) があるか確認（カンマ区切りの値があっても可）
    suffix = line[end:]
    # 閉じ括弧まで到達できるか
    close_match = re.search(r"\)", suffix)
    return close_match is not None


def _extract_in_default(matched: str) -> str:
    """IN句マッチ文字列からデフォルトリスト部分を抽出する."""
    paren_start = matched.rfind("(")
    if paren_start >= 0:
        return matched[paren_start:]
    return ""
