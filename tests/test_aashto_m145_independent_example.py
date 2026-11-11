"""Independent USCS/AASHTO soil classification example with fractional sieve results."""
from geolysis_engine import classify_uscs_aashto


def test_liu_evett_example_2_2_2_5_uscs_and_aashto():
    # Liu & Evett, Soils and Foundations, 7th ed., Examples 2-2 and 2-5:
    # P3in=100%, P10=93.2%, P40=81%, P200=60.2%, LL=42, PL=16, PI=26.
    # USCS: fine-grained, above A-line, LL<50 -> CL.
    # AASHTO M145 §3.1 rounds fractional limiting values for classification;
    # §6.1 defines F as a whole number. Thus F=60 and GI=12.45 -> 12.
    # The textbook's graph estimate (~12.8 -> 13) is approximate; this test
    # follows the normative M145 equation and whole-number F convention.
    result = classify_uscs_aashto(
        p4=100.0,
        p10=93.2,
        p40=81.0,
        p200=60.2,
        ll=42.0,
        pl=16.0,
    )
    assert result["USCS"] == "CL"
    assert result["AASHTO"] == "A-7-6"
    assert result["GI"] == 12
    assert result["PI"] == 26
