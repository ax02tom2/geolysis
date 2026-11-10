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


def test_uscs_rejects_partial_diameter_curve_inputs():
    with pytest.raises(ValueError,match='必須同時提供'):
        classify_uscs_aashto(p4=40,p10=35,p40=20,p200=2,ll=25,pl=20,d10=.1,d30=.5)


def test_spt_n60_and_n160_reference():
    r=spt_correct(20,60,1,1,12,100,'Liao & Whitman',1.7)
    assert r['N60']==pytest.approx(20)
    assert r['CN']==pytest.approx((101.3/100)**0.5)
    assert r['N1_60']==pytest.approx(20*(101.3/100)**0.5)


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
    assert r['USCS']=='OL（暫定）'
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


def test_aashto_gi_matches_published_a4_negative_example():
    r=classify_uscs_aashto(p4=100,p10=90,p40=80,p200=60,ll=25,pl=24)
    assert r['AASHTO']=='A-4'
    assert r['GI']==0


def test_aashto_gi_a2_7_uses_pi_component_only():
    r=classify_uscs_aashto(p4=100,p10=90,p40=80,p200=30,ll=50,pl=20)
    assert r['AASHTO']=='A-2-7'
    assert r['GI']==3


def test_spt_cohesive_soil_skips_cn_and_uses_cb_one():
    r=spt_correct(20,60,1.15,1.0,12,50,'Liao & Whitman',2.0,soil_behavior='cohesive')
    assert r['CB']==1.0
    assert r['CN']==1.0
    assert r['N1_60']==pytest.approx(r['N60'])


def test_spt_dilatancy_is_applied_after_overburden_correction():
    r=spt_correct(30,60,1,1,12,50,'Liao & Whitman',2.0,apply_dilatancy=True)
    assert r['N1_60']>15
    assert r['N1_60_final']==pytest.approx(15+0.5*(r['N1_60']-15))


def test_spt_profile_rejects_duplicate_depths_and_keeps_numeric_depth():
    rows=[{'Depth_m':'5','N':'10','Effective_Stress_kPa':'50'}]
    r=spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,rod_length_m=5,cn_method='不修正')
    assert r[0]['Depth_m']==5.0
    with pytest.raises(ValueError):
        spt_profile(rows*2,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,rod_length_m=5,cn_method='不修正')


def test_burland_burbidge_2025_static_example_and_factor_trends():
    from geolysis_engine import burland_burbidge_2025_settlement
    base=dict(n60_average=20,width_m=2,length_m=3,gross_pressure_kpa=150,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,
        granular_layer_thickness_m=10,years=30,load_type='static')
    r=burland_burbidge_2025_settlement(**base)
    assert r['settlement_mm']>0
    assert r['C1_shape']>1
    assert r['C3_time']==pytest.approx(1.5)
    higher_n=burland_burbidge_2025_settlement(**{**base,'n60_average':30})
    assert higher_n['settlement_mm']<r['settlement_mm']


def test_burland_burbidge_2025_dilatancy_and_gravel_adjustments():
    from geolysis_engine import burland_burbidge_2025_settlement
    base=dict(n60_average=20,width_m=2,length_m=2,gross_pressure_kpa=150,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,
        granular_layer_thickness_m=10,years=3)
    plain=burland_burbidge_2025_settlement(**base)
    dil=burland_burbidge_2025_settlement(**base,fine_sand_saturated=True)
    gravel=burland_burbidge_2025_settlement(**base,gravel_adjustment=True)
    assert dil['N60_average_used']<plain['N60_average_used']
    assert gravel['N60_average_used']>plain['N60_average_used']
    assert dil['settlement_mm']>plain['settlement_mm']
    assert gravel['settlement_mm']<plain['settlement_mm']


def test_burland_burbidge_allowable_pressure_inverts_target_settlement():
    from geolysis_engine import burland_burbidge_2025_allowable_pressure
    args=dict(n60_average=20,width_m=2,length_m=3,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,
        granular_layer_thickness_m=10,years=30,load_type='static')
    r=burland_burbidge_2025_allowable_pressure(target_settlement_mm=25,**args)
    assert r['qa_settlement_gross_kpa']>0
    assert r['settlement_mm']==pytest.approx(25,abs=1e-5)


def test_burland_burbidge_overconsolidated_pressure_branches():
    from geolysis_engine import burland_burbidge_2025_settlement
    args=dict(n60_average=20,width_m=2,length_m=2,gross_pressure_kpa=50,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=250,
        granular_layer_thickness_m=10,years=3,overconsolidated=True)
    below=burland_burbidge_2025_settlement(**args)
    above=burland_burbidge_2025_settlement(**{**args,'gross_pressure_kpa':200})
    assert below['regime']=='超固結且未超過先期固結壓力'
    assert above['regime']=='超固結且超過先期固結壓力'
    assert above['settlement_mm']>below['settlement_mm']


def test_burland_burbidge_profile_average_uses_depth_zone_and_pointwise_correction():
    from geolysis_engine import burland_burbidge_average_n60_from_profile
    rows=[{'Depth_below_base_m':0.2,'N60':20},
          {'Depth_below_base_m':0.6,'N60':30},
          {'Depth_below_base_m':2.0,'N60':40}]
    r=burland_burbidge_average_n60_from_profile(rows,width_m=2,
        granular_layer_thickness_m=10,fine_sand_saturated=True)
    # For B=2 m, Zi is about 1.55 m; third measurement is outside the zone.
    assert r['selected_count']==2
    assert r['N60_average']==pytest.approx((17.5+22.5)/2)


