# sqlym 実装案（設計案）

## 1. パッケージ構成

```
sqlym/
├── __init__.py          # 公開API
├── _parse.py            # parse_sql便利関数
├── config.py            # エラーメッセージ設定
├── dialect.py           # Dialect enum（RDBMS方言）
├── escape_utils.py      # LIKEエスケープ等ユーティリティ
├── exceptions.py        # 例外クラス
├── loader.py            # SQLファイル読み込み
├── parser/
│   ├── __init__.py
│   ├── tokenizer.py     # SQLトークナイザー
│   ├── line_unit.py     # 行単位処理
│   └── twoway.py        # 2way SQLパーサー本体
└── mapper/
    ├── __init__.py
    ├── protocol.py      # RowMapperプロトコル
    ├── dataclass.py     # dataclass用マッパー
    ├── pydantic.py      # Pydantic用マッパー
    ├── column.py        # カラムマッピング
    ├── manual.py        # ManualMapper
    └── factory.py       # create_mapperファクトリ
```

---

## 2. コアクラス設計

### 2.1 LineUnit（行単位）

```python
# sqlym/parser/line_unit.py

from dataclasses import dataclass, field

@dataclass
class LineUnit:
    """1行を表すユニット（Clione-SQL Rule 1）"""
    
    line_number: int          # 元のSQL内での行番号
    original: str             # 元の行文字列
    indent: int               # インデント深さ
    content: str              # インデント除去後の内容
    children: list['LineUnit'] = field(default_factory=list)
    parent: 'LineUnit | None' = None
    removed: bool = False     # 削除フラグ
    
    @property
    def is_empty(self) -> bool:
        """空行かどうか"""
        return self.indent < 0 or not self.content.strip()
```

### 2.2 TwoWaySQLParser

```python
# sqlym/parser/twoway.py

import re
from dataclasses import dataclass
from typing import Any

@dataclass
class ParsedSQL:
    """パース結果"""
    sql: str
    params: list[Any]                    # ?形式用
    named_params: dict[str, Any]         # :name形式用


class TwoWaySQLParser:
    """Clione-SQL風 2way SQLパーサー"""
    
    # パラメータパターン
    # /* $name */'default' : 削除可能
    # /* name */'default'  : 削除不可
    PARAM_PATTERN = re.compile(
        r"/\*\s*(\$)?(\w+)\s*\*/\s*"
        r"("
        r"'[^']*'"           # 'string'
        r'|"[^"]*"'          # "string"
        r"|\d+(?:\.\d+)?"    # number
        r"|\w+"              # identifier
        r"|\([^)]*\)"        # (list)
        r"|NULL"             # NULL
        r")?"
    )
    
    # IN句パターン
    IN_PATTERN = re.compile(
        r"\bIN\s*/\*\s*(\$)?(\w+)\s*\*/\s*\([^)]*\)",
        re.IGNORECASE
    )
    
    def __init__(self, sql: str, placeholder: str = "?"):
        """
        Args:
            sql: SQLテンプレート
            placeholder: プレースホルダ形式 ("?", "%s", ":name")
        """
        self.original_sql = sql
        self.placeholder = placeholder
    
    def parse(self, params: dict[str, Any]) -> ParsedSQL:
        """SQLをパースしてパラメータをバインド"""
        # 1. 行をパースしてLineUnitリスト作成
        units = self._parse_lines()
        
        # 2. インデントから親子関係構築（Rule 2）
        self._build_tree(units)
        
        # 3. パラメータ評価、行の削除判定（Rule 4）
        self._evaluate_params(units, params)
        
        # 4. 子が全削除なら親も削除（Rule 3）
        self._propagate_removal(units)
        
        # 5. SQL再構築
        sql, bind_params = self._rebuild_sql(units, params)
        
        # 6. 不要なWHERE/AND/OR/括弧を除去
        sql = self._clean_sql(sql)
        
        return ParsedSQL(
            sql=sql,
            params=bind_params,
            named_params=params,
        )
    
    def _parse_lines(self) -> list[LineUnit]:
        """行をパースしてLineUnitリストを作成"""
        ...
    
    def _build_tree(self, units: list[LineUnit]) -> None:
        """インデントに基づいて親子関係を構築"""
        ...
    
    def _evaluate_params(self, units: list[LineUnit], params: dict) -> None:
        """パラメータを評価して行の削除を決定"""
        ...
    
    def _propagate_removal(self, units: list[LineUnit]) -> None:
        """子が全削除なら親も削除（ボトムアップ処理）"""
        ...
    
    def _rebuild_sql(self, units: list[LineUnit], params: dict) -> tuple[str, list]:
        """削除されていない行からSQLを再構築"""
        ...
    
    def _clean_sql(self, sql: str) -> str:
        """不要なWHERE/AND/OR/空括弧を除去"""
        ...
```

