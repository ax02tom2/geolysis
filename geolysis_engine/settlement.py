"""settlement calculation functions."""
from __future__ import annotations
import math
from ._common import _finite, _pct

def consolidation_settlement_1d(*, layer_thickness_m, initial_void_ratio, compression_index,
                                recompression_index, initial_effective_stress_kpa,
                                preconsolidation_stress_kpa, stress_increase_kpa):
    """Primary 1-D consolidation settlement using e-log(sigma') relationship."""
    H=_finite('壓縮層厚度',layer_thickness_m); e0=_finite('初始孔隙比',initial_void_ratio)
    Cc=_finite('壓縮指數 Cc',compression_index); Cr=_finite('回脹／再壓縮指數 Cr',recompression_index)
    s0=_finite('初始有效應力',initial_effective_stress_kpa); sp=_finite('先期固結壓力',preconsolidation_stress_kpa); ds=_finite('應力增量',stress_increase_kpa)
    if H<=0 or e0<=0 or Cc<=0 or Cr<0 or Cr>Cc or s0<=0 or sp<s0 or ds<0:
        raise ValueError('固結參數不合理：H、Cc、σ′0 須為正，0≤Cr≤Cc，σ′p 不可小於 σ′0，Δσ 不可為負')
    sf=s0+ds
    if ds==0: settlement=0.0; regime='無新增應力'
    elif sf<=sp:
        settlement=Cr*H/(1+e0)*math.log10(sf/s0); regime='再壓縮／超固結範圍'
    elif sp>s0:
        settlement=(Cr*H/(1+e0)*math.log10(sp/s0) + Cc*H/(1+e0)*math.log10(sf/sp)); regime='跨越先期固結壓力'
    else:
        settlement=Cc*H/(1+e0)*math.log10(sf/s0); regime='正常固結範圍'
    return {'settlement_m':settlement,'settlement_mm':settlement*1000,'final_effective_stress_kpa':sf,'regime':regime}

def consolidation_allowable_pressure(*, target_settlement_mm, footing_pressure_factor,
                                     layer_thickness_m, initial_void_ratio, compression_index,
                                     recompression_index, initial_effective_stress_kpa,
                                     preconsolidation_stress_kpa, max_pressure_kpa=5000.0, stress_method='2:1'):
    """Find maximum net contact pressure satisfying primary consolidation target.
    footing_pressure_factor is Δσmid/q from the 2:1 rectangular stress method.
    """
    target=_finite('容許固結沉陷',target_settlement_mm); factor=_finite('2:1 應力比',footing_pressure_factor)
    max_pressure=_finite('壓力搜尋上限',max_pressure_kpa)
    if target<=0 or not 0<factor<=1 or max_pressure<=0: raise ValueError('容許沉陷須大於 0、2:1 應力比須在 (0,1]，壓力搜尋上限須大於 0')
    lo,hi=0.0,max_pressure
    for _ in range(80):
        mid=(lo+hi)/2
        r=consolidation_settlement_1d(layer_thickness_m=layer_thickness_m,initial_void_ratio=initial_void_ratio,
            compression_index=compression_index,recompression_index=recompression_index,
            initial_effective_stress_kpa=initial_effective_stress_kpa,
            preconsolidation_stress_kpa=preconsolidation_stress_kpa,stress_increase_kpa=mid*factor)
        if r['settlement_mm']<=target: lo=mid
        else: hi=mid
    final=consolidation_settlement_1d(layer_thickness_m=layer_thickness_m,initial_void_ratio=initial_void_ratio,
        compression_index=compression_index,recompression_index=recompression_index,
        initial_effective_stress_kpa=initial_effective_stress_kpa,
        preconsolidation_stress_kpa=preconsolidation_stress_kpa,stress_increase_kpa=lo*factor)
    at_limit=consolidation_settlement_1d(layer_thickness_m=layer_thickness_m,initial_void_ratio=initial_void_ratio,
        compression_index=compression_index,recompression_index=recompression_index,
        initial_effective_stress_kpa=initial_effective_stress_kpa,
        preconsolidation_stress_kpa=preconsolidation_stress_kpa,stress_increase_kpa=max_pressure*factor)
    return {'qa_primary_consolidation_kpa':lo,'delta_sigma_mid_kpa':lo*factor,
            'search_limit_reached':at_limit['settlement_mm']<=target,**final,
            'method':f'1-D primary consolidation; {stress_method} rectangular stress distribution'}

