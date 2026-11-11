"""bearing calculation functions."""
from __future__ import annotations
import math
from ._common import _finite

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
                     vertical_load=None, area=None, failure_mode='general', load_direction='parallel_B', adhesion_ratio=0.6, eccentricity_B=0.0, eccentricity_L=0.0, footing_type='isolated'):
    """Shallow footing ultimate bearing capacity using consistent theory families.
    Strip/rectangular footing; level base/ground only. Base/ground slope and seismic
    effects intentionally excluded rather than approximated with wrong factors.
    """
    if gamma_below is None:
        gamma_below=gamma_moist
    vals={'c':c_kpa,'phi':phi_deg,'gamma':gamma_moist,'gamma_sub':gamma_sub,'gamma_below':gamma_below,'B':B,'L':L,'Df':Df,'Dw':water_depth,'FS':fs,'beta':load_angle,'eB':eccentricity_B,'eL':eccentricity_L}
    v={k:_finite(k,x) for k,x in vals.items()}
    c,phi_deg,gamma,gsub,gbelow,B,L,Df,Dw,FS,beta,eB,eL=[v[k] for k in ('c','phi','gamma','gamma_sub','gamma_below','B','L','Df','Dw','FS','beta','eB','eL')]
    if c<0 or not 0<=phi_deg<=50 or gamma<=0 or gsub<=0 or gbelow<=0 or gsub>gbelow or B<=0 or L<=0 or (footing_type=='isolated' and L<B) or Df<0 or Dw<0 or FS<=1 or not 0<=beta<90 or footing_type not in ('isolated','continuous'):
        raise ValueError('承載力輸入值不合理；需 γ′≤基礎底下總單位重、矩形基礎 L≥B、FS>1，且 ϕ≤50°')
    if eB<0 or eL<0: raise ValueError('偏心距不可為負值；請輸入偏心距絕對值')
    if footing_type=='continuous' and eL>0: raise ValueError('連續條形基礎不支援沿條形長度方向的偏心距；請改用獨立／矩形基礎模型或專用分析')
    Be=B-2*eB; Le=L-2*eL
    if Be<=0 or Le<=0 or (footing_type=='isolated' and Le<Be): raise ValueError('有效基礎尺寸必須為正；獨立／矩形基礎另需 L′ ≥ B′')
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
    br=0.0 if footing_type=='continuous' else Be/Le
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
            'B_original':B,'L_original':L,'Df':Df,'water_depth':Dw,
            'dc':dc,'dq':dq,'dg':dg,'ic':ic,'iq':iq,'ig':ig,'q_surcharge':q,
            'gamma_effective':gamma_eff,'gamma_below_total':gbelow,'shear_zone_depth':shear_zone_depth,'term_c':tc,'term_q':tq,'term_gamma':tg,
            'qu_gross':qu,'qu_net':qnet,'qu_gross_over_FS':qu/FS,'qa_gross_direct_FS':qu/FS,'qa_net':qallow_net,'qa_gross':qallow_gross,
            'FS':FS,'B_effective':Be,'L_effective':Le,'footing_type':footing_type,'eccentricity_B':eB,'eccentricity_L':eL,'c_used':c_use,'phi_used':phi_use,'failure_mode':failure_mode,'adhesion_ratio':adhesion_ratio,'limitations':'水平基底、水平地表、淺基礎靜力分析；未含斜坡地表、基底傾斜、地震及分層地盤。偏心載重以 B′=B−2eB、L′=L−2eL 有效尺寸處理；Terzaghi 模式不接受偏心距。水平力僅納入 Hansen／Vesic 承載力傾斜係數，未計算基底滑動安全係數、被動土壓或整體穩定；本模組亦不取代沉陷檢核。'}


def bearing_pressure_safety_check(*, ultimate_bearing_kpa, vertical_load_kN,
        footing_width_m, footing_length_m, footing_depth_m, water_depth_m,
        eccentricity_B_m=0.0, eccentricity_L_m=0.0,
        footing_type='isolated', gamma_water_kn_m3=9.81,
        required_fs=3.0):
    """USACE EM 1110-1-1905 (2025), Eqs. 5-2 to 5-8 and 5-23.

    Computes gross equivalent applied pressure q_eq = V/A' - u_D for
    isolated footings, or V/B' - u_D for continuous strip footings.
    V is the total downward foundation load Q + W_f (kN for isolated,
    kN/m for continuous); it must already include footing and overburden
    weight. Water uplift u_D is hydrostatic pressure at the footing base.
    """
    qult=_finite('極限承載力 qult',ultimate_bearing_kpa)
    V=_finite('總垂直力 V=Q+Wf',vertical_load_kN)
    B=_finite('基礎寬度 B',footing_width_m)
    L=_finite('基礎長度 L',footing_length_m)
    Df=_finite('基礎埋深 Df',footing_depth_m)
    Dw=_finite('地下水位深度 Dw',water_depth_m)
    eB=_finite('短邊偏心距 eB',eccentricity_B_m)
    eL=_finite('長邊偏心距 eL',eccentricity_L_m)
    gw=_finite('水單位重 gamma_w',gamma_water_kn_m3)
    fs_req=_finite('要求承載力安全係數',required_fs)
    if footing_type not in ('isolated','continuous'):
        raise ValueError('基礎型式須為 isolated 或 continuous')
    if qult<=0 or V<=0 or B<=0 or L<=0 or Df<0 or Dw<0 or eB<0 or eL<0 or gw<=0 or fs_req<=1:
        raise ValueError('承載力檢核輸入不合理；qult、V、尺寸及水單位重須為正，深度與偏心距不可為負')
    if footing_type=='continuous' and eL>0:
        raise ValueError('連續條形基礎不支援沿條形長度方向偏心；請以短邊方向偏心距表示')
    if footing_type=='isolated' and L<B:
        raise ValueError('獨立／矩形基礎須 L≥B')
    Be=B-2*eB
    Le=L-2*eL
    if Be<=0 or (footing_type=='isolated' and Le<=0):
        raise ValueError('偏心距使有效基礎尺寸小於或等於零')
    if footing_type=='isolated':
        Aeff=Be*Le
        q_vertical=V/Aeff
    else:
        Aeff=None
        q_vertical=V/Be
    ud=gw*max(Df-Dw,0.0)
    qeq=q_vertical-ud
    middle_B=(eB < B/6.0)
    middle_L=(True if footing_type=='continuous' else eL < L/6.0)
    fs_actual=(qult/qeq) if qeq>0 else None
    passes_bearing=(fs_actual is not None and fs_actual+1e-12>=fs_req)
    passes_overturning=middle_B and middle_L
    return {
        'qult_gross_kpa':qult,'vertical_load_kN':V,
        'footing_type':footing_type,'B_m':B,'L_m':L,
        'B_effective_m':Be,'L_effective_m':Le,'effective_area_m2':Aeff,
        'vertical_pressure_before_uplift_kpa':q_vertical,
        'water_uplift_pressure_kpa':ud,'qeq_gross_kpa':qeq,
        'FS_bearing':fs_actual,'FS_required':fs_req,
        'passes_bearing':passes_bearing,
        'eccentricity_B_m':eB,'eccentricity_L_m':eL,
        'middle_third_B_limit_m':B/6.0,
        'middle_third_L_limit_m':(L/6.0 if footing_type=='isolated' else None),
        'passes_middle_third':passes_overturning,
        'passes_all_checks':passes_bearing and passes_overturning,
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-2 to 5-8 and 5-23; Table 2-1',
        'limitations':'V 必須是傳至基礎底面的總向下垂直力 Q+Wf，已包含基礎自重及基礎底以上覆土；獨立基礎單位 kN，連續條形基礎單位 kN/m。qeq=V/A′−uD（獨立基礎）或 V/B′−uD（連續基礎），uD=γw·max(Df−Dw,0)。承載力 FS=qult,gross/qeq，USACE 2025 Table 2-1 最低值 3.0。偏心距另須位於中三分點內；本函式不取代滑動、整體穩定、地震及沉陷檢核。'
    }

