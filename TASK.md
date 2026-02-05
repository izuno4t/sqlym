# TASKS

マイルストーン: M1
ゴール: sqly v1.0の全機能（2way SQLパーサー、マッパー、SQLローダー）を実装し統合テストで動作検証する

## ステータス表記ルール

| Status | 意味 |
| ---- | ----- |
| ⏳ | 未着手、TODO |
| 🚧 | 作業中、IN_PROGRESS |
| 🧪 | 確認待ち、REVIEW |
| ✅ | 完了、DONE |
| 🚫 | 中止、CANCELLED |

## ワークフロールール

- タスク着手時にステータスを 🚧 に更新する
- タスク完了時にステータスを ✅ に更新する
- DependsOn のタスクがすべて ✅ でないタスクには着手しない

## タスク一覧

| ID | Status | Summary | DependsOn |
|---|---|---|---|
| TASK-001 | ✅ | プロジェクト基盤を構築する（pyproject.toml、パッケージ構成、テスト設定） | - |
| TASK-002 | ✅ | 例外クラスを実装する（exceptions.py） | TASK-001 |
| TASK-003 | ✅ | LineUnitクラスを実装しテストする | TASK-001 |
| TASK-004 | ✅ | Tokenizerを実装しテストする | TASK-001 |
| TASK-005 | ✅ | TwoWaySQLParserの行パースと親子関係構築を実装しテストする | TASK-003,TASK-004 |
| TASK-006 | ✅ | TwoWaySQLParserの基本パラメータ置換を実装しテストする | TASK-005 |
| TASK-007 | ✅ | TwoWaySQLParserの行削除ロジックを実装しテストする（Rule 3, Rule 4） | TASK-006 |
| TASK-008 | ✅ | TwoWaySQLParserのIN句自動展開を実装しテストする | TASK-006 |
| TASK-009 | ✅ | TwoWaySQLParserのSQL整形を実装しテストする（WHERE/AND/OR/空括弧除去） | TASK-007 |
| TASK-010 | ✅ | TwoWaySQLParserの複数プレースホルダ形式対応を実装しテストする（%s, :name） | TASK-009 |
| TASK-011 | ✅ | RowMapper ProtocolとManualMapperを実装する | TASK-001 |
| TASK-012 | ✅ | Column・entityデコレータを実装しテストする | TASK-001 |
| TASK-013 | ✅ | DataclassMapperを実装しテストする | TASK-011,TASK-012 |
| TASK-014 | ✅ | PydanticMapperを実装しテストする | TASK-011 |
| TASK-015 | ✅ | create_mapperファクトリを実装しテストする | TASK-013,TASK-014 |
| TASK-016 | ✅ | SqlLoaderを実装しテストする | TASK-002 |
| TASK-017 | ✅ | 公開API（__init__.py）とparse_sql便利関数を整備する | TASK-010,TASK-015,TASK-016 |
| TASK-018 | ✅ | SQLite統合テストを作成する（パース→実行→マッピングの一連検証） | TASK-017 |
| TASK-019 | ✅ | Dialect enumを実装しテストする | - |
| TASK-020 | ✅ | parse_sql / TwoWaySQLParserにdialect引数を追加する | TASK-019 |
| TASK-021 | ✅ | Docker ComposeでPostgreSQL/MySQLサービスを構成する | - |
| TASK-022 | ✅ | pytestのDBテスト基盤を構築する（conftest, markers, dev deps） | TASK-021 |
| TASK-023 | ✅ | PostgreSQL統合テストを作成する | TASK-020, TASK-022 |
| TASK-024 | ✅ | MySQL統合テストを作成する | TASK-020, TASK-022 |
| TASK-025 | ✅ | DevContainerにDBサービスを統合する | TASK-021 |
| TASK-026 | ✅ | MakefileにDBテスト関連ターゲットを追加する | TASK-021, TASK-022 |
| TASK-027 | ✅ | Docker ComposeにOracle XEサービスを追加する | - |
| TASK-028 | ✅ | pytestのDBテスト基盤にOracleを追加する（conftest, markers, dev deps） | TASK-027 |
| TASK-029 | ✅ | Oracle統合テストを作成する | TASK-028 |
| TASK-030 | ✅ | DevContainer・MakefileにOracleを追加する | TASK-027 |
| TASK-031 | ✅ | GitHub Actions CIワークフローを作成する | TASK-022, TASK-028 |
| TASK-032 | ✅ | DialectクラスにDB固有プロパティを追加する（LIKEエスケープ、IN句上限、バックスラッシュエスケープ） | TASK-019 |
| TASK-033 | ✅ | IN句展開時のDB固有上限分割を実装しテストする（Oracle 1000件制限対応） | TASK-032, TASK-008 |
| TASK-034 | ✅ | LIKEパラメータのエスケープ処理を実装しテストする | TASK-032 |
| TASK-035 | ✅ | SqlLoaderにRDBMS別SQLファイルロードを追加しテストする | TASK-032, TASK-016 |
| TASK-036 | ⏳ | Dialect拡張機能の統合テストを作成する（全RDBMS） | TASK-033, TASK-034, TASK-035 |

