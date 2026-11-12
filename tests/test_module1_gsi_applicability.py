"""Module 1 GSI=75 applicability-boundary regression tests."""
import pytest

from geolysis_ui.module1 import _gsi_sensitivity_values
from geolysis_engine import hoek_brown_structure_applicability


def test_intact_massive_gsi_70_to_80_uses_only_applicable_sensitivity_endpoints():
    assert _gsi_sensitivity_values("A", 70, 80) == [70, 75]
    assert hoek_brown_structure_applicability(gsi=75, structure_code="A")["applicable"] is True


def test_intact_massive_gsi_range_entirely_above_75_has_no_hoek_brown_sensitivity_range():
    assert _gsi_sensitivity_values("A", 76, 80) == []


def test_blocky_rock_sensitivity_range_is_not_capped_at_75():
    assert _gsi_sensitivity_values("B", 75, 85) == [75, 85]


def test_invalid_gsi_range_is_rejected():
    with pytest.raises(ValueError, match="GSI 初判下限"):
        _gsi_sensitivity_values("A", 81, 70)


@pytest.mark.parametrize(
    ("mi_case", "ucs_case", "mode", "should_warn"),
    [
        ("砂岩 Sandstone（台灣南莊層三軸案例）",
         "南莊層砂岩｜隧道完整岩心試驗單一案例", "採用台灣岩性案例參考值", False),
        ("砂岩 Sandstone（台灣南莊層三軸案例）",
         "五指山層砂岩｜台灣岩石工程性質彙整", "採用台灣岩性案例參考值", True),
        ("砂岩 Sandstone",
         "南莊層砂岩｜隧道完整岩心試驗單一案例", "採用台灣岩性案例參考值", True),
        ("砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）",
         "東北部宜蘭線瑞芳段風化砂岩｜崩塌回算案例", "採用台灣岩性案例參考值", False),
        ("砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）",
         "南莊層砂岩｜隧道完整岩心試驗單一案例", "採用台灣岩性案例參考值", True),
        ("砂岩 Sandstone（台灣南莊層三軸案例）",
         None, "已有實驗室 UCS 試驗值", False),
    ],
)
def test_case_based_mi_and_ucs_reference_pairing(mi_case, ucs_case, mode, should_warn):
    from geolysis_ui.module1 import _hb_case_pair_warning

    warning = _hb_case_pair_warning(mi_case, ucs_case, mode)
    assert (warning is not None) is should_warn