### 2.3 RowMapper Protocol

```python
# sqlym/mapper/protocol.py

from typing import Protocol, TypeVar, Any, runtime_checkable

T = TypeVar('T')

@runtime_checkable
class RowMapper(Protocol[T]):
    """マッパーのインターフェース"""
    
    def map_row(self, row: dict[str, Any]) -> T:
        """1行をエンティティに変換"""
        ...
    
    def map_rows(self, rows: list[dict[str, Any]]) -> list[T]:
        """複数行をエンティティのリストに変換"""
        ...
```

### 2.4 DataclassMapper

```python
# sqlym/mapper/dataclass.py

from dataclasses import fields, is_dataclass
from typing import TypeVar, Type, Any, get_type_hints, get_origin, get_args, Annotated

from .column import Column

T = TypeVar('T')

class DataclassMapper:
    """dataclass用の自動マッパー"""
    
    # クラスごとのフィールドマッピングをキャッシュ
    _mapping_cache: dict[type, dict[str, str]] = {}
    
    def __init__(self, entity_cls: Type[T]):
        if not is_dataclass(entity_cls):
            raise TypeError(f"{entity_cls} is not a dataclass")
        
        self.entity_cls = entity_cls
        self._mapping = self._get_mapping(entity_cls)
    
    @classmethod
    def _get_mapping(cls, entity_cls: type) -> dict[str, str]:
        """フィールド名→カラム名のマッピングを取得（キャッシュ付き）"""
        if entity_cls not in cls._mapping_cache:
            cls._mapping_cache[entity_cls] = cls._build_mapping(entity_cls)
        return cls._mapping_cache[entity_cls]
    
    @classmethod
    def _build_mapping(cls, entity_cls: type) -> dict[str, str]:
        """フィールド名→カラム名のマッピングを構築"""
        hints = get_type_hints(entity_cls, include_extras=True)
        column_map = getattr(entity_cls, '__column_map__', {})
        naming = getattr(entity_cls, '__column_naming__', 'as_is')
        
        mapping = {}
        
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
            
            # 2. column_mapをチェック
            if field_name in column_map:
                mapping[field_name] = column_map[field_name]
                continue
            
            # 3. namingルール適用
            if naming == "snake_to_camel":
                mapping[field_name] = cls._to_camel(field_name)
            elif naming == "camel_to_snake":
                mapping[field_name] = cls._to_snake(field_name)
            else:
                mapping[field_name] = field_name
        
        return mapping
    
    @staticmethod
    def _to_camel(name: str) -> str:
        """snake_case → camelCase"""
        components = name.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    
    @staticmethod
    def _to_snake(name: str) -> str:
        """camelCase → snake_case"""
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    
    def map_row(self, row: dict[str, Any]) -> T:
        """1行をエンティティに変換"""
        kwargs = {}
        for field_name, col_name in self._mapping.items():
            if col_name in row:
                kwargs[field_name] = row[col_name]
            elif field_name in row:
                # フォールバック
                kwargs[field_name] = row[field_name]
        return self.entity_cls(**kwargs)
    
    def map_rows(self, rows: list[dict[str, Any]]) -> list[T]:
        """複数行をエンティティのリストに変換"""
        return [self.map_row(row) for row in rows]
```

### 2.5 Column & entity デコレータ

