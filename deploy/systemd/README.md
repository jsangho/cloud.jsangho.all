# EC2 systemd 유닛

서버에서 주기적으로 도는 작업의 정본이다. **서버에만 두지 않는 이유**는 단순하다 —
`/etc/systemd/system/` 안의 파일은 저장소에 없으면 아무도 모르게 낡고, 왜 그렇게
설정했는지도 함께 사라진다.

## 지금 있는 것

| 유닛 | 하는 일 | 주기 |
|------|---------|------|
| `kayfabe-fill-predictions` | 예측이 없는 경기를 찾아 채운다 | 하루 한 번 06:40 UTC (한국 15:40) |
| `kayfabe-alert@` | 실패한 유닛 이름을 받아 텔레그램으로 알린다 | 호출될 때만 (`OnFailure=`) |

## 실패를 어떻게 아는가 (2026-10-07 추가)

전에는 **알 방법이 없었다.** 타이머가 실패해도 `journalctl` 에만 남고 그것을 여는
사람이 없었다. 게다가 service 에 `SuccessExitStatus=0 1` 이 붙어 있어서 **exit 1 이
성공으로 세어졌다** — `fill_missing_predictions.py` 는 생성에 실패한 경기가 있으면
1 로 끝내므로, Gemini 무료 등급 한도가 소진돼 예측이 하나도 안 만들어진 날조차
`systemctl status` 가 초록이었다.

그 줄을 걷고 `OnFailure=kayfabe-alert@%n.service` 를 달았다. 재시도에는 영향이 없다 —
**타이머는 유닛의 지난 결과와 무관하게 다음 시각에 다시 부른다.**

알림은 `notify-unit-failure.sh` 가 보낸다. `fastapi/.env` 의 `TELEGRAM_BOT_TOKEN` ·
`TELEGRAM_CHAT_ID` 를 쓰고, **둘이 비어 있으면 조용히 건너뛴다**(알림기가 실패로
끝나면 그 사실을 알릴 통로가 또 없다).

## 왜 cron이 아닌가

이 서버에 `crontab`이 **설치돼 있지 않다**(2026-09-29 실측). systemd 타이머는 이미
넷이 돌고 있다(`logrotate`·`sysstat-collect` 등). 있는 것을 쓴다.

## 설치

```bash
scp deploy/systemd/kayfabe-fill-predictions.{service,timer} \
    deploy/systemd/kayfabe-alert@.service aws-ec2:/tmp/
ssh aws-ec2 'sudo install -m 644 /tmp/kayfabe-fill-predictions.service /etc/systemd/system/ && \
             sudo install -m 644 /tmp/kayfabe-fill-predictions.timer   /etc/systemd/system/ && \
             sudo install -m 644 "/tmp/kayfabe-alert@.service"          /etc/systemd/system/ && \
             sudo systemctl daemon-reload && \
             sudo systemctl enable --now kayfabe-fill-predictions.timer'
```

알림 스크립트는 저장소에서 바로 실행된다(유닛의 `ExecStart` 가 저장소 경로를
가리킨다). `git pull` 뒤 실행 권한만 확인한다:

```bash
ssh aws-ec2 'chmod +x /home/ec2-user/cloud.jsangho.all/deploy/systemd/notify-unit-failure.sh'
```

**템플릿 유닛은 `enable` 하지 않는다** — `OnFailure=` 가 부를 때만 돈다.

## 알림이 실제로 오는지 보기

없는 유닛 이름을 넘겨 스크립트만 직접 부른다. 실패를 만들지 않고 전송 경로만 본다:

```bash
ssh aws-ec2 'sudo /home/ec2-user/cloud.jsangho.all/deploy/systemd/notify-unit-failure.sh test.service'
```

유닛 연결까지 보려면 일부러 실패시킨다:

```bash
ssh aws-ec2 'sudo systemd-run --unit=alert-probe --property=OnFailure=kayfabe-alert@alert-probe.service /bin/false'
```

## 확인

```bash
ssh aws-ec2 'systemctl list-timers kayfabe-fill-predictions.timer --no-pager'
ssh aws-ec2 'journalctl -u kayfabe-fill-predictions.service -n 50 --no-pager'
```

## 한 번 지금 돌려 보기

타이머를 기다리지 않고 서비스만 부른다. **`--apply`가 붙어 있으므로 실제로 만든다.**

```bash
ssh aws-ec2 'sudo systemctl start kayfabe-fill-predictions.service'
```

만들지 않고 무엇을 할지만 보려면 컨테이너에서 직접 드라이런을 돌린다:

```bash
ssh aws-ec2 'cd /home/ec2-user/cloud.jsangho.all && docker compose exec -T \
    -e PYTHONUTF8=1 -e PYTHONPATH=apps:. backend \
    python apps/kayfabe/scripts/fill_missing_predictions.py'
```

## 끄기

```bash
ssh aws-ec2 'sudo systemctl disable --now kayfabe-fill-predictions.timer'
```

유닛 파일을 고쳤으면 다시 `install` 하고 `daemon-reload` 한다 — 서버의 사본은
저장소를 자동으로 따라오지 않는다.
