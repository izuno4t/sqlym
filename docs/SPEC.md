# sqlym 機能仕様書

## 1. 概要

sqlymはPython用のSQL重視データベースアクセスライブラリである。
Java の Clione-SQL と Doma2 の設計思想を参考に、Pythonらしい実装を目指す。

### 1.1 設計思想

- **SQLファースト**: ORMのようにSQLを隠蔽しない。SQLを直接書く。
- **2way SQL**: SQLファイルはそのままDBクライアントツールでも実行可能。
- **選択の自由**: 自動マッピングも自前マッピングも選べる。
- **シンプル**: 最小限のAPIで必要十分な機能を提供。

### 1.2 参考ライブラリ

| ライブラリ | 採用する要素 |
|-----------|-------------|
| Clione-SQL | 行単位処理、インデント親子関係、自動行削除 |
| Doma2 | 2way SQLの記法、カラムマッピング |

---

## 2. 2way SQLパーサー

### 2.1 Clione-SQLの4ルール

| ルール | 説明 |
|--------|------|
| Rule 1 | SQLは行単位（LineUnit）で処理する |
| Rule 2 | インデントにより親子関係を定義する |
| Rule 3 | 子が全て除去されたら親も除去される |
| Rule 4 | `$`付きパラメータがNoneなら行を除去する |

### 2.2 パラメータ記法

#### 2.2.1 バインド変数（削除可能）

```sql
/* $パラメータ名 */デフォルト値
```

- パラメータがNoneの場合、その行全体を削除する
- デフォルト値はDBツールで直接実行する際に使用される

例:
```sql
WHERE name = /* $name */'山田太郎'
```

#### 2.2.2 バインド変数（削除不可）

```sql
/* パラメータ名 */デフォルト値
```

- パラメータがNoneでも行は削除されない
- NoneはNULLとしてバインドされる

例:
```sql
WHERE deleted_at = /* deleted_at */NULL
```

#### 2.2.3 デフォルト値の形式

| 形式 | 例 |
|------|-----|
| 文字列 | `'string'` または `"string"` |
| 数値 | `123` または `45.67` |
| 識別子 | `column_name` |
| リスト | `(1, 2, 3)` |
| NULL | `NULL` |

### 2.3 IN句の自動展開

```sql
WHERE id IN /* $ids */(1, 2, 3)
```

パラメータ`ids`がリスト`[10, 20, 30]`の場合:
```sql
WHERE id IN (?, ?, ?)
-- バインド値: [10, 20, 30]
```

空リストの場合:
```sql
WHERE id IN (NULL)
-- または 1=0 に置換（検討中）
```

### 2.4 自動除去

#### 2.4.1 WHERE句の除去

条件が全て削除された場合、WHERE自体も削除する。

Before:
```sql
SELECT * FROM employee
WHERE
    name = /* $name */'太郎'
```

パラメータ `{"name": None}` の場合:
```sql
SELECT * FROM employee
```

#### 2.4.2 AND/ORの除去

先頭のAND/ORを自動削除する。

Before:
```sql
WHERE
    id = /* $id */1
    AND name = /* $name */'太郎'
```

パラメータ `{"id": None, "name": "花子"}` の場合:
```sql
WHERE
    name = ?
```

#### 2.4.3 空括弧の除去

中身が全て削除された括弧は括弧ごと削除する。

Before:
```sql
WHERE
    id = /* $id */1
    AND (
        status = /* $status1 */'active'
        OR status = /* $status2 */'pending'
    )
```

パラメータ `{"id": 1, "status1": None, "status2": None}` の場合:
```sql
WHERE
    id = ?
```

### 2.5 プレースホルダ形式

以下の形式をサポートし、選択可能とする。

| 形式 | 用途 |
|------|------|
| `?` | SQLite, JDBC互換 |
| `%s` | MySQL, PostgreSQL (psycopg2) |
| `:name` | Oracle, 名前付きパラメータ |

---

## 3. マッパー

### 3.1 概要

SQL実行結果（行）をPythonオブジェクトに変換する機能。

