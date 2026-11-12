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
    n=_finite('N',n); er=_finite('能量比',energy_ratio_pct)
    cb_in=_finite('CB',borehole_factor); cs=_finite('CS',sampler_factor); cap=_finite('CN上限',cn_cap)
    if soil_behavior not in ('cohesionless','cohesive'): raise ValueError('未知土壤行為類型')
    if cn_method not in ('Liao & Whitman','Seed & Idriss','Skempton','不修正'):
        raise ValueError('未知 CN 修正方法')
    needs_cn = soil_behavior == 'cohesionless' and cn_method != '不修正'
    sv = _finite("有效覆土應力", effective_stress_kpa) if needs_cn else None
    if (
        n < 0 or er <= 0 or er > 150 or (needs_cn and sv <= 0)
        or not 1.0 <= cb_in <= 1.15 or not 1.0 <= cs <= 1.30
        or not 1.0 <= cap <= 2.0
    ):
        raise ValueError(
            'SPT 輸入值超出 USACE 2025 修正係數範圍：CB 需 1.00–1.15、'
            'CS 需 1.00–1.30；套用 CN 時有效覆土應力須大於 0，'
            '能量比須 ≤150%，CN 上限須介於 1.0–2.0'
        )
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
    warnings = []
    if er < 50 or er > 130:
        warnings.append("能量比超出 USACE 2025 Table 4-5 常見設備範圍（約 50–130%）；請核對能量量測與設備型式。")
    if _finite('鑽桿長度', rod_length_m) > 30:
        warnings.append("鑽桿長度超過 USACE 2025 Table 4-6 列示的 30 m 範圍；CR=1.00 為延伸使用，請確認專案依據。")
    return {'N60':n60,'CE':ce,'CB':cb,'CB_input':cb_in,'CS':cs,'CR':cr,
            'CN_raw':cn_raw,'CN':cn,'CN_cap_applied':(cap_used if soil_behavior=='cohesionless' and cn_method!='不修正' else None),'N1_60':n1_60,
            'N1_60_dilatancy':n1_60_dil,'N1_60_final':n1_60_dil,
            'soil_behavior':soil_behavior,'dilatancy_applied':bool(apply_dilatancy and n1_60>15),
            'warnings':warnings}

def _profile_value(row, key, default):
    value = row.get(key, default)
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    try:
        if math.isnan(float(value)):
            return default
    except (TypeError, ValueError):
        pass
    return value


def _profile_bool(value, *, default, label):
    value = _profile_value({"value": value}, "value", default)
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in ("1", "1.0", "true", "yes", "y", "是", "套用"):
        return True
    # Refusal is a categorical field in field logs, not merely a checkbox.
    # Accept common English/Traditional Chinese field terms while keeping
    # Apply_Dilatancy restricted to explicit boolean values.
    if label == "Refusal" and normalized in (
        "refusal", "partial penetration", "partial_penetration",
        "拒錘", "拒打", "拒貫", "部分貫入",
    ):
        return True
    if normalized in ("0", "0.0", "false", "no", "n", "否", "不套用", "非拒錘", "非拒打"):
        return False
    raise ValueError(f"{label} 僅接受 true／false")