_USACE_2025_U_TV = (
    (0.0, 0.0), (10.0, 0.008), (20.0, 0.031), (30.0, 0.071),
    (40.0, 0.126), (50.0, 0.197), (60.0, 0.287), (70.0, 0.403),
    (80.0, 0.567), (90.0, 0.848), (93.1, 1.000), (95.0, 1.163),
    (98.0, 1.500), (99.4, 2.000),
)


def _linear_interpolate(x, x0, y0, x1, y1):
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def _terzaghi_time_factor_from_degree(degree_percent):
    """Map U (%) to Tv using USACE 2025 Figure 7-16 tabulated points.

    The figure is tabulated for a linear distribution of excess pore pressure.
    Values above 99.4% use the classical Terzaghi series as a tail approximation;
    U=100% requires infinite time.
    """
    U = _pct('平均固結度 U', degree_percent)
    if U >= 100.0:
        raise ValueError('平均固結度 U 必須小於 100%；理論上 100% 需無限時間')
    if U <= 0.0:
        return 0.0
    for (u0, tv0), (u1, tv1) in zip(_USACE_2025_U_TV, _USACE_2025_U_TV[1:]):
        if U <= u1:
            return _linear_interpolate(U, u0, tv0, u1, tv1)
    # Tail beyond the last tabulated point (99.4%): classical 1-D series.
    lo, hi = 2.0, 10.0
    for _ in range(90):
        mid = (lo + hi) / 2.0
        u = 1.0
        for m in range(100):
            odd = 2 * m + 1
            u -= 8.0 / (math.pi ** 2 * odd ** 2) * math.exp(-(odd ** 2 * math.pi ** 2 * mid) / 4.0)
        if u < U / 100.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _terzaghi_degree_from_time_factor(tv):
    """Map Tv to U (%) using USACE 2025 Figure 7-16 tabulated points."""
    tv = _finite('時間因子 Tv', tv)
    if tv < 0:
        raise ValueError('時間因子 Tv 不可為負')
    if tv == 0:
        return 0.0
    for (u0, tv0), (u1, tv1) in zip(_USACE_2025_U_TV, _USACE_2025_U_TV[1:]):
        if tv <= tv1:
            return _linear_interpolate(tv, tv0, u0, tv1, u1)
    # Beyond Tv=2.0, continue with the classical series as a tail approximation.
    if tv >= 10:
        return 100.0
    u = 1.0
    for m in range(100):
        odd = 2 * m + 1
        u -= 8.0 / (math.pi ** 2 * odd ** 2) * math.exp(-(odd ** 2 * math.pi ** 2 * tv) / 4.0)
    return min(100.0, max(0.0, u * 100.0))

def consolidation_time_rate(*, primary_settlement_mm, layer_thickness_m,
                            cv_m2_per_day, target_degree_percent=90.0,
                            elapsed_days=None, drainage='double'):
    """Terzaghi 1-D consolidation time rate; Cv in m²/day, Hdr in metres."""
    settlement=_finite('最終主固結沉陷',primary_settlement_mm)
    H=_finite('壓縮層厚度',layer_thickness_m)
    cv=_finite('固結係數 Cv',cv_m2_per_day)
    Utarget=_pct('目標固結度',target_degree_percent)
    if not 0<Utarget<100:
        raise ValueError('目標固結度 U 必須大於 0% 且小於 100%；理論上 100% 需無限時間')
    if settlement<0 or H<=0 or cv<=0:
        raise ValueError('主固結沉陷不可為負；壓縮層厚度與 Cv 須大於 0')
    if drainage=='double': Hdr=H/2.0
    elif drainage=='single': Hdr=H
    else: raise ValueError('排水條件須為 double（雙向）或 single（單向）')
    tv_target=_terzaghi_time_factor_from_degree(Utarget)
    target_days=tv_target*Hdr**2/cv
    result={'target_degree_percent':Utarget,'time_factor_target':tv_target,
            'drainage_path_m':Hdr,'time_to_target_days':target_days,
            'time_to_target_years':target_days/365.25,
            'ultimate_primary_settlement_mm':settlement}
    if elapsed_days is not None:
        elapsed=_finite('經過時間',elapsed_days)
        if elapsed<0: raise ValueError('經過時間不可為負')
        tv_elapsed=elapsed*cv/(Hdr**2)
        Uelapsed=_terzaghi_degree_from_time_factor(tv_elapsed)
        result.update({'elapsed_days':elapsed,'time_factor_elapsed':tv_elapsed,
            'degree_at_elapsed_percent':Uelapsed,
            'primary_settlement_at_elapsed_mm':settlement*Uelapsed/100.0})
    return result

