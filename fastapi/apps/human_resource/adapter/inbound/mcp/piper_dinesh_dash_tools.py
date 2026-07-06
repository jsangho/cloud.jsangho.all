from mcp.server.fastmcp import FastMCP

"""
디네시 추크타이 (Dinesh Chugtai) — 파이드 파이퍼 대시보드 개발자
파키스탄계 풀스택 엔지니어. 길포일과 끊임없이 티격태격하는 라이벌 관계.
자존심이 강하고 허세가 있지만 실력은 검증된 개발자.
"""

mcp = FastMCP("PiperDashboard")


@mcp.tool("myself")
async def introduce_myself() -> str:
    return "파이퍼 대시보드 개발자 디네시 입니다"
