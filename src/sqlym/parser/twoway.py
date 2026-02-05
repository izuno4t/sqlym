"""Clione-SQL風 2way SQLパーサー."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlym import config
from sqlym.exceptions import SqlFileNotFoundError, SqlParseError
from sqlym.parser.line_unit import LineUnit
from sqlym.parser.tokenizer import (
    DirectiveType,
    parse_directive,
    parse_includes,
    parse_inline_conditions,
    tokenize,
)

if TYPE_CHECKING:
    from sqlym.dialect import Dialect


def is_negative(value: Any) -> bool:
    """値が negative（無効値）かどうかを判定する.

    以下の値を negative として扱う:
    - None
    - False（Boolean）
    - 空リスト []
    - 全要素が negative のリスト

    Args:
        value: 判定対象の値

    Returns:
        negative の場合 True

    """
    if value is None:
        return True
    if value is False:
        return True
    if isinstance(value, list):
        if len(value) == 0:
            return True
        if all(is_negative(item) for item in value):
            return True
    return False


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
        base_path: str | Path | None = None,
    ) -> None:
        """初期化.

        Args:
            sql: SQLテンプレート
            placeholder: プレースホルダ形式 ("?", "%s", ":name")
            dialect: RDBMS 方言。指定時は dialect.placeholder を使用する。
            base_path: %include ディレクティブの基準パス。指定しない場合はインクルード無効。

        Raises:
            ValueError: dialect と placeholder (デフォルト以外) を同時に指定した場合

        """
        if dialect is not None and placeholder != "?":
            msg = "dialect と placeholder は同時に指定できません"
            raise ValueError(msg)
        self.original_sql = sql
        self.dialect = dialect
        self.placeholder = dialect.placeholder if dialect is not None else placeholder
        self.base_path = Path(base_path) if base_path is not None else None

    def _expand_includes(
        self,
        sql: str,
        current_base: Path,
        included_files: set[Path],
    ) -> str:
        """インクルードディレクティブを展開する.

        構文:
            /* %include "relative/path.sql" */
            -- %include "relative/path.sql"

        循環インクルードを検出した場合は例外をスロー。

        Args:
            sql: SQLテンプレート文字列
            current_base: 現在のベースパス（相対パス解決用）
            included_files: 既にインクルード済みのファイルパスの集合（循環検出用）

        Returns:
            インクルード展開後の SQL 文字列

        Raises:
            SqlParseError: 循環インクルードを検出した場合
            SqlFileNotFoundError: インクルードファイルが見つからない場合

        """
        result_lines: list[str] = []

        for line in sql.split("\n"):
            includes = parse_includes(line)
            if not includes:
                result_lines.append(line)
                continue

            # インクルードディレクティブを後ろから展開
            processed_line = line
            for include in reversed(includes):
                include_path = (current_base / include.path).resolve()

                # 循環インクルードの検出
                if include_path in included_files:
                    msg = f"循環インクルードを検出: {include_path}"
                    raise SqlParseError(msg)

                # ファイルの読み込み
                if not include_path.is_file():
                    msg = f"インクルードファイルが見つかりません: {include_path}"
                    raise SqlFileNotFoundError(msg)

                included_sql = include_path.read_text(encoding="utf-8")

                # 再帰的にインクルードを展開
                new_included_files = included_files | {include_path}
                new_base = include_path.parent
                expanded_sql = self._expand_includes(
                    included_sql,
                    new_base,
                    new_included_files,
                )

                # ディレクティブを展開後の SQL で置換
                processed_line = (
                    processed_line[: include.start]
                    + expanded_sql
                    + processed_line[include.end :]
                )

            result_lines.append(processed_line)

        return "\n".join(result_lines)

    def parse(self, params: dict[str, Any]) -> ParsedSQL:
        """SQLをパースしてパラメータをバインド."""
        # %include ディレクティブを展開
        if self.base_path is not None:
            self.original_sql = self._expand_includes(
                self.original_sql,
                self.base_path,
                included_files=set(),
            )
        units = self._parse_lines()
        units = self._process_block_directives(units, params)
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
        """行をパースしてLineUnitリストを作成(Rule 1).

        複数行にまたがる文字列リテラルは1つの論理行として結合する。
        """
        units: list[LineUnit] = []
        raw_lines = self.original_sql.splitlines()
        i = 0

        while i < len(raw_lines):
            line = raw_lines[i]
            start_line_number = i + 1
            original_lines = [line]

            # 文字列リテラルが閉じていない場合、次の行と結合
            while not self._is_string_closed(line) and i + 1 < len(raw_lines):
                i += 1
                original_lines.append(raw_lines[i])
                line = line + "\n" + raw_lines[i]

            stripped = original_lines[0].lstrip()
            indent = len(original_lines[0]) - len(stripped) if stripped else -1

            # 複数行の場合、content は結合された全体
            if len(original_lines) > 1:
                content = stripped + "\n" + "\n".join(original_lines[1:])
            else:
                content = stripped

            units.append(
                LineUnit(
                    line_number=start_line_number,
                    original="\n".join(original_lines),
                    indent=indent,
                    content=content,
                )
            )
            i += 1

        return units

    @staticmethod
    def _is_string_closed(line: str) -> bool:
        """行内の文字列リテラルがすべて閉じているか判定する."""
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" and not in_double:
                # エスケープされた引用符 '' をスキップ
                if i + 1 < len(line) and line[i + 1] == "'":
                    i += 2
                    continue
                in_single = not in_single
            elif ch == '"' and not in_single:
                # エスケープされた引用符 "" をスキップ
                if i + 1 < len(line) and line[i + 1] == '"':
                    i += 2
                    continue
                in_double = not in_double
            i += 1
        return not in_single and not in_double

    def _process_block_directives(
        self, units: list[LineUnit], params: dict[str, Any]
    ) -> list[LineUnit]:
        """ブロックディレクティブ（%IF/%ELSE/%END）を処理する.

        ディレクティブで囲まれたブロックを条件に応じて残すか削除するかを決定する。
        ディレクティブ行自体は出力から除外される。

        構文:
            -- %IF condition
            ... SQL ...
            -- %ELSEIF another_condition
            ... SQL ...
            -- %ELSE
            ... SQL ...
            -- %END

        条件式は params の値を参照し、positive なら true、negative なら false として評価。
        NOT、AND、OR 演算子をサポート。

        Args:
            units: 行単位リスト
            params: パラメータ辞書

        Returns:
            ディレクティブ処理後の行単位リスト

        Raises:
            SqlParseError: ディレクティブの構文エラー

        """
        result: list[LineUnit] = []
        i = 0

        while i < len(units):
            unit = units[i]
            directive = parse_directive(unit.content)

            if directive is None:
                # 通常の行
                result.append(unit)
                i += 1
                continue

            if directive.type == DirectiveType.IF:
                # %IF ブロックを処理
                end_idx, selected_units = self._process_if_block(
                    units, i, params
                )
                result.extend(selected_units)
                i = end_idx + 1
            elif directive.type in (
                DirectiveType.ELSEIF,
                DirectiveType.ELSE,
                DirectiveType.END,
            ):
                # 対応する %IF なしのディレクティブ
                msg = self._format_error(
                    "directive_without_if",
                    line_number=unit.line_number,
                    sql_line=unit.content,
                )
                raise SqlParseError(msg)
            else:
                result.append(unit)
                i += 1

        return result

    def _process_if_block(
        self, units: list[LineUnit], start_idx: int, params: dict[str, Any]
    ) -> tuple[int, list[LineUnit]]:
        """%IF ブロックを処理する.

        Args:
            units: 全行単位リスト
            start_idx: %IF ディレクティブのインデックス
            params: パラメータ辞書

        Returns:
            (END ディレクティブのインデックス, 選択されたブロックの行単位リスト) のタプル

        Raises:
            SqlParseError: 構文エラー

        """
        # ブロック情報を収集: [(condition, start_idx, end_idx), ...]
        blocks: list[tuple[str | None, int, int]] = []
        if_directive = parse_directive(units[start_idx].content)
        assert if_directive is not None and if_directive.type == DirectiveType.IF

        current_condition = if_directive.condition
        current_start = start_idx + 1
        i = start_idx + 1
        depth = 0  # ネストされた %IF のカウント

        while i < len(units):
            directive = parse_directive(units[i].content)

            if directive is None:
                i += 1
                continue

            if directive.type == DirectiveType.IF:
                # ネストされた %IF
                depth += 1
                i += 1
                continue

            if depth > 0:
                # ネスト内のディレクティブは無視
                if directive.type == DirectiveType.END:
                    depth -= 1
                i += 1
                continue

            if directive.type == DirectiveType.ELSEIF:
                # 現在のブロックを終了し、新しいブロックを開始
                blocks.append((current_condition, current_start, i))
                current_condition = directive.condition
                current_start = i + 1
                i += 1
            elif directive.type == DirectiveType.ELSE:
                # 現在のブロックを終了し、ELSE ブロックを開始
                blocks.append((current_condition, current_start, i))
                current_condition = None  # ELSE は条件なし（常に true）
                current_start = i + 1
                i += 1
            elif directive.type == DirectiveType.END:
                # 最後のブロックを終了
                blocks.append((current_condition, current_start, i))
                end_idx = i
                break
        else:
            # %END が見つからない
            msg = self._format_error(
                "unclosed_if_block",
                line_number=units[start_idx].line_number,
                sql_line=units[start_idx].content,
            )
            raise SqlParseError(msg)

        # 条件を評価して、最初に true となるブロックを選択
        selected_units: list[LineUnit] = []
        for condition, block_start, block_end in blocks:
            if condition is None:
                # ELSE ブロック（条件なし）
                is_true = True
            else:
                is_true = self._evaluate_condition(condition, params)

            if is_true:
                # このブロックを選択（ネストされたディレクティブも処理）
                block_units = units[block_start:block_end]
                selected_units = self._process_block_directives(block_units, params)
                break

        return end_idx, selected_units

    def _evaluate_condition(self, condition: str, params: dict[str, Any]) -> bool:
        """条件式を評価する.

        サポートする構文:
        - param : params[param] が positive なら true
        - NOT param : params[param] が negative なら true
        - param1 AND param2 : 両方が true なら true
        - param1 OR param2 : どちらかが true なら true
        - (expr) : 括弧でグループ化

        優先順位: NOT > AND > OR

        Args:
            condition: 条件式文字列
            params: パラメータ辞書

        Returns:
            条件が true なら True

        """
        return self._parse_or_expr(condition.strip(), params)

    def _parse_or_expr(self, expr: str, params: dict[str, Any]) -> bool:
        """OR 式をパースする."""
        parts = self._split_by_operator(expr, "OR")
        return any(self._parse_and_expr(part.strip(), params) for part in parts)

    def _parse_and_expr(self, expr: str, params: dict[str, Any]) -> bool:
        """AND 式をパースする."""
        parts = self._split_by_operator(expr, "AND")
        return all(self._parse_not_expr(part.strip(), params) for part in parts)

    def _parse_not_expr(self, expr: str, params: dict[str, Any]) -> bool:
        """NOT 式をパースする."""
        expr = expr.strip()
        if expr.upper().startswith("NOT "):
            inner = expr[4:].strip()
            return not self._parse_primary_expr(inner, params)
        return self._parse_primary_expr(expr, params)

    def _parse_primary_expr(self, expr: str, params: dict[str, Any]) -> bool:
        """基本式（識別子または括弧式）をパースする."""
        expr = expr.strip()
        if expr.startswith("(") and expr.endswith(")"):
            # 括弧式を再帰的に評価
            inner = expr[1:-1].strip()
            return self._parse_or_expr(inner, params)
        # 識別子（パラメータ名）
        value = params.get(expr)
        return not is_negative(value)

    @staticmethod
    def _split_by_operator(expr: str, operator: str) -> list[str]:
        """論理演算子で式を分割する（括弧内は無視）."""
        parts: list[str] = []
        current = ""
        depth = 0
        i = 0
        op_upper = operator.upper()
        op_len = len(operator)

        while i < len(expr):
            ch = expr[i]
            if ch == "(":
                depth += 1
                current += ch
                i += 1
            elif ch == ")":
                depth -= 1
                current += ch
                i += 1
            elif depth == 0 and expr[i:i + op_len].upper() == op_upper:
                # 演算子の前後がスペースまたは文字列の端であることを確認
                before_ok = i == 0 or expr[i - 1].isspace()
                after_ok = (
                    i + op_len >= len(expr) or expr[i + op_len].isspace()
                )
                if before_ok and after_ok:
                    parts.append(current)
                    current = ""
                    i += op_len
                else:
                    current += ch
                    i += 1
            else:
                current += ch
                i += 1

        if current:
            parts.append(current)

        return parts if parts else [expr]

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

        $付き(removable) または &付き(bindless) パラメータの値が negative の場合、
        その行を削除対象としてマークする。
        非 removable パラメータは negative でも行を削除しない（NULL バインド）。

        修飾記号:
        - $ : removable（negative時に行削除）
        - & : bindless（negative時に行削除、positive時はプレースホルダなし）
        - ! : negation（negative/positive 判定を反転）
        - @ : required（negative時に例外をスロー）

        negative とは: None, False, 空リスト, 全要素が negative のリスト
        """
        for unit in units:
            if unit.is_empty or unit.removed:
                continue
            tokens = tokenize(unit.content)
            for token in tokens:
                value = params.get(token.name)
                value_is_negative = is_negative(value)

                # ! 修飾子: negative/positive を反転
                if token.negated:
                    value_is_negative = not value_is_negative

                # @ 修飾子: negative 時に例外
                if token.required and value_is_negative:
                    msg = self._format_error(
                        "required_param_missing",
                        line_number=unit.line_number,
                        sql_line=unit.content,
                        param_name=token.name,
                    )
                    raise SqlParseError(msg)

                # フォールバックチェーンの評価
                if token.fallback and token.fallback_names:
                    # 全てのフォールバックパラメータが negative かチェック
                    all_negative = all(
                        is_negative(params.get(name)) for name in token.fallback_names
                    )
                    if all_negative:
                        unit.removed = True
                        break
                    continue

                # $ または & 修飾子: negative 時に行削除
                # ただし IN 句の場合、空リストは IN (NULL) に変換されるため行削除しない
                if (token.removable or token.bindless) and value_is_negative:
                    # IN 句で空リストの場合は行削除しない（IN (NULL) に変換）
                    if token.is_in_clause and isinstance(value, list) and len(value) == 0:
                        continue
                    unit.removed = True
                    break

    def _propagate_removal(self, units: list[LineUnit]) -> None:
        """子が全削除なら親も削除(ボトムアップ処理, Rule 3).

        逆順に走査することで、孫→子→親の順で伝播を実現する。
        子を持つ行が削除された場合、その兄弟でパラメータも子も持たない行
        （閉じ括弧など）も削除対象とする。収束するまで繰り返す。

        例外: SELECT/INSERT/UPDATE/DELETE で始まる行はパラメータを含まない場合でも
        削除対象外とする（CTE 内の SELECT 行を保護）。
        """
        # SELECT/INSERT/UPDATE/DELETE で始まる行は保護対象
        protected_keywords = re.compile(
            r"^(?:SELECT|INSERT|UPDATE|DELETE)\b",
            re.IGNORECASE,
        )

        changed = True
        while changed:
            changed = False
            for unit in reversed(units):
                if unit.is_empty or unit.removed:
                    continue
                if not unit.children:
                    # 子を持たない行: 親があり、兄弟が全て removed なら自身も削除
                    if unit.parent and not tokenize(unit.content):
                        # SELECT 等で始まる行は保護（CTE 内の SELECT を残す）
                        if protected_keywords.match(unit.content):
                            continue
                        siblings = unit.parent.children
                        others = [s for s in siblings if s is not unit]
                        if others and all(s.removed for s in others):
                            unit.removed = True
                            changed = True
                    continue
                if all(child.removed for child in unit.children):
                    # SELECT 等で始まる行は保護（CTE 内の SELECT を残す）
                    if protected_keywords.match(unit.content):
                        continue
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
            # インライン条件分岐を処理
            line = self._process_inline_conditions(line, params)
            tokens = tokenize(line)
            if not tokens:
                # パラメータなし: インデント付きで出力
                indent_str = " " * unit.indent
                result_lines.append(indent_str + line)
                continue

            # トークンを後ろから置換(位置ずれ防止)
            line_params: list[Any] = []
            in_limit = self.dialect.in_clause_limit if self.dialect else None
            for token in reversed(tokens):
                value = self._resolve_value(token, params)

                # & 修飾子（bindless）: プレースホルダを追加せずコメントを除去
                if token.bindless:
                    line = line[: token.start] + line[token.end :]
                    continue

                if token.is_in_clause:
                    if isinstance(value, list):
                        if in_limit and len(value) > in_limit:
                            # IN 句上限超過: (col IN (...) OR col IN (...)) に分割
                            extracted = self._extract_in_clause_column(line, token.start)
                            if extracted is None:
                                msg = self._format_error(
                                    "in_clause_column_unresolved",
                                    line_number=unit.line_number,
                                    sql_line=line,
                                )
                                raise SqlParseError(msg)
                            col_expr, col_start = extracted
                            if is_named:
                                replacement, expanded = self._expand_in_clause_split_named(
                                    token.name,
                                    value,
                                    in_limit,
                                    col_expr,
                                )
                                line = line[:col_start] + replacement + line[token.end :]
                                named_bind_params.update(expanded)
                            else:
                                replacement, expanded = self._expand_in_clause_split(
                                    value,
                                    in_limit,
                                    col_expr,
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
                elif token.operator:
                    # 比較演算子の自動変換
                    replacement, expanded, named_expanded = self._convert_operator(
                        token, value, is_named
                    )
                    line = line[: token.start] + replacement + line[token.end :]
                    if is_named:
                        named_bind_params.update(named_expanded)
                    else:
                        for v in reversed(expanded):
                            line_params.insert(0, v)
                elif token.is_like or token.is_not_like:
                    # LIKE 句のリスト展開
                    col_expr = self._extract_column_before_token(line, token.start)
                    replacement, expanded, named_expanded = self._expand_like(
                        token, value, col_expr, is_named
                    )
                    # 列式を含めて置換
                    col_start = token.start - len(col_expr) - 1  # スペース分
                    # 列式の開始位置を正確に計算
                    prefix = line[:token.start].rstrip()
                    col_start = len(prefix) - len(col_expr)
                    line = line[:col_start] + replacement + line[token.end :]
                    if is_named:
                        named_bind_params.update(named_expanded)
                    else:
                        for v in reversed(expanded):
                            line_params.insert(0, v)
                elif token.is_partial_in and isinstance(value, list):
                    # IN 句の部分展開（固定値 + パラメータ混在）
                    if not value:
                        # 空リスト → NULL
                        line = line[: token.start] + "NULL" + line[token.end :]
                    elif is_named:
                        named = {f"{token.name}_{i}": v for i, v in enumerate(value)}
                        placeholders = ", ".join(f":{k}" for k in named)
                        line = line[: token.start] + placeholders + line[token.end :]
                        named_bind_params.update(named)
                    else:
                        placeholders = ", ".join([self.placeholder] * len(value))
                        line = line[: token.start] + placeholders + line[token.end :]
                        for v in reversed(value):
                            line_params.insert(0, v)
                elif token.helper_func:
                    # 補助関数の処理
                    replacement, expanded_value = self._process_helper_func(
                        token, params, is_named
                    )
                    if token.helper_func in ("STR", "SQL"):
                        # 直接埋め込み（プレースホルダなし）
                        line = line[: token.start] + replacement + line[token.end :]
                    else:
                        # %concat, %L は値をバインド
                        placeholder = f":{token.name}" if is_named else self.placeholder
                        line = line[: token.start] + replacement + line[token.end :]
                        if is_named:
                            named_bind_params[token.name] = expanded_value
                        else:
                            line_params.insert(0, expanded_value)
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

    def _resolve_value(
        self,
        token: Any,
        params: dict[str, Any],
    ) -> Any:
        """トークンに対応する値を解決する.

        ? 修飾子（fallback）の場合、フォールバックチェーンを左から順に
        評価し、最初の positive な値を返す。

        Args:
            token: パラメータトークン
            params: パラメータ辞書

        Returns:
            解決された値

        """
        # フォールバックチェーンの評価
        if token.fallback and token.fallback_names:
            for name in token.fallback_names:
                value = params.get(name)
                if not is_negative(value):
                    return value
            # 全て negative の場合は None を返す（行削除済みのはず）
            return None

        return params.get(token.name)

    def _convert_operator(
        self,
        token: Any,
        value: Any,
        is_named: bool,
    ) -> tuple[str, list[Any], dict[str, Any]]:
        """比較演算子を値に応じて自動変換する.

        変換規則:
        - None/空リスト → IS NULL / IS NOT NULL
        - スカラー/1要素リスト → = ? / <> ?
        - 2要素以上のリスト → IN (?, ...) / NOT IN (?, ...)

        Args:
            token: パラメータトークン（operator属性を持つ）
            value: パラメータ値
            is_named: 名前付きプレースホルダを使用するか

        Returns:
            (置換文字列, バインドパラメータリスト, 名前付きパラメータ辞書) のタプル

        """
        operator = token.operator
        is_negation = operator in ("<>", "!=")

        # None または空リスト → IS NULL / IS NOT NULL
        if value is None or (isinstance(value, list) and len(value) == 0):
            if is_negation:
                return "IS NOT NULL", [], {}
            return "IS NULL", [], {}

        # リストの場合
        if isinstance(value, list):
            if len(value) == 1:
                # 1要素リスト → = ? / <> ?
                op = "<>" if is_negation else "="
                if is_named:
                    return f"{op} :{token.name}", [], {token.name: value[0]}
                return f"{op} {self.placeholder}", [value[0]], {}
            # 2要素以上 → IN / NOT IN
            not_prefix = "NOT " if is_negation else ""
            if is_named:
                named = {f"{token.name}_{i}": v for i, v in enumerate(value)}
                placeholders = ", ".join(f":{k}" for k in named)
                return f"{not_prefix}IN ({placeholders})", [], named
            placeholders = ", ".join([self.placeholder] * len(value))
            return f"{not_prefix}IN ({placeholders})", list(value), {}

        # スカラー値 → = ? / <> ?
        op = "<>" if is_negation else "="
        if is_named:
            return f"{op} :{token.name}", [], {token.name: value}
        return f"{op} {self.placeholder}", [value], {}

    def _extract_column_before_token(self, line: str, token_start: int) -> str:
        """トークン前の列式を抽出する.

        Args:
            line: SQL行文字列
            token_start: トークンの開始位置

        Returns:
            列式文字列（例: "FIELD1", "t.name"）

        """
        prefix = line[:token_start].rstrip()
        # 末尾の識別子を抽出
        extracted = self._extract_in_clause_column(line, token_start)
        if extracted:
            return extracted[0]
        # フォールバック: 最後の単語を取得
        match = re.search(r"(\w+(?:\.\w+)?)\s*$", prefix)
        if match:
            return match.group(1)
        return ""

    def _expand_like(
        self,
        token: Any,
        value: Any,
        col_expr: str,
        is_named: bool,
    ) -> tuple[str, list[Any], dict[str, Any]]:
        """LIKE 句を値に応じて展開する.

        スカラー値の場合: col LIKE ?
        リスト値の場合: (col LIKE ? OR col LIKE ? OR ...)
        NOT LIKE の場合: (col NOT LIKE ? AND col NOT LIKE ? AND ...)

        Args:
            token: パラメータトークン
            value: パラメータ値
            col_expr: 列式
            is_named: 名前付きプレースホルダを使用するか

        Returns:
            (置換文字列, バインドパラメータリスト, 名前付きパラメータ辞書) のタプル

        """
        like_kw = "NOT LIKE" if token.is_not_like else "LIKE"
        joiner = " AND " if token.is_not_like else " OR "

        # スカラー値または None
        if not isinstance(value, list):
            if is_named:
                return f"{col_expr} {like_kw} :{token.name}", [], {token.name: value}
            return f"{col_expr} {like_kw} {self.placeholder}", [value], {}

        # 空リスト
        if not value:
            # 空リストの場合: LIKE は常に偽 (1=0)、NOT LIKE は常に真 (1=1)
            if token.is_not_like:
                return "1=1", [], {}
            return "1=0", [], {}

        # リスト値 → OR/AND 展開
        if is_named:
            named: dict[str, Any] = {}
            parts: list[str] = []
            for i, v in enumerate(value):
                key = f"{token.name}_{i}"
                named[key] = v
                parts.append(f"{col_expr} {like_kw} :{key}")
            return f"({joiner.join(parts)})", [], named

        parts = [f"{col_expr} {like_kw} {self.placeholder}" for _ in value]
        return f"({joiner.join(parts)})", list(value), {}

    def _process_inline_conditions(
        self, line: str, params: dict[str, Any]
    ) -> str:
        """インライン条件分岐を処理する.

        構文: /*%if cond1 */ val1 /*%elseif cond2 */ val2 /*%else */ val3 /*%end*/

        Args:
            line: SQL行文字列
            params: パラメータ辞書

        Returns:
            条件分岐を解決後の行文字列

        """
        conditions = parse_inline_conditions(line)
        if not conditions:
            return line

        # 後ろから置換（位置ずれ防止）
        for cond in reversed(conditions):
            selected_value = ""
            found = False

            # 条件を順に評価
            for i, condition in enumerate(cond.conditions):
                if self._evaluate_condition(condition, params):
                    selected_value = cond.values[i] if i < len(cond.values) else ""
                    found = True
                    break

            # どの条件も true でなければ、else 値を使用（あれば）
            if not found and len(cond.values) > len(cond.conditions):
                selected_value = cond.values[-1]

            line = line[: cond.start] + selected_value + line[cond.end :]

        return line

    def _process_helper_func(
        self,
        token: Any,
        params: dict[str, Any],
        is_named: bool,
    ) -> tuple[str, Any]:
        """補助関数を処理する.

        Args:
            token: パラメータトークン（helper_func, helper_args を持つ）
            params: パラメータ辞書
            is_named: 名前付きプレースホルダを使用するか

        Returns:
            (置換文字列, バインドする値) のタプル

        """
        func = token.helper_func
        args = token.helper_args

        if func == "concat":
            # %concat / %C: 引数を連結
            result_parts: list[str] = []
            for arg in args:
                if arg.startswith("'") and arg.endswith("'"):
                    # 文字列リテラル
                    result_parts.append(arg[1:-1].replace("''", "'"))
                elif arg.startswith('"') and arg.endswith('"'):
                    result_parts.append(arg[1:-1].replace('""', '"'))
                else:
                    # パラメータ名
                    val = params.get(arg)
                    if val is not None:
                        result_parts.append(str(val))
            concatenated = "".join(result_parts)
            placeholder = f":{token.name}" if is_named else self.placeholder
            return placeholder, concatenated

        if func == "L":
            # %L: LIKE エスケープ + escape 句付与
            from sqlym.dialect import Dialect
            from sqlym.escape_utils import escape_like

            # dialect が設定されていない場合は SQLITE をデフォルト
            dialect = self.dialect if self.dialect else Dialect.SQLITE

            result_parts = []
            for arg in args:
                if arg.startswith("'") and arg.endswith("'"):
                    result_parts.append(arg[1:-1].replace("''", "'"))
                elif arg.startswith('"') and arg.endswith('"'):
                    result_parts.append(arg[1:-1].replace('""', '"'))
                else:
                    val = params.get(arg)
                    if val is not None:
                        # パラメータ値を LIKE エスケープ
                        escaped = escape_like(str(val), dialect, escape_char="#")
                        result_parts.append(escaped)
            concatenated = "".join(result_parts)
            placeholder = f":{token.name}" if is_named else self.placeholder
            # escape 句を付与
            return f"{placeholder} escape '#'", concatenated

        if func in ("STR", "SQL"):
            # %STR / %SQL: 直接埋め込み（SQLインジェクション注意）
            val = params.get(token.name, token.default)
            if val is None:
                val = token.default
            return str(val), None

        # 未知の補助関数はデフォルト値を返す
        return token.default, None

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
        self,
        values: list[Any],
        limit: int,
        col_expr: str,
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
        self,
        name: str,
        values: list[Any],
        limit: int,
        col_expr: str,
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
        """不要なWHERE/AND/OR/空括弧/行末区切り/孤立UNION行を除去."""
        lines = sql.split("\n")

        # 0. 孤立した区切り行（UNION/UNION ALL/EXCEPT/INTERSECT）を除去
        # これらの行は前後に有効な SELECT が必要
        lines = self._remove_orphan_set_operators(lines)

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

        # 2. 行末の AND/OR を除去（次の行が削除された場合に残る）
        sql = re.sub(
            r"[ \t]+(?:AND|OR)[ \t]*$",
            "",
            sql,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # 3. 行末のカンマを除去（次の行が削除された場合に残る）
        # ただし、括弧内の最後の要素のカンマのみ（SELECT句等は除外）
        sql = self._remove_trailing_commas(sql)

        # 4. WHERE/HAVING 直後の先頭 AND/OR を除去
        sql = re.sub(
            r"(\b(?:WHERE|HAVING)\b[ \t]*\n(?:[ \t]*\n)*)([ \t]+)(?:AND|OR)\b[ \t]+",
            r"\1\2",
            sql,
            flags=re.IGNORECASE,
        )

        # 5. 条件のない孤立 WHERE/HAVING を除去（SQL末尾）
        sql = re.sub(
            r"\n?[ \t]*\b(?:WHERE|HAVING)\b[ \t]*(?:\n[ \t]*)*$",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # 6. 条件のない WHERE/HAVING を除去（後続に別のSQL句がある場合）
        next_clause = r"ORDER|GROUP|LIMIT|UNION|EXCEPT|INTERSECT|FETCH|OFFSET|FOR"
        sql = re.sub(
            rf"[ \t]*\b(?:WHERE|HAVING)\b[ \t]*\n(?=[ \t]*\b(?:{next_clause})\b)",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    def _remove_trailing_commas(self, sql: str) -> str:
        """閉じ括弧の直前にある行末カンマを除去する."""
        lines = sql.split("\n")
        result: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # 行末がカンマで終わっていて、後続の非空行が ) で始まる場合
            if stripped.endswith(","):
                # 後続行を探す
                for j in range(i + 1, len(lines)):
                    next_stripped = lines[j].strip()
                    if next_stripped:
                        if next_stripped.startswith(")"):
                            # カンマを除去
                            line = stripped[:-1] + line[len(stripped) :]
                        break
            result.append(line)

        return "\n".join(result)

    def _remove_orphan_set_operators(self, lines: list[str]) -> list[str]:
        """孤立した集合演算子行（UNION/EXCEPT/INTERSECT）を除去する.

        集合演算子は前後に有効なクエリ（SELECT等）が必要。
        処理順序:
        1. 前後に有効なクエリがない集合演算子を除去（繰り返し）
        2. 連続する集合演算子は最初の1つだけ残す
        """
        set_op_pattern = re.compile(
            r"^\s*(?:UNION\s+ALL|UNION|EXCEPT|INTERSECT)\s*$",
            re.IGNORECASE,
        )

        def is_set_operator(line: str) -> bool:
            return set_op_pattern.match(line) is not None

        def find_valid_query_before(idx: int, lines_: list[str]) -> bool:
            """インデックス前に有効なクエリ行があるか確認."""
            for j in range(idx - 1, -1, -1):
                stripped = lines_[j].strip()
                if stripped and not is_set_operator(lines_[j]):
                    return True
            return False

        def find_valid_query_after(idx: int, lines_: list[str]) -> bool:
            """インデックス後に有効なクエリ行があるか確認."""
            for j in range(idx + 1, len(lines_)):
                stripped = lines_[j].strip()
                if stripped and not is_set_operator(lines_[j]):
                    return True
            return False

        # フェーズ1: 前後に有効なクエリがない集合演算子を除去
        changed = True
        while changed:
            changed = False
            result: list[str] = []

            for i, line in enumerate(lines):
                if not is_set_operator(line):
                    result.append(line)
                    continue

                has_before = find_valid_query_before(i, lines)
                has_after = find_valid_query_after(i, lines)

                if has_before and has_after:
                    result.append(line)
                else:
                    changed = True

            lines = result

        # フェーズ2: 連続する集合演算子は最初の1つだけ残す
        result = []
        prev_was_set_op = False
        for line in lines:
            if is_set_operator(line):
                if not prev_was_set_op:
                    result.append(line)
                    prev_was_set_op = True
                # 連続する場合はスキップ
            else:
                result.append(line)
                if line.strip():
                    prev_was_set_op = False

        return result

    @staticmethod
    def _format_error(
        key: str,
        *,
        line_number: int,
        sql_line: str,
        param_name: str | None = None,
    ) -> str:
        messages = {
            "ja": {
                "in_clause_column_unresolved": "IN句分割の列式を抽出できません",
                "required_param_missing": "必須パラメータが指定されていません",
                "directive_without_if": "対応する %IF がないディレクティブです",
                "unclosed_if_block": "%IF ブロックが閉じられていません（%END が必要）",
            },
            "en": {
                "in_clause_column_unresolved": (
                    "Failed to extract column expression for IN clause split"
                ),
                "required_param_missing": "Required parameter is missing",
                "directive_without_if": "Directive without matching %IF",
                "unclosed_if_block": "Unclosed %IF block (missing %END)",
            },
        }
        lang = config.ERROR_MESSAGE_LANGUAGE
        base = messages.get(lang, messages["ja"]).get(key, key)
        msg = f"{base}: line={line_number}"
        if param_name:
            msg = f"{msg} param='{param_name}'"
        if config.ERROR_INCLUDE_SQL:
            msg = f"{msg} sql='{sql_line.strip()}'"
        return msg

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
