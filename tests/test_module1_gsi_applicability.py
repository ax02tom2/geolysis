"""Module 1 GSI=75 applicability-boundary regression tests."""
import pytest

from geolysis_ui.module1 import _gsi_sensitivity_values
from geolysis_engine import hoek_brown_structure_applicability


def test_intact_massive_sparse_jointed_rock_has_no_standard_gsi_sensitivity_range():
    assert _gsi_sensitivity_values("A", 40, 80) == []
    for value in (40, 70, 75, 80):
        result = hoek_brown_structure_applicability(gsi=value, structure_code="A")
        assert result["applicable"] is False
        assert "均質、近似等向" in result["warning"]


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
        ("砂岩 Sandstone（台灣南莊層三軸案例）",
         None, "依現場敲擊分級初估", True),
        ("片岩 Schist（蘇花公路案例）",
         "中央山脈東翼變質雜岩片岩／片麻岩｜東部山區區域範圍", "採用台灣岩性案例參考值", True),
    ],
)
def test_case_based_mi_and_ucs_reference_pairing(mi_case, ucs_case, mode, should_warn):
    from geolysis_ui.module1 import _hb_case_pair_warning

    warning = _hb_case_pair_warning(mi_case, ucs_case, mode)
    assert (warning is not None) is should_warn


@pytest.mark.parametrize(
    ("case", "mi", "gsi", "disturbance", "should_warn"),
    [
        ("砂岩 Sandstone（台灣南莊層三軸案例）", 7.752, 45, 0.5, False),
        ("砂岩 Sandstone（台灣南莊層三軸案例）", 7.752, 60, 0.5, True),
        ("砂岩 Sandstone（台灣南莊層三軸案例）", 8.5, 45, 0.5, True),
        ("砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）", 15, 25, 0.85, False),
        ("砂岩 Sandstone（東北部宜蘭線瑞芳段崩塌案例）", 15, 35, 0.7, True),
        ("片岩 Schist（蘇花公路案例）", 10, 25, 0.7, False),
        ("片岩 Schist（蘇花公路案例）", 10, 30, 0.7, True),
        ("片岩 Schist（蘇花公路案例）", 12, 25, 0.7, True),
        ("砂岩 Sandstone", 17, 60, 0.5, False),
    ],
)
def test_case_reference_gsi_and_disturbance_ranges(case, mi, gsi, disturbance, should_warn):
    from geolysis_ui.module1 import _hb_case_parameter_warning

    warning = _hb_case_parameter_warning(case, mi, gsi, disturbance)
    assert (warning is not None) is should_warn


@pytest.mark.parametrize(
    ("mi", "gsi", "disturbance"),
    [
        (10.0, 60.0, 0.7),  # slope
        (10.0, 80.0, 0.5),  # tunnel class II
        (10.0, 60.0, 0.5),  # tunnel class III
        (10.0, 40.0, 0.5),  # tunnel class IV
    ],
)
def test_alishan_42_tunnel_design_parameter_combinations_are_recognized(mi, gsi, disturbance):
    from geolysis_ui.module1 import _hb_case_parameter_warning

    assert _hb_case_parameter_warning(
        "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）",
        mi, gsi, disturbance,
    ) is None


def test_alishan_42_tunnel_case_flags_mixed_or_unreported_parameter_combination():
    from geolysis_ui.module1 import _hb_case_parameter_warning

    warning = _hb_case_parameter_warning(
        "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）",
        17.0, 60.0, 0.7,
    )
    assert warning is not None
    assert "mi=10" in warning
    assert "17±4" in warning


@pytest.mark.parametrize(
    ("ucs_case", "should_warn"),
    [
        ("阿里山42號隧道｜邊坡設計 UCS 43.3 MPa", False),
        ("阿里山42號隧道｜隧道 II 類設計 UCS 65.7 MPa", False),
        ("阿里山42號隧道｜隧道 III 類設計 UCS 43.3 MPa", False),
        ("阿里山42號隧道｜隧道 IV 類設計 UCS 21.4 MPa", False),
        ("五指山層砂岩｜台灣岩石工程性質彙整", True),
    ],
)
def test_alishan_case_mi_is_only_paired_with_its_own_project_ucs_scenarios(ucs_case, should_warn):
    from geolysis_ui.module1 import _hb_case_pair_warning

    warning = _hb_case_pair_warning(
        "砂岩／頁岩互層（阿里山森林鐵路42號隧道案例）",
        ucs_case, "採用台灣岩性案例參考值",
    )
    assert (warning is not None) is should_warn


def test_alishan_project_ucs_cannot_be_paired_with_generic_sandstone_mi():
    from geolysis_ui.module1 import _hb_case_pair_warning

    warning = _hb_case_pair_warning(
        "砂岩 Sandstone",
        "阿里山42號隧道｜邊坡設計 UCS 43.3 MPa",
        "採用台灣岩性案例參考值",
    )
    assert warning is not None
    assert "阿里山42號隧道" in warning


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("自然坡面（無近期開挖或爆破）(D = 0.0)", 0.0),
        ("小型土木邊坡控制爆破／光面爆破 (D = 0.7)", 0.7),
        ("中度擾動／應力鬆弛 (D = 0.5)", 0.5),
        ("未良好控制的生產爆破 (D = 1.0)", 1.0),
        ("自訂擾動因子 D", 0.0),
    ],
)
def test_module1_disturbance_preset_value(preset, expected):
    from geolysis_ui.module1 import _hb_disturbance_preset_value

    assert _hb_disturbance_preset_value(preset) == pytest.approx(expected)


def test_module1_disturbance_preset_rejects_out_of_range_value():
    from geolysis_ui.module1 import _hb_disturbance_preset_value

    with pytest.raises(ValueError, match="擾動因子 D"):
        _hb_disturbance_preset_value("不合理設定 (D = 1.2)")


@pytest.mark.parametrize(
    ("application", "height_m", "span_m", "warning_fragment"),
    [
        ("slope", 25.0, None, "小於 20 m"),
        ("slope", 15.0, None, None),
        ("tunnel", 15.0, 12.0, "約 10 m"),
        ("tunnel", 50.0, 8.0, None),
        ("tunnel", 20.0, None, "尚未提供隧道開挖跨度"),
        ("general", None, None, None),
    ],
)
def test_gsi_scale_effect_uses_slope_height_and_tunnel_span_separately(
    application, height_m, span_m, warning_fragment
):
    from geolysis_engine import gsi_scale_effect_warning

    warning = gsi_scale_effect_warning(
        application=application, height_m=height_m, span_m=span_m
    )
    if warning_fragment is None:
        assert warning is None
    else:
        assert warning_fragment in warning


def test_gsi_tunnel_scale_rejects_nonpositive_span():
    from geolysis_engine import gsi_scale_effect_warning

    with pytest.raises(ValueError, match="隧道開挖跨度"):
        gsi_scale_effect_warning(application="tunnel", span_m=0.0)


def test_persistent_bedding_or_schistosity_requires_structural_failure_review():
    result = hoek_brown_structure_applicability(gsi=50.0, structure_code="D")
    assert result["applicable"] is True
    assert "持續性層理／片理" in result["warning"]
    assert "結構面" in result["warning"]


def test_laminated_sheared_rock_flags_specialized_gsi_chart_review():
    result = hoek_brown_structure_applicability(gsi=20.0, structure_code="F")
    assert result["applicable"] is True
    assert "Flysch" in result["warning"]
    assert "構造預剪切" in result["warning"]