## タスク詳細（補足が必要な場合のみ）

### TASK-001

- 補足: pyproject.toml、sqly/各サブパッケージの__init__.py、tests/ディレクトリを作成する
- 注意: 外部依存なし。Pydanticはオプション依存（extras）として定義する

### TASK-004

- 補足: DESIGN.mdのパッケージ構成に記載のtokenizer.py。SQLコメント内パラメータの字句解析を担当する
- 注意: パーサーの前提モジュールのため、パーサー実装前に完了する必要がある

### TASK-005

- 補足: `_parse_lines()`と`_build_tree()`を実装。Rule 1（行単位処理）とRule 2（インデント親子関係）に対応

### TASK-006

- 補足: `_evaluate_params()`と`_rebuild_sql()`の基本実装。`/* $name */default`と`/* name */default`の両パターン対応
- 注意: この段階ではプレースホルダは`?`形式のみ

### TASK-007

- 補足: `$`付きパラメータがNoneの場合の行削除（Rule 4）と子全削除時の親削除（Rule 3）
- 注意: `_propagate_removal()`はボトムアップで処理する

### TASK-009

- 補足: `_clean_sql()`の実装。孤立したWHERE、先頭AND/OR、空括弧を除去する

### TASK-010

- 補足: `%s`形式とOracle `:name`形式への対応。ParsedSQLのparams/named_paramsを形式に応じて出し分ける

### TASK-012

- 補足: `Column`クラスと`entity`デコレータ。`__column_map__`と`__column_naming__`属性を付与する
- 注意: naming値は`as_is`、`snake_to_camel`、`camel_to_snake`の3種

### TASK-013

- 補足: カラムマッピング優先順位: Annotated[T, Column("X")] > column_map > naming > フィールド名
- 注意: `_mapping_cache`をクラス変数として実装する

### TASK-014

- 注意: Pydanticが未インストールの場合でもインポートエラーにならないよう遅延インポートとする

### TASK-018

- 補足: SQLiteを使い、2way SQLテンプレート→パース→DB実行→マッパーでオブジェクト取得の一連フローを検証する

### TASK-019

- 補足: Dialect enum (SQLITE/POSTGRESQL/MYSQL/ORACLE) を `src/sqly/dialect.py` に実装
- 注意: POSTGRESQLとMYSQLは同じプレースホルダ `%s` だが、Enumエイリアスを回避するためvalueをタプル `(dialect_id, placeholder)` とした

### TASK-020

- 補足: `TwoWaySQLParser.__init__` と `parse_sql` に `dialect: Dialect | None = None` をkeyword-only引数で追加
- 注意: `dialect` と `placeholder` (デフォルト `?` 以外) の同時指定は `ValueError`

