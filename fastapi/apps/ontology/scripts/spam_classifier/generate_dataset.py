"""Ollama(exaone3.5:7.8b)로 스팸 분류기 파인튜닝용 합성 학습 데이터를 생성한다.

기존 dataset.jsonl이 있으면 이어서(resume) 라벨별 목표치까지만 추가 생성한다.

실행: docker compose exec backend python apps/ontology/scripts/spam_classifier/generate_dataset.py
출력: ontology/scripts/spam_classifier/data/dataset.jsonl (subject, body, label)
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import httpx

_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_MODEL = "exaone3.5:7.8b"
_OUT_PATH = Path(__file__).resolve().parent / "data" / "dataset.jsonl"
_MAX_ATTEMPTS_PER_LABEL = 700  # 중복·실패 감안한 여유

_TARGET_PER_LABEL: dict[str, int] = {
    "ham": 250,
    "phishing": 250,
    "advertisement": 380,
    "scam": 380,
    "malware": 250,
    "abusive": 250,  # swap_abusive_with_unsmile.py가 실데이터로 교체하므로 여유만 확보
}

_LABEL_GUIDES: dict[str, str] = {
    "ham": (
        "정상적인 업무/개인 메일. 문의, 안내, 회의 일정, 보고, 감사 인사, "
        "뉴스레터 구독 확인, 배송 안내, 계정 정상 알림 등 다양한 상황."
    ),
    "phishing": (
        "계정/비밀번호/로그인 정보를 입력하도록 유도하는 사칭 메일. "
        "은행, 포털, 회사 IT팀, 클라우드 서비스 등을 사칭한 다양한 시나리오."
    ),
    "advertisement": (
        "발신자가 자신의 상품/서비스를 홍보·판매하려는 광고 메일. "
        "쇼핑몰, 강의, 구독 서비스, 앱, 이벤트 등 다양한 업종."
    ),
    "scam": (
        "금전 송금이나 개인정보를 요구하는 사기 메일. "
        "복권 당첨, 유산 상속, 투자 사기, 가짜 환불, 로맨스 스캠 등 다양한 수법."
    ),
    "malware": (
        "첨부파일 실행이나 프로그램 다운로드를 유도하는 악성코드 메일. "
        "청구서, 택배 송장, 이력서, 보안 업데이트 등을 가장한 다양한 미끼."
    ),
    "abusive": (
        "욕설·모욕·혐오 표현이 포함된 메일. 불만 고객의 항의, 악의적인 비방, "
        "인신공격성 발언 등 다양한 상황(실제 비속어를 사용하되 특정 인물·집단을 "
        "실존 대상으로 지목하지 않는다)."
    ),
}

# 라벨별 시나리오 각도 — 매 호출마다 무작위로 하나씩 붙여서 템플릿 반복을 줄인다.
_ANGLES: dict[str, list[str]] = {
    "ham": [
        "동료 간 업무 확인",
        "고객 문의 응대",
        "회의 일정 조율",
        "감사 인사",
        "뉴스레터 구독 확인",
        "배송/주문 안내",
        "계정 정상 로그인 알림",
        "채용 관련 안내",
        "행사 초대(사내)",
        "간단한 안부",
    ],
    "phishing": [
        "은행 계정 잠금 경고",
        "회사 IT팀의 비밀번호 만료 안내",
        "클라우드 저장공간 초과 경고",
        "포털 로그인 이상 감지",
        "택배사 배송 확인 사칭",
        "국세청/정부기관 사칭",
        "SNS 계정 정지 경고",
        "화상회의 초대 사칭",
    ],
    "advertisement": [
        "쇼핑몰 시즌 할인",
        "온라인 강의/클래스 홍보",
        "구독 서비스 무료체험",
        "모바일 앱 설치 유도",
        "멤버십 갱신 혜택",
        "신제품 출시 안내",
        "웨비나 초대",
        "B2B 소프트웨어 영업",
        "여행 패키지 프로모션",
        "식당/카페 오픈 이벤트",
        "부동산 매물 홍보",
        "보험 상품 안내",
    ],
    "scam": [
        "복권/추첨 당첨 통보",
        "해외 유산 상속 안내",
        "투자 고수익 보장",
        "가짜 환불/보상 절차",
        "로맨스 스캠(온라인 인연)",
        "정부 지원금 사칭",
        "긴급 송금 요청(지인 사칭)",
        "암호화폐 이벤트 사기",
        "채용 미끼 선입금 요구",
    ],
    "malware": [
        "가짜 청구서 첨부파일",
        "택배 송장 사칭 첨부파일",
        "이력서 위장 첨부파일",
        "보안 업데이트 실행 유도",
        "인보이스 매크로 문서",
        "무료 소프트웨어 크랙 다운로드",
        "팩스/스캔 문서 사칭",
        "법원/고소장 사칭 첨부파일",
    ],
    "abusive": [
        "불만 고객의 항의",
        "동료 간 갈등",
        "온라인 댓글식 비방",
        "고객센터 상담원에 대한 폭언",
        "거래 취소로 인한 분노 표출",
    ],
}

_PROMPT_TEMPLATE = """당신은 한국어 이메일 데이터셋 생성기입니다.
아래 유형에 해당하는 이메일 1개를 새로 생성하세요. 이전에 만든 것과는 다른 발신자·상황·어투로 작성하세요.