def bearing_capacity_slope_base_corrections(*, base_result, c_kpa, phi_deg,
        base_inclination_deg=0.0, ground_inclination_deg=0.0,
        slope_distance_m=0.0, adjacent_slope_fs=None,
        horizontal_load=0.0, vertical_load=1.0):
    """Apply USACE EM 1110-1-1905 (2025) Tables 5-2 to 5-4.

    The base calculation must be a Meyerhof result. Drained shape/depth factors
    are rebuilt from effective footing dimensions B'/L' and Df/B' per Table 5-2
    before applying the Table 5-3 inclination factors.
    """
    c=_finite('c／Su',c_kpa); phi=_finite('phi',phi_deg)
    H=_finite('水平載重 H',horizontal_load); V=_finite('垂直載重 V',vertical_load)
    if H<0 or V<=0: raise ValueError('USACE 2025 載重傾斜修正需 H≥0 且 V>0')
    beta_2025=math.degrees(math.atan2(H,V))
    ab=_finite('基底傾角',base_inclination_deg)
    ag=_finite('地表坡角',ground_inclination_deg)
    dg=_finite('基礎至坡頂距離',slope_distance_m)
    if c<0 or not 0<=phi<=50 or not 0<=ab<60 or not 0<=ag<45 or dg<0:
        raise ValueError('斜坡／基底輸入超出適用範圍：0≤基底角<60°、0≤地表坡角<45°、距離不可為負')
    if str(base_result.get('theory','')).lower()!='meyerhof':
        raise ValueError('USACE 表 5-2 至 5-4 修正需以 Meyerhof-based 基礎結果為輸入')
    if not math.isclose(c,base_result.get('c_used',c),rel_tol=1e-7,abs_tol=1e-7):
        raise ValueError('輸入 c／Su 與基礎承載力計算值不一致，請重新計算基礎結果')
    if not math.isclose(phi,base_result.get('phi_used',phi),rel_tol=1e-7,abs_tol=1e-7):
        raise ValueError('輸入摩擦角與基礎承載力計算值不一致，請重新計算基礎結果')
    fs_slope = None if adjacent_slope_fs is None else _finite('鄰接坡體整體穩定 FS', adjacent_slope_fs)
    # USACE EM 1110-1-1905 (2025), Table 5-3 note b:
    # the adjacent-ground inclination factors assume global slope FS > 1.3.
    if ag > 0 and fs_slope is None:
        raise ValueError('套用鄰接地表坡角修正前，必須先完成坡體整體穩定檢核並輸入 FS；USACE 表 5-3 的坡角係數要求 FS > 1.3')
    if ag > 0 and fs_slope <= 1.3:
        raise ValueError('鄰接坡體整體穩定 FS 必須大於 1.3，否則不可套用 USACE 表 5-3 的地表坡角修正係數')
    B=base_result['B_effective']; L=base_result['L_effective']
    shape_ratio=0.0 if base_result.get('footing_type')=='continuous' else B/L
    Df=base_result.get('Df')
    if Df is None or B<=0 or L<=0:
        raise ValueError('基礎結果缺少有效尺寸或埋深，無法套用 USACE 2025 修正')
    Nc=base_result['Nc']; Nq=base_result['Nq']; Ng=base_result['Ngamma']
    q=base_result['q_surcharge']
    if phi>0:
        tp=math.tan(math.radians(phi))
        flow_n=math.tan(math.radians(45.0+phi/2.0))**2
        # USACE 2025 Table 5-2: use effective footing dimensions B' and L'.
        sq=1.0+0.1*flow_n*shape_ratio
        sc=1.0+0.2*flow_n*shape_ratio
        sg=1.0+0.1*flow_n*shape_ratio
        dq=1.0+0.1*math.sqrt(flow_n)*Df/B
        dc=1.0+0.2*math.sqrt(flow_n)*Df/B
        dg_factor=1.0+0.1*math.sqrt(flow_n)*Df/B
        base_term=1-(ab/57.0)*tp
        if base_term<0:
            raise ValueError('基底傾角超出此修正公式的適用範圍；請降低 αb 或改用專用分析')
        bq=base_term**2
        bgamma=bq
        bc=bq-(1-bq)/(Nc*tp)
        if bc<0: raise ValueError('基底傾角使凝聚力修正係數小於零；此幾何不適用本方法')
        gq0=(1-math.tan(math.radians(ag)))**2
        gc0=gq0-(1-gq0)/(Nc*tp)
        ggamma0=gq0
        if min(gq0,gc0,ggamma0)<0:
            raise ValueError('地表坡角使地表傾斜修正係數小於零；請改用專用斜坡承載力分析')
        # USACE Table 5-3: drained factors recover linearly over 5B'.
        recovery=min(1.0,dg/(5.0*B))
        gq=min(1.0,gq0+(1-gq0)*recovery)
        gc=min(1.0,gc0+(1-gc0)*recovery)
        ggamma=min(1.0,ggamma0+(1-ggamma0)*recovery)
        # USACE 2025 Table 5-3 defines beta = atan(H/V); do not reuse
        # the legacy Meyerhof beta entered in the classic calculation path.
        i_2025=(1.0-beta_2025/90.0)**2
        ig_2025=(1.0-beta_2025/phi)**2 if beta_2025<phi else 0.0
        tc=base_result['c_used']*Nc*sc*dc*i_2025*bc*gc
        tq=q*math.cos(math.radians(ag))*Nq*sq*dq*i_2025*bq*gq
        # USACE 2025 Eq. 5-19 groundwater correction for drained gamma term.
        gamma_t=base_result['gamma_below_total']
        gamma_corr=min(0.45+0.55*(max(base_result['water_depth']-Df,0.0)/base_result['B_original']),1.0)
        gamma_eff_2025=gamma_t*gamma_corr
        tg=0.5*B*gamma_eff_2025*Ng*sg*dg_factor*ig_2025*bgamma*ggamma
    else:
        # USACE Table 5-4 undrained corrections. The surcharge-term
        # factors (sq, dq, iq, bq, gq) are unity; Meyerhof ic=1-1.3 H/V.
        flow_n=None
        sc=base_result['sc']; sq=sg=1.0
        dc=base_result['dc']; dq=dg_factor=1.0
        bq=bgamma=1.0
        bc=max(0.0,1-ab/147.3)
        gq=ggamma=1.0
        gc0=max(0.0,1-ag/147.3)
        gc=min(1.0,gc0+(1-gc0)*min(1.0,dg/(2.0*B)))
        ic_2025=1.0-1.3*(H/V)
        if ic_2025<=0:
            raise ValueError('USACE 2025 不排水 Meyerhof 載重傾斜係數 ic≤0；請降低 H/V 或採用有依據的專用分析')
        tc=base_result['c_used']*Nc*sc*dc*ic_2025*bc*gc
        tq=q*math.cos(math.radians(ag))*Nq
        tg=0.0
    q_slope=q*math.cos(math.radians(ag))
    qu=tc+tq+tg
    qnet=qu-q_slope
    fs=base_result['FS']
    qa_net=qnet/fs
    qa_gross=qa_net+q_slope
    return {**base_result,'N_flow':flow_n,'load_inclination_beta_2025_deg':(beta_2025 if phi>0 else None),'load_factor_c_2025':(i_2025 if phi>0 else ic_2025),'load_factor_q_2025':(i_2025 if phi>0 else 1.0),'load_factor_gamma_2025':(ig_2025 if phi>0 else None),'sc':sc,'sq':sq,'sg':sg,
        'gamma_effective':(gamma_eff_2025 if phi>0 else base_result['gamma_effective']),
        'gamma_effective_2025_factor':(gamma_corr if phi>0 else None),
        'gamma_effective_method':('USACE EM 1110-1-1905 (2025), Eq. 5-19' if phi>0 else 'undrained total-stress analysis; gamma term not used'),
        'dc':dc,'dq':dq,'dg':dg_factor,
        'base_factor_c':bc,'base_factor_q':bq,'base_factor_gamma':bgamma,
        'ground_factor_c':gc,'ground_factor_q':gq,'ground_factor_gamma':ggamma,
        'ground_surcharge_kpa':q_slope,'term_c':tc,'term_q':tq,'term_gamma':tg,
        'qu_gross':qu,'qu_net':qnet,'qa_net':qa_net,'qa_gross':qa_gross,
        'qa_gross_direct_FS':qu/fs,
        'adjacent_slope_fs':fs_slope,
        'limitations':base_result['limitations']+'；已依 USACE 2025 表 5-2 以有效尺寸 B′、L′重建 drained 形狀／深度係數，再套用表 5-3／5-4 基底與地表傾斜係數。鄰接坡體須先完成整體穩定檢核且 FS > 1.3；本結果不取代該檢核。'}

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
        footing_area_m2, kh, kv=0.0, seismic_weight_kN=None):
    """Pseudo-static foundation inertia load envelope, not a seismic bearing
    resistance equation. horizontal_load_kN is the pre-earthquake static H;
    seismic_weight_kN is the effective seismic weight W. If W is omitted, V
    is retained as a backward-compatible preliminary proxy. Earthquake
    increments are kh·W horizontally and ±kv·W vertically.
    """
    V=_finite('靜態垂直力 V',vertical_load_kN); H=_finite('靜態水平力 H',horizontal_load_kN)
    A=_finite('基礎面積',footing_area_m2); khv=_finite('水平地震係數 kh',kh)
    kvv=_finite('垂直地震係數 kv',kv)
    W=V if seismic_weight_kN is None else _finite('有效地震重量 W',seismic_weight_kN)
    if V<=0 or W<=0 or A<=0 or H<0 or not 0<=khv<=1 or not 0<=kvv<=0.5:
        raise ValueError('地震分析輸入超出範圍：V、W、面積須正，H≥0，0≤kh≤1，0≤kv≤0.5')
    vertical_min=V-kvv*W
    if vertical_min<=0:
        raise ValueError('V−kv·W≤0，地震垂直作用已達零壓或上拔；本承載力包絡僅適用正向壓縮，須另作上拔／接觸分析')
    cases=[]
    # Envelope both horizontal acceleration directions by aligning kh·W
    # with existing static H. For level base/ground, Meyerhof inclination
    # factors depend on the resultant H/V magnitude.
    he=H+khv*W
    for sign in (-1,1):
        ve=V+sign*kvv*W
        cases.append({'vertical_load_kN':ve,'horizontal_load_kN':he,
            'seismic_weight_kN':W,
            'horizontal_load_direction':'靜力 H 與地震 kh·W 同向（不利包絡）',
            'average_contact_pressure_kpa':ve/A,
            'load_angle_deg':math.degrees(math.atan2(he,ve)),
            'vertical_sign':('向下增加' if ve>V else '向下減少' if ve<V else '無垂直增減')})
    return {'cases':cases,'seismic_weight_kN':W,
        'governing_vertical_load_kN':min(x['vertical_load_kN'] for x in cases),
        'governing_horizontal_load_kN':max(x['horizontal_load_kN'] for x in cases),
        'method':'Pseudo-static adverse action envelope (H + kh·W; V ± kv·W)',
        'limitations':'水平作用採既有靜力 H 與地震 kh·W 同向的不利包絡；垂直作用以靜態 V 加減 kv·W，W 為有效地震重量而非必然等於 V。W 應依適用耐震規範及結構分析計算，未輸入時才以 V 作初步代理。H 必須是不含已另行計入之地震慣性力的靜力水平作用，以免重複計算。此包絡只提供作用量大小，不代表已建立水平力方位角；對水平基底與水平地表，Meyerhof 載重傾斜係數使用合力 H/V 大小。若基底或地表有坡度，地震水平力正反向相對於坡面／基底的作用方向可能改變破壞機制，本系統目前不支援該方向性組合，地震孔壓折減承載力將拒絕非零基底／地表傾角。尚未包含土體慣性力、地震期間強度折減、孔隙水壓累積、液化、震陷、側向擴展與地震邊坡穩定；須依所在地耐震規範取得 kh、kv 及載重組合。'}

