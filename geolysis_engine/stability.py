"""stability calculation functions."""
from __future__ import annotations
import math
from ._common import _finite


def base_uplift_pressure_readiness(*, uplift_force_kN, hydrostatic_reference_kN,
        load_case, pressure_confirmed=False, tolerance_kN=0.01):
    """Gate sliding/uplift calculations against known base-water pressure.

    U must not be lower than the hydrostatic reference. Any positive U must be
    confirmed; seismic combinations also require explicit confirmation when
    U=0 so zero is not mistaken for an unreviewed default.
    """
    U=_finite("基底揚壓力合力 U",uplift_force_kN)
    Uref=_finite("靜水揚壓參考合力 U_ref",hydrostatic_reference_kN)
    tol=_finite("揚壓核對容許差",tolerance_kN)
    if U<0 or Uref<0 or tol<0:
        raise ValueError("U、U_ref 與核對容許差不可為負值")
    if load_case not in ("static","seismic"):
        raise ValueError("荷載組合須為 static 或 seismic")
    if U + tol < Uref:
        return {
            "ready":False,
            "reason":f"輸入 U={U:.2f} kN 小於基底靜水揚壓參考值 U_ref={Uref:.2f} kN；不可用較小揚壓計算滑動／抗浮。",
            "exceeds_reference":False,
        }
    if (U>tol or load_case=="seismic") and not pressure_confirmed:
        return {
            "ready":False,
            "reason":"尚未確認 U 為整個基礎底面的總揚壓合力，包含靜水壓及適用的殘餘超額孔隙水壓。",
            "exceeds_reference":U > Uref + tol,
        }
    return {
        "ready":True,
        "reason":None,
        "exceeds_reference":U > Uref + tol,
    }


def foundation_sliding_factor_of_safety(*, vertical_load_kN, uplift_kN,
        horizontal_load_kN, area_m2, friction_angle_deg, cohesion_kpa=0.0,
        adhesion_ratio=0.0, active_force_kN=0.0, passive_force_kN=0.0,
        fs_required=2.0, load_case='static'):
    """USACE EM 1110-1-1905 (2025) Eq. 5-28/5-29 drained interface sliding.
    Active/passive forces must be independently established using developed
    strengths; passive resistance is capped at the driving force.
    """
    V=_finite('垂直力',vertical_load_kN); U=_finite('揚壓力',uplift_kN)
    H=_finite('水平力',horizontal_load_kN); A=_finite('基底面積',area_m2)
    phi=_finite('基底摩擦角',friction_angle_deg); c=_finite('基底黏著強度',cohesion_kpa)
    ar=_finite('黏著折減比',adhesion_ratio); Pa=_finite('主動土壓力',active_force_kN)
    Pp=_finite('被動土壓力',passive_force_kN); req=_finite('要求安全係數',fs_required)
    minimum_fs = 2.0 if load_case == 'static' else 1.1 if load_case == 'seismic' else None
    if minimum_fs is None:
        raise ValueError('滑動荷載組合須為 static 或 seismic')
    if V<=0 or A<=0 or U<0 or U>=V or H<0 or not 0<=phi<=50 or c<0 or not 0<=ar<=1 or Pa<0 or Pp<0 or req<minimum_fs:
        raise ValueError(f'基底滑動輸入值不合理；{load_case} 荷載組合的 USACE 2025 要求 FS 不得低於 {minimum_fs:.1f}')
    drive=H+Pa
    passive_used=min(Pp,drive)
    net_drive=drive-passive_used
    resistance=(V-U)*math.tan(math.radians(phi))+ar*c*A
    passive_balance=(net_drive<=1e-12 and passive_used>0)
    fs=math.inf if net_drive<=1e-12 else resistance/net_drive
    return {'resisting_force_kN':resistance,'driving_force_kN':net_drive,
        'passive_resistance_used_kN':passive_used,'passive_resistance_capped':Pp>drive,
        'passive_balance_controls':passive_balance,
        'FS_sliding':fs,'FS_required':req,'FS_minimum_required':minimum_fs,
        'load_case':load_case,'passes':fs>=req,
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-28/5-29',
        'limitations':'被動土壓與主動土壓須以 developed strength（φd、cd）另行計算後輸入；被動抗力不可大於 H+Pa。此函式未自行估算側向土壓、差異水壓、地震載重或結構接觸面破壞。'}

