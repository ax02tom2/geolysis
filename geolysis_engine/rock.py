"""rock calculation functions."""
from __future__ import annotations
import math
from ._common import _finite

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