def immediate_elastic_settlement(*, net_pressure_kpa, footing_width_m,
                                 soil_modulus_mpa, poisson_ratio=0.5,
                                 influence_factor=0.82):
    """Simplified elastic half-space immediate settlement, q B (1-v²) Ip / Es."""
    q=_finite('即時沉陷淨接觸壓力',net_pressure_kpa)
    B=_finite('基礎短邊',footing_width_m)
    Es=_finite('土壤彈性模數 Es',soil_modulus_mpa)
    nu=_finite('蒲松比',poisson_ratio)
    Ip=_finite('沉陷影響係數 Ip',influence_factor)
    if q<0 or B<=0 or Es<=0 or not -0.99<nu<=0.5 or Ip<=0:
        raise ValueError('q 不可為負；B、Es、Ip 須大於 0；蒲松比須介於 -0.99 至 0.5')
    settlement=q*B*(1.0-nu**2)*Ip/Es
    return {'immediate_settlement_mm':settlement,
            'method':'簡化彈性半空間法：δi = qnet·B·(1−ν²)·Ip/Es',
            'limitations':'均質、線彈性半空間近似；未計入分層、基礎埋深、剛柔性差異與應力依存剛度。Es 應採工作應變範圍代表值；不可與已包含即時變形的經驗法重複加總。'}

def excavation_rebound_recompression(*, layer_thickness_m, initial_void_ratio,
                                     compression_index, recompression_index,
                                     initial_effective_stress_kpa,
                                     preconsolidation_stress_kpa,
                                     excavation_effective_stress_kpa,
                                     final_effective_stress_kpa):
    """Estimate excavation rebound and subsequent recompression using e-log-p indices.

    Idealized NC/OC unloading-reloading path; rebound is negative settlement.
    """
    H=_finite('壓縮層厚度',layer_thickness_m)
    e0=_finite('初始孔隙比',initial_void_ratio)
    Cc=_finite('壓縮指數 Cc',compression_index)
    Cr=_finite('再壓縮指數 Cr',recompression_index)
    s0=_finite('開挖前有效應力',initial_effective_stress_kpa)
    sp=_finite('先期固結壓力',preconsolidation_stress_kpa)
    se=_finite('開挖後有效應力',excavation_effective_stress_kpa)
    sf=_finite('基礎載重後最終有效應力',final_effective_stress_kpa)
    if H<=0 or e0<=0 or Cc<=0 or Cr<0 or Cr>Cc:
        raise ValueError('H、e0、Cc 須大於 0，且 0≤Cr≤Cc')
    if not 0<se<=s0<=sp or sf<se:
        raise ValueError('需符合 0 < σ′exc ≤ σ′0 ≤ σ′p，且 σ′f ≥ σ′exc')
    denom=1.0+e0
    rebound=-Cr*H/denom*math.log10(s0/se)
    e_exc=e0+Cr*math.log10(s0/se)
    if sf<=sp:
        delta_e=Cr*math.log10(sf/se)
        regime='最終應力仍在先期固結壓力以下（再壓縮）'
    else:
        delta_e=(Cr*math.log10(sp/se)+Cc*math.log10(sf/sp))
        regime='最終應力超過先期固結壓力（再壓縮＋主壓縮）'
    # USACE Eq. 7-40 uses the void ratio at the post-excavation stress.
    recompression=H*delta_e/(1.0+e_exc)
    net=rebound+recompression
    return {'rebound_mm':rebound*1000.0,
            'recompression_settlement_mm':recompression*1000.0,
            'net_settlement_mm':net*1000.0,
            'regime':regime,
            'method':'USACE EM 1110-1-1905 (2025) §7-15 / Table 7-10; idealized e-log-p path',
            'limitations':'以 Cr/Cc 理想化 e-log-p 曲線估算；實際開挖回彈量可能小於理論值，需以卸載－再載重固結試驗曲線校核。'}