def bishop_simplified_factor_of_safety(*, slices, tolerance=1e-7, max_iterations=500):
    """Bishop simplified circular limit-equilibrium method.
    Each slice: width_m, weight_kN, base_angle_deg, cohesion_kpa,
    friction_angle_deg, pore_pressure_kpa. Base length is width/cos(alpha).
    """
    if not slices or len(slices)<3:
        raise ValueError('Bishop 至少需要 3 個切片')
    tol=_finite('收斂容許差',tolerance)
    if tol<=0 or max_iterations<10:
        raise ValueError('迭代設定不合理')
    clean=[]
    for i,row in enumerate(slices,1):
        b=_finite(f'第{i}片寬度',row.get('width_m'))
        W=_finite(f'第{i}片重量',row.get('weight_kN'))
        alpha=_finite(f'第{i}片底面角',row.get('base_angle_deg'))
        c=_finite(f'第{i}片凝聚力',row.get('cohesion_kpa'))
        phi=_finite(f'第{i}片摩擦角',row.get('friction_angle_deg'))
        u=_finite(f'第{i}片孔隙水壓',row.get('pore_pressure_kpa',0.0))
        if b<=0 or W<=0 or not -45<alpha<45 or c<0 or not 0<=phi<=50 or u<0:
            raise ValueError(f'第{i}片資料不合理（寬度、重量須正；底角需介於 ±45°；強度及孔壓不可負）')
        clean.append((b,W,math.radians(alpha),c,math.radians(phi),u))
    driving=sum(W*math.sin(alpha) for _,W,alpha,_,_,_ in clean)
    # Normalize the sign convention so mirrored left/right slopes are equivalent.
    if driving < 0:
        clean=[(b,W,-alpha,c,phi,u) for b,W,alpha,c,phi,u in clean]
        driving=-driving
    if driving<=1e-12: raise ValueError('滑動面沒有正向總驅動力；請確認切片底角方向及重量')
    F=1.5
    for it in range(1,int(max_iterations)+1):
        numerator=0.0
        for b,W,alpha,c,phi,u in clean:
            m=math.cos(alpha)+math.sin(alpha)*math.tan(phi)/F
            if m<=0: raise ValueError('Bishop 中間係數非正，幾何或參數不適用')
            base_len=b/math.cos(alpha)
            numerator+=(c*b+(W-u*b)*math.tan(phi))/m
        newF=numerator/driving
        if not math.isfinite(newF) or newF<=0: raise ValueError('Bishop 迭代未得到有效安全係數')
        if abs(newF-F)<=tol:
            return {'FS':newF,'iterations':it,'converged':True,
                'method':'Bishop simplified (circular slip surface; vertical interslice forces neglected)',
                'slice_count':len(clean),
                'limitations':'需由使用者提供同一圓弧滑動面之正確切片幾何、重量、底角、各片 c′、φ′及孔隙水壓；本函式不自動搜尋最危險圓弧、不處理地震、非圓弧、張裂縫、地表荷載或複雜分層孔壓。請另做滑動面搜尋與其他方法交叉比對。'}
        F=0.5*F+0.5*newF
    raise ValueError('Bishop 迭代未收斂；請檢查切片幾何、孔壓與強度資料')

def _bishop_slice_total_weight(*, width_m, ground_elevation_m, base_elevation_m,
        groundwater_elevation_m, gamma_moist_kn_m3, gamma_sat_kn_m3):
    """Compute slice weight with moist soil above and saturated soil below a horizontal water table."""
    width = _finite("切片寬度", width_m)
    ground = _finite("切片地表高程", ground_elevation_m)
    base = _finite("切片底面高程", base_elevation_m)
    gamma_moist = _finite("地下水位以上單位重", gamma_moist_kn_m3)
    gamma_sat = _finite("地下水位以下飽和單位重", gamma_sat_kn_m3)
    if width <= 0 or gamma_moist <= 0 or gamma_sat <= 0:
        raise ValueError("切片寬度及土壤單位重必須大於 0")
    height = max(0.0, ground - base)
    if groundwater_elevation_m is None:
        saturated_height = 0.0
    else:
        gw = _finite("地下水位高程", groundwater_elevation_m)
        saturated_height = max(0.0, min(ground, gw) - base)
    moist_height = max(0.0, height - saturated_height)
    return width * (gamma_moist * moist_height + gamma_sat * saturated_height)


