from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FamilyRelation:
    """sib_sp + parch 복합 VO. 가족 동반 여부를 판단하는 도메인 개념.

    ML feature selection(sib_sp 단독 기여도 등)은 crew_lowe_boat_interactor에서 결정한다.
    도메인 레이어는 실재하는 가족 관계를 그대로 모델링한다.
    """

    sib_sp: int
    parch: int

    def __post_init__(self) -> None:
        if self.sib_sp < 0:
            raise ValueError(f"sib_sp는 0 이상이어야 합니다: {self.sib_sp}")
        if self.parch < 0:
            raise ValueError(f"parch는 0 이상이어야 합니다: {self.parch}")

    @classmethod
    def from_raw(cls, sib_sp_raw: str | None, parch_raw: str | None) -> FamilyRelation:
        try:
            sib_sp = int(sib_sp_raw.strip()) if sib_sp_raw else 0
        except ValueError as e:
            raise ValueError(f"sib_sp 파싱 실패: '{sib_sp_raw}'") from e
        try:
            parch = int(parch_raw.strip()) if parch_raw else 0
        except ValueError as e:
            raise ValueError(f"parch 파싱 실패: '{parch_raw}'") from e
        return cls(sib_sp=sib_sp, parch=parch)

    @property
    def total_family_size(self) -> int:
        """동반 가족 총 인원 (본인 제외). FamilySize 피처는 +1 필요."""
        return self.sib_sp + self.parch

    @property
    def is_alone(self) -> bool:
        return self.total_family_size == 0
