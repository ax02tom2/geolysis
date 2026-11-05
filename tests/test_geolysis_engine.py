import math
import pytest
from geolysis_engine import (classify_uscs_aashto, spt_correct, spt_profile,
    usace_meyerhof_settlement_allowable, bearing_capacity)


def test_uscs_clean_well_graded_gravel():
    r=classify_uscs_aashto(p4=40,p10=35,p40=20,p200=2,ll=25,pl=20,d10=.1,d30=1.5,d60=10)
    assert r['USCS']=='GW'


def test_uscs_dual_symbol_5_to_12_fines():
    r=classify_uscs_aashto(p4=60,p10=50,p40=25,p200=8,ll=35,pl=20,d10=.1,d30=1,d60=8)
    assert r['USCS'] in ('GW-GM','GP-GM','GW-GC','GP-GC','SW-SM','SP-SM','SW-SC','SP-SC')


def test_uscs_fines_and_aashto():
    r=classify_uscs_aashto(p4=100,p10=95,p40=90,p200=75,ll=55,pl=25)
    assert r['USCS']=='CH'
    assert r['AASHTO']=='A-7-6'
    assert r['GI']>=0


def test_classification_rejects_nonmonotonic_sieve():
    with pytest.raises(ValueError):
        classify_uscs_aashto(p4=20,p10=40,p40=30,p200=10,ll=30,pl=20)


def test_spt_n60_and_n160_reference():
    r=spt_correct(20,60,1,1,12,100,'Liao & Whitman',1.7)
    assert r['N60']==pytest.approx(20)
    assert r['CN']==pytest.approx(1)
    assert r['N1_60']==pytest.approx(20)


def test_spt_rod_correction_and_profile_sort():
    rows=[{'Depth_m':10,'N':20,'Effective_Stress_kPa':100},{'Depth_m':5,'N':10,'Effective_Stress_kPa':50}]
    r=spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,rod_length_m=5,cn_method='不修正')
    assert [x['Depth_m'] for x in r]==[5,10]
    assert r[0]['CR']==pytest.approx(.85)


def test_usace_settlement_allowable_positive_and_scaled():
    a=usace_meyerhof_settlement_allowable(n60=20,width_m=1.0,embedment_m=1.0,settlement_mm=25.4,energy_percent=70)
    b=usace_meyerhof_settlement_allowable(n60=20,width_m=1.0,embedment_m=1.0,settlement_mm=12.7,energy_percent=70)
    assert a['qa_settlement_kPa']>0
    assert a['qa_settlement_kPa']==pytest.approx(2*b['qa_settlement_kPa'])


