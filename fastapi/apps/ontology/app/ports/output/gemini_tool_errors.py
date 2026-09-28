"""도구 호출이 끝내 답을 얻지 못했을 때의 오류.

`kayfabe.app.ports.output.agent_errors`와 같은 자리다 — 포트가 무엇을 던지는지는
포트의 계약이므로 어댑터가 아니라 app 계층에 둔다. 스포크는 이 이름을 직접 import해
잡는다(허브의 app을 읽는 것은 스타 토폴로지에서 허용된다).
"""

from __future__ import annotations


class ToolCallUnavailableError(RuntimeError):
    """모델에게 물어볼 수 없었다. **벤더의 일시 장애를 다 견딘 뒤의 상태다.**

    `gemini_agent_support.MAX_ATTEMPTS`가 막는 것과 같은 장애다 — 503
    `high demand`가 실제로 관측됐고, 재시도가 없으면 그 한 번으로 실행이 끊긴다.
    2026-09-28 운영 실측에서 경기 넷째에 503이 나 **앞선 셋의 작업까지 함께 날아갔다.**

    이 오류는 "모델이 못 골랐다"와 다르다. 저쪽은 정상적인 보류(`NO_WINNER`·
    `NO_CLAIM`)이고, 이쪽은 **아예 묻지 못한 것**이다. 보고에서 두 상태를 섞으면
    "위키에 결과가 없다"와 "우리가 못 물었다"를 구분할 수 없다.
    """
