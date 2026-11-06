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
        if d10 is None or d30 is None or d60 is None:
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