def bishop_circular_search(*, ground_profile, cohesion_kpa, friction_angle_deg,
        unit_weight_kn_m3, center_x_values, center_y_values, radius_values,
        slice_count=20, groundwater_elevation=None, gamma_water=9.81,
        unit_weight_moist_kn_m3=None, unit_weight_sat_kn_m3=None):
    """Grid-search circular slip surfaces and evaluate each with Bishop simplified.
    Coordinates use metres and elevations (positive upward). Strength is homogeneous;
    slice weights may use separate moist/saturated unit weights across a horizontal
    groundwater elevation. Ground profile is a sorted list of (x, elevation) pairs.
    """
    if len(ground_profile)<3:
        raise ValueError('地表剖面至少需要 3 個 (x, elevation) 點')
    profile=sorted([(_finite('地表 x',p[0]),_finite('地表高程',p[1])) for p in ground_profile])
    if len({p[0] for p in profile})!=len(profile):
        raise ValueError('地表剖面 x 座標不可重複')
    c=_finite('土壤凝聚力',cohesion_kpa); phi=_finite('土壤摩擦角',friction_angle_deg)
    gamma_legacy=_finite('土壤單位重',unit_weight_kn_m3)
    gamma_moist=_finite('地下水位以上單位重',gamma_legacy if unit_weight_moist_kn_m3 is None else unit_weight_moist_kn_m3)
    gamma_sat=_finite('地下水位以下飽和單位重',gamma_legacy if unit_weight_sat_kn_m3 is None else unit_weight_sat_kn_m3)
    gw=_finite('水單位重',gamma_water)
    if c<0 or not 0<=phi<=50 or gamma_moist<=0 or gamma_sat<=0 or gw<=0 or int(slice_count)<5:
        raise ValueError('土壤強度、單位重或切片數不合理')
    xs=[_finite('圓心 x',x) for x in center_x_values]
    ys=[_finite('圓心 y',y) for y in center_y_values]
    rs=[_finite('滑動圓半徑',r) for r in radius_values]
    if not xs or not ys or not rs or any(r<=0 for r in rs):
        raise ValueError('圓心搜尋範圍與半徑列表不可為空，半徑須大於 0')
    gw_elev=None if groundwater_elevation is None else _finite('地下水位高程',groundwater_elevation)
    def ground_y(x):
        for k in range(len(profile)-1):
            x0,y0=profile[k]; x1,y1=profile[k+1]
            if x0<=x<=x1:
                return y0+(y1-y0)*(x-x0)/(x1-x0)
        return None
    best=None; evaluated=0; failure_reasons={}
    for cx in xs:
        for cy in ys:
            for radius in rs:
                xa=max(profile[0][0],cx-radius)
                xb=min(profile[-1][0],cx+radius)
                if xb-xa<=0: continue
                nscan=max(200,int(slice_count)*10)
                scan=[xa+(xb-xa)*i/nscan for i in range(nscan+1)]
                valid=[]
                for x in scan:
                    gy=ground_y(x)
                    rad=radius*radius-(x-cx)**2
                    by=cy-math.sqrt(max(0.0,rad))
                    valid.append(gy is not None and gy>by+1e-6)
                runs=[]; start=None
                for i,ok in enumerate(valid):
                    if ok and start is None: start=i
                    if start is not None and (not ok or i==len(valid)-1):
                        end=i-1 if not ok else i
                        if end>start: runs.append((start,end))
                        start=None
                if not runs: continue
                i0,i1=max(runs,key=lambda z:scan[z[1]]-scan[z[0]])
                x0,x1=scan[i0],scan[i1]
                if x1-x0<(profile[-1][0]-profile[0][0])*0.03: continue
                width=(x1-x0)/int(slice_count)
                slices=[]
                for j in range(int(slice_count)):
                    xl=x0+j*width; xr=xl+width; xm=(xl+xr)/2
                    yl=cy-math.sqrt(max(0.0,radius**2-(xl-cx)**2))
                    yr=cy-math.sqrt(max(0.0,radius**2-(xr-cx)**2))
                    ym=cy-math.sqrt(max(0.0,radius**2-(xm-cx)**2))
                    gl=ground_y(xl); gr=ground_y(xr); gm=ground_y(xm)
                    height=max(0.0,gm-ym)
                    if height<=0: continue
                    alpha=math.degrees(math.atan2(yr-yl,width))
                    pore=0.0 if gw_elev is None else gw*max(0.0,gw_elev-ym)
                    slice_weight=_bishop_slice_total_weight(
                        width_m=width,ground_elevation_m=gm,base_elevation_m=ym,
                        groundwater_elevation_m=gw_elev,
                        gamma_moist_kn_m3=gamma_moist,gamma_sat_kn_m3=gamma_sat)
                    slices.append({'width_m':width,'weight_kN':slice_weight,
                        'base_angle_deg':alpha,'cohesion_kpa':c,
                        'friction_angle_deg':phi,'pore_pressure_kpa':pore})
                if len(slices)<5: continue
                try:
                    result=bishop_simplified_factor_of_safety(slices=slices)
                except ValueError as exc:
                    reason=str(exc)
                    failure_reasons[reason]=failure_reasons.get(reason,0)+1
                    continue
                evaluated+=1
                candidate={**result,'center_x_m':cx,'center_elevation_m':cy,
                    'radius_m':radius,'entry_x_m':x0,'exit_x_m':x1}
                if best is None or candidate['FS']<best['FS']:
                    best=candidate
    if best is None:
        detail='；'.join(f'{reason}（{count} 次）' for reason,count in
                        sorted(failure_reasons.items(),key=lambda x:x[1],reverse=True)[:3])
        suffix=f'；主要失敗原因：{detail}' if detail else '；候選圓弧未形成有效地表交點或切片幾何'
        raise ValueError('搜尋範圍內未找到有效圓弧滑動面'+suffix+'；請擴大圓心／半徑範圍並檢查地表剖面')
    boundary=[]
    if best['center_x_m'] in (min(xs),max(xs)): boundary.append('圓心 x')
    if best['center_elevation_m'] in (min(ys),max(ys)): boundary.append('圓心高程')
    if best['radius_m'] in (min(rs),max(rs)): boundary.append('半徑')
    boundary_warning=('最低 FS 落在搜尋網格邊界（'+ '、'.join(boundary) +'），請擴大搜尋範圍並加密網格。'
                      if boundary else None)
    return {**best,'evaluated_surfaces':evaluated,
        'search_boundary_warning':boundary_warning,
        'unit_weight_moist_kn_m3':gamma_moist,
        'unit_weight_sat_kn_m3':gamma_sat,
        'water_table_weighting':gw_elev is not None,
        'method':'Grid-search circular slip surfaces + Bishop simplified',
        'limitations':'目前假設均質土層強度、水平地下水位、圓弧滑動面與簡化 Bishop 法；地下水位以上採 γ_moist、以下採 γ_sat，孔隙水壓依水平水位計算。不含分層土強度、非圓弧滑面、地震、裂縫、地表附加載重與三維效應。搜尋結果受圓心／半徑網格密度影響，正式設計須加密搜尋並以 Spencer／Morgenstern-Price 或專業軟體交叉驗證。'}


