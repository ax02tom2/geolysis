from geolysis_ui.module3 import _spt_warning_messages


def test_spt_warning_messages_include_depth_for_profile_rows():
    messages = _spt_warning_messages([
        {"Depth_m": 5.0, "warnings": ["能量比超出常見設備範圍。"]},
        {"Depth_m": 6.0, "warnings": []},
        {"Depth_m": 7.0, "warnings": ["鑽桿長度超出表列範圍。"]},
    ])
    assert messages == [
        "深度 5 m：能量比超出常見設備範圍。",
        "深度 7 m：鑽桿長度超出表列範圍。",
    ]


def test_spt_warning_messages_support_single_point_and_string_warning():
    assert _spt_warning_messages([{"warnings": "請核對設備資料。"}]) == ["請核對設備資料。"]
    assert _spt_warning_messages([{"warnings": []}]) == []

import pandas as pd
import pytest

from geolysis_ui.module3 import _normalize_spt_profile_effective_stress


def test_spt_effective_stress_aliases_merge_when_values_agree_or_are_blank():
    profile = pd.DataFrame({
        "Effective_Stress_KPa": [100.0, None, 150.0],
        "effective_stress_kpa": [100.0, 120.0, None],
    })
    normalized = _normalize_spt_profile_effective_stress(profile)
    assert normalized["Effective_Stress_KPa"].tolist() == [100.0, 120.0, 150.0]
    assert "effective_stress_kpa" not in normalized.columns


def test_spt_effective_stress_aliases_reject_conflicting_values():
    profile = pd.DataFrame({
        "Effective_Stress_KPa": [100.0, 150.0],
        "effective_stress_kpa": [100.0, 155.0],
    })
    with pytest.raises(ValueError, match="數值不一致"):
        _normalize_spt_profile_effective_stress(profile)


def test_spt_effective_stress_aliases_reject_non_numeric_nonblank_values():
    profile = pd.DataFrame({
        "Effective_Stress_KPa": [100.0, "not-a-number"],
    })
    with pytest.raises(ValueError, match="含非數字"):
        _normalize_spt_profile_effective_stress(profile)
