from __future__ import annotations

import html
from typing import Any

import jwt
from core.security.cookie import COOKIE_KWARGS
from core.security.role import UserRole
from core.security.token_verifier import verify_token

from auth.app.ports.input.login_use_case import LoginUseCase
from auth.dependencies.auth_provider import get_login_use_case
from auth.domain.services.token_issuer import create_access_token
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, RedirectResponse

docs_gate_router = APIRouter(tags=["docs-gate"], include_in_schema=False)

DOCS_COOKIE_NAME = "kayfabe_docs_session"
DOCS_SESSION_SECONDS = 15 * 60


def _safe_next(next_path: str) -> str:
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/docs"


def _get_admin_claims(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(DOCS_COOKIE_NAME)
    if not token:
        return None
    try:
        payload = verify_token(token)
    except jwt.PyJWTError:
        return None
    if UserRole.ADMIN.value not in payload.roles:
        return None
    return {"sub": payload.sub, "roles": payload.roles}


def _render_login_page(*, next_path: str, error: str | None = None) -> str:
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    next_attr = html.escape(next_path, quote=True)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>KayFabe Docs 로그인</title>
<style>
  body {{ background:#0c0a09; color:#e7e5e4; font-family: system-ui, sans-serif; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }}
  form {{ background:#1c1917; padding:2rem; border-radius:1rem; width:320px; border:1px solid #292524; }}
  h1 {{ font-size:1.1rem; margin:0 0 1.5rem; }}
  label {{ display:block; font-size:.85rem; color:#a8a29e; margin-bottom:.35rem; }}
  input {{ width:100%; box-sizing:border-box; padding:.6rem .75rem; margin-bottom:1rem; border-radius:.5rem; border:1px solid #44403c; background:#0c0a09; color:#e7e5e4; }}
  button {{ width:100%; padding:.65rem; border-radius:.5rem; border:none; background:#e7e5e4; color:#0c0a09; font-weight:600; cursor:pointer; }}
  .error {{ color:#f87171; font-size:.85rem; margin-bottom:1rem; }}
</style>
</head>
<body>
<form method="post" action="/docs/login">
  <h1>KayFabe 관리자 로그인</h1>
  {error_html}
  <input type="hidden" name="next" value="{next_attr}" />
  <label>ID</label>
  <input type="text" name="login_id" autocomplete="username" required />
  <label>비밀번호</label>
  <input type="password" name="password" autocomplete="current-password" required />
  <button type="submit">로그인</button>
</form>
</body>
</html>"""


@docs_gate_router.get("/docs/login")
async def docs_login_form(next: str = "/docs"):
    return HTMLResponse(_render_login_page(next_path=_safe_next(next)))


@docs_gate_router.post("/docs/login")
async def docs_login_submit(
    login_id: str = Form(...),
    password: str = Form(...),
    next: str = Form("/docs"),
    use_case: LoginUseCase = Depends(get_login_use_case),
):
    safe_next = _safe_next(next)
    denied_message = "ID 또는 비밀번호가 올바르지 않거나 권한이 없습니다."

    try:
        user = await use_case.login_user(login_id=login_id, password=password)
    except HTTPException:
        return HTMLResponse(
            _render_login_page(next_path=safe_next, error=denied_message),
            status_code=401,
        )

    role = UserRole(user.role)
    if role != UserRole.ADMIN:
        return HTMLResponse(
            _render_login_page(next_path=safe_next, error=denied_message),
            status_code=403,
        )

    token = create_access_token(sub=str(user.id), roles=[role.value])
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=DOCS_COOKIE_NAME,
        value=token,
        path="/",
        max_age=DOCS_SESSION_SECONDS,
        **{k: v for k, v in COOKIE_KWARGS.items() if k != "domain"},
    )
    return response


@docs_gate_router.get("/docs/logout")
async def docs_logout():
    response = RedirectResponse(url="/docs/login", status_code=303)
    response.delete_cookie(DOCS_COOKIE_NAME, path="/")
    return response


@docs_gate_router.get("/docs")
async def admin_docs(request: Request):
    if _get_admin_claims(request) is None:
        return RedirectResponse(url="/docs/login?next=/docs")
    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=f"{request.app.title} - Docs"
    )


@docs_gate_router.get("/redoc")
async def admin_redoc(request: Request):
    if _get_admin_claims(request) is None:
        return RedirectResponse(url="/docs/login?next=/redoc")
    return get_redoc_html(
        openapi_url="/openapi.json", title=f"{request.app.title} - ReDoc"
    )


@docs_gate_router.get("/openapi.json")
async def admin_openapi(request: Request):
    if _get_admin_claims(request) is None:
        return RedirectResponse(url="/docs/login?next=/openapi.json")
    return request.app.openapi()