### TASK-021

- 補足: `docker-compose.yml` にPostgreSQL 16 Alpine + MySQL 8.0を定義。healthcheck付き
- 注意: ユーザー `sqly` / パスワード `sqly_test_pass` / DB `sqly_test`

### TASK-022

- 補足: `tests/conftest.py` にDB接続判定・自動スキップ・`pg_conn`/`mysql_conn` fixtureを実装
- 注意: 環境変数 `SQLY_TEST_POSTGRESQL_URL` / `SQLY_TEST_MYSQL_URL` で接続先を指定可能

### TASK-023

- 補足: `tests/integration/test_postgresql.py` にSQLiteテストと同等の検証項目をPostgreSQLで実施

### TASK-024

- 補足: `tests/integration/test_mysql.py` にSQLiteテストと同等の検証項目をMySQLで実施

### TASK-025

- 補足: `.devcontainer/devcontainer.json` にDB環境変数・forwardPorts・initializeCommandでDB起動を追加

### TASK-026

- 補足: Makefileに `db-up`/`db-down`/`test-postgresql`/`test-mysql`/`test-db`/`test-all` ターゲットを追加

### TASK-027

- 補足: `docker-compose.yml` に `gvenzl/oracle-xe:21-slim` サービスを追加。`APP_USER`/`APP_USER_PASSWORD` でアプリユーザー自動作成

### TASK-028

- 補足: `tests/conftest.py` に Oracle 接続判定・自動スキップ・`oracle_conn` fixture を実装
- 注意: 環境変数 `SQLY_TEST_ORACLE_DSN` で接続先を指定可能（デフォルト: `localhost:1521/XEPDB1`）

### TASK-029

- 補足: `tests/integration/test_oracle.py` に PostgreSQL テストと同等の検証項目を Oracle で実施
- 注意: `Dialect.ORACLE` (`:name` プレースホルダ) を使用、`named_params` でバインド

### TASK-030

- 補足: DevContainer に Oracle ポート転送・環境変数・initializeCommand を追加、Makefile に `test-oracle` ターゲット追加

### TASK-031

- 補足: `.github/workflows/ci.yml` を作成。lint / test-sqlite / test-postgresql / test-mysql / test-oracle の5ジョブ（計9並列）
- 注意: サービスコンテナの設定は docker-compose.yml と一致させる

### TASK-032

- 補足: 既存の `Dialect` enum にDB固有プロパティを追加する
  - `like_escape_chars`: LIKE句でエスケープが必要な文字のセット（Oracle/DB2: 全角`％＿`含む、SQL Server: `[`含む）
  - `in_clause_limit`: IN句の要素数上限（Oracle: 1000、他: 無制限）
  - `backslash_is_escape`: バックスラッシュがエスケープ文字として機能するか（MySQL/PostgreSQL: True、他: False）
- 参考: Clione-SQL の `Dialect.java` / `OracleDialect.java` / `MysqlDialect.java` / `PostgresDialect.java`
- 注意: 現在の Dialect は `(dialect_id, placeholder)` のタプル値。プロパティメソッドで拡張するか、NamedTuple/dataclass に変更するか設計判断が必要

### TASK-033

- 補足: IN句展開（TASK-008で実装済み）に上限分割機能を追加する
  - `Dialect.in_clause_limit` を超える場合、`IN (?, ?, ...) OR col IN (?, ?, ...)` のように自動分割
  - Clione-SQL の `ConditionPlaceHolder.perform()` と同等の処理
- 注意: 分割時に括弧で囲む必要がある `(col IN (...) OR col IN (...))`

### TASK-034

- 補足: LIKE用パラメータのエスケープ処理を実装する
  - ユーティリティ関数 `escape_like(value, dialect)` として実装（`src/sqly/escape_utils.py`）
  - エスケープ対象文字は `Dialect.like_escape_chars` から取得
  - `Dialect.like_escape_char` プロパティを追加（デフォルト: `#`）
  - 自動検出機能は BACKLOG-009 として将来対応
