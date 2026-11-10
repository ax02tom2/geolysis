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