def seismic_bearing_capacity_residual_pore_pressure(*, footing_type,
        effective_unit_weight_kn_m3, effective_width_m, bearing_factor_ngamma,
        residual_excess_pore_pressure_ratio, shape_depth_inclination_factor=1.0,
        non_liquefiable_confirmed=False, full_shear_zone_confirmed=False,
        partial_shear_zone_affected_fraction=None,
        effective_unit_weight_unaffected_kn_m3=None):
    """USACE EM 1110-1-1905 (2025) Eqs. 9-3/9-4.

    Full-zone case: q uses (1-ru)*gamma_susceptible.
    Partial-zone case: gamma_b is the weighted average
      f*(1-ru)*gamma_susceptible + (1-f)*gamma_unaffected,
    where f is the user's weighted share of the bearing shear zone affected by
    excess pore pressure. The two gamma values must be effective/buoyant unit
    weights appropriate to the shear zone.
    """
    gamma_sus=_finite('受超額孔隙水壓影響土層有效單位重',effective_unit_weight_kn_m3)
    B=_finite('有效基礎寬度',effective_width_m)
    Ng=_finite('Nγ',bearing_factor_ngamma)
    ru=_finite('殘餘超額孔隙水壓比 ru',residual_excess_pore_pressure_ratio)
    corr=_finite('其他修正係數乘積',shape_depth_inclination_factor)
    if gamma_sus<=0 or B<=0 or Ng<0 or not 0<=ru<1 or corr<=0:
        raise ValueError('地震承載力輸入不合理：γ、B須正；0≤ru<1；修正係數乘積須大於 0')
    if not non_liquefiable_confirmed:
        raise ValueError('式 9-3／9-4 僅適用經獨立評估確認不液化／無循環剪力強度損失的砂土；請先確認適用性')
    if footing_type not in ('strip','spread'):
        raise ValueError('基礎型式須為 strip 或 spread')
    if full_shear_zone_confirmed:
        if partial_shear_zone_affected_fraction is not None or effective_unit_weight_unaffected_kn_m3 is not None:
            raise ValueError('完整剪力區模式不可同時輸入部分剪力區加權參數')
        fraction=1.0
        gamma_unaff=None
        gamma_b=(1.0-ru)*gamma_sus
        method_suffix='full shear zone'
    else:
        if partial_shear_zone_affected_fraction is None or effective_unit_weight_unaffected_kn_m3 is None:
            raise ValueError('部分剪力區模式必須提供受影響加權比例 f 與未受影響土層有效單位重')
        fraction=_finite('受超額孔隙水壓影響剪力區加權比例 f',partial_shear_zone_affected_fraction)
        gamma_unaff=_finite('未受超額孔隙水壓影響土層有效單位重',effective_unit_weight_unaffected_kn_m3)
        if not 0.0<fraction<1.0 or gamma_unaff<=0:
            raise ValueError('部分剪力區加權比例須介於 0 與 1，兩種有效單位重均須大於 0')
        gamma_b=fraction*(1.0-ru)*gamma_sus+(1.0-fraction)*gamma_unaff
        method_suffix='weighted partial shear zone'
    coeff=0.5 if footing_type=='strip' else 0.4
    q=coeff*gamma_b*B*Ng*corr
    unweighted_gamma=(fraction*gamma_sus+(1.0-fraction)*gamma_unaff) if gamma_unaff is not None else gamma_sus
    reduction=gamma_b/unweighted_gamma
    return {
        'qu_seismic_kpa':q,'ru':ru,
        'pore_pressure_resistance_factor':reduction,
        'pore_pressure_affected_fraction':fraction,
        'gamma_susceptible_kn_m3':gamma_sus,
        'gamma_unaffected_kn_m3':gamma_unaff,
        'gamma_effective_weighted_kn_m3':gamma_b,
        'base_coefficient':coeff,'gamma_effective_kn_m3':gamma_b,
        'B_effective_m':B,'Ngamma':Ng,
        'other_correction_product':corr,
        'method':f'USACE EM 1110-1-1905 (2025), Eqs. 9-3/9-4 (Day 2012), {method_suffix}',
        'limitations':'完整剪力區時採 (1−ru)γ′sus；部分剪力區依 USACE 2025 §9-10(c)(3)(b) 將受影響土層與未受影響土層的有效單位重加權：γ′b=f(1−ru)γ′sus+(1−f)γ′unaffected。f 必須依 Figure 5-4 剪力區內受影響土層的實際分布／體積比例估算，不可直接以全孔深度比例代替；γ′sus 與 γ′unaffected 必須為相應水位下的有效／浮單位重。ru 應依孔壓或液化評估取得，不可任意假設。若土層可液化、邊際液化或有顯著循環強度損失，應改用殘餘／折減剪力強度與穿刺破壞分析；此式不代表可接受液化場址。未含側向擴展、地震沉陷及完整地震 qeq／FS。'
    }

