"""캐릭터 생성 프리셋 — 실존 선수를 바탕으로 내 선수를 만든다 (하네스 §3-D10-1).

**이 파일은 생성물이다.** `scripts/generate_roster.py`가 로스터와 함께 찍어 낸다.

프리셋을 고르면 그 선수의 데이터가 **기본값으로** 들어오고, 원하는 값은 덮어쓸 수 있다
(2026-08-07 사용자 요청). 이름은 언제나 사용자가 정한다 — 실존 인물의 이름을 그대로
쓰는 캐릭터를 만들 수 있게 두면 §3-D13의 고지가 무의미해진다.

플레이스타일은 로스터 CSV의 `style` 첫 값이다 — **추정이 아니라 사용자가 적은 값**
(2026-08-10). 곁들이는 유형(`sub_styles`)은 프리셋이 물려주지 않는다: 캐릭터의
플레이스타일은 하나이고, 나머지는 그 선수를 설명하는 말이지 게임의 값이 아니다.

목록 밖 출신은 `Country.OTHER`(기타)로 뭉친다 — 게임의 권역이 다섯 개뿐이라(§3-D14)
아프리카·중동을 담을 자리가 없기 때문이다. 그래도 국적은 언제든 덮어쓸 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.countries import Country
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle


@dataclass(frozen=True)
class CharacterPreset:
    """실존 선수 한 명이 캐릭터 생성에 건네주는 값."""

    source: str
    """바탕이 된 실존 선수의 이름. 화면에 "○○를 바탕으로"라고 밝히는 데 쓴다."""
    gender: Gender
    play_style: PlayStyle
    country: Country


PRESETS: tuple[CharacterPreset, ...] = (
    CharacterPreset("아키라 토자와", Gender.MALE, PlayStyle.HIGH_FLYER, Country.JP),
    CharacterPreset("안젤로 도킨스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("오스틴 씨어리", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("타일러 베이트", Gender.MALE, PlayStyle.HIGH_FLYER, Country.GB),
    CharacterPreset("빅 캐스", Gender.MALE, PlayStyle.GIANT, Country.US),
    CharacterPreset("브론 브레이커", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("브론슨 리드", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.AU),
    CharacterPreset("브루투스 크리드", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("채드 게이블", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("크루즈 델 토로", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.MX),
    CharacterPreset(
        "도미닉 미스테리오", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.US
    ),
    CharacterPreset("드래곤 리", Gender.MALE, PlayStyle.TECHNICIAN, Country.MX),
    CharacterPreset("루드비히 카이저", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.DE),
    CharacterPreset("에릭", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("에단 페이지", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.CA),
    CharacterPreset("그레이슨 월러", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.AU),
    CharacterPreset("아이바", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("제이콥 파투", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("JD 맥도나", Gender.MALE, PlayStyle.TECHNICIAN, Country.IE),
    CharacterPreset("지본 에반스", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("제이 우소", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("지미 우소", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("호아킨 와일드", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("조 헨드리", Gender.MALE, PlayStyle.POWERHOUSE, Country.GB),
    CharacterPreset("줄리우스 크리드", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("LA 나이트", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("로건 폴", Gender.MALE, PlayStyle.STRONG_STYLE, Country.US),
    CharacterPreset("몬테즈 포드", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("오바 페미", Gender.MALE, PlayStyle.POWERHOUSE, Country.OTHER),
    CharacterPreset("오티스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("펜타", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.MX),
    CharacterPreset("피트 던", Gender.MALE, PlayStyle.HEEL_STYLE, Country.GB),
    CharacterPreset("레이 미스테리오", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.US),
    CharacterPreset("로만 레인즈", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("루세프", Gender.MALE, PlayStyle.POWERHOUSE, Country.RU),
    CharacterPreset("세스 롤린스", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("AJ 리", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("아스카", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.JP),
    CharacterPreset("베일리", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("베키 린치", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.IE),
    CharacterPreset("브리 벨라", Gender.FEMALE, PlayStyle.HEEL_STYLE, Country.US),
    CharacterPreset("아이비 나일", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("이요 스카이", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.JP),
    CharacterPreset("리브 모건", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("라이라 발키리아", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.IE),
    CharacterPreset("맥신 듀프리", Gender.FEMALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("나탈리아", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.CA),
    CharacterPreset("니키 벨라", Gender.FEMALE, PlayStyle.HEEL_STYLE, Country.US),
    CharacterPreset("라켈 로드리게스", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("록샌 페레즈", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("솔 루카", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset(
        "스테파니 바케르", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.CL
    ),
    CharacterPreset("엔젤", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.MX),
    CharacterPreset("액시옴", Gender.MALE, PlayStyle.TECHNICIAN, Country.ES),
    CharacterPreset("배런 코빈", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("베르토", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.MX),
    CharacterPreset("카멜로 헤이즈", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("CM 펑크", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("코디 로즈", Gender.MALE, PlayStyle.OLD_SCHOOL, Country.US),
    CharacterPreset("데미안 프리스트", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("드류 맥킨타이어", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("엘튼 프린스", Gender.MALE, PlayStyle.SHOWMAN, Country.GB),
    CharacterPreset("핀 밸러", Gender.MALE, PlayStyle.SHOOTER, Country.IE),
    CharacterPreset("군터", Gender.MALE, PlayStyle.OLD_SCHOOL, Country.OTHER),
    CharacterPreset(
        "일리야 드라구노프", Gender.MALE, PlayStyle.HARD_HITTING, Country.RU
    ),
    CharacterPreset("쟈니 가르가노", Gender.MALE, PlayStyle.UNDERDOG, Country.US),
    CharacterPreset("케빈 오웬스", Gender.MALE, PlayStyle.TECHNICIAN, Country.CA),
    CharacterPreset("킷 윌슨", Gender.MALE, PlayStyle.SHOWMAN, Country.GB),
    CharacterPreset("맷 카도나", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("미즈", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("네이선 프레이저", Gender.MALE, PlayStyle.TECHNICIAN, Country.GB),
    CharacterPreset("R-트루스", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("랜디 오턴", Gender.MALE, PlayStyle.OLD_SCHOOL, Country.US),
    CharacterPreset("레이 페닉스", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.MX),
    CharacterPreset("리키 세인츠", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("로이스 키스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("새미 제인", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.CA),
    CharacterPreset("나카무라 신스케", Gender.MALE, PlayStyle.STRONG_STYLE, Country.JP),
    CharacterPreset("솔로 시코아", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("탈라 통가", Gender.MALE, PlayStyle.GIANT, Country.TO),
    CharacterPreset("타마 통가", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.TO),
    CharacterPreset("트릭 윌리엄스", Gender.MALE, PlayStyle.SHOOTER, Country.US),
    CharacterPreset("알렉사 블리스", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("B-팹", Gender.FEMALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("비앙카 벨레어", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("블레이크 먼로", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("캔디스 르래", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("샬럿 플레어", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("첼시 그린", Gender.FEMALE, PlayStyle.SHOWGIRL, Country.CA),
    CharacterPreset("팰런 헨리", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("줄리아", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("제이시 제인", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("제이드 카길", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("조르딘 그레이스", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("키아나 제임스", Gender.FEMALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("레이니 리드", Gender.FEMALE, PlayStyle.HEEL_STYLE, Country.US),
    CharacterPreset("래쉬 레전드", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("미친", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("나이아 잭스", Gender.FEMALE, PlayStyle.GIANT, Country.AU),
    CharacterPreset("나오미", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("파이퍼 니븐", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.GB),
    CharacterPreset("리아 리플리", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.AU),
    CharacterPreset("테이텀 팩슬리", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset(
        "티파니 스트랫턴", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.US
    ),
    CharacterPreset("브록 레스너", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("댄 하우젠", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("오모스", Gender.MALE, PlayStyle.GIANT, Country.OTHER),
    CharacterPreset("페이지", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("브래드 베일러", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("브롱코 니마", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("브룩스 젠슨", Gender.MALE, PlayStyle.HARD_HITTING, Country.US),
    CharacterPreset("채닝 로렌조", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("찰리 뎀프시", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("크루즈 몬타나", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("커틀러 제임스", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("디온 레녹스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("도리안 반 덕스", Gender.MALE, PlayStyle.POWERHOUSE, Country.OTHER),
    CharacterPreset("EK 프로스퍼", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("엘리오 르플뢰르", Gender.MALE, PlayStyle.TECHNICIAN, Country.FR),
    CharacterPreset("행크 워커", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("잭슨 드레이크", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("재스퍼 트로이", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("조쉬 브릭스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("케일 딕슨", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("캠 헨드릭스", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("키아누 카버", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("렉시스 킹", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("린세 도라도", Gender.MALE, PlayStyle.LUCHA_LIBRE, Country.PR),
    CharacterPreset("루시엔 프라이스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("메이슨 룩", Gender.MALE, PlayStyle.GIANT, Country.GB),
    CharacterPreset("마일스 본", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("나라쿠", Gender.MALE, PlayStyle.SHOWMAN, Country.JP),
    CharacterPreset("니코 밴스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("노암 다르", Gender.MALE, PlayStyle.TECHNICIAN, Country.GB),
    CharacterPreset("오시리스 그리핀", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("리키 스모크스", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("로메오 모레노", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.ES),
    CharacterPreset("세이콴 슈거스", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("숀 레거시", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("숀 스피어스", Gender.MALE, PlayStyle.TECHNICIAN, Country.CA),
    CharacterPreset("샤일로 힐", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("탱크 레저", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("테이트 와일더", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("테비언 하이츠", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("토니 디안젤로", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("트리스탄 앤젤스", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("유라이어 코너스", Gender.MALE, PlayStyle.BRAWLER, Country.US),
    CharacterPreset("애드리아나 리조", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("아리아나 그레이스", Gender.FEMALE, PlayStyle.SHOWMAN, Country.CA),
    CharacterPreset("이지 데임", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("제이다 파커", Gender.FEMALE, PlayStyle.STRONG_STYLE, Country.US),
    CharacterPreset("칼리 암스트롱", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset(
        "카르멘 페트로비치", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.CA
    ),
    CharacterPreset("켈라니 조던", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("켄달 그레이", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("레일라 딕스", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("리지 레인", Gender.FEMALE, PlayStyle.ALL_ROUNDER, Country.GB),
    CharacterPreset("롤라 바이스", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("마이카 락우드", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("니키타 라이온스", Gender.FEMALE, PlayStyle.SHOOTER, Country.US),
    CharacterPreset("레이나 볼칸", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.DO),
    CharacterPreset("스카일라 레이", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("티아 헤일", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("웬디 추", Gender.FEMALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("렌 싱클레어", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("자리아", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.AU),
    CharacterPreset("아론 루크", Gender.MALE, PlayStyle.ALL_ROUNDER, Country.US),
    CharacterPreset("브랙스턴 콜", Gender.MALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("카푸치노 존스", Gender.MALE, PlayStyle.SHOWMAN, Country.US),
    CharacterPreset("일라이자 홀리필드", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("할렘 루이스", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("잇츠 갤", Gender.MALE, PlayStyle.POWERHOUSE, Country.OTHER),
    CharacterPreset("잭스 프레슬리", Gender.MALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("스타보이 찰리", Gender.MALE, PlayStyle.HIGH_FLYER, Country.US),
    CharacterPreset("아리아 베넷", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.US),
    CharacterPreset("샨텔 먼로", Gender.FEMALE, PlayStyle.HEEL_STYLE, Country.US),
    CharacterPreset("PJ 바사", Gender.FEMALE, PlayStyle.POWERHOUSE, Country.US),
    CharacterPreset("제나 스털링", Gender.FEMALE, PlayStyle.TECHNICIAN, Country.OTHER),
)

BY_SOURCE: dict[str, CharacterPreset] = {p.source: p for p in PRESETS}


def preset_for(source: str) -> CharacterPreset | None:
    """이름으로 프리셋을 찾는다. 없으면 None — 프리셋 없이도 캐릭터는 만들 수 있다."""
    return BY_SOURCE.get(source)
