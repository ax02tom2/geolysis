"""Layered excavation rebound and recompression settlement calculations."""
from __future__ import annotations

from ._common import _finite


def excavation_rebound_recompression_layers(*, layers):
    """Compute rebound and subsequent recompression from layer-specific e-log-p points.

    Each row represents a compressible stratum and must provide:
      rebound_thickness_m, recompression_thickness_m,
      initial_effective_stress_kpa, excavation_effective_stress_kpa,
      final_effective_stress_kpa, e0, e_exc, e_final.

    The void ratios are read from the layer's oedometer e-log-p curve at the
    corresponding effective stresses. This avoids assuming one constant Cr/Cc
    across unloading and reloading when the measured curve is nonlinear.
    """
    if not layers:
        raise ValueError("至少需要一個分層固結資料列")

    results = []
    for i, row in enumerate(layers, 1):
        required = {
            "rebound_thickness_m", "recompression_thickness_m",
            "initial_effective_stress_kpa", "excavation_effective_stress_kpa",
            "final_effective_stress_kpa", "e0", "e_exc", "e_final",
        }
        missing = required - set(row)
        if missing:
            raise ValueError(
                f"第 {i} 層缺少欄位：" + ", ".join(sorted(missing))
            )

        h_rebound = _finite("回彈計算厚度", row["rebound_thickness_m"])
        h_recompression = _finite("再壓縮計算厚度", row["recompression_thickness_m"])
        sigma0 = _finite("開挖前初始有效應力", row["initial_effective_stress_kpa"])
        sigma_exc = _finite("開挖後有效應力", row["excavation_effective_stress_kpa"])
        sigma_final = _finite("基礎載重後最終有效應力", row["final_effective_stress_kpa"])
        e0 = _finite("開挖前孔隙比 e0", row["e0"])
        e_exc = _finite("開挖後孔隙比 e_exc", row["e_exc"])
        e_final = _finite("載重後孔隙比 e_final", row["e_final"])

        if h_rebound <= 0 or h_recompression <= 0:
            raise ValueError(f"第 {i} 層回彈及再壓縮厚度均須大於 0")
        if not (0 < sigma_exc <= sigma0 and sigma_final >= sigma_exc):
            raise ValueError(
                f"第 {i} 層應符合 0 < σ'exc ≤ σ'0 且 σ'f ≥ σ'exc"
            )
        if min(e0, e_exc, e_final) <= -1:
            raise ValueError(f"第 {i} 層孔隙比必須大於 -1")
        if e_exc < e0 or e_final > e_exc:
            raise ValueError(
                f"第 {i} 層孔隙比方向不符：回彈階段應 e_exc ≥ e0，"
                "再壓縮階段應 e_final ≤ e_exc"
            )

        rebound_m = -h_rebound * (e_exc - e0) / (1.0 + e0)
        recompression_m = (
            h_recompression * (e_exc - e_final) / (1.0 + e_exc)
        )
        results.append({
            "Layer": row.get("Layer", i),
            "rebound_thickness_m": h_rebound,
            "recompression_thickness_m": h_recompression,
            "initial_effective_stress_kpa": sigma0,
            "excavation_effective_stress_kpa": sigma_exc,
            "final_effective_stress_kpa": sigma_final,
            "e0": e0,
            "e_exc": e_exc,
            "e_final": e_final,
            "rebound_mm": rebound_m * 1000.0,
            "recompression_settlement_mm": recompression_m * 1000.0,
            "net_settlement_mm": (rebound_m + recompression_m) * 1000.0,
        })

    return {
        "rebound_mm": sum(row["rebound_mm"] for row in results),
        "recompression_settlement_mm": sum(
            row["recompression_settlement_mm"] for row in results
        ),
        "net_settlement_mm": sum(row["net_settlement_mm"] for row in results),
        "layer_results": results,
        "method": (
            "USACE EM 1110-1-1905 (2025), Eqs. 7-38 and 7-40; "
            "layer-specific measured e-log-p void ratios"
        ),
        "limitations": (
            "本函式使用各層於開挖前、開挖後及基礎載重後的有效應力與 "
            "e-log-p 孔隙比計算；有效應力分布、地下水位變化及應力影響係數"
            "須先依 USACE Table 7-10 求得。未提供試驗曲線時，不應以單一 "
            "Cr/Cc 假設取代非線性卸載－再載重行為。"
        ),
    }
