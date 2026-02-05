# sqlym 実装案（設計案）

## 1. パッケージ構成

```text
sqlym/
├── __init__.py          # 公開 API
├── _parse.py            # parse_sql 便利関数
├── config.py            # エラーメッセージ設定
├── dialect.py           # Dialect enum（RDBMS 方言）
├── escape_utils.py      # LIKE エスケープ等ユーティリティ
├── exceptions.py        # 例外クラス
├── loader.py            # SQL ファイル読み込み
├── sqlym.py             # Sqlym 高レベル API
├── parser/
│   ├── __init__.py
│   ├── tokenizer.py     # SQL トークナイザー
│   ├── line_unit.py     # 行単位処理
│   └── twoway.py        # 2way SQL パーサー本体
└── mapper/
    ├── __init__.py
    ├── protocol.py      # RowMapper プロトコル
    ├── dataclass.py     # dataclass 用マッパー
    ├── pydantic.py      # Pydantic 用マッパー
    ├── column.py        # カラムマッピング
    ├── manual.py        # ManualMapper
    └── factory.py       # create_mapper ファクトリ
```

---

## 2. コアクラス設計

### 2.1 LineUnit（行単位）

**責務:** SQL の 1 行を表現し、親子関係と削除状態を管理する。

**主要属性:**

- `line_number`: 元の SQL 内での行番号
- `indent`: インデント深さ（親子関係の決定に使用）
- `children` / `parent`: ツリー構造
- `removed`: 削除フラグ

**設計判断:**

- Clione-SQL Rule 1「SQL は行単位で処理する」を実現
- インデントで親子関係を表現（Rule 2）
- `removed` フラグで削除をマーク後、ボトムアップで親に伝播（Rule 3）

### 2.2 TwoWaySQLParser

**責務:** 2way SQL テンプレートをパースし、パラメータをバインドした SQL を生成する。

**処理フロー:**

1. 行をパースして LineUnit リスト作成
2. インデントから親子関係構築（Rule 2）
3. パラメータ評価、行の削除判定（Rule 4）
4. 子が全削除なら親も削除（Rule 3）
5. SQL 再構築
6. 不要な WHERE/AND/OR/括弧を除去

**設計判断:**

- 正規表現でパラメータコメント `/* $name */value` を検出
- IN 句は専用パターンで検出し、リストを展開
- プレースホルダ形式は Dialect から取得（`?`, `%s`, `:name`）

#### 2.2.1 パラメータ修飾記号の設計

Clione-SQL 互換の修飾記号を実装。パース時に修飾記号を解析し、挙動を切り替える。

| 修飾記号 | 処理                                 | 設計理由                  |
| -------- | ------------------------------------ | ------------------------- |
| `$`      | negative 時に行削除                  | 動的 WHERE 条件の基本機能 |
| `&`      | negative 時に行削除、バインドなし    | フラグによる行の ON/OFF   |
| `@`      | negative 時に例外                    | 必須パラメータの検証      |
| `?`      | フォールバック                       | デフォルト値の連鎖        |
| `!`      | 上記の否定                           | 条件の反転                |

**negative/positive の拡張判定:**

- `None` に加え、`False`、空リスト `[]`、全要素が negative のリストも negative として扱う
- Clione-SQL の `ClioBlank` に相当する概念を Python の型に適用

#### 2.2.2 補助関数の設計

補助関数は `%` プレフィックスで識別し、専用のパーサーで処理する。

| 関数             | 処理                     | 設計理由                 |
| ---------------- | ------------------------ | ------------------------ |
| `%concat` / `%C` | 文字列連結               | LIKE パターン構築        |
| `%L`             | LIKE エスケープ + ESCAPE | SQL インジェクション防止 |
| `%STR` / `%SQL`  | 直接埋め込み             | 動的カラム名等           |
| `%if-%else-%end` | インライン条件分岐       | 1 行内での条件切り替え   |
| `%include`       | SQL ファイルインクルード | SQL の再利用             |

**設計判断:**

- 補助関数はパラメータ置換の**前**に処理する
- `%STR`/`%SQL` は SQL インジェクションのリスクがあるため、ドキュメントで警告

#### 2.2.3 ブロック切り替えの設計

`-- %IF` / `-- %ELSE` / `-- %END` は行コメント形式で、複数行の条件分岐を実現する。

```sql
-- %IF use_date
    AND date >= /* $date_from */'2020-01-01'
-- %ELSE
    AND status = /* $status */'active'
-- %END
```

**設計判断:**

- 行コメント形式を採用（DB ツールでそのまま実行可能）
- ブロック内のインデントは保持
- ネスト（`%IF` 内の `%IF`）は非サポート（Clione-SQL と同様）

### 2.3 マッパー階層

**責務:** DB の行データを Python オブジェクトに変換する。

```text
RowMapper (Protocol)
├── DataclassMapper    # dataclass を自動マッピング
├── PydanticMapper     # Pydantic BaseModel を自動マッピング
└── ManualMapper       # ユーザー関数をラップ
```

**設計判断:**

