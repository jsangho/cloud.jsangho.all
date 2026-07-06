# 엔티티·테이블 PK 규칙 (Cursor)

`fastapi/` 아래 **DB 테이블·ORM 엔티티**를 정의·마이그레이션할 때 이 문서를 따른다.  
레이어 구조 등 일반 백엔드 규칙은 `fastapi/.cursorrules`를 본다.

---

## 1. 원칙

| 항목 | 규칙 |
|------|------|
| 기본 키(PK) | **모든 테이블**에 `int` 타입 PK를 둔다 |
| PK 컬럼명 | Python 필드·DB 컬럼명 모두 **`id`** 로 통일 |
| 증가 방식 | DB **자동 증감**(auto increment / identity) |
| 용도 | 시스템 내부용 고유 번호 (서로 다른 테이블·행을 구분) |

- `user_id`, `uuid`, `login_id` 등을 **PK로 쓰지 않는다.** (비즈니스 식별자는 별도 컬럼 + `unique`/`index`)
- 복합 PK만 두지 않는다. 관계 테이블도 `id` PK를 두고, 필요 시 `(fk_a, fk_b)`에 **유니크 제약**을 추가한다.
- 외래 키는 참조 테이블의 **`id`** 를 가리킨다 (예: `user_id` 컬럼 → `users.id`).

---

## 2. 참조 패턴 — SQLModel (`Field`)

프로젝트에 `sqlmodel`이 포함되어 있을 때, 테이블 모델의 PK는 아래 형태로 정의한다.

```python
from typing import Optional

from sqlmodel import Field, SQLModel


class ExampleModel(SQLModel, table=True):
    __tablename__ = "examples"

    # 1. 시스템 내부용 자동 증감 고유 번호 (기본 키)
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"name": "id"},  # DB 컬럼명: id
    )
```

- `default=None` + `primary_key=True`: INSERT 시 DB가 다음 번호를 할당한다.
- `sa_column_kwargs={"name": "id"}`: ORM 필드명과 DB 컬럼명을 **`id`** 로 맞춘다.
- 마이그레이션(Alembic 등)에서도 PK 컬럼명은 `id`, 타입은 정수(`INTEGER` / `BIGSERIAL` 등 프로젝트 표준에 맞게)로 생성한다.

---

## 3. 참조 패턴 — SQLAlchemy 2.0 (`Mapped` + `Base`)

`database.Base`를 상속하는 모델은 동일 규칙을 `mapped_column`으로 표현한다.

```python
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # ... 이하 비즈니스 컬럼
```

- 저장소 예시: `backend/apps/secom/app/models/user_model.py`

SQLModel·SQLAlchemy Declarative **어느 쪽이든** PK는 `int` + 이름 `id`만 허용한다.

---

## 4. 비즈니스 식별자와 PK 구분

| 구분 | 예시 컬럼 | PK 여부 |
|------|-----------|---------|
| 시스템 PK | `id` | ✅ PK |
| 로그인 ID | `login_id` | ❌ (`unique`, `index` 가능) |
| 이메일 | `email` | ❌ (`unique` 가능) |
| 외래 키 | `user_id` → `users.id` | ❌ (FK 컬럼) |

---

## 5. 금지·주의

```python
# ❌ PK 이름이 id가 아님
user_id: Mapped[int] = mapped_column(primary_key=True)

# ❌ UUID·문자열 PK
id: Mapped[str] = mapped_column(primary_key=True)

# ❌ 복합 PK만 존재 (id 없음)
__table_args__ = (PrimaryKeyConstraint("order_id", "line_no"),)
```

---

## 6. Cursor 에이전트 지시문 (복사·@멘션용)

```text
docs/DevOps/Backend/ENTITY_RULE.md 를 따르세요.

이 프로젝트의 모든 테이블은 반드시 int 타입의 기본 키를 갖고,
Python 필드·DB 컬럼 이름은 id 로 통일합니다.

SQLModel 예시:
id: Optional[int] = Field(
    default=None,
    primary_key=True,
    sa_column_kwargs={"name": "id"},
)

SQLAlchemy Mapped 예시:
id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

비즈니스 식별자(login_id, email 등)는 PK가 아닌 별도 컬럼으로 둡니다.
docs/DevOps/Backend/BACKEND_RULES.md 레이어 구조도 지킵니다.
```

---

## 7. 체크리스트 (리뷰·신규 테이블)

- [ ] 테이블에 `int` PK `id`가 있는가?
- [ ] DB·ORM 모두 컬럼명이 `id`인가? (`sa_column_kwargs` 또는 `mapped_column` 기본명)
- [ ] 자동 증감(또는 identity)이 설정되어 있는가?
- [ ] 비즈니스 키를 PK로 쓰지 않았는가?
- [ ] FK는 `{table}_id` 형태로 참조 테이블의 `id`를 가리키는가?
