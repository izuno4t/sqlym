"""行単位処理ユニット（Clione-SQL Rule 1）."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LineUnit:
    """1行を表すユニット（Clione-SQL Rule 1）."""

    line_number: int
    """元のSQL内での行番号."""

    original: str
    """元の行文字列."""

    indent: int
    """インデント深さ."""

    content: str
    """インデント除去後の内容."""

    children: list[LineUnit] = field(default_factory=list)
    """子LineUnitのリスト."""

    parent: LineUnit | None = None
    """親LineUnit."""

    removed: bool = False
    """削除フラグ."""

    def __repr__(self) -> str:
        """デバッグ用の文字列表現."""
        return f"LineUnit(line={self.line_number}, indent={self.indent}, removed={self.removed})"

    @property
    def is_empty(self) -> bool:
        """空行かどうか."""
        return self.indent < 0 or not self.content.strip()
