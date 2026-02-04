"""Tokenizerのテスト."""

from sqly.parser.tokenizer import Token, tokenize


class TestTokenizeRemovableParam:
    """$付きパラメータ（削除可能）のトークン化を検証する."""

    def test_string_default(self) -> None:
        tokens = tokenize("WHERE name = /* $name */'山田太郎'")
        assert len(tokens) == 1
        t = tokens[0]
        assert t.name == "name"
        assert t.removable is True
        assert t.default == "'山田太郎'"
        assert t.is_in_clause is False

    def test_number_default(self) -> None:
        tokens = tokenize("WHERE age = /* $age */25")
        assert len(tokens) == 1
        assert tokens[0].name == "age"
        assert tokens[0].removable is True
        assert tokens[0].default == "25"

    def test_decimal_default(self) -> None:
        tokens = tokenize("WHERE rate > /* $rate */3.14")
        assert len(tokens) == 1
        assert tokens[0].default == "3.14"

    def test_null_default(self) -> None:
        tokens = tokenize("WHERE deleted_at = /* $deleted_at */NULL")
        assert len(tokens) == 1
        assert tokens[0].default == "NULL"

    def test_identifier_default(self) -> None:
        tokens = tokenize("WHERE status = /* $status */active")
        assert len(tokens) == 1
        assert tokens[0].default == "active"


class TestTokenizeNonRemovableParam:
    """$なしパラメータ（削除不可）のトークン化を検証する."""

    def test_non_removable_string(self) -> None:
        tokens = tokenize("WHERE deleted_at = /* deleted_at */NULL")
        assert len(tokens) == 1
        t = tokens[0]
        assert t.name == "deleted_at"
        assert t.removable is False
        assert t.default == "NULL"

    def test_non_removable_number(self) -> None:
        tokens = tokenize("WHERE id = /* id */1")
        assert len(tokens) == 1
        assert tokens[0].removable is False
        assert tokens[0].default == "1"


class TestTokenizeInClause:
    """IN句パラメータのトークン化を検証する."""

    def test_in_clause_removable(self) -> None:
        tokens = tokenize("WHERE id IN /* $ids */(1, 2, 3)")
        assert len(tokens) == 1
        t = tokens[0]
        assert t.name == "ids"
        assert t.removable is True
        assert t.is_in_clause is True
        assert t.default == "(1, 2, 3)"

    def test_in_clause_non_removable(self) -> None:
        tokens = tokenize("WHERE id IN /* ids */(1, 2, 3)")
        assert len(tokens) == 1
        t = tokens[0]
        assert t.removable is False
        assert t.is_in_clause is True

    def test_in_clause_case_insensitive(self) -> None:
        tokens = tokenize("WHERE id in /* $ids */(1, 2)")
        assert len(tokens) == 1
        assert tokens[0].is_in_clause is True


class TestTokenizeMultipleParams:
    """1行に複数パラメータがある場合を検証する."""

    def test_two_params_in_one_line(self) -> None:
        tokens = tokenize("WHERE name = /* $name */'test' AND age = /* $age */20")
        assert len(tokens) == 2
        assert tokens[0].name == "name"
        assert tokens[1].name == "age"
        assert tokens[0].start < tokens[1].start

    def test_mixed_removable_and_non_removable(self) -> None:
        tokens = tokenize("WHERE name = /* $name */'test' AND status = /* status */'active'")
        assert len(tokens) == 2
        assert tokens[0].removable is True
        assert tokens[1].removable is False


class TestTokenizeNoParams:
    """パラメータなしの行を検証する."""

    def test_plain_sql(self) -> None:
        tokens = tokenize("SELECT * FROM users")
        assert tokens == []

    def test_empty_line(self) -> None:
        tokens = tokenize("")
        assert tokens == []

    def test_regular_comment(self) -> None:
        tokens = tokenize("-- this is a comment")
        assert tokens == []


class TestTokenizePositions:
    """トークンの位置情報を検証する."""

    def test_start_end_positions(self) -> None:
        line = "WHERE name = /* $name */'test'"
        tokens = tokenize(line)
        assert len(tokens) == 1
        t = tokens[0]
        assert line[t.start : t.end] == "/* $name */'test'"

    def test_in_clause_positions(self) -> None:
        line = "WHERE id IN /* $ids */(1, 2, 3)"
        tokens = tokenize(line)
        assert len(tokens) == 1
        t = tokens[0]
        assert line[t.start : t.end] == "IN /* $ids */(1, 2, 3)"


class TestTokenizeNoDefault:
    """デフォルト値なしのパラメータを検証する."""

    def test_no_default_value(self) -> None:
        tokens = tokenize("/* $flag */")
        assert len(tokens) == 1
        assert tokens[0].name == "flag"
        assert tokens[0].default == ""


class TestTokenFrozen:
    """Tokenがイミュータブルであることを検証する."""

    def test_token_is_frozen(self) -> None:
        t = Token(
            name="x",
            removable=True,
            default="1",
            is_in_clause=False,
            start=0,
            end=5,
        )
        try:
            t.name = "y"  # type: ignore[misc]
            msg = "Expected FrozenInstanceError"
            raise AssertionError(msg)
        except AttributeError:
            pass
