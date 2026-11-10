"""Shared validation helpers for geolysis calculations."""
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
