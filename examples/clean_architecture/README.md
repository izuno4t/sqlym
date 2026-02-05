# Clean Architecture Example

sqlym を使った厳密な Clean Architecture の実装例。

## 構成

```
clean_architecture/
├── main.py                              # Composition Root
├── domain/                              # ドメイン層
│   ├── models/                          # ドメインモデル
│   │   ├── user.py
│   │   └── order.py
│   └── repositories/                    # リポジトリインターフェース
│       ├── user_repository.py
│       └── order_repository.py
├── application/                         # アプリケーション層
│   └── use_cases/
│       ├── create_user.py
│       └── create_order.py
├── infrastructure/                      # インフラストラクチャ層
│   ├── dao/
│   │   ├── entities/                    # 永続化エンティティ
│   │   │   ├── user_entity.py
│   │   │   └── order_entity.py
│   │   ├── user_dao.py                  # DAO (sqlym)
│   │   └── order_dao.py
│   └── repositories/                    # リポジトリ実装
│       ├── user_repository.py
│       └── order_repository.py
└── sql/
```

## Model vs Entity

| 種類 | 場所 | 役割 |
|------|------|------|
| Model | domain/models/ | ビジネスロジック、ドメインルール |
| Entity | infrastructure/dao/entities/ | DBテーブルへのマッピング |

## データフロー

```
DB ──(SQL)──▶ DAO ──(Entity)──▶ Repository ──(Model)──▶ UseCase
                                     │
                              Entity → Model 変換
```

## 実行

```bash
cd examples/clean_architecture
PYTHONPATH="../../src:." uv run python main.py
```

## コード例

### Entity (infrastructure/dao/entities)

```python
@dataclass
class UserEntity:
    """Maps directly to users table."""
    id: int | None = None
    name: str = ""
    email: str = ""
    department: str | None = None
    created_at: str | None = None  # DB format (string)
```

### Model (domain/models)

```python
@dataclass
class User:
    """Domain model with business logic."""
    id: int | None = None
    name: str = ""
    email: str = ""
    department: str | None = None
    created_at: datetime | None = None  # Python datetime
```

### DAO (infrastructure/dao)

```python
class UserDAO:
    """Returns Entity."""
    def __init__(self, db: Sqlym) -> None:
        self._db = db

    def find_by_id(self, user_id: int) -> UserEntity | None:
        return self._db.query_one(UserEntity, "users/find_by_id.sql", {"id": user_id})
```

### Repository (infrastructure/repositories)

```python
class UserRepository(UserRepositoryInterface):
    """Converts Entity to Model."""
    def __init__(self, dao: UserDAO) -> None:
        self._dao = dao

    def find_by_id(self, user_id: int) -> User | None:
        entity = self._dao.find_by_id(user_id)
        return self._to_model(entity) if entity else None

    @staticmethod
    def _to_model(entity: UserEntity) -> User:
        return User(
            id=entity.id,
            name=entity.name,
            created_at=datetime.fromisoformat(entity.created_at) if entity.created_at else None,
        )
```

### Composition Root (main.py)

```python
class Container:
    def __init__(self, conn, sql_dir):
        db = Sqlym(conn, sql_dir=sql_dir)

        # DAOs
        user_dao = UserDAO(db)
        order_dao = OrderDAO(db)

        # Repositories (Entity → Model)
        self.user_repo = UserRepository(user_dao)
        self.order_repo = OrderRepository(order_dao)

        # Use Cases
        self.create_user = CreateUserUseCase(self.user_repo)
```