- 参考: Clione-SQL の `Dialect.needLikeEscape()` メソッド
- 実装済み: `escape_like()` 関数、テスト（`tests/test_dialect.py`）

### TASK-035

- 補足: SqlLoader に RDBMS 別 SQL ファイルロード機能を追加する
  - `load("find.sql", dialect=Dialect.ORACLE)` → まず `find.sql-oracle` を探し、なければ `find.sql` にフォールバック
  - Clione-SQL の `LoaderUtil.getNodeByPath(sqlPath, productName)` と同等
- 注意: ファイル名サフィックスは `-{dialect_name}` 形式（例: `find.sql-postgresql`）
- 実装済み: `SqlLoader.load()` に `dialect` 引数追加、テスト（`tests/test_sql_loader.py`）

### TASK-036

- 補足: TASK-033〜035 で追加した Dialect 機能の統合テストを全 RDBMS（SQLite/PostgreSQL/MySQL/Oracle）で実施
- 注意: IN 句分割・LIKE エスケープ・SQL ファイルロードを各 DB で実行検証する

## Backlog（Doma2 相当の Dialect 拡張）

以下は Doma2 が提供する ORM レベルの Dialect 機能。sqly の現在のスコープ（SQL テンプレートエンジン）を超える可能性があるため、必要に応じて採用を検討する。

| ID | Summary | 参考（Doma2） |
|---|---|---|
| BACKLOG-001 | ページネーションの DB 別生成 | PostgreSQL/SQLite: `LIMIT/OFFSET`、MySQL: `LIMIT m,n`、Oracle: `OFFSET FETCH` / `ROWNUM` |
| BACKLOG-002 | 識別子クォートの DB 別対応 | MySQL: `` ` ``、MSSQL: `[]`、他: `"` |
| BACKLOG-003 | UPSERT 文の DB 別生成 | PostgreSQL/SQLite: `ON CONFLICT`、MySQL: `ON DUPLICATE KEY`、Oracle/MSSQL: `MERGE INTO` |
| BACKLOG-004 | FOR UPDATE（悲観ロック）の DB 別生成 | PostgreSQL: `FOR UPDATE OF alias`、MySQL: `FOR UPDATE`、DB2: `FOR UPDATE WITH RS` |
| BACKLOG-005 | ID 生成（IDENTITY / SEQUENCE）の DB 別対応 | PostgreSQL: `currval()`、SQLite: `last_insert_rowid()`、Oracle: `seq.nextval FROM dual` |
| BACKLOG-006 | 一意制約違反の DB 別検出 | PostgreSQL: SQLState `23505`、MySQL: エラーコード `1062`、SQLite: メッセージ判定 |
| BACKLOG-007 | スクリプトブロック区切り文字の DB 別対応 | Standard: `/`、MSSQL: `GO`、DB2: `@` |
| BACKLOG-008 | DB バージョン別 Dialect 対応 | Oracle 11g vs 12c+、MySQL 5 vs 8、MSSQL 2008 vs 2012+ 等 |
| BACKLOG-009 | LIKE 演算子自動検出による自動エスケープ | パーサーが LIKE 演算子を検出して自動的に `escape_like()` を適用 |

### 各 Backlog 詳細

#### BACKLOG-001: ページネーション

- Dialect ごとに異なるページネーション SQL を生成する
  - SQLite/PostgreSQL: `LIMIT n OFFSET m`
  - MySQL: `LIMIT m, n`（または `LIMIT n OFFSET m`）
  - Oracle 12c+: `OFFSET m ROWS FETCH NEXT n ROWS ONLY`
  - Oracle 11g: `ROWNUM` ラップ