```python
# sqlym/mapper/column.py

class Column:
    """カラム名を指定するアノテーション"""
    
    def __init__(self, name: str):
        self.name = name
    
    def __repr__(self):
        return f"Column({self.name!r})"


def entity(
    cls: type | None = None,
    *,
    column_map: dict[str, str] | None = None,
    naming: str = "as_is"
):
    """
    エンティティデコレータ
    
    Args:
        column_map: フィールド名→カラム名のマッピング
        naming: 命名規則 ("as_is", "snake_to_camel", "camel_to_snake")
    """
    def decorator(cls):
        cls.__column_map__ = column_map or {}
        cls.__column_naming__ = naming
        return cls
    
    if cls is not None:
        return decorator(cls)
    return decorator
```

### 2.6 create_mapper ファクトリ

```python
# sqlym/mapper/__init__.py

from typing import TypeVar, Type, Callable, Any
from dataclasses import is_dataclass

from .protocol import RowMapper
from .dataclass import DataclassMapper

T = TypeVar('T')

class ManualMapper:
    """ユーザー提供の関数をラップするマッパー"""
    
    def __init__(self, func: Callable[[dict], Any]):
        self._func = func
    
    def map_row(self, row: dict) -> Any:
        return self._func(row)
    
    def map_rows(self, rows: list[dict]) -> list:
        return [self._func(row) for row in rows]


def create_mapper(
    entity_cls: Type[T],
    *,
    mapper: RowMapper[T] | Callable[[dict], T] | None = None
) -> RowMapper[T]:
    """
    マッパーを生成する
    
    Args:
        entity_cls: エンティティクラス
        mapper: 
            - None: 自動判定
            - Callable: 自前関数
            - RowMapper: 自前マッパー
    """
    # 明示的に指定された場合
    if mapper is not None:
        if isinstance(mapper, RowMapper):
            return mapper
        if callable(mapper):
            return ManualMapper(mapper)
    
    # 自動判定
    if is_dataclass(entity_cls):
        return DataclassMapper(entity_cls)
    
    # Pydantic判定
    if hasattr(entity_cls, 'model_validate'):
        from .pydantic import PydanticMapper
        return PydanticMapper(entity_cls)
    
    raise TypeError(
        f"Cannot create mapper for {entity_cls}. "
        f"Use dataclass, Pydantic, or provide a custom mapper."
    )
```

### 2.7 SQLファイルローダー

```python
# sqlym/loader.py

from pathlib import Path

class SqlLoader:
    """SQLファイルの読み込み"""
    
    def __init__(self, base_path: str | Path = "sql"):
        self.base_path = Path(base_path)
    
    def load(self, path: str) -> str:
        """SQLファイルを読み込む"""
        file_path = self.base_path / path
        
        if not file_path.exists():
            raise SqlFileNotFoundError(f"SQL file not found: {file_path}")
        
        return file_path.read_text(encoding='utf-8')
```

### 2.8 例外クラス

```python
# sqlym/exceptions.py

class SqlyError(Exception):
    """sqlymの基底例外"""
    pass

class SqlParseError(SqlyError):
    """SQLパースエラー"""
    pass

class MappingError(SqlyError):
    """マッピングエラー"""
    pass

class SqlFileNotFoundError(SqlyError):
    """SQLファイルが見つからない"""
    pass
```

---

## 3. 公開API

```python
# sqlym/__init__.py

from .parser.twoway import TwoWaySQLParser, ParsedSQL, parse_sql
from .mapper import create_mapper, RowMapper, ManualMapper
from .mapper.column import Column, entity
from .loader import SqlLoader
from .exceptions import SqlyError, SqlParseError, MappingError, SqlFileNotFoundError

__all__ = [
    # パーサー
    "TwoWaySQLParser",
    "ParsedSQL",
    "parse_sql",
    
    # マッパー
    "create_mapper",
    "RowMapper",
    "ManualMapper",
    
    # カラムマッピング
    "Column",
    "entity",
    
    # ローダー
    "SqlLoader",
    
    # 例外
    "SqlyError",
    "SqlParseError",
    "MappingError",
    "SqlFileNotFoundError",
]


# 便利関数
def parse_sql(sql: str, params: dict, *, placeholder: str = "?") -> ParsedSQL:
    """SQLをパースする便利関数"""
    parser = TwoWaySQLParser(sql, placeholder=placeholder)
    return parser.parse(params)
```

---

## 4. 使用例

### 4.1 基本的な使い方

