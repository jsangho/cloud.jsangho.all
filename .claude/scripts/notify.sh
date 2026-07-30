#!/bin/bash
# Notification 훅 — 크로스 플랫폼 데스크톱 알림.
# Claude가 사용자 입력을 기다릴 때 호출된다.
# 알림 수단이 없으면 조용히 통과한다 (훅이 세션을 막지 않도록).

# 훅 JSON이 stdin으로 들어오지만 쓰지 않으므로 버린다.
cat >/dev/null 2>&1

TITLE='Claude Code'
BODY='Claude가 응답을 기다리고 있습니다'

# 1) Linux
if command -v notify-send >/dev/null 2>&1; then
  notify-send "$TITLE" "$BODY"
  exit 0
fi

# 2) macOS
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$BODY\" with title \"$TITLE\""
  exit 0
fi

# 3) Windows — 트레이 알림.
#    PowerShell 5.1은 BOM 없는 UTF-8을 ANSI로 읽어 한글이 깨진다.
#    -EncodedCommand(UTF-16LE + base64)로 넘겨 인코딩 문제를 우회한다.
if command -v powershell.exe >/dev/null 2>&1; then
  PS_SCRIPT=$(
    cat <<PS
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
\$n = New-Object System.Windows.Forms.NotifyIcon
\$n.Icon = [System.Drawing.SystemIcons]::Information
\$n.Visible = \$true
\$n.ShowBalloonTip(5000, '$TITLE', '$BODY', 'Info')
Start-Sleep -Milliseconds 1500
\$n.Dispose()
PS
  )
  ENCODED=$(printf '%s' "$PS_SCRIPT" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')
  powershell.exe -NoProfile -NonInteractive -EncodedCommand "$ENCODED" >/dev/null 2>&1
  exit 0
fi

exit 0
