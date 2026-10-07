#!/usr/bin/env bash
# systemd 유닛이 실패하면 텔레그램으로 알린다. `OnFailure=` 가 부른다.
#
# **왜 스크립트로 빼는가**: 유닛 파일의 `EnvironmentFile=` 로 `fastapi/.env` 를 통째로
# 읽히면 안 된다 — 그 파일에는 PEM 개인키처럼 여러 줄짜리 값이 있고 systemd 의
# 환경파일 파서는 그것을 못 읽는다. 필요한 두 키만 집어 온다.
#
# 사용법:  notify-unit-failure.sh <유닛이름>     (systemd 의 %n 을 넘긴다)
set -uo pipefail

UNIT="${1:-알 수 없는 유닛}"
ENV_FILE="${ENV_FILE:-/home/ec2-user/cloud.jsangho.all/fastapi/.env}"

read_key() {
  # `KEY=value` 의 값만 꺼낸다. 앞뒤 따옴표와 CR 은 떼어 낸다.
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- |
    sed -e 's/\r$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

TOKEN="$(read_key TELEGRAM_BOT_TOKEN)"
CHAT="$(read_key TELEGRAM_CHAT_ID)"

if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
  # **여기서 실패로 끝내지 않는다.** 알림기가 실패하면 그 사실을 알릴 통로가 또
  # 없어서 조용히 사라진다. 저널에 남기고 0 으로 끝낸다 — 원래의 실패 기록은
  # 실패한 유닛 쪽에 그대로 있다.
  echo "TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID 가 비어 있어 알림을 건너뛴다 ($ENV_FILE)" >&2
  exit 0
fi

RESULT="$(systemctl show -p Result --value "$UNIT" 2>/dev/null)"
STATUS="$(systemctl show -p ExecMainStatus --value "$UNIT" 2>/dev/null)"
# 텔레그램 본문 상한이 4096자다. 로그는 끝에서 20줄, 2000자로 자른다.
LOG="$(journalctl -u "$UNIT" -n 20 --no-pager -o cat 2>/dev/null | tail -c 2000)"

TEXT="🔴 ${UNIT} 실패
호스트: $(hostname)
시각: $(date -Is)
결과: ${RESULT:-unknown} (exit ${STATUS:-?})

최근 로그:
${LOG:-(로그를 읽지 못했다)}"

curl -fsS --max-time 20 \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT}" \
  --data-urlencode "text=${TEXT}" \
  -o /dev/null ||
  echo "텔레그램 전송 실패 — 네트워크나 토큰을 확인한다" >&2

exit 0