```python
from dataclasses import dataclass
from typing import Annotated
import sqlite3

from sqlym import parse_sql, create_mapper, Column, SqlLoader

# エンティティ定義
@dataclass
class Employee:
    id: int
    name: Annotated[str, Column("EMP_NAME")]
    dept_id: int | None = None

# SQLファイル読み込み
loader = SqlLoader("sql")
sql_template = loader.load("employee/find_by_condition.sql")

# パラメータ指定（Noneの行は削除される）
params = {
    "id": 100,
    "name": None,      # この条件の行は削除
    "dept_id": 10,
}

# SQL生成
result = parse_sql(sql_template, params)
print(result.sql)
print(result.params)

# DB実行
conn = sqlite3.connect("test.db")
conn.row_factory = sqlite3.Row
cursor = conn.execute(result.sql, result.params)

# マッピング
mapper = create_mapper(Employee)
employees = mapper.map_rows([dict(row) for row in cursor.fetchall()])
```

### 4.2 自前マッパー

```python
# レガシーDBでカラム名が全然違う場合
mapper = create_mapper(
    Employee,
    mapper=lambda row: Employee(
        id=row['EMP_ID'],
        name=row['EMP_NM'],
        dept_id=row['DEPT_CD'] if row['DEPT_CD'] != 0 else None,
    )
)
```

### 4.3 Pydantic

```python
from pydantic import BaseModel

class Employee(BaseModel):
    id: int
    name: str
    dept_id: int | None = None

mapper = create_mapper(Employee)  # 自動でPydanticMapper
```

---

## 5. テスト方針

### 5.1 ユニットテスト

| 対象 | テスト内容 |
|------|-----------|
| LineUnit | インデント計算、親子関係構築 |
| TwoWaySQLParser | パラメータ置換、行削除、IN句展開 |
| DataclassMapper | フィールドマッピング、型変換 |
| Column/entity | カラム名解決、優先順位 |

### 5.2 統合テスト

- SQLite を使った実際のDB操作
- 各種プレースホルダ形式での動作確認

---

## 6. Dialect 設計

### 6.1 設計方針

sqlym は Clione-SQL と同様に「SQL-first」のテンプレートエンジンである。
SQL は開発者が直接記述し、エンジンはパラメータバインド・行削除・IN 句展開を担当する。

このアーキテクチャでは、RDBMS 固有の SQL 構文（ページネーション、UPSERT、FOR UPDATE 等）は
**開発者が SQL ファイルに直接記述する** ため、エンジン側で生成する必要がない。
RDBMS ごとに構文が異なる場合は、SQL ファイルを分けて対応する（後述の RDBMS 別 SQL ファイルロード）。

したがって Dialect が扱う範囲は **テンプレートエンジン自体の動作に影響する差異のみ** に限定する。

#### Clione-SQL との比較

Clione-SQL も同じ設計思想に基づき、Dialect が扱うのは以下の 3 点のみである：

| 機能 | 理由 |
|---|---|
| LIKE エスケープ対象文字 | エンジンがパラメータ値をエスケープする際に対象文字が DB で異なる |
| IN 句要素数上限 | エンジンが IN 句を展開する際に Oracle の 1000 件制限を超えないよう分割が必要 |
| バックスラッシュのエスケープ文字扱い | エンジンが SQL 文字列リテラルをパースする際の解釈が DB で異なる |

加えて、SqlLoader による RDBMS 別 SQL ファイルロード機能を提供する。

#### Doma2 との違い

Doma2 は ORM としてINSERT/UPDATE/DELETE/UPSERT 文を **自動生成** するため、
ページネーション、識別子クォート、UPSERT 構文、ID 生成等の DB 固有構文を
すべて Dialect で吸収する必要がある。

sqlym はこれらの SQL 生成機能を持たないため、Doma2 相当の Dialect は不要である。
将来的に必要になった場合は Backlog（TASK.md 参照）として管理している。

### 6.2 Dialect クラス設計

既存の `Dialect` enum を拡張し、DB 固有プロパティをメソッドとして追加する。