def seismic_foundation_eccentricity_cases(*, vertical_load_kN, horizontal_load_kN,
        seismic_weight_kN, kh, kv, footing_type, B, L,
        eccentricity_B=0.0, eccentricity_L=0.0,
        seismic_moment_B_kNm=0.0, seismic_moment_L_kNm=0.0,
        static_moment_B_sign=1, static_moment_L_sign=1,
        allowable_bearing_pressure_kpa=None):
    """Evaluate seismic resultant location, effective area and optional q_allow check.

    Static eccentricities are converted to signed moments V·e. Seismic
    moment components are signed for the +kh direction and reverse with the
    horizontal earthquake direction. Both V±kvW combinations are evaluated.

    For seismic extreme events, the geometry criterion follows USACE
    EM 1110-1-1905 (2025) §9-10(e): the resultant must remain within the
    foundation footprint and effective dimensions must be positive. The
    static middle-third check is reported separately as information. If the
    user supplies the applicable seismic allowable bearing pressure, q_eq is
    also checked; this function never invents a seismic allowable increase.
    """
    V=_finite('靜態垂直力 V',vertical_load_kN)
    H=_finite('靜態水平力 H',horizontal_load_kN)
    W=_finite('有效地震重量 W',seismic_weight_kN)
    khv=_finite('水平地震係數 kh',kh)
    kvv=_finite('垂直地震係數 kv',kv)
    Bv=_finite('基礎短邊 B',B)
    Lv=_finite('基礎長邊 L',L)
    eB0=_finite('靜力短邊偏心距 eB',eccentricity_B)
    eL0=_finite('靜力長邊偏心距 eL',eccentricity_L)
    MBe=_finite('水平地震短邊彎矩 M_B,E',seismic_moment_B_kNm)
    MLe=_finite('水平地震長邊彎矩 M_L,E',seismic_moment_L_kNm)
    sign_MB=_finite('靜力短邊彎矩方向',static_moment_B_sign)
    sign_ML=_finite('靜力長邊彎矩方向',static_moment_L_sign)
    qallow=None if allowable_bearing_pressure_kpa is None else _finite('地震設計容許承載壓力 q_allow',allowable_bearing_pressure_kpa)
    if qallow is not None and qallow<=0:
        raise ValueError('地震設計容許承載壓力 q_allow 必須大於 0')
    if footing_type not in ('spread','strip'):
        raise ValueError('基礎型式須為 spread 或 strip')
    if V<=0 or W<=0 or H<0 or Bv<=0 or Lv<=0 or eB0<0 or eL0<0:
        raise ValueError('地震偏心輸入不合理：V、W、B、L須正；H與偏心距不可為負')
    if footing_type=='spread' and Lv<Bv:
        raise ValueError('矩形／獨立基礎長邊 L 不可小於短邊 B')
    if not 0<=khv<=1 or not 0<=kvv<=0.5:
        raise ValueError('地震係數須符合 0≤kh≤1、0≤kv≤0.5')
    if sign_MB not in (-1,1) or sign_ML not in (-1,1):
        raise ValueError('靜力彎矩方向只能為 +1 或 -1')
    if footing_type=='strip' and (eL0>1e-9 or abs(MLe)>1e-9):
        raise ValueError('連續條形基礎不支援長邊方向偏心或彎矩')
    if V-kvv*W<=0:
        raise ValueError('V−kvW≤0，地震垂直組合已達零壓或上拔，無法計算壓縮接觸偏心距')
    static_MB=sign_MB*V*eB0
    static_ML=sign_ML*V*eL0
    hsigns=(-1,1) if (abs(MBe)>1e-12 or abs(MLe)>1e-12) else (1,)
    cases=[]
    for hsign in hsigns:
        He=abs(H+hsign*khv*W)
        for vsign in (-1,1):
            Ve=V+vsign*kvv*W
            M_B=static_MB+hsign*MBe
            M_L=static_ML+hsign*MLe
            eB=abs(M_B)/Ve
            eL=abs(M_L)/Ve
            Be=Bv-2.0*eB
            Le=Lv-2.0*eL
            contact_pass=(Be>0 and (footing_type=='strip' or Le>0))
            axis_pass=(footing_type=='strip' or Le>=Be)
            resultant_inside=(eB<Bv/2.0 and (footing_type=='strip' or eL<Lv/2.0))
            geometry_pass=contact_pass and axis_pass and resultant_inside
            middle_B=eB<=Bv/6.0+1e-9
            middle_L=(footing_type=='strip' or eL<=Lv/6.0+1e-9)
            middle_pass=middle_B and middle_L
            area_eff=(Be if footing_type=='strip' else Be*Le) if contact_pass else None
            qeq=(Ve/area_eff if area_eff and area_eff>0 else None)
            qallow_pass=(None if qallow is None or qeq is None else qeq<=qallow)
            overall_pass=(None if qallow is None else geometry_pass and qallow_pass is True)
            footprint_util=max(eB/(Bv/2.0),eL/(Lv/2.0) if footing_type=='spread' else 0.0)
            middle_util=max(eB/(Bv/6.0),eL/(Lv/6.0) if footing_type=='spread' else 0.0)
            if not contact_pass or not resultant_inside:
                status='合力超出基礎底面範圍或有效尺寸非正'
            elif not axis_pass:
                status='有效長短軸交換，需雙向偏心分析'
            elif not middle_pass:
                status='合力仍在基礎範圍內，但超出靜力中三分點；地震須另核 qeq≤q_allow'
            else:
                status='合力在基礎範圍內且靜力中三分點亦符合'
            if qallow_pass is False:
                status+='；有效承載壓力超過 q_allow'
            cases.append({
                'horizontal_earthquake_sign':hsign,
                'horizontal_load_direction':('靜力 H 與地震 kh·W 同向' if hsign==1 else '靜力 H 與地震 kh·W 反向'),
                'horizontal_load_kN':He,'vertical_load_kN':Ve,
                'vertical_sign':('向下減少' if vsign==-1 else '向下增加'),
                'moment_B_kNm':M_B,'moment_L_kNm':M_L,
                'eccentricity_B_m':eB,'eccentricity_L_m':eL,
                'middle_third_B_limit_m':Bv/6.0,
                'middle_third_L_limit_m':(Lv/6.0 if footing_type=='spread' else None),
                'footprint_B_limit_m':Bv/2.0,
                'footprint_L_limit_m':(Lv/2.0 if footing_type=='spread' else None),
                'B_effective_m':Be,'L_effective_m':Le,
                'effective_area_m2':area_eff,
                'average_contact_pressure_kpa':qeq,
                'allowable_bearing_pressure_kpa':qallow,
                'bearing_pressure_pass':qallow_pass,
                'resultant_within_footprint':resultant_inside,
                'middle_third_B_pass':middle_B,'middle_third_L_pass':middle_L,
                'middle_third_pass':middle_pass,
                'compression_contact_pass':contact_pass,
                'effective_axis_order_pass':axis_pass,
                'footprint_utilization':footprint_util,
                'middle_third_utilization':middle_util,
                'overturning_utilization':footprint_util,
                'seismic_overturning_geometry_pass':geometry_pass,
                'overall_seismic_overturning_pass':overall_pass,
                'status':status,
            })
    governing=max(cases,key=lambda row:row['footprint_utilization'])
    middle_governing=max(cases,key=lambda row:row['middle_third_utilization'])
    geometry_passes=all(row['seismic_overturning_geometry_pass'] for row in cases)
    qallow_passes=(None if qallow is None else all(row['bearing_pressure_pass'] is True for row in cases))
    overall_passes=(None if qallow is None else geometry_passes and qallow_passes is True)
    return {
        'cases':cases,'governing_case':governing,'middle_third_governing_case':middle_governing,
        'passes':geometry_passes,'geometry_passes':geometry_passes,
        'middle_third_passes':all(row['middle_third_pass'] for row in cases),
        'bearing_pressure_check_complete':qallow is not None,
        'bearing_pressure_passes':qallow_passes,
        'overall_seismic_overturning_passes':overall_passes,
        'allowable_bearing_pressure_kpa':qallow,
        'seismic_moment_included':(abs(MBe)>1e-12 or abs(MLe)>1e-12),
        'static_moment_B_kNm':static_MB,'static_moment_L_kNm':static_ML,
        'seismic_moment_B_kNm':MBe,'seismic_moment_L_kNm':MLe,
        'method':'USACE EM 1110-1-1905 (2025), §9-10(e); static middle-third reference: Table 2-1 Note 3',
        'limitations':'地震極端事件幾何檢核依 USACE §9-10(e)：合力須位於基礎底面範圍內，並以偏心距計算 B′、L′；中三分點另列為靜力參考，不作為地震極端事件唯一判定。完整檢核仍須將 qeq 與適用規範／專案所定的地震容許承載壓力 q_allow 比較；未輸入 q_allow 時，本工具只回報幾何檢核，不代表整體傾覆／承載安全通過。系統不自行套用地震容許承載力提高係數。M_B,E/M_L,E 為 +kh 方向的帶符號水平地震基礎底彎矩，反向地震作用假設彎矩線性反號；若有非線性、扭轉或方向性結構分析，應分別輸入各方向結果。未處理任意水平方位角、雙向同時地震、基底／地表傾斜及土體慣性。'
    }

