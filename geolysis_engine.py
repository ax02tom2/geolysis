"""Auditable calculation functions for geolysis modules 2-5.
Units: kPa, kN/m3, m, mm unless stated otherwise.
These are screening/design-assistance calculations, not code certification.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math


def _finite(name, value):
    v=float(value)
    if not math.isfinite(v): raise ValueError(f"{name} 必須為有限數值")
    return v


def _pct(name, v):
    v=_finite(name,v)
    if not 0 <= v <= 100: raise ValueError(f"{name} 必須介於 0–100%")
    return v


def classify_uscs_aashto(*, p4, p10, p40, p200, ll, pl=None, np_flag=False,
                           d10=None, d30=None, d60=None, organic=False,
                           ll_oven_dried=None):
    """USCS (ASTM D2487 logic) and AASHTO M 145 screening classification."""
    p4,p10,p40,p200=(_pct(n,v) for n,v in [('P4',p4),('P10',p10),('P40',p40),('P200',p200)])
    ll=_finite('LL',ll)
    if ll < 0 or ll > 200: raise ValueError('LL 必須介於 0–200%')
    if not (p4 >= p10 >= p40 >= p200):
        raise ValueError('篩分析通過率必須符合 P4 ≥ P10 ≥ P40 ≥ P200')
    if np_flag:
        pi=0.0
    else:
        if pl is None: raise ValueError('請輸入 PL，或勾選 NP')
        pl=_finite('PL',pl)
        if pl<0 or pl>ll: raise ValueError('PL 必須介於 0 與 LL 之間')
        pi=ll-pl
    if organic and ll_oven_dried is not None:
        llod=_finite('烘乾後 LL',ll_oven_dried)
        if llod<0 or llod>ll: raise ValueError('烘乾後 LL 不可大於原 LL')
        organic_confirmed = llod < 0.75*ll
        organic_note = ('烘乾後 LL < 原 LL 的 75%，符合有機土輔助判別條件。'
                        if organic_confirmed else '烘乾後 LL 比值未達有機土判別條件；已依無機土塑性圖分類，請複核有機質試驗。')
    elif organic:
        organic_confirmed=True
        organic_note='有機土暫定分類：尚未提供烘乾前後 LL 比值，請以試驗確認。'
    else:
        organic_confirmed=False
        organic_note=''
    # Plasticity chart A-line and borderline CL-ML zone.
    aline=0.73*(ll-20.0)
    above_a = pi >= aline and pi > 0
    fine_symbol = ('C' if above_a else 'M')
    if ll < 50:
        if 4 <= pi <= 7 and above_a:
            fine_class = 'CL-ML'
        else:
            fine_class = 'CL' if above_a else 'ML'
    else:
        fine_class = 'CH' if above_a else 'MH'
    if organic_confirmed:
        fine_class = 'OL' if ll < 50 else 'OH'
    cu=cc=None
    if p200 >= 50:
        uscs=fine_class
    else:
        gravel=100-p4
        sand=p4-p200
        major='G' if gravel >= sand else 'S'
        if d10 is None or d30 is None or d60 is None:
            cu=cc=None; well=None
        else:
            d10,d30,d60=map(float,(d10,d30,d60))
            if not (0<d10<=d30<=d60): raise ValueError('粒徑必須符合 0 < D10 ≤ D30 ≤ D60')
            cu=d60/d10; cc=d30*d30/(d10*d60)
            well=(cu>=4 if major=='G' else cu>=6) and 1<=cc<=3
        if p200 < 5:
            if well is None: uscs=major+'? (缺少 D10/D30/D60)'
            else: uscs=major+('W' if well else 'P')
        elif p200 > 12:
            uscs=major+('C' if above_a else 'M')
        else:
            if well is None: uscs=major+'?-(C/M) (缺少級配資料)'
            else: uscs=major+('W' if well else 'P')+'-'+major+('C' if above_a else 'M')
    # AASHTO M 145; P10 is included as a data quality check / A-3 distinction.
    if p200 <= 35:
        if p200 <= 10 and p40 > 50 and np_flag:
            aashto='A-3'
        elif p200 <= 15 and p10 <= 50 and p40 <= 30 and pi <= 6:
            aashto='A-1-a'
        elif p200 <= 25 and p40 <= 50 and pi <= 6:
            aashto='A-1-b'
        else:
            if pi <= 10: aashto='A-2-4' if ll<=40 else 'A-2-5'
            else: aashto='A-2-6' if ll<=40 else 'A-2-7'
    else:
        if ll<=40 and pi<=10: aashto='A-4'
        elif ll>40 and pi<=10: aashto='A-5'
        elif ll<=40: aashto='A-6'
        else: aashto='A-7-5' if pi <= ll-30 else 'A-7-6'
    if aashto in ('A-1-a','A-1-b','A-3'): gi=0
    else:
        f1=max(0,p200-35)*(0.2+0.005*max(0,ll-40))
        f2=0.01*max(0,p200-15)*max(0,pi-10)
        gi=max(0,min(20,round(f1+f2)))
    return {'USCS':uscs,'AASHTO':aashto,'GI':int(gi),'PI':pi,'Cu':cu,'Cc':cc,
            'gravel_pct':100-p4,'sand_pct':p4-p200,'fines_pct':p200,
            'organic_note':organic_note,'A_line_PI':aline}


ROD_CORRECTION = [(3,0.75),(4,0.80),(6,0.85),(10,0.95),(float('inf'),1.00)]
def rod_factor(length_m):
    L=_finite('鑽桿長度',length_m)
    if L<=0: raise ValueError('鑽桿長度必須大於 0')
    for lim,f in ROD_CORRECTION:
        if L<lim:return f
    return 1.0


def spt_correct(n, energy_ratio_pct, borehole_factor, sampler_factor, rod_length_m,
                effective_stress_kpa, cn_method='Liao & Whitman', cn_cap=1.7):
    n=_finite('N',n); er=_finite('能量比',energy_ratio_pct); sv=_finite("有效覆土應力",effective_stress_kpa)
    cb=_finite('CB',borehole_factor); cs=_finite('CS',sampler_factor); cap=_finite('CN上限',cn_cap)
    if n<0 or er<=0 or sv<=0 or cb<=0 or cs<=0 or cap<1: raise ValueError('SPT 輸入值超出合理範圍')
    ce=er/60.0; cr=rod_factor(rod_length_m)
    n60=n*ce*cb*cs*cr
    if cn_method in ('Liao & Whitman','Seed & Idriss'):
        cn_raw=math.sqrt(100.0/sv)
        if cn_method=='Seed & Idriss': cn_raw=min(cn_raw,1.7)
    elif cn_method=='Skempton': cn_raw=2.0/(1.0+sv/100.0)
    elif cn_method=='不修正': cn_raw=1.0
    else: raise ValueError('未知 CN 修正方法')
    cn=min(cap,cn_raw)
    return {'N60':n60,'CE':ce,'CB':cb,'CS':cs,'CR':cr,'CN_raw':cn_raw,'CN':cn,
            'N1_60':cn*n60}


def spt_profile(rows, *, energy_ratio_pct, borehole_factor, sampler_factor, rod_length_m,
                cn_method='Liao & Whitman', cn_cap=1.7):
    out=[]
    for row in rows:
        r=spt_correct(row['N'],energy_ratio_pct,borehole_factor,sampler_factor,rod_length_m,
                      row['Effective_Stress_kPa'],cn_method,cn_cap)
        out.append({'Depth_m':float(row['Depth_m']),**row,**r})
    out.sort(key=lambda x:x['Depth_m'])
    if any(x['Depth_m']<0 for x in out): raise ValueError('深度不可為負值')
    return out


def usace_meyerhof_settlement_allowable(*, n60, width_m, embedment_m, settlement_mm,
                                        energy_percent=60, mat=False):
    """USACE EM 1110-1-1905 Meyerhof SPT correlation; sand preliminary screening.
    Returns gross allowable pressure kPa for settlement target. Original equations
    use ksf and ft, for 1 inch settlement; linear settlement scaling is stated.
    """
    N=_finite('N60',n60); B=_finite('基礎寬度',width_m); D=_finite('埋深',embedment_m); s=_finite('容許沉陷',settlement_mm)
    if N<=0 or B<=0 or D<0 or s<=0: raise ValueError('輸入值不合理')
    if energy_percent not in (55,70): raise ValueError('此 USACE 係數表僅支援約 55% 或 70% 能量；請選擇相符能量或使用 N60=60% 對應之經核定方法')
    # EM 1110-1-1905 factors, q in ksf, Nn is N corrected to stated energy.
    n_n=N*(energy_percent/60.0)
    Bft=B/0.3048; Dft=D/0.3048
    kd=min(1+0.33*Dft/Bft,1.33)
    if mat:
        f2=4.0 if energy_percent==55 else 3.2
        q_ksf=n_n/f2*kd
    elif Bft<=4:
        f1=2.5 if energy_percent==55 else 2.0
        q_ksf=n_n/f1*kd
    else:
        f2=4.0 if energy_percent==55 else 3.2
        f3=1.0
        q_ksf=n_n/f2*((Bft+f3)/Bft)**2*kd
    q_kpa=q_ksf*47.88025898*(s/25.4)
    return {'qa_settlement_kPa':q_kpa,'qa_1in_kPa':q_ksf*47.88025898,
            'N_energy_adjusted':n_n,'Kd':kd,'width_ft':Bft,
            'method':'USACE EM 1110-1-1905, Meyerhof SPT correlation',
            'limitations':'砂土經驗式；原式以 1 in 沉陷、特定能量比及淺基礎為前提；線性沉陷比例僅供初估。此經驗法不另作地下水修正，因 N 值可能已反映地下水影響；不得再重複折減。'}


def bearing_capacity(*, theory, c_kpa, phi_deg, gamma_moist, gamma_sub, B, L, Df,
                     water_depth, fs=3.0, load_angle=0.0, horizontal_load=None,
                     vertical_load=None, area=None, failure_mode='general', load_direction='parallel_B', adhesion_ratio=0.6, eccentricity_B=0.0, eccentricity_L=0.0):
    """Shallow footing ultimate bearing capacity using consistent theory families.
    Strip/rectangular footing; level base/ground only. Base/ground slope and seismic
    effects intentionally excluded rather than approximated with wrong factors.
    """
    vals={'c':c_kpa,'phi':phi_deg,'gamma':gamma_moist,'gamma_sub':gamma_sub,'B':B,'L':L,'Df':Df,'Dw':water_depth,'FS':fs,'beta':load_angle,'eB':eccentricity_B,'eL':eccentricity_L}
    v={k:_finite(k,x) for k,x in vals.items()}
    c,phi_deg,gamma,gsub,B,L,Df,Dw,FS,beta,eB,eL=[v[k] for k in ('c','phi','gamma','gamma_sub','B','L','Df','Dw','FS','beta','eB','eL')]
    if c<0 or not 0<=phi_deg<=50 or gamma<=0 or gsub<=0 or B<=0 or L<B or Df<0 or Dw<0 or FS<=1 or not 0<=beta<90:
        raise ValueError('承載力輸入值不合理；矩形基礎需 L≥B，FS>1，ϕ≤50°')
    if eB<0 or eL<0: raise ValueError('偏心距不可為負值；請輸入偏心距絕對值')
    Be=B-2*eB; Le=L-2*eL
    if Be<=0 or Le<=0 or Le<Be: raise ValueError('有效基礎尺寸必須為正，且有效長邊 L′ ≥ 有效短邊 B′')
    th=theory.lower()
    if not any(x in th for x in ('terzaghi','meyerhof','hansen','vesic')): raise ValueError('不支援的理論')
    # Terzaghi factors are a separate family (USACE EM 1110-1-1905, Table 4-1).
    # Interpolate the published 2-degree table; do not mix with Prandtl-Reissner factors.
    c_use=c; phi_use=phi_deg
    if 'terzaghi' in th and (eB>0 or eL>0): raise ValueError('Terzaghi 原始理論不在此工具內處理偏心載重；請改用 Meyerhof、Hansen 或 Vesic 有效尺寸法')
    if 'terzaghi' in th and failure_mode=='local':
        c_use=(2.0/3.0)*c
        phi_use=math.degrees(math.atan((2.0/3.0)*math.tan(math.radians(phi_deg))))
    elif failure_mode not in ('general','local'):
        raise ValueError('未知剪力破壞模式')
    if 'terzaghi' not in th and failure_mode!='general':
        raise ValueError('局部剪力折減選項僅在 Terzaghi 模式提供')
    ph=math.radians(phi_use); sinp=math.sin(ph); tanp=math.tan(ph)
    if 'terzaghi' in th:
        table=[(0,5.70,1.00,0.00),(2,6.30,1.22,0.20),(4,6.97,1.49,0.40),(6,7.73,1.81,0.60),
               (8,8.60,2.21,0.90),(10,9.60,2.69,1.20),(12,10.76,3.29,1.70),(14,12.11,4.02,2.30),
               (16,13.68,4.92,3.00),(18,15.52,6.04,3.90),(20,17.69,7.44,4.90),(22,20.27,9.19,5.80),
               (24,23.36,11.40,7.80),(26,27.09,14.21,11.70),(28,31.61,17.81,15.70),(30,37.16,22.46,19.70),
               (32,44.04,28.52,27.90),(34,52.64,36.50,36.00),(35,57.75,41.44,42.40),(36,63.53,47.16,52.00),
               (38,77.50,61.55,80.00),(40,95.66,81.27,100.40),(42,119.67,108.75,180.00),
               (44,151.95,147.74,257.00),(45,172.29,173.29,297.50),(46,196.22,204.19,420.00),
               (48,258.29,287.85,780.10),(50,347.50,415.14,1153.20)]
        if not 0<=phi_use<=50: raise ValueError('Terzaghi 表列因子適用 0–50°；超出範圍不外插')
        def interp(col):
            for j in range(len(table)-1):
                x0=table[j][0]; x1=table[j+1][0]
                if x0<=phi_use<=x1:
                    y0=table[j][col]; y1=table[j+1][col]
                    return y0+(y1-y0)*(phi_use-x0)/(x1-x0)
            return table[-1][col]
        Nc,Nq,Ng=interp(1),interp(2),interp(3)
    else:
        if phi_use==0: Nq,Nc=1.0,5.14
        else:
            Nq=math.exp(math.pi*tanp)*math.tan(math.radians(45)+ph/2)**2
            Nc=(Nq-1)/tanp
        if 'vesic' in th: Ng=2*(Nq+1)*tanp
        elif 'hansen' in th: Ng=1.5*(Nq-1)*tanp
        else: Ng=(Nq-1)*math.tan(1.4*ph)
    br=Be/Le
    if 'terzaghi' in th:
        if horizontal_load is not None and float(horizontal_load)>0:
            raise ValueError('Terzaghi 原始公式不套用水平載重傾斜修正；請改用 Hansen/Vesic/Meyerhof')
        sc=1.0+0.3*br
        sq=1.0
        sg=1.0-0.2*br
        dc=dq=dg=1.0
        if beta>0: raise ValueError('Terzaghi 原始公式不套用此載重傾斜修正；請改用 Hansen/Vesic/Meyerhof')
        ic=iq=ig=1.0
    elif 'meyerhof' in th:
        kp=math.tan(math.radians(45)+ph/2)**2
        sc=1+0.2*kp*br; sq=1+0.1*kp*br; sg=sq if phi_deg>10 else 1.0
        dc=1+0.2*math.sqrt(kp)*Df/B; dq=1+0.1*math.sqrt(kp)*Df/B; dg=1.0
        ic=iq=(1-beta/90.0)**2
        ig=(1-beta/phi_deg)**2 if phi_deg>0 and beta<phi_deg else (0.0 if beta>=phi_deg else 1.0)
    else: # Hansen shape/depth, shared by Vesic
        sc=1+(Nq/Nc)*br if phi_deg>0 else 1+0.2*br
        sq=1+br*sinp
        sg=1-0.4*br
        ratio=Df/B
        ang=ratio if ratio<=1 else math.atan(ratio)
        dq=1+2*tanp*(1-sinp)**2*ang
        dc=dq-(1-dq)/(Nc*tanp) if phi_deg>0 else 1+0.4*ang
        dg=1.0
        H=0.0 if horizontal_load is None else _finite('水平載重',horizontal_load)
        V=1.0 if vertical_load is None else _finite('垂直載重',vertical_load)
        A=Be*Le if area is None else _finite('基礎面積',area)
        ar=_finite('基底黏著比',adhesion_ratio)
        if H<0 or V<=0 or A<=0 or not 0<ar<=1: raise ValueError('水平載重需≥0、垂直載重及面積需>0，基底黏著比須在 (0,1]')
        ca=c*ar
        if phi_deg>0:
            denom=V+A*ca/math.tan(ph)
        else:
            denom=V
        hratio=min(0.999999,H/denom)
        theta_load=math.degrees(math.atan2(H,V))
        if 'vesic' in th:
            m=(2+B/L)/(1+B/L) if load_direction=='parallel_B' else (2+L/B)/(1+L/B)
            iq=(1-hratio)**m; ig=(1-hratio)**(m+1)
            ic=iq-(1-iq)/(Nq-1) if phi_deg>0 else max(0.0,1.0-m*H/(A*ca*Nc)) if ca>0 else 1.0
        else:
            iq=(1-0.5*hratio)**5
            ig=(1-(0.7-theta_load/450.0)*hratio)**5
            ic=iq-(1-iq)/(Nq-1) if phi_deg>0 else (0.5+0.5*math.sqrt(max(0.0,1.0-H/(A*ca))) if ca>0 else (1.0 if H==0 else 0.0))
    # Effective surcharge at foundation base and gamma in N-gamma term.
    q=gamma*min(Df,Dw)+gsub*max(0.0,Df-Dw)
    if Dw<=Df: gamma_eff=gsub
    elif Dw<Df+B: gamma_eff=gsub+(gamma-gsub)*(Dw-Df)/B
    else: gamma_eff=gamma
    tc=c_use*Nc*sc*dc*ic
    tq=q*Nq*sq*dq*iq
    tg=0.5*gamma_eff*Be*Ng*sg*dg*ig
    qu=tc+tq+tg
    qnet=qu-q
    qallow_net=qnet/FS
    qallow_gross=qallow_net+q
    return {'theory':theory,'Nc':Nc,'Nq':Nq,'Ngamma':Ng,'sc':sc,'sq':sq,'sg':sg,
            'dc':dc,'dq':dq,'dg':dg,'ic':ic,'iq':iq,'ig':ig,'q_surcharge':q,
            'gamma_effective':gamma_eff,'term_c':tc,'term_q':tq,'term_gamma':tg,
            'qu_gross':qu,'qu_net':qnet,'qa_net':qallow_net,'qa_gross':qallow_gross,
            'FS':FS,'B_effective':Be,'L_effective':Le,'eccentricity_B':eB,'eccentricity_L':eL,'c_used':c_use,'phi_used':phi_use,'failure_mode':failure_mode,'adhesion_ratio':adhesion_ratio,'limitations':'水平基底、水平地表、淺基礎靜力分析；未含斜坡地表、基底傾斜、地震及分層地盤。偏心載重以 B′=B−2eB、L′=L−2eL 有效尺寸處理；Terzaghi 模式不接受偏心距。'}


def consolidation_settlement_1d(*, layer_thickness_m, initial_void_ratio, compression_index,
                                recompression_index, initial_effective_stress_kpa,
                                preconsolidation_stress_kpa, stress_increase_kpa):
    """Primary 1-D consolidation settlement using e-log(sigma') relationship."""
    H=_finite('壓縮層厚度',layer_thickness_m); e0=_finite('初始孔隙比',initial_void_ratio)
    Cc=_finite('壓縮指數 Cc',compression_index); Cr=_finite('回脹／再壓縮指數 Cr',recompression_index)
    s0=_finite('初始有效應力',initial_effective_stress_kpa); sp=_finite('先期固結壓力',preconsolidation_stress_kpa); ds=_finite('應力增量',stress_increase_kpa)
    if H<=0 or e0<0 or Cc<=0 or Cr<0 or s0<=0 or sp<s0 or ds<0:
        raise ValueError('固結參數不合理：H、Cc、σ′0 須為正，σ′p 不可小於 σ′0，Δσ 不可為負')
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
                                     preconsolidation_stress_kpa, max_pressure_kpa=5000.0):
    """Find maximum net contact pressure satisfying primary consolidation target.
    footing_pressure_factor is Δσmid/q from the 2:1 rectangular stress method.
    """
    target=_finite('容許固結沉陷',target_settlement_mm); factor=_finite('2:1 應力比',footing_pressure_factor)
    if target<=0 or factor<=0: raise ValueError('容許沉陷及應力比須大於 0')
    lo,hi=0.0,_finite('壓力搜尋上限',max_pressure_kpa)
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
        preconsolidation_stress_kpa=preconsolidation_stress_kpa,stress_increase_kpa=hi*factor)
    return {'qa_primary_consolidation_kpa':lo,'delta_sigma_mid_kpa':lo*factor,
            'search_limit_reached':at_limit['settlement_mm']<=target,**final,
            'method':'1-D primary consolidation; 2:1 rectangular stress distribution'}