def foundation_sliding_pseudostatic_cases(*, vertical_load_kN, uplift_kN,
        horizontal_load_kN, seismic_weight_kN, kh, kv, area_m2,
        friction_angle_deg, cohesion_kpa=0.0, adhesion_ratio=0.0,
        active_force_kN=0.0, passive_force_kN=0.0, fs_required=1.1):
    """Evaluate USACE pseudo-static sliding FS for both vertical kv directions.

    The horizontal driving load is the adverse aligned envelope H + kh·W.
    The vertical normal force is evaluated as V ± kv·W. The supplied uplift,
    active force, and passive force are held constant across the two vertical
    cases; direction-specific earth-pressure actions must be provided as the
    adverse values by the user when the two sides are not symmetric.
    """
    V=_finite('靜態總垂直力 V',vertical_load_kN)
    U=_finite('基底揚壓力 U',uplift_kN)
    H=_finite('靜態水平力 H',horizontal_load_kN)
    W=_finite('有效地震重量 W',seismic_weight_kN)
    khv=_finite('水平地震係數 kh',kh)
    kvv=_finite('垂直地震係數 kv',kv)
    if V<=0 or W<=0 or H<0 or not 0<=khv<=1 or not 0<=kvv<=0.5:
        raise ValueError('地震滑動輸入不合理：V、W須正，H不可為負，0≤kh≤1、0≤kv≤0.5')
    Vmin=V-kvv*W
    if Vmin<=0:
        raise ValueError('V−kvW≤0，地震組合已達零壓或上拔；不可使用基底摩擦滑動公式')
    if U<0 or U>=Vmin:
        raise ValueError('至少一組 V±kvW 組合的基底揚壓力 U 已達總垂直力；須先作抗浮／接觸分析')
    He=H+khv*W
    cases=[]
    for sign in (-1,1):
        Ve=V+sign*kvv*W
        result=foundation_sliding_factor_of_safety(
            vertical_load_kN=Ve,uplift_kN=U,
            horizontal_load_kN=He,area_m2=area_m2,
            friction_angle_deg=friction_angle_deg,
            cohesion_kpa=cohesion_kpa,adhesion_ratio=adhesion_ratio,
            active_force_kN=active_force_kN,
            passive_force_kN=passive_force_kN,
            fs_required=fs_required,load_case='seismic')
        cases.append({
            **result,'vertical_load_kN':Ve,'horizontal_load_kN':He,
            'seismic_weight_kN':W,
            'vertical_sign':('向下減少' if sign==-1 else '向下增加'),
        })
    governing=min(cases,key=lambda row:row['FS_sliding'])
    return {
        'cases':cases,'governing_case':governing,
        'FS_sliding':governing['FS_sliding'],
        'FS_required':governing['FS_required'],
        'FS_minimum_required':1.1,
        'passes':all(row['passes'] for row in cases),
        'passive_balance_controls':any(row['passive_balance_controls'] for row in cases),
        'resisting_force_kN':governing['resisting_force_kN'],
        'driving_force_kN':governing['driving_force_kN'],
        'governing_vertical_load_kN':governing['vertical_load_kN'],
        'governing_horizontal_load_kN':He,
        'seismic_weight_kN':W,
        'load_case':'seismic',
        'method':'USACE EM 1110-1-1905 (2025), Table 2-1 Note 2 and Eqs. 5-28/5-29; pseudo-static H+khW, V±kvW',
        'limitations':'水平地震作用採與靜力 H 同向的不利包絡 H+khW；垂直方向逐一評估 V±kvW，控制值取兩者較小 FS。U 在兩個垂直組合中保持不變。Pa/Pp 及 uplift 由使用者提供或由既有 developed Rankine 模型估算；若結構／回填幾何不對稱，應先分別建立正反向水平作用的 Pa/Pp，並輸入較不利組合。本方法未納入土體慣性、孔壓累積、液化強度損失、基礎接觸區因傾覆而變化及任意水平方位角。FS≥1.1 是 USACE Table 2-1 Note 2 對含地震荷載滑動的最低要求，不適用於承載力或傾覆檢核。'
    }

