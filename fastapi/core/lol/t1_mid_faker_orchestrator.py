"""
exaone3.5:2.4b 오케스트레이터 — Ollama 로컬 LLM 래퍼
"""

from dataclasses import dataclass, field

import ollama

MODEL_ID = "exaone3.5:2.4b"


@dataclass
class FakerOrchestrator:
    """exaone3.5:2.4b 를 오케스트레이터로 등록·구동한다."""

    model: str = MODEL_ID
    system_prompt: str = "당신은 유능한 AI 어시스턴트입니다."
    host: str = "http://localhost:11434"
    history: list[dict] = field(default_factory=list)
    _client: ollama.AsyncClient = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = ollama.AsyncClient(host=self.host)

    def reset(self) -> None:
        self.history.clear()

    async def chat(self, user_message: str) -> str:
        """히스토리를 유지한 채 exaone 과 대화한다."""
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": self.system_prompt}, *self.history]
        response = await self._client.chat(model=self.model, messages=messages)
        assistant_message = response.message.content

        self.history.append({"role": "assistant", "content": assistant_message})
        return assistant_message

    async def generate(self, prompt: str) -> str:
        """단발성 프롬프트 → 응답 (히스토리 없음)."""
        response = await self._client.generate(model=self.model, prompt=prompt)
        return response.response

    async def is_available(self) -> bool:
        """Ollama 서버에서 exaone 모델이 사용 가능한지 확인한다."""
        try:
            models = await self._client.list()
            return any(m.model.startswith(self.model) for m in models.models)
        except Exception:
            return False