1. **Protocol ベースのインターフェース**
   - `@runtime_checkable` で duck typing をサポート
   - 外部ライブラリのマッパーも受け入れ可能

2. **クラスレベルキャッシュ**
   - `DataclassMapper._mapping_cache` でフィールド解析結果をキャッシュ
   - 同じ dataclass の繰り返しマッピングを高速化

3. **カラム名解決の優先順位**
   - `Annotated[T, Column("X")]` > `@entity(column_map={})` >
     `@entity(naming="...")` > フィールド名
   - 柔軟性と明示性のバランス

4. **Pydantic の遅延インポート**
   - `create_mapper` 内で `hasattr(cls, 'model_validate')` で判定
   - Pydantic 未インストール環境でもエラーにならない

### 2.4 Sqlym（高レベル API）

**責務:** SQL ファイルの読み込み、パース、実行、結果マッピングを統合する。

**設計判断:**

1. **Dialect 自動検出**
   - `connection.__module__` から RDBMS を推測
   - 検出できない場合は SQLite をデフォルト

2. **トランザクション管理の委譲**
   - `commit()` / `rollback()` は connection に委譲
   - コンテキストマネージャも connection の `__enter__` / `__exit__` に委譲
   - sqlym はトランザクションロジックを持たない

3. **auto_commit モード**
   - `execute()` 後に自動で `connection.commit()` を呼ぶ
   - ツールやスクリプト向けの簡易モード

### 2.5 SqlLoader

**責務:** SQL ファイルを読み込み、Dialect に応じたファイル解決を行う。

**設計判断:**

1. **ファイル解決順序**
   - `{path}.{dialect}.sql` を優先（例: `find.oracle.sql`）
   - 見つからなければ `{path}.sql` にフォールバック

2. **エンコーディング**
   - UTF-8 固定（国際化対応）

### 2.6 例外階層

```text
SqlyError (基底)
├── SqlParseError      # SQL パースエラー（行番号付き）
├── MappingError       # オブジェクトマッピングエラー
└── SqlFileNotFoundError  # SQL ファイルが見つからない
```

**設計判断:**

- すべて `SqlyError` を継承し、`except SqlyError` でまとめてキャッチ可能
- `SqlParseError` は行番号と SQL 断片をエラーメッセージに含める

---

## 3. 公開 API

公開 API の詳細は [SPEC.md](SPEC.md) を参照。

### 3.1 API 階層設計

```text
┌─────────────────────────────────────────────────┐
│ Sqlym（高レベル API）                            │
│   - SQL ファイル読み込み、パース、実行、マッピング   │
│   - トランザクション管理は connection に委譲       │
└───────────────┬─────────────────────────────────┘
                │ 内部で使用
┌───────────────┴─────────────────────────────────┐
│ 低レベル API                                     │
│   - parse_sql: SQL テンプレートのパース           │
│   - SqlLoader: SQL ファイルの読み込み            │
│   - create_mapper: 結果マッピング                │
└─────────────────────────────────────────────────┘
```

### 3.2 設計判断: 2 層 API

**理由:**

- 高レベル API（Sqlym）: 一般的なユースケースを簡潔に記述
- 低レベル API: フレームワーク統合や特殊ケースに対応

**トレードオフ:**

- 高レベル API は connection に依存し、テストが難しくなる
- 低レベル API は柔軟だが、使用コードが冗長になる

この構成により、シンプルなアプリは Sqlym で完結し、
Clean Architecture 等では低レベル API で Repository パターンを実装できる。

---

## 4. テスト方針

### 4.1 テスト階層

```text
tests/
├── unit/                    # ユニットテスト（モック使用、高速）
│   ├── parser/              # パーサーのユニットテスト
│   │   ├── test_twoway_*.py # 各機能ごとのテスト
│   │   └── test_tokenizer.py
│   └── mapper/              # マッパーのユニットテスト
│       ├── test_dataclass.py
│       └── test_column.py
└── integration/             # 統合テスト（実 DB 使用）
    ├── test_sqlite.py       # SQLite（CI で常時実行）
    ├── test_postgresql.py   # PostgreSQL（マーカー付き）
    ├── test_mysql.py        # MySQL（マーカー付き）
    └── test_oracle.py       # Oracle（マーカー付き）
```

### 4.2 テスト対象

| 対象            | テスト内容                                   |
| --------------- | -------------------------------------------- |
| LineUnit        | インデント計算、親子関係構築                 |
| TwoWaySQLParser | パラメータ置換、行削除、IN 句展開、修飾記号  |
| DataclassMapper | フィールドマッピング、型変換                 |
| Column/entity   | カラム名解決、優先順位                       |
| Sqlym           | query/execute の統合動作                     |

### 4.3 設計判断: RDBMS 別テストファイル

**理由:**

- プレースホルダ形式が RDBMS ごとに異なる
- LIKE エスケープや IN 句上限が異なる
- CI 環境では SQLite のみ実行し、他は手動またはオプションマーカーで実行

**トレードオフ:**

- テストコードの重複が増える
- ただし RDBMS 固有の挙動を確実にテストできる

---

## 5. Dialect 設計

### 5.1 対象 RDBMS の選択

