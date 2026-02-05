# Examples

sqlym の使用例。

## clean_architecture/

Clean Architecture での実装例。

```
clean_architecture/
├── domain/models/           # エンティティ
├── application/use_cases/   # ユースケース
├── infrastructure/repositories/  # Repository (sqlym)
└── sql/
```

```bash
cd examples/clean_architecture
PYTHONPATH="../../src:." uv run python main.py
```

詳細は [clean_architecture/README.md](clean_architecture/README.md) を参照。
