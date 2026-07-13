# manager 앱 — 인바운드 이벤트 처리 현황

## 1. 아키텍처

스타 토폴로지 구조다. `ontology`가 허브, `manager`를 포함한 나머지 앱이 스포크다 (`.importlinter` 계약으로 강제됨).

```
Gmail
  │  (Pub/Sub Push → Cloudflare Tunnel → n8n Webhook)
  ▼
n8n (gmail-pubsub 웹훅) ──POST──▶ manager/adapter/inbound/api/v1/receiver_router.py
                                          │
                                          ▼
                              manager/app/use_cases/receiver_interactor.py
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                                ▼
        ontology/app/use_cases/spam_classifier_interactor.py   receiver_emails (pgvector)
        (키워드 매칭 + Neo4j 그래프 조회로 라벨 판정)             (spam_label, embedding 포함 저장)
                          │
                          ▼
              label == "ham" 이면 텔레그램 알림 발송
```

## 2. manager의 인바운드/아웃바운드 라우터 실제 현황

| 라우터 | 경로 | 상태 |
|---|---|---|
| `receiver_router.py` | `POST /api/manager/receiver/receive`, `GET /list`, `PATCH /{id}/read` | 운영 — Gmail 메일 인입 → 스팸 분류 → 임베딩 → 저장 |
| `watcher_router.py` | `GET /api/manager/watcher/myself` | 운영 — 자기소개 엔드포인트만 존재. 실제 트리아지(VIP 판정·의도 분류) 로직은 없음 |
| `judge_router.py` | `GET /api/manager/judge/myself` | 운영 — 자기소개 엔드포인트만 존재. 실제 판정 로직은 없음 |
| `telegram_router.py` | `POST /api/manager/telegram/send` | 운영 — 아웃바운드만. 인바운드(수신 메시지 처리) 없음 |
| `discord_router.py` | `GET /api/manager/discord/myself` | 자기소개만 존재. 발송/수신 기능 없음 |
| `email_router.py`, `juso_router.py` | — | 운영 (알림 발송, 연락처 관리) |

## 3. 실제 메일 처리 흐름 (`receiver_interactor.py`)

```python
async def receiver(self, cmd: ReceiverCommand) -> dict[str, int]:
    classification = await self._spam_classifier.classify(cmd.subject, cmd.body)
    item_id = await self._repository.save(cmd, classification.label, classification.confidence)
    if classification.label == "ham":
        await _telegram_notify(subject=cmd.subject, from_email=cmd.from_email)
    return {"id": item_id}
```

- 라벨 종류: `ham`, `phishing`, `advertisement`, `scam`, `malware` (`ontology/domain/enums/spam_classes.py`)
- 판정 방식: 키워드 매칭 (`ontology/domain/enums/spam_rules.py`) → Neo4j에서 라벨별 가중치 합산 → 최고점 라벨 선택
- 저장: `ham`만 저장하고 나머지 라벨(phishing/advertisement/scam/malware/abusive)은 저장 자체를 스킵. `bge-m3`(Ollama, 로컬) 임베딩을 함께 저장(`receiver_emails.embedding`, 1024차원)
- 중복 방지: `message_id` 유니크 제약 — 같은 메일이 두 번 들어오면 재사용, 재계산 안 함
- 분기: `ham`일 때만 텔레그램 알림. 그 외 라벨은 저장만 하고 알림 생략

## 4. 아직 없는 것

- 발신자 중요도(VIP) 판단, 보고서 요청 의도 분류 — 없음
- 온톨로지 허브를 경유한 에스컬레이션(다른 앱으로 이벤트 발행) — 없음
- Telegram/Discord 인바운드(수신 메시지 처리) — 없음
- `watcher_router`/`judge_router`의 실제 판단 로직 — 없음 (현재는 자기소개만 응답)