- 参考: Doma2 の `*PagingTransformer` クラス群
- 注意: sqly は SQL テンプレートエンジンのため、開発者が SQL に直接記述することでも対応可能。エンジン側で提供する必要性は低い

#### BACKLOG-002: 識別子クォート

- テーブル名・カラム名のクォート文字を Dialect で切り替える
- `Dialect.quote_identifier(name)` / `Dialect.unquote_identifier(name)` メソッド
- 参考: Doma2 `Dialect.applyQuote()` / `removeQuote()`

#### BACKLOG-003: UPSERT 文生成

- Dialect ごとに異なる UPSERT 構文を生成するビルダー
  - PostgreSQL/SQLite: `INSERT INTO ... ON CONFLICT (key) DO UPDATE SET ...`
  - MySQL: `INSERT INTO ... ON DUPLICATE KEY UPDATE ...`
  - Oracle/MSSQL: `MERGE INTO target USING source ON (...) WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...`
- 参考: Doma2 `*UpsertAssembler` クラス群

#### BACKLOG-004: FOR UPDATE（悲観ロック）

- SELECT 文への FOR UPDATE 句付与を Dialect で制御
  - サポート有無（SQLite/HSQLDB は非対応）
  - NOWAIT オプション対応（MySQL 8+、PostgreSQL、MSSQL）
  - テーブル指定（`FOR UPDATE OF alias`、PostgreSQL）
- 参考: Doma2 `SelectForUpdateType` / `*ForUpdateTransformer`

#### BACKLOG-005: ID 生成

- INSERT 後の自動生成 ID 取得を Dialect で抽象化
  - IDENTITY 方式: `last_insert_rowid()`（SQLite）、JDBC `getGeneratedKeys()`（MySQL）
  - SEQUENCE 方式: `nextval('seq')`（PostgreSQL）、`seq.nextval FROM dual`（Oracle）
- 参考: Doma2 `Dialect.getIdentitySelectSql()` / `getSequenceNextValSql()`

#### BACKLOG-006: 一意制約違反検出

- DB 固有のエラーコード / SQLState から一意制約違反を判定するユーティリティ
  - PostgreSQL/DB2: SQLState `23505`
  - MySQL: エラーコード `1022` or `1062`
  - SQLite: メッセージ内の `SQLITE_CONSTRAINT_UNIQUE`
- 参考: Doma2 `Dialect.isUniqueConstraintViolation()`

#### BACKLOG-007: スクリプトブロック区切り文字

- SQL スクリプト実行時のステートメント区切り文字を Dialect で制御
- DDL マイグレーション等で使用
- 参考: Doma2 `Dialect.getScriptBlockDelimiter()`

#### BACKLOG-008: DB バージョン別 Dialect

- 同一 RDBMS でもバージョンにより機能差がある場合の対応
  - Oracle 11g: `ROWNUM` ページネーション / IDENTITY 非対応
  - Oracle 12c+: `OFFSET FETCH` / IDENTITY 対応
  - MySQL 5: FOR UPDATE NOWAIT 非対応
  - MySQL 8: FOR UPDATE NOWAIT 対応
- 参考: Doma2 `Oracle11Dialect` → `OracleDialect`、`MysqlDialect.MySqlVersion`

#### BACKLOG-009: LIKE 演算子自動検出による自動エスケープ

- パーサーが LIKE 演算子を検出して、パラメータ値に対して自動的に `escape_like()` を適用する
  - `WHERE name LIKE /* $name */'%太郎%'` のようなパターンを検出
  - 検出時にパラメータ値を自動エスケープし、ESCAPE 句を自動付与
- 参考: Clione-SQL の `Dialect.needLikeEscape()` メソッド
- 現在は `escape_like()` ユーティリティ関数として手動エスケープが可能（TASK-034 で実装済み）
- 注意: 自動検出は複雑なため、ユーザーが明示的に `escape_like()` を使う方式を推奨する可能性もあり