def seismic_bearing_capacity_residual_pore_pressure_cases(*, vertical_load_kN,
        horizontal_load_kN, kh, kv, footing_type, residual_excess_pore_pressure_ratio,
        c_kpa, phi_deg, gamma_moist, gamma_sub, gamma_below, B, L, Df,
        water_depth, seismic_weight_kN=None, eccentricity_B=0.0, eccentricity_L=0.0,
        seismic_moment_B_kNm=0.0, seismic_moment_L_kNm=0.0,
        static_moment_B_sign=1, static_moment_L_sign=1,
        base_inclination_deg=0.0, ground_inclination_deg=0.0,
        slope_distance_m=0.0, adjacent_slope_fs=None,
        non_liquefiable_confirmed=False, full_shear_zone_confirmed=False,
        partial_shear_zone_affected_fraction=None,
        gamma_effective_susceptible_kn_m3=None,
        gamma_effective_unaffected_kn_m3=None):
    """USACE 2025 residual-pore-pressure bearing resistance for level geometry.

    Supports full shear-zone influence or a user-weighted partial shear-zone
    effective unit weight. It remains restricted to sand-like, non-liquefiable
    soils without cyclic strength loss and is not a seismic factor of safety.
    """
    c=_finite('有效凝聚力 c′',c_kpa)
    phi=_finite('有效摩擦角 φ′',phi_deg)
    if c<0 or c>1e-9 or phi<=0:
        raise ValueError('式 9-3／9-4 僅供砂狀排水土使用；需 c′≈0 且 φ′>0，不可套用不排水黏土或含顯著凝聚力土層')
    if not non_liquefiable_confirmed:
        raise ValueError('式 9-3／9-4 僅適用經獨立評估確認不液化／無循環剪力強度損失的砂土；請先確認適用性')
    ru=_finite('殘餘超額孔隙水壓比 ru',residual_excess_pore_pressure_ratio)
    if full_shear_zone_confirmed:
        if any(value is not None for value in (partial_shear_zone_affected_fraction,gamma_effective_susceptible_kn_m3,gamma_effective_unaffected_kn_m3)):
            raise ValueError('完整剪力區模式不可同時輸入部分剪力區加權參數')
        partial_fraction=None
        gamma_susceptible_input=None
        gamma_unaffected_input=None
    else:
        if partial_shear_zone_affected_fraction is None or gamma_effective_susceptible_kn_m3 is None or gamma_effective_unaffected_kn_m3 is None:
            raise ValueError('部分剪力區模式必須提供受影響加權比例 f、受影響及未受影響土層有效單位重')
        partial_fraction=_finite('受超額孔隙水壓影響剪力區加權比例 f',partial_shear_zone_affected_fraction)
        gamma_susceptible_input=_finite('受影響土層有效單位重',gamma_effective_susceptible_kn_m3)
        gamma_unaffected_input=_finite('未受影響土層有效單位重',gamma_effective_unaffected_kn_m3)
        if not 0.0<partial_fraction<1.0 or gamma_susceptible_input<=0 or gamma_unaffected_input<=0:
            raise ValueError('部分剪力區加權比例須介於 0 與 1，兩種有效單位重均須大於 0')
    if not 0<=ru<1:
        raise ValueError('殘餘超額孔隙水壓比須符合 0≤ru<1')
    footing_map={'spread':'isolated','strip':'continuous'}
    if footing_type not in footing_map:
        raise ValueError('基礎型式須為 spread 或 strip')
    V=_finite('靜態垂直力 V',vertical_load_kN)
    H=_finite('靜態水平力 H',horizontal_load_kN)
    khv=_finite('水平地震係數 kh',kh)
    kvv=_finite('垂直地震係數 kv',kv)
    Bv=_finite('基礎短邊 B',B)
    Lv=_finite('基礎長邊 L',L)
    eB0=_finite('靜力短邊偏心距 eB',eccentricity_B)
    eL0=_finite('靜力長邊偏心距 eL',eccentricity_L)
    MBe=_finite('地震短邊方向彎矩 M_B,E',seismic_moment_B_kNm)
    MLe=_finite('地震長邊方向彎矩 M_L,E',seismic_moment_L_kNm)
    sign_MB=_finite('靜力短邊彎矩方向',static_moment_B_sign)
    sign_ML=_finite('靜力長邊彎矩方向',static_moment_L_sign)
    if sign_MB not in (-1,1) or sign_ML not in (-1,1):
        raise ValueError('靜力彎矩方向只能為 +1 或 -1')
    if V<=0 or H<0 or Bv<=0 or Lv<=0 or eB0<0 or eL0<0 or not 0<=khv<=1 or not 0<=kvv<=0.5:
        raise ValueError('地震載重輸入不合理：V、B、L須正；H、偏心距不可為負；0≤kh≤1、0≤kv≤0.5')
    ab=_finite('基底傾角',base_inclination_deg)
    ag=_finite('地表坡角',ground_inclination_deg)
    if abs(ab)>1e-9 or abs(ag)>1e-9:
        raise ValueError('目前地震孔壓折減承載力僅支援水平基底與水平地表；非零基底／地表傾角涉及地震水平力正反向與坡面方位的交互作用，尚未建立方向性模型，請勿將靜力斜坡修正直接套入地震承載力')
    if footing_type=='strip' and (eL0>1e-9 or abs(MLe)>1e-9):
        raise ValueError('連續條形基礎不支援長邊方向偏心或彎矩；請將荷載轉換為短邊方向彎矩，或改用矩形基礎分析')
    action=seismic_bearing_capacity_pseudostatic(
        vertical_load_kN=V,horizontal_load_kN=H,footing_area_m2=1.0,
        kh=khv,kv=kvv,seismic_weight_kN=seismic_weight_kN)
    W=action['seismic_weight_kN']
    static_MB=sign_MB*V*eB0
    static_ML=sign_ML*V*eL0
    horizontal_signs=(-1,1) if (abs(MBe)>1e-12 or abs(MLe)>1e-12) else (1,)
    cases=[]
    for hsign in horizontal_signs:
        He=abs(H+hsign*khv*W)
        for vsign in (-1,1):
            Ve=V+vsign*kvv*W
            if Ve<=0:
                raise ValueError('地震垂直組合 V±kvW≤0，已達零壓或上拔；須另作接觸／抗浮分析')
            M_B=static_MB+hsign*MBe
            M_L=static_ML+hsign*MLe
            eB_case=abs(M_B)/Ve
            eL_case=abs(M_L)/Ve
            Be=Bv-2.0*eB_case
            Le=Lv-2.0*eL_case
            common={
                'vertical_load_kN':Ve,'horizontal_load_kN':He,
                'seismic_weight_kN':W,
                'horizontal_load_direction':('靜力 H 與地震 kh·W 同向' if hsign==1 else '靜力 H 與地震 kh·W 反向'),
                'horizontal_earthquake_sign':hsign,
                'vertical_sign':('向下增加' if Ve>V else '向下減少' if Ve<V else '無垂直增減'),
                'moment_B_kNm':M_B,'moment_L_kNm':M_L,
                'eccentricity_B_m':eB_case,'eccentricity_L_m':eL_case,
                'middle_third_B_limit_m':Bv/6.0,
                'middle_third_L_limit_m':(Lv/6.0 if footing_type=='spread' else None),
                'footprint_B_limit_m':Bv/2.0,
                'footprint_L_limit_m':(Lv/2.0 if footing_type=='spread' else None),
                'middle_third_B_pass':eB_case<=Bv/6.0+1e-9,
                'middle_third_L_pass':(eL_case<=Lv/6.0+1e-9 if footing_type=='spread' else True),
                'middle_third_pass':(eB_case<=Bv/6.0+1e-9 and (eL_case<=Lv/6.0+1e-9 if footing_type=='spread' else True)),
                'middle_third_utilization':max(eB_case/(Bv/6.0),eL_case/(Lv/6.0) if footing_type=='spread' else 0.0),
                'resultant_within_footprint':(eB_case<Bv/2.0 and (eL_case<Lv/2.0 if footing_type=='spread' else True)),
                'compression_contact_pass':(Be>0 and (footing_type=='strip' or Le>0)),
                'effective_axis_order_pass':(footing_type=='strip' or Le>=Be),
                'overturning_check_pass':(eB_case<Bv/2.0 and (eL_case<Lv/2.0 if footing_type=='spread' else True) and Be>0 and (footing_type=='strip' or Le>0) and (footing_type=='strip' or Le>=Be)),
                'overturning_utilization':max(eB_case/(Bv/2.0),eL_case/(Lv/2.0) if footing_type=='spread' else 0.0),
                'B_effective_m':Be,'L_effective_m':Le,
                'average_contact_pressure_kpa':None,
            }
            invalid_reason=None
            if Be<=0 or (footing_type=='spread' and Le<=0):
                invalid_reason='地震彎矩使有效基礎尺寸≤0；已超出壓縮接觸有效尺寸法適用範圍，須另作接觸／抗拔分析'
            elif footing_type=='spread' and Le<Be:
                invalid_reason='偏心後有效長邊 L′ 小於有效短邊 B′；目前矩形基礎模型不自動旋轉／交換軸向，須改用專用雙向偏心分析'
            if invalid_reason:
                cases.append({**common,'qu_seismic_kpa':None,'zero_resistance_reason':invalid_reason,
                    'method':'USACE EM 1110-1-1905 (2025), Eqs. 9-3/9-4; no valid compression-contact dimensions'})
                continue
            base=bearing_capacity(
                theory='Meyerhof',c_kpa=0.0,phi_deg=phi,
                gamma_moist=gamma_moist,gamma_sub=gamma_sub,
                gamma_below=gamma_below,B=Bv,L=Lv,Df=Df,
                water_depth=water_depth,fs=3.0,
                eccentricity_B=eB_case,eccentricity_L=eL_case,
                footing_type=footing_map[footing_type])
            corrected=bearing_capacity_slope_base_corrections(
                base_result=base,c_kpa=0.0,phi_deg=phi,
                base_inclination_deg=0.0,ground_inclination_deg=0.0,
                slope_distance_m=slope_distance_m,
                adjacent_slope_fs=None,
                horizontal_load=He,vertical_load=Ve)
            factors={
                'shape_s_gamma':corrected['sg'],
                'depth_d_gamma':corrected['dg'],
                'inclination_i_gamma':corrected['load_factor_gamma_2025'],
                'base_b_gamma':corrected['base_factor_gamma'],
                'ground_g_gamma':corrected['ground_factor_gamma'],
            }
            product=math.prod(factors.values())
            if product<=0:
                qu=0.0
                resistance=None
                reason='地震載重傾角 β≥φ′，Meyerhof iγ=0，無正值 Nγ 承載力貢獻'
            else:
                resistance=seismic_bearing_capacity_residual_pore_pressure(
                    footing_type=footing_type,
                    effective_unit_weight_kn_m3=(corrected['gamma_effective'] if full_shear_zone_confirmed else gamma_susceptible_input),
                    effective_width_m=base['B_effective'],
                    bearing_factor_ngamma=base['Ngamma'],
                    residual_excess_pore_pressure_ratio=ru,
                    shape_depth_inclination_factor=product,
                    non_liquefiable_confirmed=non_liquefiable_confirmed,
                    full_shear_zone_confirmed=full_shear_zone_confirmed,
                    partial_shear_zone_affected_fraction=partial_fraction,
                    effective_unit_weight_unaffected_kn_m3=gamma_unaffected_input)
                qu=resistance['qu_seismic_kpa']
                reason=None
            cases.append({
                **common,
                'average_contact_pressure_kpa':Ve/(Be*Le if footing_type=='spread' else Be),
                'load_inclination_beta_deg':corrected['load_inclination_beta_2025_deg'],
                **factors,'correction_product':product,
                'gamma_effective_eq_5_19_kn_m3':corrected['gamma_effective'],
                'gamma_effective_weighted_kn_m3':(resistance['gamma_effective_weighted_kn_m3'] if resistance else None),
                'pore_pressure_affected_fraction':(resistance['pore_pressure_affected_fraction'] if resistance else (1.0 if full_shear_zone_confirmed else partial_fraction)),
                'pore_pressure_resistance_factor':(resistance['pore_pressure_resistance_factor'] if resistance else None),
                'effective_width_m':base['B_effective'],
                'Ngamma_meyerhof':base['Ngamma'],
                'qu_seismic_kpa':qu,'zero_resistance_reason':reason,
                'method':(resistance['method'] if resistance else 'USACE EM 1110-1-1905 (2025), Tables 5-2/5-3 and Eqs. 9-3/9-4'),
            })
    invalid_cases=[case for case in cases if case['qu_seismic_kpa'] is None]
    if invalid_cases:
        governing=invalid_cases[0]
        qu_governing=None
    else:
        governing=min(cases,key=lambda x:x['qu_seismic_kpa'])
        qu_governing=governing['qu_seismic_kpa']
    return {
        'cases':cases,'seismic_weight_kN':W,
        'governing_case':governing,'qu_seismic_governing_kpa':qu_governing,
        'footing_type':footing_type,'ru':ru,
        'full_shear_zone_confirmed':full_shear_zone_confirmed,
        'partial_shear_zone_affected_fraction':(None if full_shear_zone_confirmed else partial_fraction),
        'gamma_effective_susceptible_kn_m3':(None if full_shear_zone_confirmed else gamma_susceptible_input),
        'gamma_effective_unaffected_kn_m3':(None if full_shear_zone_confirmed else gamma_unaffected_input),
        'static_moment_B_kNm':static_MB,'static_moment_L_kNm':static_ML,
        'seismic_moment_B_kNm':MBe,'seismic_moment_L_kNm':MLe,
        'seismic_moment_included':(abs(MBe)>1e-12 or abs(MLe)>1e-12),
        'overturning_check_pass':all(case['overturning_check_pass'] for case in cases),
        'overturning_geometry_check_pass':all(case['overturning_check_pass'] for case in cases),
        'overall_seismic_overturning_check_complete':False,
        'overturning_failed_cases':[case for case in cases if not case['overturning_check_pass']],
        'overturning_governing_case':max(cases,key=lambda case:case['overturning_utilization']),
        'middle_third_check_pass':all(case.get('middle_third_pass',False) for case in cases),
        'middle_third_failed_cases':[case for case in cases if not case.get('middle_third_pass',False)],
        'middle_third_governing_case':max(cases,key=lambda case:case.get('middle_third_utilization',0.0)),
        'method':'USACE EM 1110-1-1905 (2025), §9-10(e), Tables 5-2/5-3, Eq. 5-19 and Eqs. 9-3/9-4 with per-case effective footing dimensions',
        'limitations':'已逐一評估地震水平力正反向及垂直 kv 增減組合；靜力偏心距轉為 V·e，並將輸入的地震基礎底彎矩按水平地震方向反號，逐組合計算 eB=|M_B|/V_eq、eL=|M_L|/V_eq 與 B′=B−2eB、L′=L−2eL，再依 USACE Meyerhof-based Nγ 抗力程序計算。地震彎矩須由結構分析取得並傳至基礎底面；輸入的 M_B,E、M_L,E 定義為 +kh 方向的帶符號分量，反向作用時系統自動反號。若兩分量均為 0，代表本次未納入地震彎矩。地震傾覆幾何依 USACE §9-10(e) 檢核合力是否仍在基礎 footprint 內、有效尺寸是否為正；中三分點另列為靜力參考，不作為地震極端事件唯一判定。有效承載壓力仍須另與適用規範的 q_allow 比較。此處仍為單一水平作用軸向包絡，並未處理任意方位角、扭轉耦合或雙向水平地震同時作用。剪力區孔壓影響可選完整區或部分區；部分區以使用者輸入的加權比例 f 與兩種有效單位重計算 γ′b=f(1−ru)γ′sus+(1−f)γ′unaffected，f 必須依剪力區內土層分布／體積估算，不會由全孔深度自動推定。結果僅為地震孔壓折減後極限抗力；未計算地震 qeq／FS、液化後殘餘強度、側向擴展、震陷及場址整體液化適用性。若任一組合造成有效尺寸非正或有效長短軸交換，系統停止提供控制承載力，須另作接觸壓力／雙向偏心分析。'
    }

