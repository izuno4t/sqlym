"""DataclassMapper: dataclass 用の自動マッパー."""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints

from sqly.mapper.column import Column


class DataclassMapper:
    """Dataclass 用の自動マッパー."""

    _mapping_cache: ClassVar[dict[type, dict[str, str]]] = {}

    def __init__(self, entity_cls: type) -> None:
        if not is_dataclass(entity_cls):
            msg = f"{entity_cls} is not a dataclass"
            raise TypeError(msg)
        self.entity_cls = entity_cls
        self._mapping = self._get_mapping(entity_cls)

    @classmethod
    def _get_mapping(cls, entity_cls: type) -> dict[str, str]:
        """フィールド名→カラム名のマッピングを取得（キャッシュ付き）."""
        if entity_cls not in cls._mapping_cache:
            cls._mapping_cache[entity_cls] = cls._build_mapping(entity_cls)
        return cls._mapping_cache[entity_cls]

    @classmethod
    def _build_mapping(cls, entity_cls: type) -> dict[str, str]:
        """フィールド名→カラム名のマッピングを構築."""
        hints = get_type_hints(entity_cls, include_extras=True)
        column_map: dict[str, str] = getattr(entity_cls, "__column_map__", {})
        naming: str = getattr(entity_cls, "__column_naming__", "as_is")

        mapping: dict[str, str] = {}

        for f in fields(entity_cls):
            field_name = f.name

            # 1. Annotated[..., Column("X")] をチェック
            type_hint = hints.get(field_name)
            if type_hint and get_origin(type_hint) is Annotated:
                for arg in get_args(type_hint)[1:]:
                    if isinstance(arg, Column):
                        mapping[field_name] = arg.name
                        break

            if field_name in mapping:
                continue

            # 2. column_map をチェック
            if field_name in column_map:
                mapping[field_name] = column_map[field_name]
                continue

            # 3. naming ルール適用
            if naming == "snake_to_camel":
                mapping[field_name] = cls._to_camel(field_name)
            elif naming == "camel_to_snake":
                mapping[field_name] = cls._to_snake(field_name)
            else:
                mapping[field_name] = field_name

        return mapping

    @staticmethod
    def _to_camel(name: str) -> str:
        """Snake_case → camelCase."""
        components = name.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    @staticmethod
    def _to_snake(name: str) -> str:
        """CamelCase → snake_case."""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def map_row(self, row: dict[str, Any]) -> Any:
        """1行をエンティティに変換."""
        row_lower = {k.lower(): v for k, v in row.items()}
        kwargs: dict[str, Any] = {}
        for field_name, col_name in self._mapping.items():
            if col_name in row:
                kwargs[field_name] = row[col_name]
            elif col_name.lower() in row_lower:
                kwargs[field_name] = row_lower[col_name.lower()]
            elif field_name in row:
                kwargs[field_name] = row[field_name]
            elif field_name.lower() in row_lower:
                kwargs[field_name] = row_lower[field_name.lower()]
        return self.entity_cls(**kwargs)

    def map_rows(self, rows: list[dict[str, Any]]) -> list[Any]:
        """複数行をエンティティのリストに変換."""
        return [self.map_row(row) for row in rows]
