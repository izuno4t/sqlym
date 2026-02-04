"""Clione-SQL風 2way SQLパーサー."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqly.exceptions import SqlParseError
from sqly.parser.line_unit import LineUnit
from sqly.parser.tokenizer import tokenize

if TYPE_CHECKING:
    from sqly.dialect import Dialect


@dataclass
class ParsedSQL:
    """パース結果."""

    sql: str
    params: list[Any] = field(default_factory=list)
    """?形式用."""

    named_params: dict[str, Any] = field(default_factory=dict)
    """:name形式用."""


class TwoWaySQLParser:
    """Clione-SQL風 2way SQLパーサー."""

    def __init__(
        self,
        sql: str,
        placeholder: str = "?",
        *,
        dialect: Dialect | None = None,
    ) -> None:
        """初期化.

        Args:
            sql: SQLテンプレート
            placeholder: プレースホルダ形式 ("?", "%s", ":name")
            dialect: RDBMS 方言。指定時は dialect.placeholder を使用する。

        Raises:
            ValueError: dialect と placeholder (デフォルト以外) を同時に指定した場合

        """
        if dialect is not None and placeholder != "?":
            msg = "dialect と placeholder は同時に指定できません"
            raise ValueError(msg)
        self.original_sql = sql
        self.dialect = dialect
        self.placeholder = dialect.placeholder if dialect is not None else placeholder

    def parse(self, params: dict[str, Any]) -> ParsedSQL:
        """SQLをパースしてパラメータをバインド."""
        units = self._parse_lines()
        self._build_tree(units)
        self._evaluate_params(units, params)
        self._propagate_removal(units)
        sql, bind_params, named_bind_params = self._rebuild_sql(units, params)
        sql = self._clean_sql(sql)
        if self.placeholder == ":name":
            return ParsedSQL(
                sql=sql,
                params=[],
                named_params=named_bind_params,
            )
        return ParsedSQL(
            sql=sql,
            params=bind_params,
            named_params=params,
        )

    def _parse_lines(self) -> list[LineUnit]:
        """行をパースしてLineUnitリストを作成(Rule 1)."""
        units: list[LineUnit] = []
        for i, line in enumerate(self.original_sql.splitlines()):
            stripped = line.lstrip()
            indent = len(line) - len(stripped) if stripped else -1
            units.append(
                LineUnit(
                    line_number=i + 1,
                    original=line,
                    indent=indent,
                    content=stripped,
                )
            )
        return units

    def _build_tree(self, units: list[LineUnit]) -> None:
        """インデントに基づいて親子関係を構築(Rule 2)."""
        stack: list[LineUnit] = []
        for unit in units:
            if unit.is_empty:
                continue
            # スタックから現在行と同じかより深いインデントを持つものを除去
            while stack and stack[-1].indent >= unit.indent:
                stack.pop()
            # スタックが残っていれば、その先頭が親
            if stack:
                unit.parent = stack[-1]
                stack[-1].children.append(unit)
            stack.append(unit)

    def _evaluate_params(self, units: list[LineUnit], params: dict[str, Any]) -> None:
        """パラメータを評価して行の削除を決定(Rule 4).

        $付き(removable)パラメータの値が None または params に存在しない場合、
        その行を削除対象としてマークする。
        非 removable パラメータは None でも行を削除しない（NULL バインド）。
        """
        for unit in units:
            if unit.is_empty or unit.removed:
                continue
            tokens = tokenize(unit.content)
            for token in tokens:
                if token.removable and params.get(token.name) is None:
                    unit.removed = True
                    break

    def _propagate_removal(self, units: list[LineUnit]) -> None:
        """子が全削除なら親も削除(ボトムアップ処理, Rule 3).

        逆順に走査することで、孫→子→親の順で伝播を実現する。
        子を持つ行が削除された場合、その兄弟でパラメータも子も持たない行
        （閉じ括弧など）も削除対象とする。収束するまで繰り返す。
        """
        changed = True
        while changed:
            changed = False
            for unit in reversed(units):
                if unit.is_empty or unit.removed:
                    continue
                if not unit.children:
                    # 子を持たない行: 親があり、兄弟が全て removed なら自身も削除
                    if unit.parent and not tokenize(unit.content):
                        siblings = unit.parent.children
                        others = [s for s in siblings if s is not unit]
                        if others and all(s.removed for s in others):
                            unit.removed = True
                            changed = True
                    continue
                if all(child.removed for child in unit.children):
                    unit.removed = True
                    changed = True

    def _rebuild_sql(
        self, units: list[LineUnit], params: dict[str, Any]
    ) -> tuple[str, list[Any], dict[str, Any]]:
        """削除されていない行からSQLを再構築."""
        result_lines: list[str] = []
        bind_params: list[Any] = []
        named_bind_params: dict[str, Any] = {}
        is_named = self.placeholder == ":name"

        for unit in units:
            if unit.removed:
                continue
            if unit.is_empty:
                result_lines.append(unit.original)
                continue

            line = unit.content
            tokens = tokenize(line)
            if not tokens:
                # パラメータなし: インデント付きでそのまま出力
                result_lines.append(unit.original)
                continue

            # トークンを後ろから置換(位置ずれ防止)
            line_params: list[Any] = []
            in_limit = self.dialect.in_clause_limit if self.dialect else None
            for token in reversed(tokens):
                value = params.get(token.name)
                if token.is_in_clause:
                    if isinstance(value, list):
                        if in_limit and len(value) > in_limit:
                            # IN 句上限超過: (col IN (...) OR col IN (...)) に分割
                            extracted = self._extract_in_clause_column(line, token.start)
                            if extracted is None:
                                msg = "IN句分割の列式を抽出できません"
                                raise SqlParseError(msg)
                            col_expr, col_start = extracted
                            if is_named:
                                replacement, expanded = self._expand_in_clause_split_named(
                                    token.name, value, in_limit, col_expr,
                                )
                                line = line[:col_start] + replacement + line[token.end :]
                                named_bind_params.update(expanded)
                            else:
                                replacement, expanded = self._expand_in_clause_split(
                                    value, in_limit, col_expr,
                                )
                                line = line[:col_start] + replacement + line[token.end :]
                                for v in reversed(expanded):
                                    line_params.insert(0, v)
                        elif is_named:
                            replacement, expanded = self._expand_in_clause_named(token.name, value)
                            line = line[: token.start] + replacement + line[token.end :]
                            named_bind_params.update(expanded)
                        else:
                            replacement, expanded = self._expand_in_clause(value)
                            line = line[: token.start] + replacement + line[token.end :]
                            for v in reversed(expanded):
                                line_params.insert(0, v)
                    else:
                        # リストでない値（None等）は単一要素として IN (:name) に展開
                        placeholder = f":{token.name}" if is_named else self.placeholder
                        line = line[: token.start] + f"IN ({placeholder})" + line[token.end :]
                        if is_named:
                            named_bind_params[token.name] = value
                        else:
                            line_params.insert(0, value)
                else:
                    placeholder = f":{token.name}" if is_named else self.placeholder
                    line = line[: token.start] + placeholder + line[token.end :]
                    if is_named:
                        named_bind_params[token.name] = value
                    else:
                        line_params.insert(0, value)
            bind_params.extend(line_params)

            # 元のインデントを復元
            indent_str = " " * unit.indent
            result_lines.append(indent_str + line)

        return "\n".join(result_lines), bind_params, named_bind_params

    def _expand_in_clause(self, values: list[Any]) -> tuple[str, list[Any]]:
        """IN句のリストをプレースホルダに展開する.

        Args:
            values: バインドする値のリスト

        Returns:
            (置換文字列, バインドパラメータリスト) のタプル

        """
        if not values:
            return "IN (NULL)", []
        placeholders = ", ".join([self.placeholder] * len(values))
        return f"IN ({placeholders})", list(values)

    def _expand_in_clause_named(self, name: str, values: list[Any]) -> tuple[str, dict[str, Any]]:
        """IN句のリストを名前付きプレースホルダに展開する.

        Args:
            name: パラメータ名
            values: バインドする値のリスト

        Returns:
            (置換文字列, 名前付きバインドパラメータ辞書) のタプル

        """
        if not values:
            return "IN (NULL)", {}
        named = {f"{name}_{i}": v for i, v in enumerate(values)}
        placeholders = ", ".join(f":{k}" for k in named)
        return f"IN ({placeholders})", named

    def _expand_in_clause_split(
        self, values: list[Any], limit: int, col_expr: str,
    ) -> tuple[str, list[Any]]:
        """IN句のリストを上限で分割してOR結合する.

        Args:
            values: バインドする値のリスト
            limit: 1つのIN句あたりの要素数上限
            col_expr: カラム式（例: "dept_id", "e.id"）

        Returns:
            (置換文字列, バインドパラメータリスト) のタプル

        """
        chunks = [values[i : i + limit] for i in range(0, len(values), limit)]
        parts: list[str] = []
        for chunk in chunks:
            phs = ", ".join([self.placeholder] * len(chunk))
            parts.append(f"{col_expr} IN ({phs})")
        return "(" + " OR ".join(parts) + ")", list(values)

    def _expand_in_clause_split_named(
        self, name: str, values: list[Any], limit: int, col_expr: str,
    ) -> tuple[str, dict[str, Any]]:
        """IN句のリストを上限で分割して名前付きプレースホルダでOR結合する.

        Args:
            name: パラメータ名
            values: バインドする値のリスト
            limit: 1つのIN句あたりの要素数上限
            col_expr: カラム式（例: "dept_id", "e.id"）

        Returns:
            (置換文字列, 名前付きバインドパラメータ辞書) のタプル

        """
        chunks = [values[i : i + limit] for i in range(0, len(values), limit)]
        parts: list[str] = []
        named: dict[str, Any] = {}
        idx = 0
        for chunk in chunks:
            chunk_keys: list[str] = []
            for v in chunk:
                key = f"{name}_{idx}"
                named[key] = v
                chunk_keys.append(f":{key}")
                idx += 1
            parts.append(f"{col_expr} IN ({', '.join(chunk_keys)})")
        return "(" + " OR ".join(parts) + ")", named

    def _clean_sql(self, sql: str) -> str:
        """不要なWHERE/AND/OR/空括弧を除去."""
        lines = sql.split("\n")

        # 1. 対応する開き括弧がない ')' だけの行を除去
        paren_stack: list[int] = []
        remove_indices: set[int] = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == ")":
                if paren_stack:
                    paren_stack.pop()
                else:
                    remove_indices.add(i)
            elif stripped.endswith("("):
                opens = stripped.count("(")
                closes = stripped.count(")")
                if opens > closes:
                    paren_stack.append(i)
        lines = [line for i, line in enumerate(lines) if i not in remove_indices]
        sql = "\n".join(lines)

        # 2. WHERE/HAVING 直後の先頭 AND/OR を除去
        sql = re.sub(
            r"(\b(?:WHERE|HAVING)\b[ \t]*\n(?:[ \t]*\n)*)([ \t]+)(?:AND|OR)\b[ \t]+",
            r"\1\2",
            sql,
            flags=re.IGNORECASE,
        )

        # 3. 条件のない孤立 WHERE/HAVING を除去（SQL末尾）
        sql = re.sub(
            r"\n?[ \t]*\b(?:WHERE|HAVING)\b[ \t]*(?:\n[ \t]*)*$",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # 4. 条件のない WHERE/HAVING を除去（後続に別のSQL句がある場合）
        next_clause = r"ORDER|GROUP|LIMIT|UNION|EXCEPT|INTERSECT|FETCH|OFFSET|FOR"
        sql = re.sub(
            rf"[ \t]*\b(?:WHERE|HAVING)\b[ \t]*\n(?=[ \t]*\b(?:{next_clause})\b)",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    @staticmethod
    def _extract_in_clause_column(line: str, token_start: int) -> tuple[str, int] | None:
        """IN句分割用に列式を抽出する.

        末尾が識別子/引用符付き識別子/関数呼び出し/括弧式の場合に対応する。
        抽出できない場合は None を返す。
        """
        prefix = line[:token_start].rstrip()
        if not prefix:
            return None
        end = len(prefix) - 1

        if prefix[end] == ")":
            open_idx = TwoWaySQLParser._find_matching_open_paren(prefix, end)
            if open_idx is None:
                return None
            expr_start = open_idx
            func_start = TwoWaySQLParser._parse_identifier_chain(prefix, open_idx - 1)
            if func_start is not None:
                expr_start = func_start
            return prefix[expr_start : end + 1].strip(), expr_start

        ident_start = TwoWaySQLParser._parse_identifier_chain(prefix, end)
        if ident_start is None:
            return None
        return prefix[ident_start : end + 1].strip(), ident_start

    @staticmethod
    def _parse_identifier_chain(s: str, end: int) -> int | None:
        """末尾の識別子/引用符付き識別子の連鎖を抽出して開始位置を返す."""
        i = end
        while i >= 0 and s[i].isspace():
            i -= 1
        if i < 0:
            return None

        start = TwoWaySQLParser._parse_identifier_segment(s, i)
        if start is None:
            return None
        i = start - 1

        while i >= 0:
            if s[i].isspace():
                return start
            if s[i] != ".":
                return start
            i -= 1
            seg_start = TwoWaySQLParser._parse_identifier_segment(s, i)
            if seg_start is None:
                return start
            start = seg_start
            i = start - 1

        return start

    @staticmethod
    def _parse_identifier_segment(s: str, end: int) -> int | None:
        """識別子セグメントを解析し開始位置を返す."""
        if end < 0:
            return None
        if s[end] == '"':
            i = end - 1
            while i >= 0:
                if s[i] == '"':
                    if i - 1 >= 0 and s[i - 1] == '"':
                        i -= 2
                        continue
                    return i
                i -= 1
            return None
        if not TwoWaySQLParser._is_ident_char(s[end]):
            return None
        i = end
        while i >= 0 and TwoWaySQLParser._is_ident_char(s[i]):
            i -= 1
        start = i + 1
        if not s[start].isalpha() and s[start] != "_":
            return None
        return start

    @staticmethod
    def _is_ident_char(ch: str) -> bool:
        return ch.isalnum() or ch in {"_", "$"}

    @staticmethod
    def _find_matching_open_paren(s: str, close_idx: int) -> int | None:
        """close_idx に対応する '(' の位置を返す（簡易バランス）."""
        depth = 0
        in_single = False
        in_double = False
        i = close_idx
        while i >= 0:
            ch = s[i]
            if ch == "'" and not in_double:
                if i > 0 and s[i - 1] == "'":
                    i -= 2
                    continue
                in_single = not in_single
                i -= 1
                continue
            if ch == '"' and not in_single:
                if i > 0 and s[i - 1] == '"':
                    i -= 2
                    continue
                in_double = not in_double
                i -= 1
                continue
            if in_single or in_double:
                i -= 1
                continue
            if ch == ")":
                depth += 1
            elif ch == "(":
                depth -= 1
                if depth == 0:
                    return i
            i -= 1
        return None
