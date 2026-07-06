from mcp.server.fastmcp import FastMCP

"""
버트럼 길포일 (Bertram Gilfoyle) — 파이드 파이퍼 시스템 엔지니어
캐나다 출신 시스템·보안 전문가. 사탄주의자이며 냉소적이고 독설이 특기.
감정 없이 논리만으로 판단하며, 인프라·보안 분야에서는 타의 추종을 불허.
"""

mcp = FastMCP("PiperSys")


@mcp.tool("myself")
async def introduce_myself() -> str:
    return "파이퍼 시스템 엔지니어 길포일 입니다"
