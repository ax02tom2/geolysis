"""Regression tests for result/signature session-state helpers."""
from geolysis_ui.state import clear_result_state, read_result_state, store_result_state


def test_result_state_round_trip_and_signature_match():
    state = {}
    signature = (12.0, 30.0, "Meyerhof")
    result = {"qult": 1200.0}
    store_result_state(state, "result", "signature", result, signature)
    assert read_result_state(state, "result", "signature", signature) == (result, True)


def test_result_state_marks_stale_inputs_without_returning_false_current_flag():
    state = {"result": {"qult": 1200.0}, "signature": (12.0, 30.0)}
    result, is_current = read_result_state(state, "result", "signature", (13.0, 30.0))
    assert result == {"qult": 1200.0}
    assert is_current is False


def test_clear_result_state_removes_both_cached_values():
    state = {"result": {"qult": 1200.0}, "signature": (12.0, 30.0)}
    clear_result_state(state, "result", "signature")
    assert read_result_state(state, "result", "signature", (12.0, 30.0)) == (None, False)
