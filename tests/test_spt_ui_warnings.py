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