#### 対象 RDBMS

| RDBMS      | 選択理由                                                           |
| ---------- | ------------------------------------------------------------------ |
| SQLite     | 組み込み DB。テスト・開発環境で必須。Python 標準ライブラリに含まれる |
| PostgreSQL | OSS で最も機能が充実。クラウド対応（RDS, Cloud SQL 等）            |
| MySQL      | 世界シェア最大級の OSS DB。Web アプリで広く使用                    |
| Oracle     | エンタープライズ領域でのデファクト。Clione-SQL の主要ターゲット    |

#### 対象外とした RDBMS

| RDBMS      | 対象外の理由                                 |
| ---------- | -------------------------------------------- |
| SQL Server | Python での利用が限定的。将来的に追加検討    |
| MariaDB    | MySQL 互換のため MySQL ドライバーで対応可能  |
| その他     | 需要があれば Issue で検討                    |

#### 選択基準

1. **Python エコシステムでの普及度** - 安定したドライバーが存在すること
2. **Clione-SQL との互換性** - 元ライブラリがサポートする RDBMS を優先
3. **プレースホルダ形式の代表性** - `?`, `%s`, `:name` の 3 形式をカバー

### 5.2 設計方針

sqlym は Clione-SQL と同様に「SQL-first」のテンプレートエンジンである。
SQL は開発者が直接記述し、エンジンはパラメータバインド・行削除・IN 句展開を担当する。

このアーキテクチャでは、RDBMS 固有の SQL 構文（ページネーション、UPSERT、FOR UPDATE 等）は
**開発者が SQL ファイルに直接記述する** ため、エンジン側で生成する必要がない。
RDBMS ごとに構文が異なる場合は、SQL ファイルを分けて対応する（後述の RDBMS 別 SQL ファイルロード）。

したがって Dialect が扱う範囲は **テンプレートエンジン自体の動作に影響する差異のみ** に限定する。

#### Clione-SQL との比較

Clione-SQL も同じ設計思想に基づき、Dialect が扱うのは以下の 3 点のみである：

| 機能                       | 理由                                           |
| -------------------------- | ---------------------------------------------- |
| LIKE エスケープ対象文字    | エスケープ対象文字が DB で異なる               |
| IN 句要素数上限            | Oracle の 1000 件制限を超えないよう分割が必要  |
| バックスラッシュエスケープ | 文字列リテラルのパース時の解釈が DB で異なる   |

加えて、SqlLoader による RDBMS 別 SQL ファイルロード機能を提供する。

#### Doma2 との違い

Doma2 は ORM としてINSERT/UPDATE/DELETE/UPSERT 文を **自動生成** するため、
ページネーション、識別子クォート、UPSERT 構文、ID 生成等の DB 固有構文を
すべて Dialect で吸収する必要がある。

sqlym はこれらの SQL 生成機能を持たないため、Doma2 相当の Dialect は不要である。
将来的に必要になった場合は Backlog（TASK.md 参照）として管理している。

### 5.3 Dialect クラス設計

`Dialect` enum で RDBMS ごとの差異を管理する。

| RDBMS      | プレースホルダ | IN 句上限 | バックスラッシュエスケープ |
| ---------- | -------------- | --------- | -------------------------- |
| SQLite     | `?`            | なし      | No                         |
| PostgreSQL | `%s`           | なし      | Yes                        |
| MySQL      | `%s`           | なし      | Yes                        |
| Oracle     | `:name`        | 1000      | No                         |

**提供プロパティ:**

- `placeholder`: プレースホルダ形式
- `like_escape_chars`: LIKE エスケープ対象文字（`#`, `%`, `_`）
- `in_clause_limit`: IN 句要素数上限（Oracle のみ 1000）
- `backslash_is_escape`: バックスラッシュがエスケープ文字か

### 5.4 IN 句上限分割

`Dialect.in_clause_limit` が設定されている場合（Oracle の 1000 件制限）、
IN 句の展開時に要素数が上限を超えると自動的に `OR` で分割する。

**設計判断:**

- 分割時は括弧で囲み、`OR` で結合
- 開発者が意識せずに Oracle の制限を回避可能

### 5.5 LIKE エスケープ処理

`escape_like()` ユーティリティ関数で LIKE パラメータ値をエスケープする。

**設計判断:**

- `ESCAPE` 句は開発者が SQL に明示的に記述する
- エスケープ文字はデフォルト `#`（Clione-SQL と同じ）
- 補助関数 `%L` を使うと ESCAPE 句の自動付与も可能

### 5.6 RDBMS 別 SQL ファイルロード

SqlLoader は Dialect 指定時に RDBMS 固有ファイルを優先ロードする。
Clione-SQL の `LoaderUtil.getNodeByPath()` と同等のフォールバック機構。

**ファイル解決順序:**

1. `{name}.{dialect}.sql` （例: `find.oracle.sql`）
2. `{name}.sql` （例: `find.sql`）

**設計判断:**

- 大部分の SQL は共通ファイルで記述
- ページネーションや UPSERT 等、RDBMS 固有構文のみ別ファイルで上書き

---

## 6. 実装フェーズ

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
