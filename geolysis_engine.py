"""Auditable calculation functions for geolysis modules 2-5.
Units: kPa, kN/m3, m, mm unless stated otherwise.
These are screening/design-assistance calculations, not code certification.
"""
from __future__ import annotations
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
                           ll_oven_dried=None, peat=False):
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
    organic_test_rejected=False
    if organic and ll_oven_dried is not None:
        llod=_finite('烘乾後 LL',ll_oven_dried)
        if llod<0 or llod>ll: raise ValueError('烘乾後 LL 不可大於原 LL')
        organic_confirmed = llod < 0.75*ll
        organic_test_rejected = not organic_confirmed
        organic_note = ('烘乾後 LL < 原 LL 的 75%，符合有機土輔助判別條件。'
                        if organic_confirmed else '烘乾後 LL 比值未達有機土判別條件；已依無機土塑性圖分類，請複核有機質試驗。')
    elif organic:
        organic_confirmed=False
        organic_note='有機土暫定分類：尚未提供烘乾前後 LL 比值，OL/OH 僅為待確認候選，不應視為已確認分類。'
    else:
        organic_confirmed=False
        organic_note=''
    # Plasticity chart A-line and borderline CL-ML zone.
    aline=0.73*(ll-20.0)
    above_a = pi >= aline and pi > 0
    if ll < 50:
        if 4 <= pi <= 7 and above_a:
            fine_class = 'CL-ML'
        elif pi > 7 and above_a:
            fine_class = 'CL'
        else:
            fine_class = 'ML'
    else:
        fine_class = 'CH' if above_a else 'MH'
    if organic_confirmed:
        fine_class = 'OL' if ll < 50 else 'OH'
    elif organic and not organic_test_rejected:
        fine_class = ('OL' if ll < 50 else 'OH') + '（暫定）'
    cu=cc=None
    if peat:
        uscs='PT'
    elif p200 >= 50:
        uscs=fine_class
    else:
        gravel=100-p4
        sand=p4-p200
        major='G' if gravel > sand else 'S'
        grad_values=(d10,d30,d60)
        supplied_grad=sum(v is not None for v in grad_values)
        if supplied_grad not in (0,3):
            raise ValueError('D10、D30、D60 必須同時提供；若沒有完整粒徑曲線，請三者全部留空')
        if supplied_grad==0:
            cu=cc=None; well=None
        else:
            d10,d30,d60=(_finite('D10',d10),_finite('D30',d30),_finite('D60',d60))
            if not (0<d10<=d30<=d60): raise ValueError('粒徑必須符合 0 < D10 ≤ D30 ≤ D60')
            cu=d60/d10; cc=d30*d30/(d10*d60)
            well=(cu>=4 if major=='G' else cu>=6) and 1<=cc<=3
        if p200 < 5:
            if well is None: uscs=major+'? (缺少 D10/D30/D60)'
            else: uscs=major+('W' if well else 'P')
        elif p200 > 12:
            if 4 <= pi <= 7 and above_a:
                uscs=major+'C-'+major+'M'
            else:
                uscs=major+('C' if pi>7 and above_a else 'M')
        else:
            if well is None: uscs=major+'?-(C/M) (缺少級配資料)'
            else:
                fines_symbol='C' if (above_a and (pi>=4)) else 'M'
                uscs=major+('W' if well else 'P')+'-'+major+fines_symbol
    # AASHTO M 145 §3.2: round reported fractional limits to whole numbers
    # before applying the classification boundaries (half-up, not Python bankers' rounding).
    def _round_whole(x): return int(math.floor(float(x)+0.5))
    Fg=_round_whole(p200); P40g=_round_whole(p40); P10g=_round_whole(p10)
    LLg=_round_whole(ll); PIg=_round_whole(pi)
    # Re-evaluate the AASHTO group using the rounded test values.
    if peat:
        aashto='A-8'
    elif Fg <= 35:
        if Fg <= 10 and P40g >= 51 and np_flag:
            aashto='A-3'
        elif Fg <= 15 and P10g <= 50 and P40g <= 30 and PIg <= 6:
            aashto='A-1-a'
        elif Fg <= 25 and P40g <= 50 and PIg <= 6:
            aashto='A-1-b'
        else:
            if PIg <= 10: aashto='A-2-4' if LLg<=40 else 'A-2-5'
            else: aashto='A-2-6' if LLg<=40 else 'A-2-7'
    else:
        if LLg<=40 and PIg<=10: aashto='A-4'
        elif LLg>40 and PIg<=10: aashto='A-5'
        elif LLg<=40: aashto='A-6'
        else: aashto='A-7-5' if PIg <= LLg-30 else 'A-7-6'
    if aashto in ('A-1-a','A-1-b','A-3','A-8'):
        gi=0.0
    else:
        # Keep the signed partial terms: AASHTO's own A-4 example has a
        # negative PI contribution that offsets part of the LL contribution.
        f1=(Fg-35)*(0.2+0.005*(LLg-40))
        f2=0.01*(Fg-15)*(PIg-10)
        if aashto in ('A-2-6','A-2-7'):
            raw_gi=f2
        else:
            raw_gi=f1+f2
        # AASHTO M 145 §6.1.1: negative total GI is reported as zero;
        # §6.1.2: report to nearest whole number. The standard does not cap GI at 20.
        gi=max(0,int(math.floor(raw_gi+0.5)))
    return {'USCS':uscs,'AASHTO':aashto,'GI':int(gi),'PI':pi,'Cu':cu,'Cc':cc,
            'gravel_pct':100-p4,'sand_pct':p4-p200,'fines_pct':p200,
            'organic_note':organic_note,'A_line_PI':aline,'peat':bool(peat)}


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
    if n<0 or er<=0 or sv<=0 or cb_in<=0 or cs<=0 or cap<1: raise ValueError('SPT 輸入值超出合理範圍')
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
        flag=row.get('Refusal',False)
        is_refusal=(flag is True or str(flag).strip().lower() in ('1','1.0','true','yes','y','refusal','拒錘','部分貫入'))
        if is_refusal:
            out.append({**clean,'N60':None,'CE':None,'CB':None,'CS':None,'CR':None,
                'CN_raw':None,'CN':None,'N1_60':None,'N1_60_dilatancy':None,
                'N1_60_final':None,'soil_behavior':soil_behavior,
                'dilatancy_applied':False,'Correction_status':'拒錘／部分貫入：不可套用一般 N 值修正'})
            continue
        r=spt_correct(row['N'],energy_ratio_pct,borehole_factor,sampler_factor,rod_length_m,
                      row['Effective_Stress_kPa'],cn_method,cn_cap,
                      soil_behavior=soil_behavior,apply_dilatancy=apply_dilatancy)
        out.append({**clean,**r,'Correction_status':'已完成一般 N 值修正'})
    out.sort(key=lambda x:x['Depth_m'])
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
    if c<0 or not 0<=phi_deg<=50 or gamma<=0 or gsub<=0 or gsub>gamma or B<=0 or L<B or Df<0 or Dw<0 or FS<=1 or not 0<=beta<90:
        raise ValueError('承載力輸入值不合理；需 γ′≤γ、矩形基礎 L≥B、FS>1，且 ϕ≤50°')
    if eB<0 or eL<0: raise ValueError('偏心距不可為負值；請輸入偏心距絕對值')
    Be=B-2*eB; Le=L-2*eL
    if Be<=0 or Le<=0 or Le<Be: raise ValueError('有效基礎尺寸必須為正，且有效長邊 L′ ≥ 有效短邊 B′')
    th=theory.lower()
    if not any(x in th for x in ('terzaghi','meyerhof','hansen','vesic')): raise ValueError('不支援的理論')
    if 'terzaghi' in th and failure_mode not in ('general','local'): raise ValueError('Terzaghi 破壞模式須為 general 或 local')
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
        dc=1+0.2*math.sqrt(kp)*Df/Be; dq=1+0.1*math.sqrt(kp)*Df/Be; dg=1.0
        ic=iq=(1-beta/90.0)**2
        ig=(1-beta/phi_deg)**2 if phi_deg>0 and beta<phi_deg else (0.0 if beta>=phi_deg else 1.0)
    else: # Hansen shape/depth, shared by Vesic
        sc=1+(Nq/Nc)*br if phi_deg>0 else 1+0.2*br
        sq=1+br*sinp
        sg=1-0.4*br
        ratio=Df/Be
        ang=ratio if ratio<=1 else math.atan(ratio)
        dq=1+2*tanp*(1-sinp)**2*ang
        dc=dq-(1-dq)/(Nc*tanp) if phi_deg>0 else 1+0.4*ang
        dg=1.0
        H=0.0 if horizontal_load is None else _finite('水平載重',horizontal_load)
        V=1.0 if vertical_load is None else _finite('垂直載重',vertical_load)
        A=Be*Le if area is None else _finite('基礎面積',area)
        if load_direction not in ('parallel_B','parallel_L'): raise ValueError('未知水平力方向')
        ar=_finite('基底黏著比',adhesion_ratio)
        if H<0 or V<=0 or A<=0 or not 0<=ar<=1: raise ValueError('水平載重需≥0、垂直載重及面積需>0，基底黏著比須在 [0,1]')
        ca=c*ar
        if phi_deg>0:
            denom=V+A*ca/math.tan(ph)
        else:
            denom=V
        hratio=H/denom
        if hratio>=1.0: raise ValueError('水平載重已達或超過此公式的可用垂直／基底抗力；請核對 H、V、基底面積及 ca/c')
        theta_load=math.degrees(math.atan2(H,V))
        if 'vesic' in th:
            m=(2+Be/Le)/(1+Be/Le) if load_direction=='parallel_B' else (2+Le/Be)/(1+Le/Be)
            iq=(1-hratio)**m; ig=(1-hratio)**(m+1)
            ic=iq-(1-iq)/(Nq-1) if phi_deg>0 else max(0.0,1.0-m*H/(A*ca*Nc)) if ca>0 else (1.0 if H==0 else 0.0)
        else:
            iq=(1-0.5*hratio)**5
            ig=(1-(0.7-theta_load/450.0)*hratio)**5
            ic=iq-(1-iq)/(Nq-1) if phi_deg>0 else (0.5+0.5*math.sqrt(max(0.0,1.0-H/(A*ca))) if ca>0 else (1.0 if H==0 else 0.0))
    # Effective surcharge at foundation base and gamma in N-gamma term.
    q=gamma*min(Df,Dw)+gsub*max(0.0,Df-Dw)
    if Dw<=Df: gamma_eff=gsub
    elif Dw<Df+Be: gamma_eff=gsub+(gamma-gsub)*(Dw-Df)/Be
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
            'qu_gross':qu,'qu_net':qnet,'qu_gross_over_FS':qu/FS,'qa_net':qallow_net,'qa_gross':qallow_gross,
            'FS':FS,'B_effective':Be,'L_effective':Le,'eccentricity_B':eB,'eccentricity_L':eL,'c_used':c_use,'phi_used':phi_use,'failure_mode':failure_mode,'adhesion_ratio':adhesion_ratio,'limitations':'水平基底、水平地表、淺基礎靜力分析；未含斜坡地表、基底傾斜、地震及分層地盤。偏心載重以 B′=B−2eB、L′=L−2eL 有效尺寸處理；Terzaghi 模式不接受偏心距。水平力僅納入 Hansen／Vesic 承載力傾斜係數，未計算基底滑動安全係數、被動土壓或整體穩定；本模組亦不取代沉陷檢核。'}


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
            'sigma_cm_mpa':sig_cm,'sigma_c_mass_mpa':sigc_mass,
            'sigma3_max_mpa':sig3max,'sigma3n':sig3n,
            'c_equiv_mpa':c_mpa,'c_equiv_kpa':c_mpa*1000,
            'phi_equiv_deg':phi,'Em_gpa':em_gpa,
            'application':application}


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