def seismic_uplift_stability_cases(*, resisting_weight_kN, structure_seismic_weight_kN,
        uplift_force_kN, kv, fs_required=1.5):
    """USACE EM 1110-1-1905 (2025), §9-10(f) and §5-7 Eq. 5-36.

    resisting_weight_kN is Wf + Ws + Wc. structure_seismic_weight_kN is Ws,
    the structure component subject to vertical seismic inertia. uplift_force_kN
    is the total resultant U acting on the full foundation base, including
    hydrostatic and residual excess pore-water pressures.
    """
    Wres=_finite('抗浮永久向下重量 Wf+Ws+Wc',resisting_weight_kN)
    Ws=_finite('結構地震重量 Ws',structure_seismic_weight_kN)
    U=_finite('基礎底面總揚壓力合力 U',uplift_force_kN)
    kvv=_finite('垂直地震係數 kv',kv)
    fs=_finite('抗浮最低安全係數',fs_required)
    if Wres<=0 or Ws<0 or Wres+1e-9<Ws or U<0:
        raise ValueError('抗浮重量輸入不合理：Wf+Ws+Wc須為正且不得小於Ws；U不可為負')
    if not 0<=kvv<=0.5:
        raise ValueError('垂直地震係數須介於 0 與 0.5')
    if fs<1.5:
        raise ValueError('USACE 2025 §9-10(f) 地震抗浮安全係數不得低於 1.5')
    if U==0:
        return {
            'cases':[],'applicable':False,'FS_uplift':None,
            'FS_required':fs,'passes':None,
            'resisting_weight_kN':Wres,'structure_seismic_weight_kN':Ws,
            'uplift_force_kN':U,'kv':kvv,
            'method':'USACE EM 1110-1-1905 (2025), §9-10(f), §5-7 Eq. 5-36',
            'limitations':'U=0，未輸入基底揚壓力；本次不計算抗浮 FS，不能據此宣稱已完成基底孔壓／揚壓評估。'
        }
    cases=[]
    for sign in (-1,1):
        Weq=Wres+sign*kvv*Ws
        fs_uplift=(Weq/U if Weq>0 else 0.0)
        cases.append({
            'vertical_sign':('向上慣性（降低結構向下重量）' if sign==-1 else '向下慣性（增加結構向下重量）'),
            'resisting_weight_kN':Wres,
            'structure_seismic_weight_kN':Ws,
            'vertical_seismic_adjustment_kN':sign*kvv*Ws,
            'effective_downward_weight_kN':Weq,
            'uplift_force_kN':U,
            'FS_uplift':fs_uplift,
            'FS_required':fs,
            'passes':fs_uplift>=fs,
        })
    governing=min(cases,key=lambda row:row['FS_uplift'])
    return {
        'cases':cases,'applicable':True,
        'FS_uplift':governing['FS_uplift'],
        'FS_required':fs,'passes':all(row['passes'] for row in cases),
        'governing_case':governing,
        'resisting_weight_kN':Wres,'structure_seismic_weight_kN':Ws,
        'uplift_force_kN':U,'kv':kvv,
        'method':'USACE EM 1110-1-1905 (2025), §9-10(f), §5-7 Eq. 5-36',
        'limitations':'重量定義須由專案結構／大地技師確認：本工具依 §5-7 Eq. 5-36 採 Wf+Ws+Wc，並依 §9-10(f) 對 Ws 施加 ±kv；但 §5-7(b) 同時指出永久死重僅在風力揚壓評估時納入，與 §9-10(f) 指示地震抗浮沿用 §5-7 方法之間，仍須依專案適用規範確認 Wf、Wc 是否可計入地震抗浮。未完成此確認前，不應僅憑本函式 FS 判定設計合格。U 必須是整個基礎底面的總揚壓合力，且須包含靜水壓與地震殘餘超額孔隙水壓；本函式不自行推估孔壓分布、不計入周圍土體剪力抗拔或界面黏著抗力。連續基礎各輸入均須採每延米線荷載。'
    }


