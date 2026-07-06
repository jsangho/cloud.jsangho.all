"""dataset.jsonl의 합성 abusive 예시를 Korean UnSmile Dataset의 실제 혐오/욕설 문장으로 교체한다.

실행 (host, pytorch_env — `datasets` 라이브러리 필요):
  pytorch_env/Scripts/python.exe fastapi/apps/ontology/scripts/spam_classifier/swap_abusive_with_unsmile.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from datasets import load_dataset

_DATA_PATH = Path(__file__).resolve().parent / "data" / "dataset.jsonl"
_TARGET_COUNT = 250
_SEED = 42

# UnSmile 문장은 원래 제목이 없다. subject를 전부 빈 문자열로 두면
# "subject 없음(선행 공백)" 자체가 abusive 라벨의 지름길 신호가 되어버리므로,
# 다른 라벨과 유사하게 제목이 있는 것처럼 보이도록 문구를 순환시켜 붙인다.
_GENERIC_SUBJECTS = [
    "댓글 답장",
    "회신",
    "그 얘기 관련",
    "아까 그건",
    "이거 봐라",
    "진짜 어이없어서",
]


def main() -> None:
    rows = []
    with _DATA_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["label"] != "abusive":
                rows.append(row)

    removed = sum(1 for _ in _DATA_PATH.open(encoding="utf-8")) - len(rows)
    print(f"기존 합성 abusive {removed}개 제거")

    ds = load_dataset("smilegate-ai/kor_unsmile")["train"]
    ds = ds.filter(lambda r: r["clean"] == 0)
    ds = ds.shuffle(seed=_SEED).select(range(min(_TARGET_COUNT, len(ds))))

    for item in ds:
        sentence = item["문장"].strip()
        if not sentence:
            continue
        subject = random.choice(_GENERIC_SUBJECTS)
        rows.append({"subject": subject, "body": sentence, "label": "abusive"})

    with _DATA_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"UnSmile 실데이터 {len(ds)}개 추가")
    print(f"총 {len(rows)}개 저장 → {_DATA_PATH}")

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["label"]] = counts.get(row["label"], 0) + 1
    for label, count in counts.items():
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
