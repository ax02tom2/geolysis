"""classification calculation functions."""
from __future__ import annotations
import math
from ._common import _finite, _pct

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
    # ASTM D2487 Fig. 3: A-line is horizontal at PI=4 through LL=25.5,
    # then follows PI=0.73(LL-20).
    aline = 4.0 if ll <= 25.5 else 0.73*(ll-20.0)
    above_a = pi >= aline and pi > 0
    # U-line: vertical at LL=16 to PI=7, then PI=0.9(LL-8).
    uline = 7.0 if ll <= 16.0 else 0.9*(ll-8.0)
    plasticity_warning = ""
    if ll < 16.0:
        plasticity_warning = "LL 位於 U-line 垂直界線（LL=16）左側；請複驗液限／塑限與資料輸入。"
    elif pi > uline + 1e-9:
        plasticity_warning = f"PI={pi:.2f}% 高於 U-line={uline:.2f}%；ASTM D2487 指出應複驗，不宜直接採信本次塑性試驗值。"
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
            'organic_note':organic_note,'A_line_PI':aline,'U_line_PI':uline,'plasticity_warning':plasticity_warning,'peat':False}

ROD_CORRECTION = [(3,0.75),(4,0.80),(6,0.85),(10,0.95),(float('inf'),1.00)]
