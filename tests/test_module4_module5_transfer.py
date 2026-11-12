"""Regression tests for Module 4 ↔ Module 5 result transfer."""

from geolysis_ui import module4


def _transfer_fixture():
    return {
        "transfer_id": "transfer123",
        "qult_gross_kpa": 900.0,
        "qa_net_kpa": 300.0,
        "qeq_gross_kpa": 240.0,
        "B_m": 2.0,
        "L_m": 3.0,
        "Df_m": 1.5,
        "footing_type": "isolated",
        "theory": "Meyerhof",
        "FS_bearing": 3.75,
        "passes_bearing": True,
    }


def _patch_transfer_ui(monkeypatch, transfer, checkbox_values):
    monkeypatch.setattr(
        module4.st, "session_state", {"m5_bearing_transfer": transfer}, raising=False
    )
    monkeypatch.setattr(
        module4.st,
        "checkbox",
        lambda label, value=False, key=None: checkbox_values.get(key, value),
    )
    monkeypatch.setattr(module4.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(module4.st, "warning", lambda *args, **kwargs: None)


def test_module4_transfer_can_use_module5_qult_and_equivalent_gross_pressure(monkeypatch):
    transfer = _transfer_fixture()
    _patch_transfer_ui(
        monkeypatch,
        transfer,
        {
            "m4_dmt_use_m5_transfer123": True,
            "m4_dmt_conditions_transfer123_2.00_3.00_0.00_isolated": True,
            "m4_dmt_use_m5_qeq_transfer123": True,
        },
    )

    qult, qeq = module4._module5_transfer_value(
        key_prefix="m4_dmt",
        label="gross 極限承載力 qult",
        field="qult_gross_kpa",
        width_m=2.0,
        length_m=3.0,
        footing_type="isolated",
    )

    assert qult == 900.0
    assert qeq == 240.0


def test_module4_transfer_keeps_manual_pressure_when_qeq_not_selected(monkeypatch):
    transfer = _transfer_fixture()
    _patch_transfer_ui(
        monkeypatch,
        transfer,
        {
            "m4_cpt_use_m5_transfer123": True,
            "m4_cpt_conditions_transfer123_2.00_3.00_0.00_isolated": True,
            "m4_cpt_use_m5_qeq_transfer123": False,
        },
    )

    qult, qeq = module4._module5_transfer_value(
        key_prefix="m4_cpt",
        label="gross 極限承載力 qult",
        field="qult_gross_kpa",
        width_m=2.0,
        length_m=3.0,
        footing_type="isolated",
    )

    assert qult == 900.0
    assert qeq is None


def test_module4_transfer_rejects_geometry_mismatch(monkeypatch):
    _patch_transfer_ui(monkeypatch, _transfer_fixture(), {})

    qult, qeq = module4._module5_transfer_value(
        key_prefix="m4_pmt",
        label="gross 極限承載力 qult",
        field="qult_gross_kpa",
        width_m=2.5,
        length_m=3.0,
        footing_type="isolated",
    )

    assert qult is None
    assert qeq is None


def test_module4_transfer_requires_explicit_matching_conditions(monkeypatch):
    _patch_transfer_ui(
        monkeypatch,
        _transfer_fixture(),
        {"m4_bb_use_m5_transfer123": True},
    )

    qult, qeq = module4._module5_transfer_value(
        key_prefix="m4_bb",
        label="gross 極限承載力 qult",
        field="qult_gross_kpa",
        width_m=2.0,
        length_m=3.0,
        depth_m=1.5,
    )

    assert qult is None
    assert qeq is None