def test_bearing_capacity_four_theories_and_water_table():
    args=dict(c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    vals={t:bearing_capacity(theory=t,**args) for t in ['Terzaghi','Meyerhof','Hansen','Vesic']}
    assert all(v['qu_gross']>0 and v['qa_gross']>0 for v in vals.values())
    assert len({round(v['Ngamma'],5) for v in vals.values()})==4
    shallow=bearing_capacity(theory='Vesic',**{**args,'water_depth':1.5})
    assert shallow['gamma_effective']==pytest.approx(9)
    assert shallow['qa_gross']<vals['Vesic']['qa_gross']


def test_bearing_rejects_invalid_geometry():
    with pytest.raises(ValueError):
        bearing_capacity(theory='Hansen',c_kpa=0,phi_deg=30,gamma_moist=18,gamma_sub=9,B=3,L=2,Df=1,water_depth=5)


def test_uscs_exact_12_percent_fines_keeps_dual_symbol():
    r=classify_uscs_aashto(p4=60,p10=50,p40=25,p200=12,ll=35,pl=20,d10=.1,d30=1,d60=8)
    assert '-' in r['USCS']


def test_uscs_cl_ml_crosshatched_zone():
    r=classify_uscs_aashto(p4=100,p10=98,p40=90,p200=70,ll=25,pl=19)
    assert r['USCS']=='CL-ML'


def test_spt_energy_correction_and_cn_cap():
    r=spt_correct(20,80,1.0,1.0,12,25,'Liao & Whitman',1.7)
    assert r['N60']==pytest.approx(20*80/60)
    assert r['CN']==pytest.approx(1.7)


def test_meyerhof_inclination_reduces_capacity():
    args=dict(theory='Meyerhof',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    vertical=bearing_capacity(**args,load_angle=0)
    inclined=bearing_capacity(**args,load_angle=10)
    assert inclined['qu_gross'] < vertical['qu_gross']


def test_terzaghi_uses_distinct_usace_factors_at_30deg():
    r=bearing_capacity(theory='Terzaghi',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=2,Df=1.5,water_depth=5)
    assert r['Nc']==pytest.approx(37.16)
    assert r['Nq']==pytest.approx(22.46)
    assert r['Ngamma']==pytest.approx(19.7)


def test_terzaghi_local_shear_reduces_strength_and_capacity():
    args=dict(theory='Terzaghi',c_kpa=20,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=2,Df=1.5,water_depth=5)
    general=bearing_capacity(**args,failure_mode='general')
    local=bearing_capacity(**args,failure_mode='local')
    assert local['c_used']==pytest.approx(20*2/3)
    assert local['phi_used']<30
    assert local['qu_gross']<general['qu_gross']


def test_organic_soil_requires_confirmation_note():
    r=classify_uscs_aashto(p4=100,p10=98,p40=90,p200=70,ll=45,pl=20,organic=True)
    assert r['USCS']=='OL'
    assert '暫定' in r['organic_note']


def test_organic_soil_drying_ratio_can_reject_organic_flag():
    r=classify_uscs_aashto(p4=100,p10=98,p40=90,p200=70,ll=45,pl=20,organic=True,ll_oven_dried=40)
    assert r['USCS']=='CL'
    assert '未達' in r['organic_note']


def test_aashto_a3_nonplastic_sand():
    r=classify_uscs_aashto(p4=100,p10=90,p40=60,p200=5,ll=0,np_flag=True,d10=.08,d30=.2,d60=.5)
    assert r['AASHTO']=='A-3'
    assert r['GI']==0


def test_hansen_load_inclination_factors_reduce_capacity():
    args=dict(theory='Hansen',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    vertical=bearing_capacity(**args,horizontal_load=0,vertical_load=1000)
    inclined=bearing_capacity(**args,horizontal_load=100,vertical_load=1000)
    assert inclined['qu_gross']<vertical['qu_gross']
    assert inclined['iq']<1 and inclined['ig']<1


def test_vesic_load_direction_changes_exponent():
    args=dict(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=4,Df=1.5,water_depth=5,fs=3,horizontal_load=100,vertical_load=1000)
    b=bearing_capacity(**args,load_direction='parallel_B')
    l=bearing_capacity(**args,load_direction='parallel_L')
    assert b['iq'] != pytest.approx(l['iq'])


def test_eccentricity_uses_effective_dimensions_and_reduces_capacity():
    args=dict(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    centered=bearing_capacity(**args)
    eccentric=bearing_capacity(**args,eccentricity_B=.2,eccentricity_L=.1)
    assert eccentric['B_effective']==pytest.approx(1.6)
    assert eccentric['L_effective']==pytest.approx(2.8)
    assert eccentric['qu_gross']<centered['qu_gross']


def test_terzaghi_rejects_eccentricity_instead_of_silently_mixing_methods():
    with pytest.raises(ValueError):
        bearing_capacity(theory='Terzaghi',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,eccentricity_B=.1)


def test_1d_consolidation_nc_settlement():
    from geolysis_engine import consolidation_settlement_1d
    r=consolidation_settlement_1d(layer_thickness_m=5,initial_void_ratio=.8,compression_index=.3,recompression_index=.05,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,stress_increase_kpa=50)
    expected=.3*5/1.8*math.log10(1.5)
    assert r['settlement_m']==pytest.approx(expected)
    assert r['regime']=='正常固結範圍'


def test_1d_consolidation_overconsolidated_recompression():
    from geolysis_engine import consolidation_settlement_1d
    r=consolidation_settlement_1d(layer_thickness_m=5,initial_void_ratio=.8,compression_index=.3,recompression_index=.05,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=200,stress_increase_kpa=50)
    assert r['regime']=='再壓縮／超固結範圍'
    assert r['settlement_mm']>0


def test_consolidation_allowable_pressure_hits_target():
    from geolysis_engine import consolidation_allowable_pressure
    r=consolidation_allowable_pressure(target_settlement_mm=25,footing_pressure_factor=.5,layer_thickness_m=5,
        initial_void_ratio=.8,compression_index=.3,recompression_index=.05,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100)
    assert r['qa_primary_consolidation_kpa']>0
    assert r['settlement_mm']==pytest.approx(25,abs=.001)


def test_published_general_theory_factors_at_30deg():
    base=dict(c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5)
    expected={'Meyerhof':(30.14,18.40,15.67),'Hansen':(30.14,18.40,15.07),'Vesic':(30.14,18.40,22.40)}
    for theory, factors in expected.items():
        r=bearing_capacity(theory=theory,**base)
        assert r['Nc']==pytest.approx(factors[0],abs=.03)
        assert r['Nq']==pytest.approx(factors[1],abs=.03)
        assert r['Ngamma']==pytest.approx(factors[2],abs=.03)
