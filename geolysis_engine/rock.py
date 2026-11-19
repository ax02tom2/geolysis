"""rock calculation functions."""
from __future__ import annotations
import math
from ._common import _finite

def gsi_scale_effect_warning(*, application, height_m=None, span_m=None):
    """Warn when the FHWA Figure 9-24 GSI chart's reference scale is exceeded.

    FHWA-NHI-16-072 Figure 9-24 gives slopes below 20 m and tunnels of about
    10 m span as reference scales. It advises reconsidering GSI for larger
    excavations but does not prescribe a universal numerical reduction.
    """
    app = str(application).strip().lower()
    if app not in {"slope", "tunnel", "general"}:
        raise ValueError("application 僅接受 slope、tunnel 或 general")
    if app == "slope":
        height = _finite("邊坡高度", height_m)
        if height <= 0:
            raise ValueError("邊坡高度必須大於 0")
        if height > 20.0:
            return (
                f"目前邊坡高度 {height:.1f} m 超過 FHWA-NHI-16-072 Figure 9-24 "
                "所述小於 20 m 的尺度參考；目前 GSI 未自動折減。"
                "較大邊坡應依現地節理組數、塊體互鎖與尺度效應重新評估 GSI，"
                "並以合理上下限進行敏感度分析。"
            )
    elif app == "tunnel":
        if span_m is None:
            return (
                "尚未提供隧道開挖跨度，無法核對 FHWA-NHI-16-072 Figure 9-24 "
                "約 10 m 的隧道尺度參考；請補入跨度後再判斷 GSI 適用性。"
            )
        span = _finite("隧道開挖跨度", span_m)
        if span <= 0:
            raise ValueError("隧道開挖跨度必須大於 0")
        if span > 10.0:
            return (
                f"目前隧道跨度 {span:.1f} m 超過 FHWA-NHI-16-072 Figure 9-24 "
                "約 10 m 的尺度參考；目前 GSI 未自動折減。"
                "較大跨度應依現地節理組數、塊體互鎖與尺度效應重新評估 GSI，"
                "並以合理上下限進行敏感度分析。"
            )
    return None


def hoek_brown_structure_applicability(*, gsi, structure_code):
    """Check GSI/Hoek-Brown continuum assumptions and structure-specific caveats."""
    G = _finite("GSI", gsi)
    code = str(structure_code).strip().upper()
    if not 0.0 <= G <= 100.0:
        raise ValueError("GSI 應介於 0–100")
    if code not in {"A", "B", "C", "D", "E", "F"}:
        raise ValueError("岩體結構代碼須為 A–F")
    if code == "A":
        return {
            "applicable": False,
            "warning": (
                "目前選擇的是完整／巨塊狀岩體，且描述為節理稀少、間距很大。"
                "Hoek, Carter & Diederichs (2013), Figure 4 指出完整／巨塊狀或極稀疏節理岩體"
                "不符合 GSI／Hoek–Brown 所需的均質、近似等向連續體假設；"
                "此矩陣的高 GSI 區間不得直接用於岩體強度換算。"
                "請改以完整岩石試驗強度評估，並另作控制性結構面／楔形破壞分析。"
            ),
        }
    warnings = []
    if code == "D":
        warnings.append(
            "此類岩體具有持續性層理／片理。請核對其方向與潛在滑動方向；"
            "若破壞由不利方向的弱面或楔形塊體控制，基本 GSI／Hoek–Brown 連續體模型不適用，"
            "應另作結構面強度與運動學分析。"
        )
    if code == "F":
        warnings.append(
            "層狀／剪切狀岩體須確認是否屬構造預剪切、運移或高度異質岩體。"
            "若是，基本 jointed-rock GSI 矩陣不宜直接套用，應評估 Flysch／異質岩體專用 GSI 圖"
            "或場址專用參數；若弱片理／剪裂面控制破壞，另作結構面分析。"
        )
    if G > 75.0:
        warnings.append(
            "GSI>75 屬高品質岩體，仍須檢查脆性剝落與少數控制性結構面；"
            "若破壞由少數節理控制，應改採結構面／楔形分析，不可僅依 Hoek–Brown 等效連續體。"
        )
    return {"applicable": True, "warning": " ".join(warnings) if warnings else None}