def bearing_capacity_in_situ(*, test_type, measurements, drainage, B, L, Df,
        gamma_moist, gamma_sub, water_depth, fs=3.0, footing_type='isolated'):
    """USACE 2025 in-situ-test bearing capacity, Eqs. 5-25/5-26 and Table 5-5.

    measurements are shear-zone readings: N60 (SPT, blows/ft), qne (CPT, kPa),
    or pne (PMT, kPa). Their geometric mean is used. The method assumes a
    centered vertical load, level base and level ground; inclination/seismic
    factors and layered punch-through must be checked separately.
    """
    kind=str(test_type).strip().upper()
    condition=str(drainage).strip().lower()
    if kind not in ('SPT','CPT','PMT'):
        raise ValueError('原位試驗類型須為 SPT、CPT 或 PMT')
    if condition not in ('drained','undrained'):
        raise ValueError('排水條件須為 drained 或 undrained')
    if footing_type not in ('isolated','continuous'):
        raise ValueError('基礎型式須為 isolated 或 continuous')
    if not isinstance(measurements,(list,tuple)) or not measurements:
        raise ValueError('至少輸入一筆剪力區原位試驗值')
    vals=[_finite(f'{kind} 試驗值',v) for v in measurements]
    if any(v<=0 for v in vals):
        raise ValueError('原位試驗值必須全部大於零，幾何平均不接受零或負值')
    B=_finite('基礎寬度 B',B); L=_finite('基礎長度 L',L)
    Df=_finite('基礎埋深 Df',Df); Dw=_finite('地下水深度 Dw',water_depth)
    gamma=_finite('基礎底以上總單位重',gamma_moist)
    gsub=_finite('基礎底以下有效單位重',gamma_sub)
    FS=_finite('安全係數',fs)
    if B<=0 or L<=0 or (footing_type=='isolated' and L<B) or Df<0 or Dw<0:
        raise ValueError('基礎尺寸或深度不合理')
    if gamma<=0 or gsub<=0 or FS<=1:
        raise ValueError('單位重須為正，安全係數須大於 1')
    geomean=math.exp(sum(math.log(v) for v in vals)/len(vals))
    if kind=='SPT':
        s_parameter=geomean*2.0*47.88025898  # pref=2 ksf
        k_table={'drained':0.60,'undrained':0.35}
    elif kind=='CPT':
        s_parameter=geomean
        k_table={'drained':0.10,'undrained':0.35}
    else:
        s_parameter=geomean
        k_table={'drained':0.90,'undrained':0.70}
    k=k_table[condition]
    # Effective surcharge for drained conditions; total-stress surcharge
    # for undrained conditions (submerged unit weight + gamma_w below WT).
    q0=gamma*min(Df,Dw)
    if Df>Dw:
        q0+=(gsub if condition=='drained' else gsub+9.81)*(Df-Dw)
    N=3.0  # USACE specifies N=3 when no friction-angle estimate is available.
    shape_ratio=0.0 if footing_type=='continuous' else B/L
    if condition=='drained':
        shape=1.0+0.1*N*shape_ratio
        depth=1.0+0.1*math.sqrt(N)*(Df/B)
    else:
        shape=1.0+0.2*shape_ratio
        depth=min(1.0+0.2*(Df/B),1.5)
    qult=k*shape*depth*s_parameter+q0
    return {
        'test_type':kind,'drainage':condition,'footing_type':footing_type,
        'measurement_count':len(vals),'measurements':vals,
        'geometric_mean':geomean,'N60_equivalent':geomean if kind=='SPT' else None,
        's_parameter_kpa':s_parameter,'k':k,'flow_number':N,
        'shape_factor':shape,'depth_factor':depth,
        'q_surcharge_kpa':q0,'qu_gross':qult,'qu_net':qult-q0,
        'qa_gross_direct_FS':qult/FS,'qa_net_direct_FS':(qult-q0)/FS,
        'FS':FS,'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-25/5-26, Table 5-5',
        'limitations':'採剪力區內原位試驗值之幾何平均；SPT 使用 N60（非 N1,60）並乘 pref=2 ksf，CPT 使用 qne、PMT 使用 pne。依手冊缺少摩擦角時採 Flow Number N=3。此函式僅計算垂直置中載重、水平地表與水平基底；未計入載重傾斜、基底／地表傾斜、地震修正、偏心及分層穿刺。實際 FS 尚須以結構傳遞的 qeq 比較，不可將 qa=qult/FS 當作已完成工址載重檢核。'
    }