def test_burland_burbidge_profile_rejects_incompatible_adjustments():
    from geolysis_engine import burland_burbidge_average_n60_from_profile
    with pytest.raises(ValueError):
        burland_burbidge_average_n60_from_profile(
            [{'Depth_below_base_m':.5,'N60':20}],width_m=2,
            granular_layer_thickness_m=5,gravel_adjustment=True,fine_sand_saturated=True)


def test_spt_profile_refusal_row_is_retained_but_not_corrected():
    rows=[{'Depth_m':5,'N':50,'Effective_Stress_kPa':50,'Refusal':'true'},
          {'Depth_m':10,'N':20,'Effective_Stress_kPa':100,'Refusal':'false'}]
    r=spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,rod_length_m=5,cn_method='不修正')
    assert r[0]['N1_60_final'] is None
    assert '拒錘' in r[0]['Correction_status']
    assert r[1]['N1_60_final'] is not None


def test_spt_profile_refusal_rows_still_validate_source_values():
    bad_n=[{'Depth_m':5,'N':-1,'Effective_Stress_kPa':50,'Refusal':True}]
    bad_stress=[{'Depth_m':5,'N':50,'Effective_Stress_kPa':0,'Refusal':True}]
    for rows in (bad_n,bad_stress):
        with pytest.raises(ValueError,match='逐深度資料'):
            spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,
                rod_length_m=5,cn_method='不修正')


def test_bearing_eccentricity_updates_depth_factor_using_effective_width():
    args=dict(theory='Meyerhof',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,
        B=2,L=3,Df=1.5,water_depth=5,fs=3)
    centered=bearing_capacity(**args)
    eccentric=bearing_capacity(**args,eccentricity_B=.2)
    assert eccentric['B_effective']==pytest.approx(1.6)
    assert eccentric['dq']>centered['dq']


def test_bearing_rejects_submerged_unit_weight_above_moist_unit_weight():
    with pytest.raises(ValueError):
        bearing_capacity(theory='Hansen',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=20,
            B=2,L=3,Df=1.5,water_depth=5)


def test_bearing_groundwater_gamma_adjustment_uses_effective_width():
    args=dict(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,
        B=2,L=3,Df=1.5,water_depth=2.5,fs=3)
    centered=bearing_capacity(**args)
    eccentric=bearing_capacity(**args,eccentricity_B=.2)
    assert centered['gamma_effective']==pytest.approx(13.5)
    assert eccentric['gamma_effective']==pytest.approx(9+9*(1.0/1.6))


def test_hoek_brown_2002_slope_parameters_and_gsi_sensitivity():
    from geolysis_engine import hoek_brown_parameters
    args=dict(mi=20,sigma_ci_mpa=35,disturbance=0.7,application='slope',
              gamma_rock_kn_m3=21,height_m=20)
    low=hoek_brown_parameters(gsi=35,**args)
    mid=hoek_brown_parameters(gsi=40,**args)
    high=hoek_brown_parameters(gsi=45,**args)
    assert 0<low['phi_equiv_deg']<90
    assert low['c_equiv_kpa']>0
    assert low['sigma3_max_mpa']>0
    assert low['mb']<mid['mb']<high['mb']
    assert low['c_equiv_kpa']<mid['c_equiv_kpa']<high['c_equiv_kpa']
    assert low['Em_gpa']<mid['Em_gpa']<high['Em_gpa']


def test_hoek_brown_general_mode_requires_explicit_confinement():
    from geolysis_engine import hoek_brown_parameters
    args=dict(gsi=50,mi=17,sigma_ci_mpa=25,disturbance=0.0,
              application='general',gamma_rock_kn_m3=23,height_m=20)
    with pytest.raises(ValueError):
        hoek_brown_parameters(**args)
    r=hoek_brown_parameters(**args,sigma3_custom_mpa=1.0)
    assert r['sigma3_max_mpa']==pytest.approx(1.0)
    with pytest.raises(ValueError):
        hoek_brown_parameters(**args,sigma3_custom_mpa=30.0)


def test_uscs_low_plasticity_below_four_is_ml_even_if_above_a_line():
    # LL=20 gives A-line PI=0; PI=3 is above the A-line but below the PI=4 boundary.
    r=classify_uscs_aashto(p4=100,p10=90,p40=80,p200=60,ll=20,pl=17)
    assert r['USCS']=='ML'


def test_uscs_coarse_grained_cl_ml_fines_over_twelve_uses_dual_fines_symbol():
    r=classify_uscs_aashto(p4=80,p10=70,p40=55,p200=20,ll=25,pl=19,
        d10=.1,d30=.3,d60=.8)
    assert r['USCS']=='SC-SM'


def test_uscs_equal_gravel_and_sand_is_sand_dominant():
    r=classify_uscs_aashto(p4=55,p10=50,p40=40,p200=10,ll=30,pl=20,
        d10=.1,d30=.3,d60=.8)
    assert r['USCS'].startswith('SP-') or r['USCS'].startswith('SW-')


def test_aashto_peat_is_a8_and_gi_zero():
    r=classify_uscs_aashto(p4=100,p10=100,p40=100,p200=90,ll=100,pl=50,peat=True)
    assert r['USCS']=='PT'
    assert r['AASHTO']=='A-8'
    assert r['GI']==0