### 3.2 マッパーの種類

#### 3.2.1 自動マッパー

dataclassまたはPydantic BaseModelを自動的にマッピングする。

```python
from sqlym import create_mapper

mapper = create_mapper(Employee)  # 自動判定
```

- dataclass: `dataclasses.fields()`でフィールド情報取得
- Pydantic: `model_validate()`でマッピング
- リフレクション結果はキャッシュ（初回のみ解析）

#### 3.2.2 自前マッパー（関数）

```python
mapper = create_mapper(
    Employee,
    mapper=lambda row: Employee(
        id=row['EMP_ID'],
        name=row['EMP_NM'],
    )
)
```

#### 3.2.3 自前マッパー（クラス）

```python
class MyMapper:
    def map_row(self, row: dict) -> Employee:
        # 複雑な変換ロジック
        return Employee(...)
    
    def map_rows(self, rows: list[dict]) -> list[Employee]:
        return [self.map_row(row) for row in rows]

mapper = create_mapper(Employee, mapper=MyMapper())
```

### 3.3 マッパーインターフェース

```python
from typing import Protocol, TypeVar

T = TypeVar('T')

@runtime_checkable
class RowMapper(Protocol[T]):
    def map_row(self, row: dict[str, Any]) -> T: ...
    def map_rows(self, rows: list[dict[str, Any]]) -> list[T]: ...
```

---

## 4. カラムマッピング

### 4.1 個別指定（Annotated）

```python
from typing import Annotated
from sqlym import Column

@dataclass
class Employee:
    id: Annotated[int, Column("EMP_ID")]
    name: Annotated[str, Column("EMP_NAME")]
    email: str  # カラム名 = フィールド名
```

### 4.2 一括指定（デコレータ）

```python
from sqlym import entity

@entity(column_map={
    "id": "EMP_ID",
    "name": "EMP_NAME",
})
@dataclass
class Employee:
    id: int
    name: str
```

### 4.3 命名規則

```python
@entity(naming="snake_to_camel")
@dataclass
class Employee:
    dept_id: int  # → deptId
    user_name: str  # → userName
```

| naming値 | 変換 |
|----------|------|
| `as_is` | そのまま（デフォルト） |
| `snake_to_camel` | snake_case → camelCase |
| `camel_to_snake` | camelCase → snake_case |

### 4.4 優先順位

1. `Annotated[..., Column("X")]` の指定
2. `@entity(column_map={...})` の指定
3. `@entity(naming="...")` の変換
4. フィールド名そのまま

---

## 5. SQLファイル管理

### 5.1 パス規約

```
project/
├── sql/
│   ├── employee/
│   │   ├── find_all.sql
│   │   ├── find_by_id.sql
│   │   └── find_by_dept.sql
│   └── department/
│       └── find_all.sql
```

### 5.2 ファイル読み込み

- 毎回ファイルから読み込む（v1.0）
- キャッシュは将来機能

---

## 6. 将来機能（v2.0以降）

### 6.1 ディレクティブ

```sql
/*%if condition */
...
/*%end*/

/*%for item : items */
...
/*%end*/

/*%elseif condition */
/*%else*/
```

### 6.2 埋め込み変数

```sql
ORDER BY /*$ order_column */id
```

- SQLに直接展開される（プレースホルダではない）
- SQLインジェクション対策必須

### 6.3 SQLキャッシュ

- パフォーマンス最適化のためのキャッシュ機構
- 開発時: 無効、本番時: 有効 の切り替え

---

## 7. エラーハンドリング

### 7.1 例外クラス

| 例外 | 説明 |
|------|------|
| `SqlyError` | 基底例外 |
| `SqlParseError` | SQLパースエラー |
| `MappingError` | マッピングエラー |
| `SqlFileNotFoundError` | SQLファイルが見つからない |

---

## 8. 対応環境

- Python 3.10+
- 依存ライブラリ: なし（標準ライブラリのみ）
- オプション依存: Pydantic（Pydanticマッパー使用時）
