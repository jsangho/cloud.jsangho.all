from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeminiGenerationCommand:
    prompt: str
    #: 쓸 모델. 비우면 어댑터의 기본값(`GEMINI_MODEL` 환경변수)을 쓴다.
    #:
    #: 무료 등급의 호출 한도가 **모델 단위**라, 부르는 쪽이 모델을 나눠 쓰면 서로의
    #: 한도를 갉아먹지 않는다. 그래서 호출마다 지정할 수 있게 열어 둔다.
    model: str | None = None