def test_spt_rod_factor_at_ten_meter_boundary_enters_one_point_zero_range():
    from geolysis_engine import rod_factor
    assert rod_factor(9.99)==pytest.approx(.95)
    assert rod_factor(10.0)==pytest.approx(1.0)
    assert rod_factor(10.01)==pytest.approx(1.0)


def test_burland_burbidge_reports_no_feasible_pressure_if_baseline_exceeds_target():
    from geolysis_engine import burland_burbidge_2025_allowable_pressure
    r=burland_burbidge_2025_allowable_pressure(target_settlement_mm=1,
        n60_average=5,width_m=3,length_m=3,initial_effective_stress_kpa=300,
        preconsolidation_stress_kpa=300,granular_layer_thickness_m=10,years=30)
    assert r['no_feasible_pressure'] is True
    assert r['qa_settlement_gross_kpa']==pytest.approx(0,abs=1e-6)


def test_aashto_gi_matches_published_m145_high_value_example_without_cap():
    # AASHTO M 145 §6.4.2: F=80, LL=90, PI=50 -> GI=46.3 -> 46.
    r=classify_uscs_aashto(p4=100,p10=100,p40=100,p200=80,ll=90,pl=40)
    assert r['AASHTO']=='A-7-5'
    assert r['GI']==46


def test_aashto_rounds_limits_before_group_assignment():
    # P200=35.49 rounds to 35; P200=35.50 rounds to 36.
    a=classify_uscs_aashto(p4=100,p10=80,p40=60,p200=35.49,ll=40,pl=29)
    b=classify_uscs_aashto(p4=100,p10=80,p40=60,p200=35.50,ll=40,pl=29)
    assert a['AASHTO'].startswith('A-2-')
    assert b['AASHTO']=='A-6'



