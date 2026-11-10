"""stability calculation functions."""
from __future__ import annotations
import math
from ._common import _finite

def foundation_sliding_factor_of_safety(*, vertical_load_kN, uplift_kN,
        horizontal_load_kN, area_m2, friction_angle_deg, cohesion_kpa=0.0,
        adhesion_ratio=0.0, active_force_kN=0.0, passive_force_kN=0.0,
        fs_required=2.0):
    """USACE EM 1110-1-1905 (2025) Eq. 5-28/5-29 drained interface sliding.
    Active/passive forces must be independently established using developed
    strengths; passive resistance is capped at the driving force.
    """
    V=_finite('垂直力',vertical_load_kN); U=_finite('揚壓力',uplift_kN)
    H=_finite('水平力',horizontal_load_kN); A=_finite('基底面積',area_m2)
    phi=_finite('基底摩擦角',friction_angle_deg); c=_finite('基底黏著強度',cohesion_kpa)
    ar=_finite('黏著折減比',adhesion_ratio); Pa=_finite('主動土壓力',active_force_kN)
    Pp=_finite('被動土壓力',passive_force_kN); req=_finite('要求安全係數',fs_required)
    if V<=0 or A<=0 or U<0 or U>=V or H<0 or not 0<=phi<=50 or c<0 or not 0<=ar<=1 or Pa<0 or Pp<0 or req<=1:
        raise ValueError('基底滑動輸入值不合理')
    drive=H+Pa
    passive_used=min(Pp,drive)
    net_drive=drive-passive_used
    resistance=(V-U)*math.tan(math.radians(phi))+ar*c*A
    passive_balance=(net_drive<=1e-12 and passive_used>0)
    fs=math.inf if net_drive<=1e-12 else resistance/net_drive
    return {'resisting_force_kN':resistance,'driving_force_kN':net_drive,
        'passive_resistance_used_kN':passive_used,'passive_resistance_capped':Pp>drive,
        'passive_balance_controls':passive_balance,
        'FS_sliding':fs,'FS_required':req,'passes':fs>=req,
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

def bishop_circular_search(*, ground_profile, cohesion_kpa, friction_angle_deg,
        unit_weight_kn_m3, center_x_values, center_y_values, radius_values,
        slice_count=20, groundwater_elevation=None, gamma_water=9.81):
    """Grid-search circular slip surfaces and evaluate each with Bishop simplified.
    Coordinates use metres and elevations (positive upward); uniform soil only.
    Ground profile is a sorted list of (x, elevation) pairs.
    """
    if len(ground_profile)<3:
        raise ValueError('地表剖面至少需要 3 個 (x, elevation) 點')
    profile=sorted([(_finite('地表 x',p[0]),_finite('地表高程',p[1])) for p in ground_profile])
    if len({p[0] for p in profile})!=len(profile):
        raise ValueError('地表剖面 x 座標不可重複')
    c=_finite('土壤凝聚力',cohesion_kpa); phi=_finite('土壤摩擦角',friction_angle_deg)
    gamma=_finite('土壤單位重',unit_weight_kn_m3); gw=_finite('水單位重',gamma_water)
    if c<0 or not 0<=phi<=50 or gamma<=0 or gw<=0 or int(slice_count)<5:
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
                    slices.append({'width_m':width,'weight_kN':gamma*height*width,
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
        'method':'Grid-search circular slip surfaces + Bishop simplified',
        'limitations':'目前假設均質土層、水平地下水位、圓弧滑動面與簡化 Bishop 法；不含分層土、非圓弧滑面、地震、裂縫、地表附加載重與三維效應。搜尋結果受圓心／半徑網格密度影響，正式設計須加密搜尋並以 Spencer／Morgenstern-Price 或專業軟體交叉驗證。'}

def developed_rankine_sliding_earth_pressures(*, effective_unit_weight_kn_m3,
        footing_depth_m, footing_length_m, friction_angle_deg,
        cohesion_kpa, fs_sliding=2.0):
    """USACE EM 1110-1-1905 (2025) Eqs. 5-31 to 5-35, Rankine earth
    pressure coefficients with developed soil strengths for sliding.
    """
    gamma=_finite('回填土有效單位重',effective_unit_weight_kn_m3)
    Df=_finite('基礎埋深',footing_depth_m)
    L=_finite('基礎長度',footing_length_m)
    phi=_finite('回填土摩擦角',friction_angle_deg)
    c=_finite('回填土凝聚力',cohesion_kpa)
    fs=_finite('滑動設計安全係數',fs_sliding)
    if gamma<=0 or Df<0 or L<=0 or not 0<=phi<50 or c<0 or fs<=1:
        raise ValueError('主動／被動土壓輸入不合理')
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
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-31 to 5-35; Rankine',
        'limitations':'假設均質回填土、垂直牆背／水平地表且可採 Rankine 壓力係數；側摩擦、斜坡地表、分層土、施工擾動及水壓需另行處理。被動抗力在 FS 計算中仍會受 driving force cap 限制。'}
