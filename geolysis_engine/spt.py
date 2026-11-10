"""spt calculation functions."""
from __future__ import annotations
import math
from ._common import _finite

ROD_CORRECTION = [(3,0.75),(4,0.80),(6,0.85),(10,0.95),(float('inf'),1.00)]

def rod_factor(length_m):
    L=_finite('鑽桿長度',length_m)
    if L<=0: raise ValueError('鑽桿長度必須大於 0')
    for lim,f in ROD_CORRECTION[:-1]:
        if L<lim:return f
    return 0.95 if L<10.0 else 1.00

def spt_correct(n, energy_ratio_pct, borehole_factor, sampler_factor, rod_length_m,
                effective_stress_kpa, cn_method='Liao & Whitman', cn_cap=2.0,
                *, soil_behavior='cohesionless', apply_dilatancy=False):
    """Correct measured SPT N using USACE EM 1110-1-1905 (2025) conventions.

    CN is applied to cohesionless soils only. For clay-like soils CB is fixed at
    1.0 per the manual. Optional dilatancy correction is only appropriate for
    dense/very dense saturated fine sand or silt below the water table.
    """
    n=_finite('N',n); er=_finite('能量比',energy_ratio_pct); sv=_finite("有效覆土應力",effective_stress_kpa)
    cb_in=_finite('CB',borehole_factor); cs=_finite('CS',sampler_factor); cap=_finite('CN上限',cn_cap)
    if n<0 or er<=0 or er>150 or sv<=0 or cb_in<=0 or cs<=0 or not 1<=cap<=2.0: raise ValueError('SPT 輸入值超出合理範圍；能量比須 ≤150%，CN 上限須介於 1.0–2.0')
    if soil_behavior not in ('cohesionless','cohesive'): raise ValueError('未知土壤行為類型')
    if apply_dilatancy and (soil_behavior!='cohesionless' or cn_method=='不修正'):
        raise ValueError('膨脹修正僅能用於已完成覆土修正的飽和細砂／粉土')
    ce=er/60.0; cr=rod_factor(rod_length_m)
    cap_used=min(cap,1.7) if cn_method=='Seed & Idriss' else cap
    cb=1.0 if soil_behavior=='cohesive' else cb_in
    n60=n*ce*cb*cs*cr
    if soil_behavior=='cohesive' or cn_method=='不修正':
        cn_raw=1.0; cn=1.0
    elif cn_method in ('Liao & Whitman','Seed & Idriss'):
        cn_raw=math.sqrt(101.3/sv)
        cn=min(cap_used,cn_raw)
    elif cn_method=='Skempton':
        cn_raw=2.0/(1.0+sv/101.3)
        cn=min(cap_used,cn_raw)
    else: raise ValueError('未知 CN 修正方法')
    n1_60=cn*n60
    n1_60_dil=n1_60
    if apply_dilatancy and n1_60>15:
        n1_60_dil=15.0+0.5*(n1_60-15.0)
    return {'N60':n60,'CE':ce,'CB':cb,'CB_input':cb_in,'CS':cs,'CR':cr,
            'CN_raw':cn_raw,'CN':cn,'CN_cap_applied':(cap_used if soil_behavior=='cohesionless' and cn_method!='不修正' else None),'N1_60':n1_60,
            'N1_60_dilatancy':n1_60_dil,'N1_60_final':n1_60_dil,
            'soil_behavior':soil_behavior,'dilatancy_applied':bool(apply_dilatancy and n1_60>15)}

def spt_profile(rows, *, energy_ratio_pct, borehole_factor, sampler_factor, rod_length_m,
                cn_method='Liao & Whitman', cn_cap=2.0, soil_behavior='cohesionless',
                apply_dilatancy=False):
    out=[]
    if not rows: raise ValueError('逐深度資料不可為空')
    seen=set()
    for row in rows:
        missing={'Depth_m','N','Effective_Stress_kPa'}-set(row)
        if missing: raise ValueError('逐深度資料缺少欄位：'+', '.join(sorted(missing)))
        depth=_finite('Depth_m',row['Depth_m'])
        if depth<0: raise ValueError('深度不可為負值')
        if depth in seen: raise ValueError(f'深度 {depth:g} m 重複，請先合併或修正資料')
        seen.add(depth)
        clean={**row,'Depth_m':depth,'N':_finite('N',row['N']),
               'Effective_Stress_kPa':_finite('Effective_Stress_kPa',row['Effective_Stress_kPa'])}
        # Refusal rows skip correction, but must still pass source-data validation.
        if clean['N']<0 or clean['Effective_Stress_kPa']<=0:
            raise ValueError('逐深度資料的 N 不可為負值，Effective_Stress_kPa 必須大於 0')
        flag=row.get('Refusal',False)
        is_refusal=(flag is True or str(flag).strip().lower() in ('1','1.0','true','yes','y','refusal','拒錘','部分貫入'))
        if is_refusal:
            out.append({**clean,'N60':None,'CE':None,'CB':None,'CS':None,'CR':None,
                'CN_raw':None,'CN':None,'N1_60':None,'N1_60_dilatancy':None,
                'N1_60_final':None,'soil_behavior':soil_behavior,
                'dilatancy_applied':False,'Correction_status':'拒錘／部分貫入：不可套用一般 N 值修正'})
            continue
        row_rod_length=row.get('Rod_Length_m',rod_length_m)
        if (row_rod_length is None or
            (isinstance(row_rod_length,str) and not row_rod_length.strip()) or
            (isinstance(row_rod_length,(int,float)) and math.isnan(float(row_rod_length)))):
            row_rod_length=rod_length_m
        row_rod_length=_finite('逐深度鑽桿長度',row_rod_length)
        r=spt_correct(row['N'],energy_ratio_pct,borehole_factor,sampler_factor,row_rod_length,
                      row['Effective_Stress_kPa'],cn_method,cn_cap,
                      soil_behavior=soil_behavior,apply_dilatancy=apply_dilatancy)
        out.append({**clean,'Rod_Length_m':row_rod_length,**r,'Correction_status':'已完成一般 N 值修正'})
    out.sort(key=lambda x:x['Depth_m'])
    return out
