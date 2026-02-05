# TASKS

マイルストーン: M2
ゴール: sqlym の高レベル API（Sqlym クラス）と Clione-SQL 互換機能を実装し v0.2.0 をリリースする

## ワークフロールール

- タスク着手時にステータスを 🚧 に更新する
- タスク完了時にステータスを ✅ に更新する
- DependsOn のタスクがすべて ✅ でないタスクには着手しない

## ステータス表記ルール

| Status | 意味 |
| ---- | ----- |
| ⏳ | 未着手、TODO |
| 🚧 | 作業中、IN_PROGRESS |
| 🧪 | 確認待ち、REVIEW |
| ✅ | 完了、DONE |
| 🚫 | 中止、CANCELLED |

## タスク一覧

| ID | Status | Summary | DependsOn |
|----|--------|---------|-----------|
| TASK-001 | ⏳ | Sqlym クラスの基本実装（__init__、query、query_one、execute） | - |
| TASK-002 | ⏳ | commit/rollback メソッドの実装（connection への委譲） | TASK-001 |
| TASK-003 | ⏳ | コンテキストマネージャの実装（__enter__/__exit__ の委譲） | TASK-002 |
| TASK-004 | ⏳ | auto_commit 機能の実装 | TASK-001 |
| TASK-005 | ⏳ | Dialect 自動検出機能の実装 | TASK-001 |
| TASK-006 | ⏳ | Sqlym クラスのユニットテスト作成 | TASK-003,TASK-004,TASK-005 |
| TASK-007 | ⏳ | Sqlym クラスの統合テスト作成（SQLite） | TASK-006 |
| TASK-008 | ⏳ | negative/positive 判定の拡張（False、空リスト対応） | - |
| TASK-009 | ⏳ | negative/positive 拡張のテスト作成 | TASK-008 |
| TASK-010 | ⏳ | 行末区切り（AND/OR/カンマ）の自動除去機能を実装 | - |
| TASK-011 | ⏳ | 行末区切り除去のテスト作成 | TASK-010 |
| TASK-012 | ⏳ | `&` 修飾記号（バインドなし行削除）の実装 | - |
| TASK-013 | ⏳ | `&` 修飾記号のテスト作成 | TASK-012 |
| TASK-014 | ⏳ | `!` 否定修飾子の実装 | TASK-012 |
| TASK-015 | ⏳ | `!` 否定修飾子のテスト作成 | TASK-014 |
| TASK-016 | ⏳ | `@` 必須パラメータ修飾記号の実装 | - |
| TASK-017 | ⏳ | `@` 修飾記号のテスト作成 | TASK-016 |
| TASK-018 | ⏳ | `?` フォールバック修飾記号の実装 | TASK-008 |
| TASK-019 | ⏳ | `?` 修飾記号のテスト作成 | TASK-018 |
| TASK-020 | ⏳ | 区切りのみの行（UNION/UNION ALL 等）の結合処理実装 | - |
| TASK-021 | ⏳ | 区切り行結合のテスト作成 | TASK-020 |
| TASK-022 | ⏳ | 比較演算子の自動変換（`/* param */=` 形式）の実装 | TASK-008 |
| TASK-023 | ⏳ | 比較演算子自動変換のテスト作成 | TASK-022 |
| TASK-024 | ⏳ | IN 句の部分展開（固定値 + パラメータ混在）の実装 | - |
| TASK-025 | ⏳ | IN 句部分展開のテスト作成 | TASK-024 |
| TASK-026 | ⏳ | LIKE 句のリスト展開（OR 展開）の実装 | TASK-022 |
| TASK-027 | ⏳ | LIKE 句リスト展開のテスト作成 | TASK-026 |
| TASK-028 | ⏳ | WITH 句（CTE）過剰削除バグの修正 | - |
| TASK-029 | ⏳ | WITH 句修正のテスト更新 | TASK-028 |
| TASK-030 | ⏳ | 複数行文字列リテラルの解析対応 | - |
| TASK-031 | ⏳ | 複数行文字列リテラルのテスト作成 | TASK-030 |
| TASK-032 | ⏳ | `%concat` / `%C` 補助関数の実装 | - |
| TASK-033 | ⏳ | `%concat` 補助関数のテスト作成 | TASK-032 |
| TASK-034 | ⏳ | `%L` 補助関数（LIKE エスケープ + escape 句付与）の実装 | TASK-032 |
| TASK-035 | ⏳ | `%L` 補助関数のテスト作成 | TASK-034 |
| TASK-036 | ⏳ | `-- %IF` / `-- %ELSE` ブロック切り替えの実装 | - |
| TASK-037 | ⏳ | ブロック切り替えのテスト作成 | TASK-036 |
| TASK-038 | ⏳ | `%if-%elseif-%else` インライン条件分岐の実装 | TASK-036 |
| TASK-039 | ⏳ | インライン条件分岐のテスト作成 | TASK-038 |
| TASK-040 | ⏳ | `%STR` / `%SQL` 直接埋め込み補助関数の実装 | - |
| TASK-041 | ⏳ | `%STR` / `%SQL` のテスト作成 | TASK-040 |
| TASK-042 | ⏳ | `%include` SQL インクルード機能の実装 | - |
| TASK-043 | ⏳ | `%include` のテスト作成 | TASK-042 |
| TASK-044 | ⏳ | Clean Architecture 実装例の追加（examples/clean_architecture/） | TASK-007 |
| TASK-045 | ⏳ | シンプルツール実装例の追加（examples/simple_tool/） | TASK-004 |
| TASK-046 | ⏳ | M2 全機能の統合テスト作成 | TASK-007,TASK-009,TASK-011,TASK-013,TASK-015,TASK-017,TASK-019,TASK-021,TASK-023,TASK-025,TASK-027,TASK-029,TASK-031 |
| TASK-047 | ⏳ | README の API 例を Sqlym に更新 | TASK-007 |
| TASK-048 | ⏳ | ドキュメント更新（SPEC.md、SQL_SYNTAX.md） | TASK-046 |
| TASK-049 | ⏳ | バージョンを 0.2.0 に更新しリリース準備 | TASK-048 |

