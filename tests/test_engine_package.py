"""Package boundary and legacy-import compatibility checks."""
import geolysis_engine
from geolysis_engine import (
    ROD_CORRECTION, bearing_capacity, bishop_circular_search, classify_uscs_aashto,
    consolidation_time_rate, hoek_brown_parameters, spt_correct,
)
from geolysis_engine.bearing import layered_bearing_capacity_profile
from geolysis_engine.classification import classify_uscs_aashto as classify_from_module
from geolysis_engine.rock import hoek_brown_parameters as hoek_from_module
from geolysis_engine.settlement import consolidation_time_rate as consolidation_from_module
from geolysis_engine.spt import spt_correct as spt_from_module
from geolysis_engine.stability import bishop_circular_search as bishop_from_module


def test_legacy_public_imports_remain_available():
    assert callable(bearing_capacity)
    assert callable(bishop_circular_search)
    assert callable(classify_uscs_aashto)
    assert callable(consolidation_time_rate)
    assert callable(hoek_brown_parameters)
    assert callable(spt_correct)
    assert ROD_CORRECTION[0] == (3, 0.75)


def test_domain_modules_export_the_same_function_objects():
    assert classify_from_module is classify_uscs_aashto
    assert hoek_from_module is hoek_brown_parameters
    assert consolidation_from_module is consolidation_time_rate
    assert spt_from_module is spt_correct
    assert bishop_from_module is bishop_circular_search
    assert callable(layered_bearing_capacity_profile)


def test_package_exports_only_public_calculation_api():
    assert all(not name.startswith("_") for name in geolysis_engine.__all__)
    assert len(geolysis_engine.__all__) == len(set(geolysis_engine.__all__))
