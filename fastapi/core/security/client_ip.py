"""프록시 뒤에서 실제 클라이언트 IP를 뽑는다.

이 스택은 cloudflared 터널 뒤에 있어서 `request.client.host`가 항상 터널 컨테이너의
내부 IP(예: `172.28.0.3`)로 찍힌다. 그 값으로 감사 로그를 남기면 모든 요청이 같은
IP로 보여 아무 의미가 없다.

**신뢰 경계 주의**: 아래 헤더들은 클라이언트가 위조할 수 있다. 우리처럼 신뢰하는
프록시(cloudflared)만이 앱에 도달할 수 있는 구성에서는 프록시가 헤더를 덮어쓰므로
안전하지만, 앱 포트가 외부에 직접 노출되면 이 값을 믿으면 안 된다.
현재 `backend`는 cloudflared를 통해서만, `auth`는 포트 미노출로 들어온다.
"""

from __future__ import annotations

from fastapi import Request

# Cloudflare가 원본 IP를 넣는 헤더. 터널을 쓰면 항상 채워진다.
_CLOUDFLARE_HEADER = "cf-connecting-ip"
# 일반 리버스 프록시 표준. 쉼표로 이어지며 **맨 앞이 원본 클라이언트**다.
_FORWARDED_FOR_HEADER = "x-forwarded-for"


def client_ip(request: Request) -> str:
    """실제 클라이언트 IP. 알 수 없으면 빈 문자열."""
    cloudflare_ip = request.headers.get(_CLOUDFLARE_HEADER)
    if cloudflare_ip:
        return cloudflare_ip.strip()

    forwarded = request.headers.get(_FORWARDED_FOR_HEADER)
    if forwarded:
        # "203.0.113.7, 172.28.0.3" → 맨 앞. 뒤쪽은 거쳐온 프록시들이다.
        first = forwarded.split(",")[0].strip()
        if first:
            return first

    return request.client.host if request.client else ""
