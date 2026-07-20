export const OAUTH_POPUP_MESSAGE_TYPE = "oauth-login-result";

type OAuthPopupMessage = {
  type: typeof OAUTH_POPUP_MESSAGE_TYPE;
  token: string | null;
  next: string | null;
};

function isOAuthPopupMessage(data: unknown): data is OAuthPopupMessage {
  return (
    !!data &&
    typeof data === "object" &&
    (data as { type?: unknown }).type === OAUTH_POPUP_MESSAGE_TYPE
  );
}

/**
 * OAuth 로그인 URL을 팝업 창으로 열고, 콜백 페이지가 postMessage로 보내는 결과를 기다린다.
 * 팝업이 차단되면 false를 반환한다 — 호출 측에서 전체 페이지 리다이렉트로 폴백해야 한다.
 */
export function openOAuthPopup(
  url: string,
  onResult: (token: string | null, next: string | null) => void,
): boolean {
  const width = 480;
  const height = 640;
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;

  const popup = window.open(
    url,
    "sns-login",
    `width=${width},height=${height},left=${left},top=${top}`,
  );
  if (!popup) return false;

  let settled = false;
  const pollClosed = window.setInterval(() => {
    if (popup.closed) {
      cleanup();
      if (!settled) onResult(null, null);
    }
  }, 500);

  function handleMessage(event: MessageEvent) {
    if (event.origin !== window.location.origin) return;
    if (!isOAuthPopupMessage(event.data)) return;
    settled = true;
    cleanup();
    onResult(event.data.token, event.data.next);
  }

  function cleanup() {
    window.clearInterval(pollClosed);
    window.removeEventListener("message", handleMessage);
  }

  window.addEventListener("message", handleMessage);
  return true;
}
