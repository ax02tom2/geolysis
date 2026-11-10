"""Auditable calculation functions for geolysis modules 2-5.
Units: kPa, kN/m3, m, mm unless stated otherwise.
These are screening/design-assistance calculations, not code certification.
"""
from __future__ import annotations
import math


def _finite(name, value):
    try:
        v=float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 必須為數值") from None
    if not math.isfinite(v): raise ValueError(f"{name} 必須為有限數值")
    return v


def _pct(name, v):
    v=_finite(name,v)
    if not 0 <= v <= 100: raise ValueError(f"{name} 必須介於 0–100%")
    return v


def classify_uscs_aashto(*, p4=None, p10=None, p40=None, p200=None, ll=None, pl=None, np_flag=False,
                           d10=None, d30=None, d60=None, organic=False,
                           ll_oven_dried=None, peat=False):
    """USCS (ASTM D2487 logic) and AASHTO M 145 screening classification.

    Highly organic peat is identified visually and is not forced through
    particle-size or Atterberg-limit calculations.
    """
    if peat:
        return {
            'USCS':'PT','AASHTO':'A-8','GI':0,'PI':None,'Cu':None,'Cc':None,
            'gravel_pct':None,'sand_pct':None,'fines_pct':None,
            'organic_note':'依現場辨識為泥炭／高度有機土；PT 與 A-8 屬視覺辨識分類，不以篩分析或液塑限數值判定。',
            'A_line_PI':None,'peat':True
        }
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
    fine_class_chart=fine_class
    if p200 >= 50:
        if organic_confirmed:
            fine_class = 'OL' if ll < 50 else 'OH'
        elif organic and not organic_test_rejected:
            fine_class = ('OL' if ll < 50 else 'OH') + '（暫定）'
    elif organic_confirmed:
        organic_note += ' 粗粒土含有機細料；粗粒土符號仍依細料塑性圖判定，組名須加註「含有機細料」。'
    elif organic and not organic_test_rejected:
        organic_note += ' 粗粒土疑似含有機細料；符號暫依細料塑性圖判定，須補烘乾比值試驗並加註有機細料。'
    cu=cc=None
    gravel=100-p4
    sand=p4-p200
    major='G' if gravel > sand else 'S'
    if p200 >= 50:
        # D10/D30/D60 are not classification criteria for fine-grained soils.
        cu=cc=None
        well=None
        uscs=fine_class
    else:
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
            if fine_class_chart=='CL-ML':
                uscs=major+'C-'+major+'M'
            else:
                uscs=major+('C' if fine_class_chart in ('CL','CH') else 'M')
        else:
            if well is None: uscs=major+'?-(C/M) (缺少級配資料)'
            else:
                # ASTM D2487: 5–12% fines require a dual symbol. If fines plot
                # in CL-ML, the second symbol is C (e.g. SP-SC).
                fines_symbol='C' if fine_class_chart in ('CL','CH','CL-ML') else 'M'
                uscs=major+('W' if well else 'P')+'-'+major+fines_symbol
    def _round_whole(x): return int(math.floor(float(x)+0.5))
    Fg=_round_whole(p200); P40g=_round_whole(p40); P10g=_round_whole(p10)
    LLg=_round_whole(ll); PIg=_round_whole(pi)
    if Fg <= 35:
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
    if aashto in ('A-1-a','A-1-b','A-3'):
        gi=0
    else:
        f1=(Fg-35)*(0.2+0.005*(LLg-40))
        f2=0.01*(Fg-15)*(PIg-10)
        raw_gi=f2 if aashto in ('A-2-6','A-2-7') else f1+f2
        gi=max(0,int(math.floor(raw_gi+0.5)))
    return {'USCS':uscs,'AASHTO':aashto,'GI':int(gi),'PI':pi,'Cu':cu,'Cc':cc,
            'gravel_pct':100-p4,'sand_pct':p4-p200,'fines_pct':p200,
            'organic_note':organic_note,'A_line_PI':aline,'peat':False}

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
    n_n=N*(60.0/energy_percent)
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
                     water_depth, gamma_below=None, fs=3.0, load_angle=0.0, horizontal_load=None,
                     vertical_load=None, area=None, failure_mode='general', load_direction='parallel_B', adhesion_ratio=0.6, eccentricity_B=0.0, eccentricity_L=0.0):
    """Shallow footing ultimate bearing capacity using consistent theory families.
    Strip/rectangular footing; level base/ground only. Base/ground slope and seismic
    effects intentionally excluded rather than approximated with wrong factors.
    """
    if gamma_below is None:
        gamma_below=gamma_moist
    vals={'c':c_kpa,'phi':phi_deg,'gamma':gamma_moist,'gamma_sub':gamma_sub,'gamma_below':gamma_below,'B':B,'L':L,'Df':Df,'Dw':water_depth,'FS':fs,'beta':load_angle,'eB':eccentricity_B,'eL':eccentricity_L}
    v={k:_finite(k,x) for k,x in vals.items()}
    c,phi_deg,gamma,gsub,gbelow,B,L,Df,Dw,FS,beta,eB,eL=[v[k] for k in ('c','phi','gamma','gamma_sub','gamma_below','B','L','Df','Dw','FS','beta','eB','eL')]
    if c<0 or not 0<=phi_deg<=50 or gamma<=0 or gsub<=0 or gbelow<=0 or gsub>gbelow or B<=0 or L<B or Df<0 or Dw<0 or FS<=1 or not 0<=beta<90:
        raise ValueError('承載力輸入值不合理；需 γ′≤基礎底下總單位重、矩形基礎 L≥B、FS>1，且 ϕ≤50°')
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
        sc=1+0.2*kp*br
        if phi_deg == 0:
            # USACE EM 1110-1-1905 (2025), Table 5-4: undrained
            # q-term factors are all unity; Meyerhof dc is capped at 1.5.
            sq=sg=1.0
            dc=min(1+0.2*Df/Be,1.5)
            dq=dg=1.0
            # Table 5-4 undrained Meyerhof inclination: ic=1-1.3 H/V.
            # beta is the entered load angle, so H/V=tan(beta).
            ic=1-1.3*math.tan(math.radians(beta))
            if ic<=0:
                raise ValueError('Meyerhof 不排水載重傾斜係數已≤0；請降低載重傾角或改用有依據的分析方法')
            iq=ig=1.0
        else:
            if phi_deg<=10.0:
                # EM 1110-1-1905 (1992), Table 4-3: interpolate Meyerhof
                # shape/depth factors linearly from phi=0 to phi=10 degrees.
                kp10=math.tan(math.radians(45)+math.radians(10)/2)**2
                sq=sg=1.0+0.1*kp10*br*(phi_deg/10.0)
                dc0=min(1.0+0.2*Df/B,1.5)
                dc10=1.0+0.2*math.sqrt(kp10)*Df/B
                dq10=1.0+0.1*math.sqrt(kp10)*Df/B
                dc=dc0+(dc10-dc0)*(phi_deg/10.0)
                dq=dg=1.0+(dq10-1.0)*(phi_deg/10.0)
            else:
                sq=1+0.1*kp*br; sg=sq
                dc=1+0.2*math.sqrt(kp)*Df/B
                dq=1+0.1*math.sqrt(kp)*Df/B
                dg=1+0.1*math.sqrt(kp)*Df/B
            ic=iq=(1-beta/90.0)**2
            ig=(1-beta/phi_deg)**2 if beta<phi_deg else (0.0 if beta>=phi_deg else 1.0)
    else: # Hansen shape/depth, shared by Vesic
        sc=1+(Nq/Nc)*br if phi_deg>0 else 1+0.2*br
        # USACE 1992 Tables 4-5 and 4-6: both Hansen and Vesic use
        # 1 + (B'/W') tan(phi) for the surcharge shape factor.
        sq=1+br*tanp
        sg=max(0.6,1-0.4*br)
        # USACE EM 1110-1-1905 (1992), Tables 4-5/4-6 define
        # k=D/B using the actual footing width, not eccentric effective B'.
        ratio=Df/B
        ang=ratio if ratio<=1 else math.atan(ratio)
        dq=1+2*tanp*(1-sinp)**2*ang
        # Classical Hansen (1970) / Vesic (1973) depth factors:
        # phi=0 uses dc=1+0.4k for both theories (USACE 1992 Tables 4-5/4-6).
        # The 2025 AASHTO/FHWA Vesic-based design family conservatively
        # omits phi=0 depth correction; that is a different factor system.
        if phi_deg>0:
            dc=dq-(1-dq)/(Nc*tanp)
        else:
            dc=1+0.4*ang
        dg=1.0
        H=0.0 if horizontal_load is None else _finite('水平載重',horizontal_load)
        V=1.0 if vertical_load is None else _finite('垂直載重',vertical_load)
        A=Be*Le if area is None else _finite('基礎面積',area)
        if load_direction not in ('parallel_B','parallel_L'): raise ValueError('未知水平力方向')
        ar=_finite('基底黏著比',adhesion_ratio)
        if H<0 or V<=0 or A<=0 or not 0<=ar<=1: raise ValueError('水平載重需≥0、垂直載重及面積需>0，基底黏著比須在 [0,1]')
        ca=c*ar
        if 'vesic' in th:
            # Vesic's m uses the aspect ratio perpendicular to the
            # horizontal-load direction: parallel B -> L/B; parallel L -> B/L.
            # Classical Vesic (USACE 1992 Table 4-6): use B'/L' when
            # H is parallel to B, and L'/B' when H is parallel to L.
            m=(2+Be/Le)/(1+Be/Le) if load_direction=='parallel_B' else (2+Le/Be)/(1+Le/Be)
            if phi_deg>0:
                # Classical Vesic (USACE 1992 Table 4-6) uses footing
                # interface adhesion ca, consistent with the Hansen branch.
                denom=V+A*ca/math.tan(ph)
                hratio=H/denom
                if hratio>=1.0: raise ValueError('水平載重已達或超過 Vesic 公式可用抗力；請核對 H、V、基礎面積及基底黏著 ca')
                iq=(1-hratio)**m; ig=(1-hratio)**(m+1)
                ic=iq-(1-iq)/(Nq-1)
            else:
                # Undrained Table 5-4: q-term factors remain unity;
                # Vesic inclination acts on the undrained cohesion term.
                iq=ig=1.0
                ic=1.0-m*H/(A*ca*Nc) if ca>0 else (1.0 if H==0 else 0.0)
                if ic<=0:
                    raise ValueError('Vesic 不排水水平載重傾斜係數已≤0；請核對 H、基底黏著 ca、基礎面積及方向')
        else:
            if phi_deg>0:
                denom=V+A*ca/math.tan(ph)
                hratio=H/denom
                if hratio>=1.0: raise ValueError('水平載重已達或超過 Hansen 公式可用抗力；請核對 H、V、基底面積及 ca/c')
                iq=(1-0.5*hratio)**5
                # Level ground is assumed; Hansen's 0.7 coefficient is
                # reduced only by ground slope beta, which is not modeled here.
                ig=(1-0.7*hratio)**5
                ic=iq-(1-iq)/(Nq-1)
            else:
                # Undrained q-term factors are unity; retain Hansen's
                # classical undrained cohesion inclination expression.
                iq=ig=1.0
                if ca>0:
                    h_adhesion_ratio=H/(A*ca)
                    if h_adhesion_ratio>1.0:
                        raise ValueError('Hansen 不排水水平載重已超過基底黏著抗力 ca·A；請核對 H、ca 及有效基礎面積')
                    ic=0.5+0.5*math.sqrt(1.0-h_adhesion_ratio)
                else:
                    if H>0:
                        raise ValueError('Hansen 不排水水平載重無基底黏著 ca 可提供抗力；請核對界面參數')
                    ic=1.0
    # Surcharge at footing base: drained analyses use effective stress;
    # undrained (phi=0) analyses use total stress, per USACE Table 5-1.
    # gamma_sub is submerged unit weight, so gamma_sat = gamma_sub + gamma_w.
    if phi_use == 0:
        q=gamma*min(Df,Dw)+(gsub+9.81)*max(0.0,Df-Dw)
    else:
        q=gamma*min(Df,Dw)+gsub*max(0.0,Df-Dw)
    # Classical groundwater correction over the shear-zone depth
    # H = B' tan(45 + phi/2), consistent with USACE 1992 Example 4-5.
    # gamma_below is the total unit weight beneath the footing; gamma_sub
    # is its submerged/effective unit weight.
    shear_zone_depth=Be*math.tan(math.radians(45+phi_use/2))
    if Dw<=Df: gamma_eff=gsub
    elif Dw<Df+shear_zone_depth:
        gamma_eff=gsub+(gbelow-gsub)*(Dw-Df)/shear_zone_depth
    else: gamma_eff=gbelow
    tc=c_use*Nc*sc*dc*ic
    tq=q*Nq*sq*dq*iq
    tg=0.5*gamma_eff*Be*Ng*sg*dg*ig
    qu=tc+tq+tg
    qnet=qu-q
    qallow_net=qnet/FS
    qallow_gross=qallow_net+q
    return {'theory':theory,'Nc':Nc,'Nq':Nq,'Ngamma':Ng,'sc':sc,'sq':sq,'sg':sg,
            'dc':dc,'dq':dq,'dg':dg,'ic':ic,'iq':iq,'ig':ig,'q_surcharge':q,
            'gamma_effective':gamma_eff,'gamma_below_total':gbelow,'shear_zone_depth':shear_zone_depth,'term_c':tc,'term_q':tq,'term_gamma':tg,
            'qu_gross':qu,'qu_net':qnet,'qu_gross_over_FS':qu/FS,'qa_gross_direct_FS':qu/FS,'qa_net':qallow_net,'qa_gross':qallow_gross,
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



def _terzaghi_time_factor_from_degree(degree_percent):
    """Average 1-D consolidation degree U (%) to Terzaghi time factor Tv."""
    U=_pct('平均固結度 U',degree_percent)/100.0
    if U>=1.0: raise ValueError('平均固結度 U 必須小於 100%；理論上 100% 需無限時間')
    if U<=0: return 0.0
    lo,hi=0.0,10.0
    for _ in range(90):
        mid=(lo+hi)/2.0
        u=1.0
        for m in range(100):
            odd=2*m+1
            u-=8.0/(math.pi**2*odd**2)*math.exp(-(odd**2*math.pi**2*mid)/4.0)
        if u<U: lo=mid
        else: hi=mid
    return (lo+hi)/2.0


def _terzaghi_degree_from_time_factor(tv):
    """Invert Terzaghi's one-dimensional average degree-of-consolidation series."""
    tv=_finite('時間因子 Tv',tv)
    if tv<0: raise ValueError('時間因子 Tv 不可為負')
    if tv==0: return 0.0
    if tv>=10: return 100.0
    u=1.0
    for m in range(100):
        odd=2*m+1
        u-=8.0/(math.pi**2*odd**2)*math.exp(-(odd**2*math.pi**2*tv)/4.0)
    return min(100.0,max(0.0,u*100.0))


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

def bearing_capacity_slope_base_corrections(*, base_result, c_kpa, phi_deg,
        base_inclination_deg=0.0, ground_inclination_deg=0.0,
        slope_distance_m=0.0):
    """Apply USACE EM 1110-1-1905 (2025) Table 5-3/5-4 base and ground
    inclination factors to a previously calculated Meyerhof-based result.
    Ground slope is assumed to fall away from the footing. The adjacent-slope
    global stability check is separate and mandatory.
    """
    c=_finite('c／Su',c_kpa); phi=_finite('phi',phi_deg)
    ab=_finite('基底傾角',base_inclination_deg)
    ag=_finite('地表坡角',ground_inclination_deg)
    dg=_finite('基礎至坡頂距離',slope_distance_m)
    if c<0 or not 0<=phi<=50 or not 0<=ab<60 or not 0<=ag<45 or dg<0:
        raise ValueError('斜坡／基底輸入超出適用範圍：0≤基底角<60°、0≤地表坡角<45°、距離不可為負')
    B=base_result['B_effective']; L=base_result['L_effective']
    Nc=base_result['Nc']; q=base_result['q_surcharge']
    if phi>0:
        tp=math.tan(math.radians(phi))
        base_term=1-(ab/57.0)*tp
        if base_term<0:
            raise ValueError('基底傾角超出此修正公式的適用範圍；請降低 αb 或改用專用分析')
        bq=base_term**2
        bgamma=bq
        bc=bq-(1-bq)/(Nc*tp) if tp>0 else 1.0
        if bc<0: raise ValueError('基底傾角使凝聚力修正係數小於零；此幾何不適用本方法')
        gq0=(1-math.tan(math.radians(ag)))**2
        gc0=gq0-(1-gq0)/(Nc*tp)
        ggamma0=gq0
        if min(gq0,gc0,ggamma0)<0:
            raise ValueError('地表坡角使地表傾斜修正係數小於零；請改用專用斜坡承載力分析')
        # USACE Table 5-3: drained factors recover linearly over 5B.
        recovery=min(1.0,dg/(5.0*B))
        gq=min(1.0,gq0+(1-gq0)*recovery)
        gc=min(1.0,gc0+(1-gc0)*recovery)
        ggamma=min(1.0,ggamma0+(1-ggamma0)*recovery)
    else:
        # USACE Table 5-4 undrained corrections.
        bq=bgamma=1.0
        bc=max(0.0,1-ab/147.3)
        gq=ggamma=1.0
        gc0=max(0.0,1-ag/147.3)
        gc=min(1.0,gc0+(1-gc0)*min(1.0,dg/(2.0*B)))
    # The USACE figure defines surcharge on a sloping surface as q0=γDf cos(ag).
    q_slope=q*math.cos(math.radians(ag))
    tc=base_result['term_c']*bc*gc
    tq=q_slope*base_result['Nq']*base_result['sq']*base_result['dq']*base_result['iq']*bq*gq
    tg=base_result['term_gamma']*bgamma*ggamma
    qu=tc+tq+tg
    qnet=qu-q_slope
    fs=base_result['FS']
    qa_net=qnet/fs
    qa_gross=qa_net+q_slope
    return {**base_result,'base_factor_c':bc,'base_factor_q':bq,'base_factor_gamma':bgamma,
        'ground_factor_c':gc,'ground_factor_q':gq,'ground_factor_gamma':ggamma,
        'ground_surcharge_kpa':q_slope,'term_c':tc,'term_q':tq,'term_gamma':tg,
        'qu_gross':qu,'qu_net':qnet,'qa_net':qa_net,'qa_gross':qa_gross,
        'qa_gross_direct_FS':qu/fs,
        'limitations':base_result['limitations']+'；已套用 USACE 2025 表 5-3／5-4 基底與地表傾斜係數。地表坡體整體穩定仍須另行驗算。'}


def layered_bearing_capacity_punching(*, q_ult_strong_kpa, q_ult_weak_kpa,
        strong_layer_thickness_m, footing_width_m, footing_length_m,
        footing_type='isolated'):
    """USACE EM 1110-1-1905 (2025) Eqs. 5-17/5-18, 2V:1H load spreading.
    Input q_ult values are gross ultimate pressures for each homogeneous layer.
    """
    q1=_finite('上層極限承載力',q_ult_strong_kpa)
    q2=_finite('下層極限承載力',q_ult_weak_kpa)
    hs=_finite('上層厚度',strong_layer_thickness_m)
    B=_finite('基礎寬度',footing_width_m)
    L=_finite('基礎長度',footing_length_m)
    if min(q1,q2,hs,B,L)<=0 or L<B:
        raise ValueError('兩層極限承載力、厚度及基礎尺寸必須為正，且 L≥B')
    if footing_type not in ('isolated','continuous'):
        raise ValueError('基礎型式須為 isolated 或 continuous')
    if footing_type=='isolated':
        spread=((B+hs)*(L+hs))/(B*L)
    else:
        spread=(B+hs)/B
    q_punch=spread*q2
    q=min(q1,q_punch)
    mode='上層一般承載力控制' if q1<=q_punch else '強上層穿刺至弱下層控制'
    return {'qult_kpa':q,'qult_strong_kpa':q1,'qult_weak_kpa':q2,
        'load_spread_factor':spread,'punching_capacity_kpa':q_punch,
        'controlling_mode':mode,'strong_layer_thickness_m':hs,
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-17/5-18; 2V:1H',
        'limitations':'適用強上層覆蓋弱下層的簡化穿刺檢核；弱層需位於相應承載力剪力區範圍（方／矩形約 0.5B–2B，條形約 1B–4B）。兩層 q_ult 須採相同載重、排水條件及修正係數體系；不取代多層有限元素或完整破壞機制分析。'}


def seismic_bearing_capacity_pseudostatic(*, vertical_load_kN, horizontal_load_kN,
        footing_area_m2, kh, kv=0.0):
    """Pseudo-static foundation inertia load envelope, not a seismic bearing
    resistance equation. Returns equivalent actions for use with static
    bearing/sliding checks; soil inertia, cyclic strength degradation,
    liquefaction and seismic settlement are not included.
    """
    V=_finite('靜態垂直力',vertical_load_kN); H=_finite('靜態水平力',horizontal_load_kN)
    A=_finite('基礎面積',footing_area_m2); khv=_finite('水平地震係數 kh',kh)
    kvv=_finite('垂直地震係數 kv',kv)
    if V<=0 or A<=0 or H<0 or not 0<=khv<=1 or not -0.5<=kvv<=0.5:
        raise ValueError('地震分析輸入超出範圍：V、面積須正，H≥0，0≤kh≤1，-0.5≤kv≤0.5')
    cases=[]
    for sign in (-1,1):
        ve=V*(1+sign*kvv)
        he=H+khv*V
        cases.append({'vertical_load_kN':ve,'horizontal_load_kN':he,
            'average_contact_pressure_kpa':ve/A,
            'load_angle_deg':math.degrees(math.atan2(he,ve)),
            'vertical_sign':'向下增加' if sign==1 else '向下減少'})
    return {'cases':cases,'governing_vertical_load_kN':min(x['vertical_load_kN'] for x in cases),
        'governing_horizontal_load_kN':max(x['horizontal_load_kN'] for x in cases),
        'method':'Pseudo-static inertial action envelope (kh·V, kv·V)',
        'limitations':'僅將結構／基礎慣性作用轉為等效靜力載重包絡；不得視為完整地震承載力公式。尚未包含土體慣性力、地震期間強度折減、孔隙水壓累積、液化、震陷、側向擴展與地震邊坡穩定；須依所在地耐震規範取得 kh、kv 及載重組合。'}


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


def seismic_bearing_capacity_residual_pore_pressure(*, footing_type,
        effective_unit_weight_kn_m3, effective_width_m, bearing_factor_ngamma,
        residual_excess_pore_pressure_ratio, shape_depth_inclination_factor=1.0):
    """USACE EM 1110-1-1905 (2025) Eqs. 9-3/9-4 for sand-like soil with
    earthquake-induced excess pore pressure affecting the full shear zone.
    The surcharge term is omitted as specified for potential punching failure.
    """
    gamma=_finite('剪力區有效單位重',effective_unit_weight_kn_m3)
    B=_finite('有效基礎寬度',effective_width_m)
    Ng=_finite('Nγ',bearing_factor_ngamma)
    ru=_finite('殘餘超額孔隙水壓比 ru',residual_excess_pore_pressure_ratio)
    corr=_finite('其他修正係數乘積',shape_depth_inclination_factor)
    if gamma<=0 or B<=0 or Ng<0 or not 0<=ru<1 or corr<=0:
        raise ValueError('地震承載力輸入不合理：γ、B須正；0≤ru<1；修正係數須在 (0,1]')
    if footing_type not in ('strip','spread'):
        raise ValueError('基礎型式須為 strip 或 spread')
    coeff=0.5 if footing_type=='strip' else 0.4
    q=coeff*(1-ru)*gamma*B*Ng*corr
    return {'qu_seismic_kpa':q,'ru':ru,'pore_pressure_resistance_factor':1-ru,
        'base_coefficient':coeff,'gamma_effective_kn_m3':gamma,'B_effective_m':B,
        'Ngamma':Ng,'other_correction_product':corr,
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 9-3/9-4 (Day 2012)',
        'limitations':'適用砂狀土且地震超額孔隙水壓影響完整承載力剪力區之情境；依手冊移除覆土 Nq 項，並以 (1−ru) 折減 Nγ 項。ru 應依 FSliq／孔壓評估取得，不可任意假設。若土層可液化、邊際液化或顯著強度損失，USACE 原則上不建議使用淺基礎；此式是補充評估，不代表可接受液化場址。未含分層穿刺、側向擴展與地震沉陷。'}


def layered_bearing_capacity_profile(*, layers, footing_width_m, footing_length_m,
        footing_depth_m, water_depth_m, fs=3.0, footing_type='isolated',
        eccentricity_B_m=0.0, eccentricity_L_m=0.0):
    """Evaluate a layered profile by checking each weaker underlying stratum
    for 2V:1H punching through the overlying cover, per USACE 2025 Eqs. 5-17/5-18.
    Each layer has thickness_m, c_kpa, phi_deg, gamma_below_kn_m3.
    The top layer also supplies gamma_moist_kn_m3 and gamma_sub_kn_m3.
    """
    if not isinstance(layers,(list,tuple)) or len(layers)<2:
        raise ValueError('至少輸入兩層土壤')
    top=layers[0]
    required=('thickness_m','c_kpa','phi_deg','gamma_moist_kn_m3','gamma_sub_kn_m3','gamma_below_kn_m3')
    for k in required:
        if k not in top: raise ValueError(f'第 1 層缺少 {k}')
    gamma_top=_finite('上層天然單位重',top['gamma_moist_kn_m3'])
    gamma_sub_top=_finite('上層浮／飽和單位重',top['gamma_sub_kn_m3'])
    if gamma_top<=0 or gamma_sub_top<=0: raise ValueError('上層單位重須為正')
    B=_finite('基礎寬度',footing_width_m); L=_finite('基礎長度',footing_length_m)
    Df=_finite('基礎埋深',footing_depth_m); Dw=_finite('地下水深度',water_depth_m)
    if B<=0 or L<B or Df<0 or Dw<0: raise ValueError('基礎尺寸或深度不合理')
    if footing_type not in ('isolated','continuous'): raise ValueError('基礎型式不支援')
    results=[]; cumulative=0.0
    for i,layer in enumerate(layers,1):
        for k in ('thickness_m','c_kpa','phi_deg','gamma_below_kn_m3'):
            if k not in layer: raise ValueError(f'第 {i} 層缺少 {k}')
        thickness=_finite(f'第{i}層厚度',layer['thickness_m'])
        if thickness<=0: raise ValueError('各層厚度須大於零')
        c=_finite(f'第{i}層 c／Su',layer['c_kpa'])
        phi=_finite(f'第{i}層 φ',layer['phi_deg'])
        gb=_finite(f'第{i}層剪力區單位重',layer['gamma_below_kn_m3'])
        r=bearing_capacity(theory='Meyerhof',c_kpa=c,phi_deg=phi,
            gamma_moist=gamma_top,gamma_sub=gamma_sub_top,gamma_below=gb,
            B=B,L=L,Df=Df,water_depth=Dw,fs=fs,
            eccentricity_B=eccentricity_B_m,eccentricity_L=eccentricity_L_m)
        results.append({'layer':i,'thickness_m':thickness,'top_depth_m':cumulative,
            'c_kpa':c,'phi_deg':phi,'gamma_below_kn_m3':gb,'qult_kpa':r['qu_gross']})
        cumulative+=thickness
    B_eff=max(1e-9,B-2*eccentricity_B_m); L_eff=max(1e-9,L-2*eccentricity_L_m)
    candidates=[{'mode':'上層一般承載力','controlling_layer':1,
        'capacity_kpa':results[0]['qult_kpa'],'spread_factor':1.0}]
    # USACE 2025 §5-5a(1)-(2): weak strata within the near shear zone
    # (approximately 0.5B for isolated footings) are checked directly;
    # punch-through is checked from 0.5B to 2B (or 1B to 4B for strips).
    lower_punch_depth=(0.5*B if footing_type=='isolated' else 1.0*B)
    upper_bound=(2.0*B if footing_type=='isolated' else 4.0*B)
    unchecked_deep_layers=[]
    for idx,item in enumerate(results[1:],start=1):
        Hs=item['top_depth_m']
        cover_capacity=min(x['qult_kpa'] for x in results[:idx])
        if item['qult_kpa']>=cover_capacity:
            continue
        if Hs<lower_punch_depth:
            candidates.append({'mode':'剪力區弱層控制','controlling_layer':item['layer'],
                'capacity_kpa':item['qult_kpa'],'spread_factor':1.0,
                'underlying_layer_qult_kpa':item['qult_kpa'],
                'weak_layer_top_depth_m':Hs})
        elif Hs<=upper_bound:
            spread=((B_eff+Hs)*(L_eff+Hs)/(B*L)
                    if footing_type=='isolated' else (B_eff+Hs)/B_eff)
            candidates.append({'mode':'下層穿刺控制','controlling_layer':item['layer'],
                'capacity_kpa':min(cover_capacity,spread*item['qult_kpa']),
                'spread_factor':spread,'cover_capacity_kpa':cover_capacity,
                'underlying_layer_qult_kpa':item['qult_kpa'],'strong_cover_thickness_m':Hs})
        else:
            unchecked_deep_layers.append(item['layer'])
    control=min(candidates,key=lambda x:x['capacity_kpa'])
    warning=('以下層位超出 USACE 穿刺檢核深度範圍，未套用 2V:1H 穿刺式：'
             +', '.join(map(str,unchecked_deep_layers))+'。' if unchecked_deep_layers else None)
    return {'qult_kpa':control['capacity_kpa'],'controlling_mode':control['mode'],
        'controlling_layer':control['controlling_layer'],'layers':results,
        'candidates':candidates,'unchecked_deep_layers':unchecked_deep_layers,
        'warning':warning,'method':'USACE EM 1110-1-1905 (2025), §5-5a(1)-(2), Eqs. 5-17/5-18',
        'limitations':'以 Meyerhof-based 單層承載力分別計算各層；近基礎剪力區內弱層直接作控制候選，規定深度範圍內強上層覆蓋弱下層才採 2V:1H 穿刺檢核。多層上覆土以其中最低承載力作保守上覆層控制值。假設水平分層、各層參數均質且基礎載重／排水條件一致。未涵蓋斜交層面、軟弱夾層側向擠出、任意破壞面與有限元素分析。'}


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