def developed_rankine_sliding_earth_pressures(*, effective_unit_weight_kn_m3,
        footing_depth_m, footing_length_m, friction_angle_deg,
        cohesion_kpa, fs_sliding=2.0, load_case='static'):
    """USACE EM 1110-1-1905 (2025) Eqs. 5-31 to 5-35, Rankine earth
    pressure coefficients with developed soil strengths for sliding.
    """
    gamma=_finite('回填土有效單位重',effective_unit_weight_kn_m3)
    Df=_finite('基礎埋深',footing_depth_m)
    L=_finite('基礎長度',footing_length_m)
    phi=_finite('回填土摩擦角',friction_angle_deg)
    c=_finite('回填土凝聚力',cohesion_kpa)
    fs=_finite('滑動設計安全係數',fs_sliding)
    minimum_fs = 2.0 if load_case == 'static' else 1.1 if load_case == 'seismic' else None
    if minimum_fs is None:
        raise ValueError('滑動荷載組合須為 static 或 seismic')
    if gamma<=0 or Df<0 or L<=0 or not 0<=phi<50 or c<0 or fs<minimum_fs:
        raise ValueError(f'主動／被動土壓輸入不合理；{load_case} 荷載組合的 USACE 2025 滑動 FS 不得低於 {minimum_fs:.1f}')
    phi_d=math.degrees(math.atan(math.tan(math.radians(phi))/fs))
    c_d=c/fs
    sin_d=math.sin(math.radians(phi_d))
    Ka=(1-sin_d)/(1+sin_d)
    Kp=1/Ka
    Pa=max(0.0,(0.5*gamma*Df*Ka-2*c_d)*Df*L)
    Pp=(0.5*gamma*Df*Kp+2*c_d)*Df*L
    return {'developed_phi_deg':phi_d,'developed_cohesion_kpa':c_d,
        'Ka_developed':Ka,'Kp_developed':Kp,
        'active_force_kN':Pa,'passive_force_kN':Pp,
        'load_case':load_case,'FS_minimum_required':minimum_fs,
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-31 to 5-35; Rankine',
        'limitations':'假設均質回填土、垂直牆背／水平地表且可採 Rankine 壓力係數；側摩擦、斜坡地表、分層土、施工擾動及水壓需另行處理。被動抗力在 FS 計算中仍會受 driving force cap 限制。'}
