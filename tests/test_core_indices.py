from core_photo_analysis import calculate_core_indices


def test_recovery_and_rqd_use_separate_confirmed_lengths():
    result = calculate_core_indices(
        1.0,
        [920.0],
        rqd_piece_lengths_mm=[180.0, 70.0, 220.0, 95.0, 150.0],
    )
    assert result["recovered_length_mm"] == 920.0
    assert result["recovery_percent"] == 92.0
    assert result["rqd_length_mm"] == 550.0
    assert abs(result["rqd_percent"] - 55.0) < 1e-9
    assert result["qualifying_piece_count"] == 3


def test_rqd_can_warn_when_natural_segments_exceed_recovered_total():
    result = calculate_core_indices(1.0, [500.0], rqd_piece_lengths_mm=[300.0, 250.0])
    assert result["rqd_exceeds_recovered"] is True