```python
# sqlym/dialect.py

from __future__ import annotations

import re
from enum import Enum


class Dialect(Enum):
    """RDBMS ごとの SQL 方言."""

    SQLITE = ("sqlite", "?")
    POSTGRESQL = ("postgresql", "%s")
    MYSQL = ("mysql", "%s")
    ORACLE = ("oracle", ":name")

    def __init__(self, dialect_id: str, placeholder_fmt: str) -> None:
        self._dialect_id = dialect_id
        self._placeholder_fmt = placeholder_fmt

    @property
    def placeholder(self) -> str:
        """プレースホルダ文字列を返す."""
        return self._placeholder_fmt

    @property
    def like_escape_chars(self) -> frozenset[str]:
        """LIKE 句でエスケープが必要な特殊文字を返す.

        Note:
            Oracle の LIKE ESCAPE 構文では、エスケープ文字の後には
            % または _ のみ指定可能（ORA-01424）。全角文字は
            LIKE ワイルドカードではないためエスケープ不要。

        Returns:
            エスケープ対象文字の集合
        """
        return frozenset({"#", "%", "_"})

    @property
    def in_clause_limit(self) -> int | None:
        """IN 句に指定できる要素数の上限を返す.

        Returns:
            上限値。None は無制限を意味する。
        """
        match self:
            case Dialect.ORACLE:
                return 1000
            case _:
                return None

    @property
    def backslash_is_escape(self) -> bool:
        """バックスラッシュが文字列リテラル内でエスケープ文字として機能するか.

        MySQL と PostgreSQL ではデフォルトで True。
        """
        match self:
            case Dialect.MYSQL | Dialect.POSTGRESQL:
                return True
            case _:
                return False
```

### 6.3 IN 句上限分割

`Dialect.in_clause_limit` が設定されている場合、IN 句の展開時に要素数が上限を超えると
自動的に `OR` で分割する。

```sql
-- 元の SQL（パラメータ ids に 1500 要素）
SELECT * FROM t WHERE id IN /* $ids */(1)

-- Oracle (in_clause_limit=1000) での展開結果
SELECT * FROM t WHERE (id IN (:ids_1, :ids_2, ..., :ids_1000)
    OR id IN (:ids_1001, :ids_1002, ..., :ids_1500))
```

分割時は括弧で囲み、`OR` で結合する。

### 6.4 LIKE エスケープ処理

LIKE パラメータのエスケープ処理をユーティリティ関数として提供する。

```python
from sqlym import Dialect

# Dialect に応じたエスケープ処理
def escape_like(value: str, dialect: Dialect, escape_char: str = "#") -> str:
    """LIKE パラメータ値をエスケープする."""
    for ch in dialect.like_escape_chars:
        value = value.replace(ch, escape_char + ch)
    return value
```

SQL テンプレート側では `ESCAPE` 句を開発者が明示的に記述する：

```sql
SELECT * FROM t WHERE name LIKE /* $pattern */'%' ESCAPE '#'
```

### 6.5 RDBMS 別 SQL ファイルロード

SqlLoader に Dialect 指定オプションを追加する。
Clione-SQL の `LoaderUtil.getNodeByPath()` と同等のフォールバック機構を提供する。

```python
loader = SqlLoader("sql")

# dialect 指定あり: まず "find.oracle.sql" を探し、なければ "find.sql" にフォールバック
sql = loader.load("employee/find.sql", dialect=Dialect.ORACLE)
```

ファイル解決順序：

1. `{base_path}/{dir}/{name}.{dialect_id}.{ext}` （例: `sql/employee/find.oracle.sql`）
2. `{base_path}/{path}` （例: `sql/employee/find.sql`）

これにより、大部分の SQL は共通ファイルで記述し、
RDBMS 固有の構文が必要な場合のみ `.{dialect}` サフィックス付きファイルで上書きできる。

---

## 7. 実装順序

1. **Phase 1: パーサー基盤**
   - LineUnit
   - 行パース、親子関係構築
   - パラメータ置換（基本）

2. **Phase 2: パーサー完成**
   - 行削除ロジック
   - IN句展開
   - SQL整形（WHERE/AND除去）

3. **Phase 3: マッパー**
   - RowMapper Protocol
   - DataclassMapper
   - Column, entity

4. **Phase 4: 統合**
   - SqlLoader
   - 公開API
   - ドキュメント