def differential_settlement(*, settlement_a_mm, settlement_b_mm, spacing_m):
    """Compute differential settlement and angular distortion between two points."""
    a=_finite('位置 A 總沉陷',settlement_a_mm)
    b=_finite('位置 B 總沉陷',settlement_b_mm)
    spacing=_finite('兩位置水平距離',spacing_m)
    if a<0 or b<0 or spacing<=0:
        raise ValueError('兩處沉陷量不可為負，兩位置距離須大於 0')
    delta=abs(a-b)
    return {'settlement_a_mm':a,'settlement_b_mm':b,
            'differential_settlement_mm':delta,
            'spacing_m':spacing,'angular_distortion':(delta/1000.0)/spacing,
            'angular_distortion_ratio':(delta/1000.0)/spacing,
            'method':'兩點總沉陷差／水平距離；未自動套用建築物容許值'}

def secondary_compression_settlement(*, layer_thickness_m,
                                      secondary_compression_index,
                                      void_ratio_at_primary_end,
                                      time_start_days, time_end_days):
    """Secondary compression after primary consolidation, USACE Eq. 7-47."""
    H=_finite('次壓縮層厚度',layer_thickness_m)
    Ca=_finite('次壓縮指數 Cα',secondary_compression_index)
    ep=_finite('主固結完成時孔隙比 ep',void_ratio_at_primary_end)
    t1=_finite('次壓縮起算時間 t1',time_start_days)
    t2=_finite('計算終止時間 t2',time_end_days)
    if H<=0 or Ca<0 or ep<=-1 or t1<=0 or t2<=t1:
        raise ValueError('H 須大於 0、Cα 不可為負、ep 須大於 -1，且 t2 必須大於 t1>0')
    settlement=Ca*H/(1.0+ep)*math.log10(t2/t1)
    return {'secondary_settlement_m':settlement,
            'secondary_settlement_mm':settlement*1000.0,
            'time_ratio':t2/t1,
            'method':'USACE EM 1110-1-1905 (2025) Eq. 7-47'}

def usace_settlement_design_pressure(*, gross_equivalent_pressure_kpa,
        ultimate_bearing_kpa, factor_of_safety=3.0):
    """Apply the USACE 2025 settlement pressure limit.

    Settlement calculations use the applicable gross pressure (q) or gross
    equivalent pressure (q_eq), limited to q_ult / FS. For eccentric footings,
    the caller must supply q_eq rather than average V/A.
    """
    q=_finite('gross／gross equivalent pressure q or qeq',gross_equivalent_pressure_kpa)
    qult=_finite('gross ultimate bearing pressure qult',ultimate_bearing_kpa)
    fs=_finite('承載力安全係數 FS',factor_of_safety)
    if q<=0 or qult<=0 or fs<=1:
        raise ValueError('q／qeq 與 qult 須大於 0，承載力安全係數 FS 須大於 1')
    limit=qult/fs
    used=min(q,limit)
    return {
        'input_gross_equivalent_pressure_kpa':q,
        'ultimate_bearing_pressure_kpa':qult,
        'factor_of_safety':fs,
        'capacity_pressure_limit_kpa':limit,
        'design_pressure_kpa':used,
        'capacity_limit_governs':limit<q,
        'method':'USACE EM 1110-1-1905 (2025), §7-2 and settlement method procedures',
        'limitations':'輸入 q 應為適用的 gross bearing pressure；偏心基礎應輸入 qeq。沉陷計算採 min(q 或 qeq, qult/FS)。本函式只執行壓力上限控制，不代替模組五的實際承載力、偏心、滑動、抗浮及整體穩定檢核。'
    }