def test_meyerhof_depth_factor_applies_to_all_three_terms_per_usace_table_5_2():
    # USACE EM 1110-1-1905 (2025), Table 5-2:
    # d_c=1+0.2*sqrt(N)*Df/B, d_q=d_gamma=1+0.1*sqrt(N)*Df/B.
    args=dict(theory='Meyerhof',c_kpa=10,phi_deg=30,gamma_moist=18,
        gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    r=bearing_capacity(**args)
    N=math.tan(math.radians(45+30/2))**2
    expected_dq=1+0.1*math.sqrt(N)*1.5/2
    expected_dc=1+0.2*math.sqrt(N)*1.5/2
    assert r['dq']==pytest.approx(expected_dq)
    assert r['dg']==pytest.approx(expected_dq)
    assert r['dc']==pytest.approx(expected_dc)
    assert r['dg']>1.0



def test_meyerhof_zero_embedment_has_unit_depth_factors():
    r=bearing_capacity(theory='Meyerhof',c_kpa=10,phi_deg=30,
        gamma_moist=18,gamma_sub=9,B=2,L=3,Df=0,water_depth=5)
    assert r['dc']==pytest.approx(1.0)
    assert r['dq']==pytest.approx(1.0)
    assert r['dg']==pytest.approx(1.0)


def test_classical_bearing_factor_values_at_phi_30():
    args=dict(c_kpa=10,phi_deg=30,gamma_moist=18,gamma_sub=9,
        B=2,L=3,Df=1.5,water_depth=5,fs=3)
    expected={'Meyerhof':15.67,'Hansen':15.07,'Vesic':22.40}
    for theory,value in expected.items():
        r=bearing_capacity(theory=theory,**args)
        assert r['Ngamma']==pytest.approx(value,abs=.02)
        assert r['Nq']==pytest.approx(18.40,abs=.02)
        assert r['Nc']==pytest.approx(30.14,abs=.03)


def test_hoek_brown_tunnel_mode_uses_tunnel_confinement_relation():
    from geolysis_engine import hoek_brown_parameters
    r=hoek_brown_parameters(gsi=50,mi=17,sigma_ci_mpa=25,disturbance=.3,
        application='tunnel',gamma_rock_kn_m3=23,height_m=100)
    assert r['sigma3_max_mpa']>0
    assert r['sigma3_max_mpa']<r['sigma_ci_mpa']


def test_clay_consolidation_search_limit_flag_uses_original_pressure_cap():
    from geolysis_engine import consolidation_allowable_pressure
    args=dict(target_settlement_mm=200,footing_pressure_factor=.5,
        layer_thickness_m=5,initial_void_ratio=.8,compression_index=.3,
        recompression_index=.05,initial_effective_stress_kpa=100,
        preconsolidation_stress_kpa=150,max_pressure_kpa=10)
    r=consolidation_allowable_pressure(**args)
    assert r['search_limit_reached'] is True
    args['target_settlement_mm']=.001
    r2=consolidation_allowable_pressure(**args)
    assert r2['search_limit_reached'] is False


def test_clay_consolidation_rejects_invalid_stress_factor_and_void_ratio():
    from geolysis_engine import consolidation_allowable_pressure, consolidation_settlement_1d
    with pytest.raises(ValueError):
        consolidation_allowable_pressure(target_settlement_mm=25,footing_pressure_factor=1.1,
            layer_thickness_m=5,initial_void_ratio=.8,compression_index=.3,
            recompression_index=.05,initial_effective_stress_kpa=100,
            preconsolidation_stress_kpa=150)
    with pytest.raises(ValueError):
        consolidation_settlement_1d(layer_thickness_m=5,initial_void_ratio=0,
            compression_index=.3,recompression_index=.05,
            initial_effective_stress_kpa=100,preconsolidation_stress_kpa=150,
            stress_increase_kpa=50)


def test_hansen_vesic_allow_zero_base_adhesion_for_smooth_footing():
    base=dict(c_kpa=20,phi_deg=0,gamma_moist=18,gamma_sub=9,
        B=2,L=3,Df=1,water_depth=5,fs=3,horizontal_load=0,
        vertical_load=1000,adhesion_ratio=0)
    h=bearing_capacity(theory='Hansen',**base)
    v=bearing_capacity(theory='Vesic',**base)
    assert h['ic']==pytest.approx(1.0)
    assert v['ic']==pytest.approx(1.0)




def test_vesic_undrained_classical_depth_factor_matches_hansen_table_4_6():
    args=dict(theory='Vesic',c_kpa=50,phi_deg=0,gamma_moist=18,
        gamma_sub=9,B=2,L=6,Df=3,water_depth=10,fs=3)
    r=bearing_capacity(**args)
    assert r['Nc']==pytest.approx(5.14)
    assert r['Nq']==pytest.approx(1.0)
    assert r['Ngamma']==pytest.approx(0.0)
    assert r['dc']==pytest.approx(1+0.4*math.atan(3/2))

def test_vesic_horizontal_load_direction_uses_classical_aspect_ratio_mapping():
    base=dict(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,
        gamma_sub=9,B=2,L=6,Df=1,water_depth=5,fs=3,
        horizontal_load=100,vertical_load=1000)
    rb=bearing_capacity(**base,load_direction='parallel_B')
    rl=bearing_capacity(**base,load_direction='parallel_L')
    m_parallel_b=(2+2/6)/(1+2/6)
    m_parallel_l=(2+6/2)/(1+6/2)
    hratio=100/(1000+2*6*0.6*10/math.tan(math.radians(30)))
    assert rb['iq']==pytest.approx((1-hratio)**m_parallel_b)
    assert rl['iq']==pytest.approx((1-hratio)**m_parallel_l)
    assert rb['iq']!=pytest.approx(rl['iq'])


def test_bearing_distinguishes_net_safety_factor_conversion_from_usace_gross_fs():
    r=bearing_capacity(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,
        gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    assert r['qa_gross']==pytest.approx(r['qa_net']+r['q_surcharge'])
    assert r['qa_gross_direct_FS']==pytest.approx(r['qu_gross']/3)
    assert r['qa_gross_direct_FS']==pytest.approx(r['qu_gross_over_FS'])
    assert r['qa_gross']!=pytest.approx(r['qa_gross_direct_FS'])


def test_bearing_returns_gross_ultimate_over_fs_for_burland_cap():
    r=bearing_capacity(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,
        gamma_sub=9,B=2,L=3,Df=1.5,water_depth=5,fs=3)
    assert r['qu_gross_over_FS']==pytest.approx(r['qu_gross']/3)
    assert r['qa_gross']==pytest.approx(r['qa_net']+r['q_surcharge'])


def test_burland_burbidge_rejects_mutually_exclusive_gravel_and_dilatancy_corrections():
    from geolysis_engine import burland_burbidge_2025_settlement
    with pytest.raises(ValueError):
        burland_burbidge_2025_settlement(n60_average=20,width_m=2,length_m=2,
            gross_pressure_kpa=150,initial_effective_stress_kpa=100,
            preconsolidation_stress_kpa=100,granular_layer_thickness_m=10,
            gravel_adjustment=True,fine_sand_saturated=True)


def test_seed_idriss_cn_cap_is_limited_to_1_7_even_if_ui_cap_is_two():
    r=spt_correct(20,60,1,1,12,25,'Seed & Idriss',2.0)
    assert r['CN_cap_applied']==pytest.approx(1.7)
    assert r['CN']==pytest.approx(1.7)


def test_boussinesq_rectangular_center_factor_reference_limits_and_2to1_comparison():
    from geolysis_engine import boussinesq_rectangular_center_factor
    assert boussinesq_rectangular_center_factor(2,2,0)==pytest.approx(1.0)
    exact=boussinesq_rectangular_center_factor(2,2,1)
    simplified=4/((2+1)*(2+1))
    assert exact==pytest.approx(.70088593,abs=1e-6)
    assert exact>simplified
    assert boussinesq_rectangular_center_factor(2,2,5)<exact


def test_multilayer_consolidation_sums_layer_settlement_and_inverts_pressure():
    from geolysis_engine import consolidation_settlement_layers, consolidation_allowable_pressure_layers
    layers=[
        {'Layer':'A','Depth_center_m':1.5,'Thickness_m':3,'e0':.8,'Cc':.3,'Cr':.05,'Sigma0_kPa':60,'SigmaP_kPa':100},
        {'Layer':'B','Depth_center_m':5,'Thickness_m':4,'e0':.9,'Cc':.4,'Cr':.06,'Sigma0_kPa':100,'SigmaP_kPa':150},
    ]
    s=consolidation_settlement_layers(layers=layers,footing_width_m=2,footing_length_m=3,
        net_pressure_kpa=100,stress_method='Boussinesq')
    assert s['settlement_mm']==pytest.approx(sum(x['Settlement_mm'] for x in s['layer_results']))
    q=consolidation_allowable_pressure_layers(layers=layers,footing_width_m=2,footing_length_m=3,
        target_settlement_mm=25,stress_method='Boussinesq')
    assert q['qa_primary_consolidation_kpa']>0
    assert q['settlement_mm']==pytest.approx(25,abs=1e-5)
    assert len(q['layer_results'])==2


def test_multilayer_consolidation_rejects_duplicate_depths_and_bad_layer_inputs():
    from geolysis_engine import consolidation_settlement_layers
    base={'Depth_center_m':2,'Thickness_m':3,'e0':.8,'Cc':.3,'Cr':.05,'Sigma0_kPa':60,'SigmaP_kPa':100}
    with pytest.raises(ValueError):
        consolidation_settlement_layers(layers=[base,{**base,'Layer':'duplicate'}],
            footing_width_m=2,footing_length_m=3,net_pressure_kpa=100)
    with pytest.raises(ValueError):
        consolidation_settlement_layers(layers=[{**base,'Cc':.01,'Cr':.2}],
            footing_width_m=2,footing_length_m=3,net_pressure_kpa=100)


def test_single_layer_consolidation_accepts_boussinesq_influence_factor():
    from geolysis_engine import consolidation_allowable_pressure, boussinesq_rectangular_center_factor
    factor=boussinesq_rectangular_center_factor(2,3,2)
    r=consolidation_allowable_pressure(target_settlement_mm=25,
        footing_pressure_factor=factor,layer_thickness_m=5,initial_void_ratio=.8,
        compression_index=.3,recompression_index=.05,initial_effective_stress_kpa=100,
        preconsolidation_stress_kpa=150,stress_method='Boussinesq')
    assert r['qa_primary_consolidation_kpa']>0
    assert 'Boussinesq' in r['method']


def test_bearing_rejects_unknown_terzaghi_failure_mode():
    with pytest.raises(ValueError):
        bearing_capacity(theory='Terzaghi',c_kpa=10,phi_deg=30,gamma_moist=18,
            gamma_sub=9,B=2,L=3,Df=1,water_depth=5,failure_mode='unknown')


@pytest.mark.parametrize(("p4","p10","p40","p200","ll","pl","np_flag","expected"), [
    (80,50,30,15,25,20,False,"A-1-a"),
    (90,70,50,25,25,20,False,"A-1-b"),
    (100,95,51,10,0,None,True,"A-3"),
    (100,90,80,35,40,30,False,"A-2-4"),
    (100,90,80,35,41,31,False,"A-2-5"),
    (100,90,80,35,40,29,False,"A-2-6"),
    (100,90,80,35,41,30,False,"A-2-7"),
    (100,90,80,36,40,30,False,"A-4"),
    (100,90,80,36,41,31,False,"A-5"),
    (100,90,80,36,40,29,False,"A-6"),
    (100,90,80,36,60,30,False,"A-7-5"),
    (100,90,80,36,60,29,False,"A-7-6"),
])
def test_aashto_all_group_and_subgroup_boundaries(
    p4,p10,p40,p200,ll,pl,np_flag,expected
):
    r=classify_uscs_aashto(
        p4=p4,p10=p10,p40=p40,p200=p200,ll=ll,pl=pl,np_flag=np_flag
    )
    assert r["AASHTO"]==expected


def test_uscs_fines_boundary_at_five_and_twelve_percent():
    args=dict(p4=60,p10=50,p40=25,ll=25,pl=19,d10=.1,d30=.3,d60=.8)
    clean=classify_uscs_aashto(**args,p200=4.99)
    at_five=classify_uscs_aashto(**args,p200=5.0)
    at_twelve=classify_uscs_aashto(**args,p200=12.0)
    above_twelve=classify_uscs_aashto(**args,p200=12.01)
    assert clean["USCS"]=="SW"
    assert at_five["USCS"]=="SW-SC"
    assert at_twelve["USCS"]=="SW-SC"
    assert above_twelve["USCS"]=="SC-SM"


@pytest.mark.parametrize(("pi","expected"), [(3.99,"ML"),(4.0,"CL-ML"),(7.0,"CL-ML"),(7.01,"CL")])
def test_uscs_plasticity_chart_pi_transition_boundaries(pi,expected):
    r=classify_uscs_aashto(
        p4=100,p10=95,p40=90,p200=70,ll=25,pl=25-pi
    )
    assert r["USCS"]==expected


def test_uscs_ll_exactly_fifty_uses_high_plasticity_symbol():
    r=classify_uscs_aashto(p4=100,p10=95,p40=90,p200=70,ll=50,pl=28)
    assert r["USCS"]=="CH"


def test_organic_soil_requires_strictly_less_than_seventy_five_percent_drying_ratio():
    r=classify_uscs_aashto(
        p4=100,p10=98,p40=90,p200=70,ll=40,pl=20,
        organic=True,ll_oven_dried=30
    )
    assert r["USCS"]=="CL"
    assert "未達" in r["organic_note"]


def test_uscs_rejects_nonpositive_or_nonmonotonic_particle_diameters():
    base=dict(p4=40,p10=35,p40=20,p200=2,ll=25,pl=20)
    for curve in (
        dict(d10=0,d30=.3,d60=.8),
        dict(d10=.3,d30=.2,d60=.8),
        dict(d10=.1,d30=.3,d60=.2),
    ):
        with pytest.raises(ValueError):
            classify_uscs_aashto(**base,**curve)


def test_peat_returns_pt_a8_without_lab_values():
    r=classify_uscs_aashto(peat=True)
    assert r["USCS"]=="PT"
    assert r["AASHTO"]=="A-8"
    assert r["GI"]==0
    assert r["PI"] is None
    assert r["gravel_pct"] is None


def test_non_peat_classification_requires_particle_size_and_atterberg_inputs():
    with pytest.raises(ValueError,match="必須為數值"):
        classify_uscs_aashto()


def test_fine_grained_uscs_does_not_require_or_report_grain_size_coefficients():
    r=classify_uscs_aashto(
        p4=100,p10=95,p40=90,p200=70,ll=25,pl=19,d10=.1
    )
    assert r["USCS"]=="CL-ML"
    assert r["Cu"] is None
    assert r["Cc"] is None


def test_coarse_soil_with_organic_fines_keeps_plasticity_chart_symbol_and_adds_note():
    r=classify_uscs_aashto(
        p4=60,p10=50,p40=25,p200=20,ll=25,pl=19,
        d10=.1,d30=.3,d60=.8,organic=True,ll_oven_dried=15
    )
    assert r["USCS"]=="SC-SM"
    assert "含有機細料" in r["organic_note"]


def test_coarse_soil_with_organic_silty_fines_uses_silty_symbol():
    r=classify_uscs_aashto(
        p4=60,p10=50,p40=25,p200=20,ll=25,pl=22,
        d10=.1,d30=.3,d60=.8,organic=True,ll_oven_dried=15
    )
    assert r["USCS"]=="SM"


def test_spt_profile_uses_per_depth_rod_length_when_provided():
    rows=[
        {'Depth_m':5,'N':12,'Effective_Stress_kPa':50,'Rod_Length_m':2.5},
        {'Depth_m':10,'N':18,'Effective_Stress_kPa':95,'Rod_Length_m':5.0},
        {'Depth_m':15,'N':25,'Effective_Stress_kPa':140,'Rod_Length_m':12.0},
    ]
    r=spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,
        rod_length_m=8,cn_method='不修正')
    assert [x['CR'] for x in r]==pytest.approx([.75,.85,1.0])
    assert [x['Rod_Length_m'] for x in r]==pytest.approx([2.5,5.0,12.0])


def test_spt_profile_falls_back_to_shared_rod_length_when_row_value_blank():
    rows=[{'Depth_m':5,'N':12,'Effective_Stress_kPa':50,'Rod_Length_m':float('nan')}]
    r=spt_profile(rows,energy_ratio_pct=60,borehole_factor=1,sampler_factor=1,
        rod_length_m=5,cn_method='不修正')
    assert r[0]['CR']==pytest.approx(.85)
    assert r[0]['Rod_Length_m']==pytest.approx(5.0)


@pytest.mark.parametrize("cap",[0.99,2.01,2.5])
def test_spt_rejects_cn_cap_outside_usace_range(cap):
    with pytest.raises(ValueError,match="CN 上限"):
        spt_correct(20,60,1,1,12,100,'Liao & Whitman',cap)


def test_spt_rejects_implausible_energy_ratio_over_150_percent():
    with pytest.raises(ValueError,match="能量比"):
        spt_correct(20,151,1,1,12,100,'Liao & Whitman',2.0)


def test_spt_cn_methods_match_reference_equations():
    lw=spt_correct(20,60,1,1,12,50,'Liao & Whitman',2.0)
    seed=spt_correct(20,60,1,1,12,50,'Seed & Idriss',2.0)
    skempton=spt_correct(20,60,1,1,12,50,'Skempton',2.0)
    assert lw['CN']==pytest.approx((101.3/50)**.5)
    assert seed['CN']==pytest.approx(min(1.7,(101.3/50)**.5))
    assert skempton['CN']==pytest.approx(2/(1+50/101.3))


def test_consolidation_time_rate_matches_usace_table_values():
    from geolysis_engine import consolidation_time_rate
    r=consolidation_time_rate(primary_settlement_mm=40,layer_thickness_m=4,
        cv_m2_per_day=0.01,target_degree_percent=90,drainage='double',
        elapsed_days=0.848*(2.0**2)/0.01)
    assert r['time_factor_target']==pytest.approx(0.848,abs=1e-4)
    assert r['time_to_target_days']==pytest.approx(0.848*4/0.01,abs=0.04)
    assert r['degree_at_elapsed_percent']==pytest.approx(90,abs=0.05)
    assert r['primary_settlement_at_elapsed_mm']==pytest.approx(36,abs=0.02)


def test_consolidation_time_rate_single_drainage_takes_four_times_double():
    from geolysis_engine import consolidation_time_rate
    args=dict(primary_settlement_mm=25,layer_thickness_m=6,cv_m2_per_day=.02,
        target_degree_percent=90)
    double=consolidation_time_rate(**args,drainage='double')
    single=consolidation_time_rate(**args,drainage='single')
    assert single['time_to_target_days']==pytest.approx(4*double['time_to_target_days'])


def test_consolidation_time_rate_rejects_100_percent_and_bad_cv():
    from geolysis_engine import consolidation_time_rate
    with pytest.raises(ValueError,match='小於 100'):
        consolidation_time_rate(primary_settlement_mm=20,layer_thickness_m=3,
            cv_m2_per_day=.01,target_degree_percent=100)
    with pytest.raises(ValueError):
        consolidation_time_rate(primary_settlement_mm=20,layer_thickness_m=3,
            cv_m2_per_day=0,target_degree_percent=90)


def test_secondary_compression_matches_usace_equation_7_47():
    from geolysis_engine import secondary_compression_settlement
    r=secondary_compression_settlement(layer_thickness_m=5,
        secondary_compression_index=.02,void_ratio_at_primary_end=.8,
        time_start_days=365.25,time_end_days=3652.5)
    assert r['secondary_settlement_mm']==pytest.approx(
        .02*5/1.8*math.log10(10)*1000)


def test_secondary_compression_rejects_invalid_time_order():
    from geolysis_engine import secondary_compression_settlement
    with pytest.raises(ValueError,match='t2'):
        secondary_compression_settlement(layer_thickness_m=5,
            secondary_compression_index=.02,void_ratio_at_primary_end=.8,
            time_start_days=3650,time_end_days=365)


def test_differential_settlement_and_angular_distortion():
    from geolysis_engine import differential_settlement
    r=differential_settlement(settlement_a_mm=20,settlement_b_mm=10,spacing_m=5)
    assert r['differential_settlement_mm']==pytest.approx(10)
    assert r['angular_distortion']==pytest.approx(.002)


def test_differential_settlement_rejects_invalid_spacing_or_negative_values():
    from geolysis_engine import differential_settlement
    with pytest.raises(ValueError):
        differential_settlement(settlement_a_mm=20,settlement_b_mm=10,spacing_m=0)
    with pytest.raises(ValueError):
        differential_settlement(settlement_a_mm=-1,settlement_b_mm=10,spacing_m=5)


def test_excavation_rebound_and_recompression_returns_zero_when_reloaded_to_original_stress():
    from geolysis_engine import excavation_rebound_recompression
    r=excavation_rebound_recompression(layer_thickness_m=5,initial_void_ratio=.8,
        compression_index=.3,recompression_index=.05,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,
        excavation_effective_stress_kpa=50,final_effective_stress_kpa=100)
    assert r['rebound_mm']<0
    assert r['recompression_settlement_mm']>0
    assert abs(r['net_settlement_mm'])<1.0  # small difference from the distinct Eq. 7-38 / 7-40 denominators


def test_excavation_rebound_recompression_crosses_preconsolidation_pressure():
    from geolysis_engine import excavation_rebound_recompression
    r=excavation_rebound_recompression(layer_thickness_m=5,initial_void_ratio=.8,
        compression_index=.3,recompression_index=.05,
        initial_effective_stress_kpa=100,preconsolidation_stress_kpa=150,
        excavation_effective_stress_kpa=50,final_effective_stress_kpa=200)
    assert r['regime'].endswith('主壓縮）')
    assert r['net_settlement_mm']>0


def test_excavation_rebound_recompression_rejects_inconsistent_stress_path():
    from geolysis_engine import excavation_rebound_recompression
    with pytest.raises(ValueError,match='σ′exc'):
        excavation_rebound_recompression(layer_thickness_m=5,initial_void_ratio=.8,
            compression_index=.3,recompression_index=.05,
            initial_effective_stress_kpa=100,preconsolidation_stress_kpa=100,
            excavation_effective_stress_kpa=120,final_effective_stress_kpa=150)


def test_immediate_elastic_settlement_reference_equation():
    from geolysis_engine import immediate_elastic_settlement
    r=immediate_elastic_settlement(net_pressure_kpa=100,footing_width_m=2,
        soil_modulus_mpa=10,poisson_ratio=.5,influence_factor=.82)
    assert r['immediate_settlement_mm']==pytest.approx(12.3)


def test_immediate_elastic_settlement_rejects_invalid_modulus_and_poisson_ratio():
    from geolysis_engine import immediate_elastic_settlement
    with pytest.raises(ValueError):
        immediate_elastic_settlement(net_pressure_kpa=100,footing_width_m=2,
            soil_modulus_mpa=0,poisson_ratio=.5)
    with pytest.raises(ValueError):
        immediate_elastic_settlement(net_pressure_kpa=100,footing_width_m=2,
            soil_modulus_mpa=10,poisson_ratio=.6)


def test_meyerhof_undrained_uses_usace_table_5_4_factors():
    base=dict(theory='Meyerhof',c_kpa=50,phi_deg=0,gamma_moist=18,
        gamma_sub=9,B=2,L=6,Df=3,water_depth=10,fs=3)
    r=bearing_capacity(**base)
    assert r['Nc']==pytest.approx(5.14)
    assert r['sc']==pytest.approx(1+0.2*2/6)
    assert r['dc']==pytest.approx(1.3)
    assert r['dq']==pytest.approx(1.0)
    assert r['dg']==pytest.approx(1.0)
    assert r['sq']==pytest.approx(1.0)
    assert r['sg']==pytest.approx(1.0)
    assert r['iq']==pytest.approx(1.0)
    assert r['ig']==pytest.approx(1.0)
    assert r['term_q']==pytest.approx(r['q_surcharge'])
    assert r['term_gamma']==pytest.approx(0.0)


def test_meyerhof_undrained_depth_factor_is_capped_at_1_5():
    r=bearing_capacity(theory='Meyerhof',c_kpa=50,phi_deg=0,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=20,water_depth=30)
    assert r['dc']==pytest.approx(1.5)


def test_meyerhof_undrained_load_inclination_uses_usace_horizontal_to_vertical_ratio():
    beta=10.0
    r=bearing_capacity(theory='Meyerhof',c_kpa=50,phi_deg=0,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=1,water_depth=10,
        load_angle=beta)
    assert r['ic']==pytest.approx(1-1.3*math.tan(math.radians(beta)))
    assert r['iq']==pytest.approx(1.0)
    assert r['ig']==pytest.approx(1.0)


def test_meyerhof_undrained_rejects_nonpositive_inclination_factor():
    with pytest.raises(ValueError,match='傾斜係數'):
        bearing_capacity(theory='Meyerhof',c_kpa=50,phi_deg=0,
            gamma_moist=18,gamma_sub=9,B=2,L=6,Df=1,water_depth=10,
            load_angle=40)


def test_vesic_surcharge_shape_factor_uses_tan_phi_not_sin_phi():
    r=bearing_capacity(theory='Vesic',c_kpa=10,phi_deg=30,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=1,water_depth=5)
    assert r['sq']==pytest.approx(1+(2/6)*math.tan(math.radians(30)))


def test_hansen_surcharge_shape_factor_retains_sin_phi():
    r=bearing_capacity(theory='Hansen',c_kpa=10,phi_deg=30,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=1,water_depth=5)
    assert r['sq']==pytest.approx(1+(2/6)*math.sin(math.radians(30)))


def test_undrained_hansen_and_vesic_keep_surcharge_and_unit_weight_factors_unity():
    common=dict(c_kpa=50,phi_deg=0,gamma_moist=18,gamma_sub=9,
        B=2,L=6,Df=3,water_depth=10,horizontal_load=100,vertical_load=1000)
    for theory in ('Hansen','Vesic'):
        r=bearing_capacity(theory=theory,**common)
        assert r['iq']==pytest.approx(1.0)
        assert r['ig']==pytest.approx(1.0)
        assert r['term_q']==pytest.approx(r['q_surcharge'])
        assert r['term_gamma']==pytest.approx(0.0)


@pytest.mark.parametrize("theory",["Terzaghi","Meyerhof","Hansen","Vesic"])
def test_undrained_bearing_uses_total_surcharge_below_groundwater(theory):
    r=bearing_capacity(theory=theory,c_kpa=50,phi_deg=0,
        gamma_moist=18,gamma_sub=9,B=2,L=3,Df=3,water_depth=1)
    expected=18*1+(9+9.81)*(3-1)
    assert r['q_surcharge']==pytest.approx(expected)
    assert r['term_q']==pytest.approx(expected)


def test_vesic_undrained_rejects_nonpositive_inclination_factor():
    with pytest.raises(ValueError,match='Vesic 不排水'):
        bearing_capacity(theory='Vesic',c_kpa=5,phi_deg=0,
            gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1,water_depth=5,
            horizontal_load=1000,vertical_load=1000)


def test_meyerhof_drained_unit_weight_shape_factor_is_not_suppressed_below_ten_degrees():
    phi=5.0
    r=bearing_capacity(theory='Meyerhof',c_kpa=0,phi_deg=phi,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=1,water_depth=5)
    kp=math.tan(math.radians(45+phi/2))**2
    expected=1+0.1*kp*(2/6)
    assert r['sq']==pytest.approx(expected)
    assert r['sg']==pytest.approx(expected)


def test_drained_bearing_surcharge_uses_effective_unit_weight_below_water_table():
    r=bearing_capacity(theory='Vesic',c_kpa=10,phi_deg=30,
        gamma_moist=18,gamma_sub=9,B=2,L=3,Df=3,water_depth=1)
    assert r['q_surcharge']==pytest.approx(18*1+9*(3-1))


def test_hansen_undrained_rejects_horizontal_load_beyond_interface_adhesion():
    with pytest.raises(ValueError,match='Hansen 不排水'):
        bearing_capacity(theory='Hansen',c_kpa=10,phi_deg=0,
            gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1,water_depth=5,
            horizontal_load=1000,vertical_load=1000,adhesion_ratio=0.5)


@pytest.mark.parametrize("theory",["Hansen","Vesic"])
def test_classical_undrained_horizontal_load_requires_nonzero_base_adhesion(theory):
    with pytest.raises(ValueError):
        bearing_capacity(theory=theory,c_kpa=20,phi_deg=0,
            gamma_moist=18,gamma_sub=9,B=2,L=3,Df=1,water_depth=5,
            horizontal_load=100,vertical_load=1000,adhesion_ratio=0)


def test_hansen_undrained_classical_depth_factor_uses_hansen_k():
    r=bearing_capacity(theory='Hansen',c_kpa=50,phi_deg=0,
        gamma_moist=18,gamma_sub=9,B=2,L=6,Df=3,water_depth=10)
    assert r['dc']==pytest.approx(1+0.4*math.atan(3/2))
    assert r['dq']==pytest.approx(1.0)
    assert r['dg']==pytest.approx(1.0)


def test_vesic_drained_inclination_uses_base_adhesion_ratio():
    args=dict(theory='Vesic',c_kpa=10,phi_deg=30,gamma_moist=18,
        gamma_sub=9,B=2,L=6,Df=1,water_depth=5,horizontal_load=100,
        vertical_load=1000)
    low=bearing_capacity(**args,adhesion_ratio=.3)
    high=bearing_capacity(**args,adhesion_ratio=.9)
    assert low['iq']<high['iq']
