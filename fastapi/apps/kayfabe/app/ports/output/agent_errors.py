"""에이전트 어댑터가 공유하는 실패 신호.

세 에이전트 포트가 같은 예외를 던지므로 한 곳에 둔다. 도메인·포트는 HTTP를
모르므로 상태 코드는 라우터가 붙인다(하네스 §2-D8).
"""

from __future__ import annotations


class AgentUnavailableError(Exception):
    """LLM 오류·한도 초과·응답 형식 파손. 클라이언트에는 503.

    **의견 없음과 다르다.** 참고할 근거가 없어 판단을 못 한 것은 정상 상태이고
    `AgentReport(pick=None)`으로 표현한다. 이 예외는 물어보지 못한 경우다.
    """