유형: {label} — {guide}
이번 시나리오: {angle}

제목(subject)은 짧게 1개 문구로, 본문(body)은 1~2문장으로 간결하게 작성하세요.
제목과 본문을 합쳐 반드시 100~150자 이내로 작성하세요. 실제 이메일처럼 자연스럽게 작성하세요.

다음 형식의 JSON으로만 답하세요: {{"subject": "...", "body": "..."}}
"""

# LLM이 길이 지시를 안 지킬 때가 있어 사후 필터로 강제한다(UnSmile abusive 평균 길이와 격차를 줄이기 위함).
_MIN_LENGTH = 40
_MAX_LENGTH = 200


def _generate_one(label: str) -> dict[str, str] | None:
    angle = random.choice(_ANGLES[label])
    prompt = _PROMPT_TEMPLATE.format(
        label=label, guide=_LABEL_GUIDES[label], angle=angle
    )
    try:
        response = httpx.post(
            f"{_HOST}/api/generate",
            json={
                "model": _MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 1.1},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        raw = json.loads(response.json()["response"])
    except Exception as e:  # noqa: BLE001
        print(f"  생성 실패: {e}")
        return None

    subject, body = raw.get("subject"), raw.get("body")
    if not subject or not body:
        return None
    if not (_MIN_LENGTH <= len(subject) + len(body) <= _MAX_LENGTH):
        return None
    return {"subject": subject, "body": body}


def _load_existing() -> list[dict[str, str]]:
    if not _OUT_PATH.exists():
        return []
    with _OUT_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> None:
    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_existing()
    seen: set[tuple[str, str]] = {(r["subject"], r["body"]) for r in rows}
    print(f"기존 {len(rows)}개 로드 (라벨별 목표까지 추가 생성)")

    for label, target in _TARGET_PER_LABEL.items():
        collected = sum(1 for r in rows if r["label"] == label)
        attempts = 0
        start = collected
        while collected < target and attempts < _MAX_ATTEMPTS_PER_LABEL:
            attempts += 1
            item = _generate_one(label)
            if item is None:
                continue
            key = (item["subject"], item["body"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({**item, "label": label})
            collected += 1
            if collected % 40 == 0:
                print(f"[{label}] {collected}/{target}")
        print(
            f"[{label}] 완료: {collected}/{target} ({collected - start}개 추가, 시도 {attempts}회)"
        )

    with _OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n총 {len(rows)}개 저장 → {_OUT_PATH}")
    for label in _TARGET_PER_LABEL:
        count = sum(1 for r in rows if r["label"] == label)
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