## タスク詳細（補足が必要な場合のみ）

### TASK-001

- 補足: 既存の低レベル API（SqlLoader, parse_sql, create_mapper）を内部で使用する
- 注意: カーソル管理と行の dict 変換は内部で行う

### TASK-003

- 補足: `__enter__` / `__exit__` を connection に委譲する
- 注意: sqlym はトランザクションロジックを実装しない（connection の動作に依存）

### TASK-004

- 補足: `auto_commit=True` の場合、execute() 後に自動で connection.commit() を呼ぶ
- 用途: ツールやライトなアプリケーション向け

### TASK-005

- 補足: connection オブジェクトのモジュール名から RDBMS を推測する
- 注意: 検出できない場合は Dialect.SQLITE をデフォルトとする

### TASK-008

- 補足: None に加え、False、空リスト []、全要素が negative のリストも negative として扱う

### TASK-018

- 補足: `/* ?param1 ?param2 */default` 形式で、左から順に positive な値を使用
- 注意: TASK-008 の negative/positive 拡張に依存する

### TASK-022

- 補足: パラメータを `=`, `<>`, `IS`, `IN` 等の前に置いた場合に演算子を自動変換する
- 注意: TASK-008 の negative/positive 拡張に依存する

### TASK-028

- 補足: CTE 内の SELECT 行はパラメータを含まない場合、削除対象外とする
- 注意: 既存の test_twoway_with_clause.py のテストケースを更新する

### TASK-040

- 補足: SQL インジェクションのリスクがあるため、警告をドキュメントに明記する

### TASK-042

- 補足: SqlLoader と連携して相対パスで SQL ファイルをインクルードする
- 注意: 循環インクルードの検出が必要

### TASK-044

- 補足: Clean Architecture / Onion Architecture での UnitOfWork パターン実装例
- 内容: Service 層、Repository 層、UnitOfWork の構成例

### TASK-045

- 補足: auto_commit を使ったシンプルな CLI ツールの実装例
- 内容: DB マイグレーションツールや一括更新スクリプト等