def spt_profile(rows, *, energy_ratio_pct, borehole_factor, sampler_factor, rod_length_m,
                cn_method='Liao & Whitman', cn_cap=2.0, soil_behavior='cohesionless',
                apply_dilatancy=False):
    """Correct a depth profile with optional per-row soil and equipment overrides.

    Optional CSV columns: Soil_Behavior (cohesionless/cohesive),
    Apply_Dilatancy (true/false), Energy_Ratio_pct, Borehole_Factor,
    Sampler_Factor and Rod_Length_m. Global settings remain the fallback;
    if global dilatancy is enabled, every profile row must explicitly declare
    Apply_Dilatancy to avoid blanket correction of non-eligible soil layers.
    """
    out=[]
    if not rows: raise ValueError('逐深度資料不可為空')
    seen=set()
    for row in rows:
        missing={'Depth_m','N'}-set(row)
        if missing: raise ValueError('逐深度資料缺少欄位：'+', '.join(sorted(missing)))
        depth=_finite('Depth_m',row['Depth_m'])
        measured_n=_finite('N',row['N'])
        if depth<0: raise ValueError('深度不可為負值')
        if depth in seen: raise ValueError(f'深度 {depth:g} m 重複，請先合併或修正資料')
        seen.add(depth)
        if measured_n<0: raise ValueError('逐深度資料的 N 不可為負值')
        row_soil = str(_profile_value(row, "Soil_Behavior", soil_behavior)).strip().lower()
        if row_soil not in ("cohesionless", "cohesive"):
            raise ValueError(f"深度 {depth:g} m 的 Soil_Behavior 僅接受 cohesionless 或 cohesive")
        if apply_dilatancy and row_soil == "cohesionless" and _profile_value(row, "Apply_Dilatancy", None) is None:
            raise ValueError(
                f"深度 {depth:g} m 為非凝聚性土層；若逐深度剖面啟用膨脹修正，"
                "必須在 Apply_Dilatancy 欄逐列明確填 true／false。"
            )
        row_dilatancy = _profile_bool(
            _profile_value(row, "Apply_Dilatancy", None),
            default=(bool(apply_dilatancy) and row_soil == "cohesionless"),
            label=f"深度 {depth:g} m 的 Apply_Dilatancy",
        )
        row_er = _finite("逐深度能量比", _profile_value(row, "Energy_Ratio_pct", energy_ratio_pct))
        row_cb = _finite("逐深度鑽孔修正係數", _profile_value(row, "Borehole_Factor", borehole_factor))
        row_cs = _finite("逐深度取樣器修正係數", _profile_value(row, "Sampler_Factor", sampler_factor))
        flag = _profile_bool(row.get('Refusal', False), default=False, label="Refusal")
        raw_stress = _profile_value(row, "Effective_Stress_KPa", None)
        if raw_stress is None:
            raw_stress = _profile_value(row, "Effective_Stress_kPa", None)
        if flag:
            refusal_stress = None if raw_stress is None else _finite('Effective_Stress_KPa',raw_stress)
            if refusal_stress is not None and refusal_stress <= 0:
                raise ValueError('逐深度資料的 Effective_Stress_KPa 若有提供必須大於 0')
            clean={**row,'Depth_m':depth,'N':measured_n,
                   'Effective_Stress_KPa':refusal_stress}
            out.append({**clean,'N60':None,'CE':None,'CB':None,'CS':None,'CR':None,
                'CN_raw':None,'CN':None,'N1_60':None,'N1_60_dilatancy':None,
                'N1_60_final':None,'soil_behavior':row_soil,
                'dilatancy_applied':False,'Correction_status':'拒錘／部分貫入：不可套用一般 N 值修正'})
            continue
        needs_cn = row_soil == "cohesionless" and cn_method != "不修正"
        if needs_cn and raw_stress is None:
            raise ValueError(f"深度 {depth:g} m 為非凝聚性土層且套用 CN，必須提供 Effective_Stress_KPa")
        row_stress = None if raw_stress is None else _finite('Effective_Stress_KPa',raw_stress)
        if needs_cn and row_stress <= 0:
            raise ValueError(f"深度 {depth:g} m 的 Effective_Stress_KPa 必須大於 0")
        if row_stress is not None and row_stress <= 0:
            raise ValueError(f"深度 {depth:g} m 的 Effective_Stress_KPa 若有提供必須大於 0")
        clean={**row,'Depth_m':depth,'N':measured_n,'Effective_Stress_KPa':row_stress}
        row_rod_length=_finite('逐深度鑽桿長度',_profile_value(row, "Rod_Length_m", rod_length_m))
        result=spt_correct(clean['N'],row_er,row_cb,row_cs,row_rod_length,
                      clean['Effective_Stress_KPa'],cn_method,cn_cap,
                      soil_behavior=row_soil,apply_dilatancy=row_dilatancy)
        out.append({**clean,'Rod_Length_m':row_rod_length,
            'Energy_Ratio_pct_used':row_er,'Borehole_Factor_used':result['CB'],
            'Sampler_Factor_used':row_cs,**result,
            'Correction_status':'已完成逐深度修正'})
    out.sort(key=lambda x:x['Depth_m'])
    return out