def layered_bearing_capacity_in_situ_profile(*, layers, footing_width_m,
        footing_length_m, footing_depth_m, water_depth_m, gamma_moist_kn_m3,
        gamma_sub_kn_m3, footing_type='isolated', fs=3.0):
    """USACE 2025 in-situ bearing capacity for layered profiles.

    Each layer supplies thickness_m, test_type (SPT/CPT/PMT), drainage
    (drained/undrained), and measurements from that layer's bearing shear zone.
    Per-layer ultimate resistances use Eqs. 5-25/5-26 and Table 5-5; weaker
    underlying layers are checked using Eqs. 5-17/5-18 and 2V:1H spreading.
    This initial implementation is for centered vertical load, level base and
    level ground; horizontal/inclined/seismic corrections are not included.
    """
    if not isinstance(layers,(list,tuple)) or len(layers)<2:
        raise ValueError('原位試驗分層穿刺至少需要兩層')
    if footing_type not in ('isolated','continuous'):
        raise ValueError('基礎型式須為 isolated 或 continuous')
    B=_finite('基礎寬度 B',footing_width_m)
    L=_finite('基礎長度 L',footing_length_m)
    Df=_finite('基礎埋深 Df',footing_depth_m)
    Dw=_finite('地下水深度 Dw',water_depth_m)
    gamma=_finite('基礎底以上天然單位重',gamma_moist_kn_m3)
    gsub=_finite('基礎底以下有效單位重',gamma_sub_kn_m3)
    FS=_finite('安全係數 FS',fs)
    if B<=0 or L<=0 or (footing_type=='isolated' and L<B) or Df<0 or Dw<0:
        raise ValueError('基礎尺寸或深度不合理')
    if gamma<=0 or gsub<=0 or FS<=1:
        raise ValueError('單位重須為正，安全係數須大於 1')
    results=[]
    cumulative=0.0
    for i,layer in enumerate(layers,1):
        if not isinstance(layer,dict):
            raise ValueError(f'第 {i} 層資料格式錯誤')
        for key in ('thickness_m','test_type','drainage','measurements'):
            if key not in layer:
                raise ValueError(f'第 {i} 層缺少 {key}')
        thickness=_finite(f'第 {i} 層厚度',layer['thickness_m'])
        if thickness<=0:
            raise ValueError('各層厚度須大於零')
        result=bearing_capacity_in_situ(
            test_type=layer['test_type'],measurements=layer['measurements'],
            drainage=layer['drainage'],B=B,L=L,Df=Df,
            gamma_moist=gamma,gamma_sub=gsub,water_depth=Dw,
            fs=FS,footing_type=footing_type)
        results.append({
            'layer':i,'thickness_m':thickness,'top_depth_m':cumulative,
            'test_type':result['test_type'],'drainage':result['drainage'],
            'measurement_count':result['measurement_count'],
            'geometric_mean':result['geometric_mean'],
            's_parameter_kpa':result['s_parameter_kpa'],
            'k':result['k'],'qult_kpa':result['qu_gross'],
            'q_surcharge_kpa':result['q_surcharge_kpa'],
        })
        cumulative+=thickness
    lower_depth=0.5*B if footing_type=='isolated' else 1.0*B
    upper_depth=2.0*B if footing_type=='isolated' else 4.0*B
    candidates=[{
        'mode':'上層一般承載力','controlling_layer':1,
        'capacity_kpa':results[0]['qult_kpa'],'spread_factor':1.0,
    }]
    unchecked=[]
    for idx,item in enumerate(results[1:],start=1):
        hs=item['top_depth_m']
        cover=min(x['qult_kpa'] for x in results[:idx])
        if item['qult_kpa']>=cover:
            continue
        if hs<lower_depth:
            candidates.append({
                'mode':'剪力區弱層直接控制','controlling_layer':item['layer'],
                'capacity_kpa':item['qult_kpa'],'spread_factor':1.0,
                'weak_layer_top_depth_m':hs,
            })
        elif hs<=upper_depth:
            if item['drainage']!='undrained':
                raise ValueError(
                    f"第 {item['layer']} 層弱層位於穿刺檢核深度範圍，但 USACE 2025 §5-5a(2) 的 2V:1H 穿刺案例為強層覆蓋弱黏土；此層需以 undrained 條件評估，否則請改用土壤強度參數式 5-22 並另行評估破壞機制"
                )
            spread=((B+hs)*(L+hs)/(B*L)
                    if footing_type=='isolated' else (B+hs)/B)
            candidates.append({
                'mode':'原位試驗弱層穿刺控制','controlling_layer':item['layer'],
                'capacity_kpa':min(cover,spread*item['qult_kpa']),
                'spread_factor':spread,'cover_capacity_kpa':cover,
                'underlying_layer_qult_kpa':item['qult_kpa'],
                'strong_cover_thickness_m':hs,
            })
        else:
            unchecked.append(item['layer'])
    control=min(candidates,key=lambda x:x['capacity_kpa'])
    warning=('以下弱層超出 USACE 穿刺檢核深度範圍，未套用 2V:1H 穿刺式：'
             +', '.join(map(str,unchecked))+'。' if unchecked else None)
    return {
        'qult_kpa':control['capacity_kpa'],
        'controlling_mode':control['mode'],
        'controlling_layer':control['controlling_layer'],
        'layers':results,'candidates':candidates,
        'unchecked_deep_layers':unchecked,'warning':warning,
        'footing_type':footing_type,
        'punching_depth_range_m':(lower_depth,upper_depth),
        'method':'USACE EM 1110-1-1905 (2025), Eqs. 5-17/5-18 and 5-25/5-26; Table 5-5',
        'limitations':'各層分別以該層剪力區原位試驗值幾何平均計算 q_ult,1、q_ult,2，再依 USACE 2V:1H 式檢查弱層穿刺。SPT 輸入 N60，CPT 輸入 qne，PMT 輸入 pne；各層排水條件須符合預期設計載重時的排水狀態。僅支援置中垂直載重、水平基底與水平地表；未計入偏心、水平載重、基底／地表傾斜及地震修正。若各層排水條件與實際載重條件不一致，應改用土壤強度參數式 5-22，不應直接套用此原位試驗法。'
    }

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
    if B<=0 or L<=0 or (footing_type=='isolated' and L<B) or Df<0 or Dw<0: raise ValueError('基礎尺寸或深度不合理')
    if footing_type not in ('isolated','continuous'): raise ValueError('基礎型式不支援')
    if footing_type=='continuous' and eccentricity_L_m>0: raise ValueError('連續條形基礎不支援沿條形長度方向的偏心距')
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
            B=B,L=L,Df=Df,water_depth=Dw,fs=fs,footing_type=footing_type,
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
