from mcp.server.fastmcp import FastMCP

"""
리처드 헨드릭스 (Richard Hendricks) — 파이드 파이퍼 CEO
천재 알고리즘 엔지니어 출신. 중간 아웃 압축 알고리즘을 개발해 회사를 창업.
기술적 완벽주의자이지만 리더십과 대인관계에서 자주 어려움을 겪음.
"""

mcp = FastMCP("PiperCEO")


@mcp.tool("myself")
async def introduce_myself() -> str:
    return "파이퍼 CEO 헨드릭스 입니다"
