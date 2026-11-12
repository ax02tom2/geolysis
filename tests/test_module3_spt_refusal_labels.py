"""SPT refusal-label normalization regression tests."""
import pandas as pd
import pytest

from geolysis_ui.module3 import _spt_refusal_mask


@pytest.mark.parametrize("label", [
    "true", "1", "1.0", "yes", "y", "refusal",
    "partial penetration", "partial_penetration",
    "拒錘", "拒打", "拒貫", "部分貫入",
])
def test_spt_ui_refusal_mask_accepts_engine_refusal_vocabulary(label):
    result = _spt_refusal_mask(pd.Series([label, "false", "正常"]))
    assert result.tolist() == [True, False, False]
