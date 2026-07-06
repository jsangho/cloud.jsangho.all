import pytest

from titanic.domain.value_objects.age_vo import Age
from titanic.domain.value_objects.family_relation_vo import FamilyRelation
from titanic.domain.value_objects.gender_vo import Gender, GenderType
from titanic.domain.value_objects.survived_vo import Survived


class TestGender:
    def test_from_raw_male(self):
        assert Gender.from_raw("male").value == GenderType.MALE

    def test_from_raw_female(self):
        assert Gender.from_raw("female").value == GenderType.FEMALE

    def test_from_raw_none_is_unknown(self):
        assert Gender.from_raw(None).value == GenderType.UNKNOWN

    def test_from_raw_uppercase_is_normalized(self):
        assert Gender.from_raw("MALE").value == GenderType.MALE

    def test_from_raw_unrecognized_string_is_unknown(self):
        assert Gender.from_raw("other").value == GenderType.UNKNOWN

    def test_is_female_true_for_female(self):
        assert Gender.from_raw("female").is_female() is True

    def test_is_female_false_for_male(self):
        assert Gender.from_raw("male").is_female() is False

    def test_is_female_false_for_unknown(self):
        assert Gender.from_raw(None).is_female() is False


class TestAge:
    def test_from_raw_valid_string(self):
        assert Age.from_raw("22.5").value == 22.5

    def test_from_raw_none_is_unknown(self):
        assert Age.from_raw(None).is_unknown is True

    def test_from_raw_empty_string_is_unknown(self):
        assert Age.from_raw("").is_unknown is True

    def test_negative_age_raises(self):
        with pytest.raises(ValueError):
            Age(value=-1.0)

    def test_age_over_120_raises(self):
        with pytest.raises(ValueError):
            Age(value=121.0)

    def test_boundary_0_is_valid(self):
        Age(value=0.0)

    def test_boundary_120_is_valid(self):
        Age(value=120.0)

    def test_non_numeric_string_raises(self):
        with pytest.raises(ValueError, match="파싱 실패"):
            Age.from_raw("abc")

    def test_is_minor_true_under_18(self):
        assert Age(value=17.9).is_minor is True

    def test_is_minor_false_at_18(self):
        assert Age(value=18.0).is_minor is False

    def test_is_minor_false_for_unknown_age(self):
        assert Age(value=None).is_minor is False


class TestFamilyRelation:
    def test_total_family_size_sums_sib_sp_and_parch(self):
        assert FamilyRelation(sib_sp=2, parch=3).total_family_size == 5

    def test_is_alone_when_both_zero(self):
        assert FamilyRelation(sib_sp=0, parch=0).is_alone is True

    def test_not_alone_with_siblings(self):
        assert FamilyRelation(sib_sp=1, parch=0).is_alone is False

    def test_not_alone_with_children(self):
        assert FamilyRelation(sib_sp=0, parch=1).is_alone is False

    def test_from_raw_parses_string_values(self):
        relation = FamilyRelation.from_raw("1", "2")
        assert relation.sib_sp == 1
        assert relation.parch == 2

    def test_from_raw_none_defaults_to_zero(self):
        relation = FamilyRelation.from_raw(None, None)
        assert relation.sib_sp == 0
        assert relation.parch == 0

    def test_negative_sib_sp_raises(self):
        with pytest.raises(ValueError, match="sib_sp"):
            FamilyRelation(sib_sp=-1, parch=0)

    def test_negative_parch_raises(self):
        with pytest.raises(ValueError, match="parch"):
            FamilyRelation(sib_sp=0, parch=-1)


class TestSurvived:
    def test_from_raw_1_means_survived(self):
        assert Survived.from_raw("1").survived is True

    def test_from_raw_0_means_did_not_survive(self):
        assert Survived.from_raw("0").survived is False

    def test_from_raw_none_is_unknown(self):
        assert Survived.from_raw(None).is_unknown is True

    def test_from_raw_empty_string_is_unknown(self):
        assert Survived.from_raw("").is_unknown is True

    def test_from_raw_invalid_value_raises(self):
        with pytest.raises(ValueError, match="파싱 실패"):
            Survived.from_raw("2")

    def test_is_unknown_false_when_survival_is_known(self):
        assert Survived.from_raw("1").is_unknown is False