def hoek_brown_parameters(*, gsi, mi, sigma_ci_mpa, disturbance, application='slope',
                          gamma_rock_kn_m3=23.0, height_m=20.0, sigma3_custom_mpa=None):
    """Hoek-Brown (2002) generalized criterion and equivalent Mohr-Coulomb parameters.

    The equivalent c-phi pair is fitted over the selected sigma3_max range;
    it is not a unique material constant and must match the stress range and
    failure mechanism of the intended analysis.
    """
    G=_finite('GSI',gsi); mi=_finite('mi',mi); sci=_finite('完整岩石 UCS',sigma_ci_mpa)
    D=_finite('擾動因子 D',disturbance); gamma=_finite('岩體單位重',gamma_rock_kn_m3)
    H=_finite('坡高／覆蓋深度',height_m)
    if not (0<=G<=100) or mi<=0 or sci<=0 or not (0<=D<=1) or gamma<=0 or H<=0:
        raise ValueError('GSI 應介於 0–100、mi/UCS/單位重/高度須為正，D 應介於 0–1')
    mb=mi*math.exp((G-100.0)/(28.0-14.0*D))
    s=math.exp((G-100.0)/(9.0-3.0*D))
    a=0.5+(1.0/6.0)*(math.exp(-G/15.0)-math.exp(-20.0/3.0))
    sig_cm=sci*((mb+4*s-a*(mb-8*s))*((mb/4+s)**(a-1)))/(2*(1+a)*(2+a))
    sigc_mass=sci*(s**a)
    sigt_mass=-(s*sci/mb)
    gamma_mpa=gamma/1000.0
    if application=='slope':
        sig3max=sig_cm*0.72*((sig_cm/(gamma_mpa*H))**(-0.91))
    elif application=='tunnel':
        sig3max=sig_cm*0.47*((sig_cm/(gamma_mpa*H))**(-0.94))
    elif application=='general':
        if sigma3_custom_mpa is None: raise ValueError('一般分析必須輸入自訂 σ3_max')
        sig3max=_finite('自訂 σ3_max',sigma3_custom_mpa)
        if sig3max<=0: raise ValueError('自訂 σ3_max 必須大於 0')
    else:
        raise ValueError('application 須為 slope、tunnel 或 general')
    if sig3max>sci:
        raise ValueError('σ3_max 不可大於完整岩石 UCS；請檢查圍壓範圍')
    sig3n=max(1e-12,sig3max/sci)
    term=6*a*mb*((s+mb*sig3n)**(a-1))
    sinphi=term/(2*(1+a)*(2+a)+term)
    if not (0<=sinphi<1): raise ValueError('等效摩擦角計算超出物理範圍，請檢查輸入')
    phi=math.degrees(math.asin(sinphi))
    numc=sci*((1+2*a)*s+(1-a)*mb*sig3n)*((s+mb*sig3n)**(a-1))
    denc=(1+a)*(2+a)*math.sqrt(1+(term/((1+a)*(2+a))))
    c_mpa=numc/denc
    if c_mpa<0 or not math.isfinite(c_mpa): raise ValueError('等效凝聚力計算結果不合理')
    if sci<=100:
        em_gpa=(1-D/2)*math.sqrt(sci/100)*(10**((G-10)/40))
    else:
        em_gpa=(1-D/2)*(10**((G-10)/40))
    return {'GSI':G,'mb':mb,'s':s,'a':a,'sigma_ci_mpa':sci,
            'sigma_cm_mpa':sig_cm,'sigma_c_mass_mpa':sigc_mass,'sigma_t_mass_mpa':sigt_mass,
            'sigma3_max_mpa':sig3max,'sigma3n':sig3n,
            'c_equiv_mpa':c_mpa,'c_equiv_kpa':c_mpa*1000,
            'phi_equiv_deg':phi,'Em_gpa':em_gpa,
            'application':application}
