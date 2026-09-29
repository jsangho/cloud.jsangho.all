# EC2 systemd 유닛

서버에서 주기적으로 도는 작업의 정본이다. **서버에만 두지 않는 이유**는 단순하다 —
`/etc/systemd/system/` 안의 파일은 저장소에 없으면 아무도 모르게 낡고, 왜 그렇게
설정했는지도 함께 사라진다.

## 지금 있는 것

| 유닛 | 하는 일 | 주기 |
|------|---------|------|
| `kayfabe-fill-predictions` | 예측이 없는 경기를 찾아 채운다 | 하루 한 번 06:40 UTC (한국 15:40) |

## 왜 cron이 아닌가

이 서버에 `crontab`이 **설치돼 있지 않다**(2026-09-29 실측). systemd 타이머는 이미
넷이 돌고 있다(`logrotate`·`sysstat-collect` 등). 있는 것을 쓴다.

## 설치

```bash
scp deploy/systemd/kayfabe-fill-predictions.{service,timer} aws-ec2:/tmp/
ssh aws-ec2 'sudo install -m 644 /tmp/kayfabe-fill-predictions.service /etc/systemd/system/ && \
             sudo install -m 644 /tmp/kayfabe-fill-predictions.timer   /etc/systemd/system/ && \
             sudo systemctl daemon-reload && \
             sudo systemctl enable --now kayfabe-fill-predictions.timer'
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