def burland_burbidge_2025_settlement(*, n60_average, width_m, length_m,
                                      gross_pressure_kpa, initial_effective_stress_kpa,
                                      preconsolidation_stress_kpa, granular_layer_thickness_m,
                                      years=30.0, load_type='static',
                                      overconsolidated=False, gravel_adjustment=False,
                                      fine_sand_saturated=False, n_decreases_with_depth=False):
    """USACE EM 1110-1-1905 (31 Jul 2025), §7-13 Burland-Burbidge SPT method.

    Uses N60 (not (N1)60) averaged over the influence zone. Imperial equations
    are evaluated in ft/tsf and converted to mm/kPa. This is a granular-soil
    settlement estimate, not a bearing-capacity check.
    """
    N=_finite('影響深度內平均 N60',n60_average)
    B=_finite('基礎寬度 B',width_m); L=_finite('基礎長度 L',length_m)
    q=_finite('總接觸壓力 q',gross_pressure_kpa)
    s0=_finite('影響深度內平均初始有效應力',initial_effective_stress_kpa)
    sp=_finite('先期固結壓力',preconsolidation_stress_kpa)
    Hs=_finite('基礎底下砂礫層厚度',granular_layer_thickness_m)
    t=_finite('載重作用時間',years)
    if N<=0 or B<=0 or L<B or q<=0 or s0<0 or (overconsolidated and (sp<=0 or sp<s0)) or Hs<=0 or t<=0:
        raise ValueError('B、N60、q、層厚及時間須為正；L≥B；有效應力不可為負')
    if gravel_adjustment and fine_sand_saturated:
        raise ValueError('礫土修正與飽和細砂／粉土膨脹修正不可同時套用，請依土壤粒徑組成選擇')
    if gravel_adjustment: N*=1.25
    if fine_sand_saturated and N>15: N=15+0.5*(N-15)
    Bft=B/0.3048; Lft=L/0.3048; Hsft=Hs/0.3048
    zi_ft=1.43*(Bft**0.7)
    if n_decreases_with_depth:
        zi_ft=min(2.0*Bft,Hsft)
    if zi_ft<=0: raise ValueError('影響深度計算結果不合理')
    ic_tsf_inv=0.35/(N**1.4)
    c1=max(1.0,(1.25*(Lft/Bft)/(Lft/Bft+0.25))**2)
    ratio=Hsft/zi_ft
    c2=min(1.0,ratio*(2.0-ratio)) if ratio<1.0 else 1.0
    if load_type=='static': r3,rt=0.3,0.2
    elif load_type=='fluctuating': r3,rt=0.7,0.8
    else: raise ValueError('載重型態須為 static 或 fluctuating')
    c3=1.0+r3+(rt*math.log10(t/3.0) if t>3.0 else 0.0)
    # Convert stresses to tsf; USACE equations 7-29 to 7-31 return ft.
    q_tsf=q/95.7605; s0_tsf=s0/95.7605; sp_tsf=(sp if overconsolidated else s0)/95.7605
    total=q_tsf+s0_tsf
    if not overconsolidated:
        settlement_ft=c1*c2*c3*(q_tsf+sp_tsf)*zi_ft*ic_tsf_inv
        regime='正常固結顆粒土'
    elif total<=sp_tsf:
        settlement_ft=c1*c2*c3*(q_tsf+s0_tsf)*zi_ft*ic_tsf_inv/3.0
        regime='超固結且未超過先期固結壓力'
    else:
        settlement_ft=c1*c2*c3*(total-(2.0/3.0)*sp_tsf)*zi_ft*ic_tsf_inv
        regime='超固結且超過先期固結壓力'
    return {'settlement_mm':settlement_ft*304.8,'influence_depth_m':zi_ft*0.3048,
            'Ic_tsf_inv':ic_tsf_inv,'N60_average_used':N,'C1_shape':c1,
            'C2_layer':c2,'C3_time':c3,'regime':regime,
            'method':'USACE EM 1110-1-1905 (2025) §7-13 / Burland & Burbidge SPT',
            'limitations':'僅適用砂土／礫土；平均 N60 必須取基礎底至影響深度內，不能用 (N1)60 或以單一點 N 值取代剖面平均。影響深度公式假設 N60 隨深度不減；若 N60 下降，依規範採 2B 或至鬆弱層底（取較小者）。本法仍為經驗沉陷估算，須另做極限承載力與差異沉陷檢核。'}

