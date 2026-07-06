from mcp.server.fastmcp import FastMCP

"""
넬슨 빅헤티 (Nelson "Big Head" Bighetti) — 파이드 파이퍼 HR
리처드의 오랜 친구. 뛰어난 기술력보다 운으로 성공하는 캐릭터.
후플리에서 아무것도 안 하고 고액 연봉을 받으며 스탠퍼드 교수까지 역임.
"""

mcp = FastMCP("PiperHR")


@mcp.tool("myself")
async def introduce_myself() -> str:
    return "파이퍼 HR 빅헤티 입니다"
