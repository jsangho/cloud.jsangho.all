from mcp.server.fastmcp import FastMCP

"""
도널드 던 / 재러드 (Donald "Jared" Dunn) — 파이드 파이퍼 COO
전직 후플리 사업개발팀 출신. 냉철한 비즈니스 감각과 따뜻한 인간미를 겸비.
팀의 운영·계획·투자자 관리를 도맡으며 리처드의 든든한 버팀목 역할.
"""

mcp = FastMCP("PiperCOO")


@mcp.tool("myself")
async def introduce_myself() -> str:
    return "파이퍼 COO 던 입니다"