def burland_burbidge_2025_allowable_pressure(*, target_settlement_mm, max_pressure_kpa=5000.0, **kwargs):
    """Invert the 2025 Burland-Burbidge settlement equation for gross pressure."""
    target=_finite('容許沉陷量',target_settlement_mm)
    upper=_finite('壓力搜尋上限',max_pressure_kpa)
    if target<=0 or upper<=0: raise ValueError('容許沉陷量及壓力搜尋上限須大於 0')
    lo,hi=0.0,upper
    for _ in range(90):
        mid=(lo+hi)/2.0
        r=burland_burbidge_2025_settlement(gross_pressure_kpa=max(mid,1e-12),**kwargs)
        if r['settlement_mm']<=target: lo=mid
        else: hi=mid
    at_zero=burland_burbidge_2025_settlement(gross_pressure_kpa=1e-12,**kwargs)
    at_limit=burland_burbidge_2025_settlement(gross_pressure_kpa=upper,**kwargs)
    result=burland_burbidge_2025_settlement(gross_pressure_kpa=max(lo,1e-12),**kwargs)
    result.update({'qa_settlement_gross_kpa':lo,
                   'pressure_search_limit_reached':at_limit['settlement_mm']<=target,
                   'no_feasible_pressure':at_zero['settlement_mm']>target,
                   'target_settlement_mm':target})
    return result

def burland_burbidge_average_n60_from_profile(profile, *, width_m, granular_layer_thickness_m,
                                                n_decreases_with_depth=False,
                                                gravel_adjustment=False,
                                                fine_sand_saturated=False):
    """Compute arithmetic mean adjusted N60 within the 2025 USACE influence zone.

    Profile depths are measured downward from the footing base. Adjustments are
    applied to each individual test before averaging, as required by §7-13.
    """
    B=_finite('基礎寬度 B',width_m); Hs=_finite('砂／礫層厚度',granular_layer_thickness_m)
    if B<=0 or Hs<=0 or not profile: raise ValueError('需提供正值 B、層厚及至少一筆 N60 剖面資料')
    if gravel_adjustment and fine_sand_saturated:
        raise ValueError('礫土修正與飽和細砂／粉土膨脹修正不可同時套用，請依土壤粒徑組成選擇')
    zi=1.43*(B/0.3048)**0.7*0.3048
    if n_decreases_with_depth: zi=min(2.0*B,Hs)
    selected=[]
    seen=set()
    for row in profile:
        if 'Depth_below_base_m' not in row or 'N60' not in row:
            raise ValueError('SPT 剖面 CSV 必須包含 Depth_below_base_m、N60 欄位')
        z=_finite('Depth_below_base_m',row['Depth_below_base_m'])
        n=_finite('N60',row['N60'])
        if z<0 or n<=0: raise ValueError('SPT 剖面深度不可為負，N60 必須大於 0')
        if z in seen: raise ValueError(f'SPT 剖面深度 {z:g} m 重複')
        seen.add(z)
        if z<=zi:
            raw_n=n
            if fine_sand_saturated and n>15: n=15+0.5*(n-15)
            if gravel_adjustment: n*=1.25
            selected.append((z,raw_n,n))
    if not selected: raise ValueError(f'影響深度 Zi={zi:.2f} m 內沒有 SPT 測點')
    selected.sort(key=lambda x:x[0])
    return {'N60_average':sum(adjusted for _,_,adjusted in selected)/len(selected),
            'influence_depth_m':zi,'selected_count':len(selected),
            'selected_profile':selected,
            'adjustments':'逐點修正後平均' if (gravel_adjustment or fine_sand_saturated) else '未另作粒料修正'}

def boussinesq_rectangular_center_factor(width_m, length_m, depth_m):
    """Vertical stress influence factor beneath the center of a uniformly loaded rectangle."""
    B=_finite('基礎寬度 B',width_m); L=_finite('基礎長度 L',length_m); z=_finite('深度 z',depth_m)
    if B<=0 or L<=0 or z<0: raise ValueError('B、L 須大於 0，深度 z 不可為負')
    if z==0: return 1.0
    m=B/(2*z); n=L/(2*z)
    root=math.sqrt(m*m+n*n+1.0)
    numerator=2*m*n*root
    term1=(numerator/(m*m+n*n+m*m*n*n+1.0))*((m*m+n*n+2.0)/(m*m+n*n+1.0))
    term2=math.atan2(numerator,m*m+n*n+1.0-m*m*n*n)
    influence=(term1+term2)/math.pi
    if not 0<influence<=1.0000001: raise ValueError('Boussinesq 應力影響係數計算超出 0–1')
    return min(1.0,influence)

def _layer_stress_factor(B,L,z,method):
    if method=='2:1': return (B*L)/((B+z)*(L+z))
    if method=='Boussinesq': return boussinesq_rectangular_center_factor(B,L,z)
    raise ValueError('應力分布方法須為 2:1 或 Boussinesq')

def consolidation_settlement_layers(*, layers, footing_width_m, footing_length_m,
                                    net_pressure_kpa, stress_method='Boussinesq'):
    """Sum 1-D primary consolidation settlement over multiple layers."""
    B=_finite('基礎寬度',footing_width_m); L=_finite('基礎長度',footing_length_m)
    q=_finite('淨接觸壓力',net_pressure_kpa)
    if B<=0 or L<=0 or q<0 or not layers: raise ValueError('需提供正值基礎尺寸、非負淨壓力及至少一個壓縮層')
    results=[]
    for i,row in enumerate(layers,1):
        required={'Depth_center_m','Thickness_m','e0','Cc','Cr','Sigma0_kPa','SigmaP_kPa'}
        missing=required-set(row)
        if missing: raise ValueError('分層固結 CSV 缺少欄位：'+', '.join(sorted(missing)))
        z=_finite('Depth_center_m',row['Depth_center_m'])
        H=_finite('Thickness_m',row['Thickness_m'])
        factor=_layer_stress_factor(B,L,z,stress_method)
        ds=q*factor
        r=consolidation_settlement_1d(layer_thickness_m=H,initial_void_ratio=row['e0'],
            compression_index=row['Cc'],recompression_index=row['Cr'],
            initial_effective_stress_kpa=row['Sigma0_kPa'],
            preconsolidation_stress_kpa=row['SigmaP_kPa'],stress_increase_kpa=ds)
        results.append({'Layer':row.get('Layer',i),'Depth_center_m':z,'Thickness_m':H,
            'Stress_factor':factor,'Delta_sigma_kPa':ds,
            'Settlement_mm':r['settlement_mm'],'Regime':r['regime']})
    results.sort(key=lambda x:x['Depth_center_m'])
    if any(results[i]['Depth_center_m']>=results[i+1]['Depth_center_m'] for i in range(len(results)-1)):
        raise ValueError('分層中心深度必須由淺至深且不可重複')
    for i,row in enumerate(results):
        if row['Depth_center_m']-row['Thickness_m']/2 < -1e-9:
            raise ValueError('壓縮層頂面不可位於基礎底以上；請檢查 Depth_center_m 與 Thickness_m')
        if i and row['Depth_center_m']-row['Thickness_m']/2 < results[i-1]['Depth_center_m']+results[i-1]['Thickness_m']/2-1e-9:
            raise ValueError('分層厚度互相重疊；請檢查各層中心深度與厚度')
    return {'settlement_mm':sum(x['Settlement_mm'] for x in results),
            'layer_results':results,'method':f'分層一維主固結；{stress_method} 應力分布'}

def consolidation_allowable_pressure_layers(*, layers, footing_width_m, footing_length_m,
                                            target_settlement_mm, stress_method='Boussinesq',
                                            max_pressure_kpa=5000.0):
    target=_finite('容許主固結沉陷',target_settlement_mm)
    upper=_finite('壓力搜尋上限',max_pressure_kpa)
    if target<=0 or upper<=0: raise ValueError('容許沉陷及壓力搜尋上限須大於 0')
    lo,hi=0.0,upper
    for _ in range(90):
        mid=(lo+hi)/2
        r=consolidation_settlement_layers(layers=layers,footing_width_m=footing_width_m,
            footing_length_m=footing_length_m,net_pressure_kpa=mid,stress_method=stress_method)
        if r['settlement_mm']<=target: lo=mid
        else: hi=mid
    at_limit=consolidation_settlement_layers(layers=layers,footing_width_m=footing_width_m,
        footing_length_m=footing_length_m,net_pressure_kpa=upper,stress_method=stress_method)
    final=consolidation_settlement_layers(layers=layers,footing_width_m=footing_width_m,
        footing_length_m=footing_length_m,net_pressure_kpa=lo,stress_method=stress_method)
    return {'qa_primary_consolidation_kpa':lo,'search_limit_reached':at_limit['settlement_mm']<=target,
            'settlement_mm':final['settlement_mm'],'layer_results':final['layer_results'],
            'method':final['method']}
