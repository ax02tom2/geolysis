"""Layered excavation rebound and recompression settlement calculations."""
from __future__ import annotations
from ._common import _finite


def excavation_rebound_recompression_layers(*, layers):
    """Compute rebound and subsequent recompression from layer-specific e-log-p points.

    Required per layer: rebound_thickness_m, recompression_thickness_m,
    initial_effective_stress_kpa, excavation_effective_stress_kpa,
    final_effective_stress_kpa, e0, e_exc, e_final.
    Void ratios are read from the layer's oedometer e-log-p curve at the
    corresponding effective stresses, avoiding a single constant Cr/Cc.
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
            raise ValueError(f"第 {i} 層缺少欄位：" + ", ".join(sorted(missing)))
        hr = _finite("回彈計算厚度", row["rebound_thickness_m"])
        hc = _finite("再壓縮計算厚度", row["recompression_thickness_m"])
        s0 = _finite("開挖前初始有效應力", row["initial_effective_stress_kpa"])
        se = _finite("開挖後有效應力", row["excavation_effective_stress_kpa"])
        sf = _finite("基礎載重後最終有效應力", row["final_effective_stress_kpa"])
        e0 = _finite("開挖前孔隙比 e0", row["e0"])
        ee = _finite("開挖後孔隙比 e_exc", row["e_exc"])
        ef = _finite("載重後孔隙比 e_final", row["e_final"])
        if hr <= 0 or hc <= 0:
            raise ValueError(f"第 {i} 層回彈及再壓縮厚度均須大於 0")
        if not (0 < se <= s0 and sf >= se):
            raise ValueError(f"第 {i} 層應符合 0 < σ'exc ≤ σ'0 且 σ'f ≥ σ'exc")
        if min(e0, ee, ef) <= -1:
            raise ValueError(f"第 {i} 層孔隙比必須大於 -1")
        if ee < e0 or ef > ee:
            raise ValueError(
                f"第 {i} 層孔隙比方向不符：回彈階段應 e_exc ≥ e0，"
                "再壓縮階段應 e_final ≤ e_exc"
            )
        rebound = -hr * (ee - e0) / (1.0 + e0)
        recompression = hc * (ee - ef) / (1.0 + ee)
        results.append({
            "Layer": row.get("Layer", i),
            "rebound_thickness_m": hr,
            "recompression_thickness_m": hc,
            "initial_effective_stress_kpa": s0,
            "excavation_effective_stress_kpa": se,
            "final_effective_stress_kpa": sf,
            "e0": e0, "e_exc": ee, "e_final": ef,
            "rebound_mm": rebound * 1000.0,
            "recompression_settlement_mm": recompression * 1000.0,
            "net_settlement_mm": (rebound + recompression) * 1000.0,
        })
    return {
        "rebound_mm": sum(r["rebound_mm"] for r in results),
        "recompression_settlement_mm": sum(r["recompression_settlement_mm"] for r in results),
        "net_settlement_mm": sum(r["net_settlement_mm"] for r in results),
        "layer_results": results,
        "method": "USACE EM 1110-1-1905 (2025), Eqs. 7-38 and 7-40; layer-specific measured e-log-p void ratios",
        "limitations": (
            "本函式使用各層於開挖前、開挖後及基礎載重後的有效應力與 e-log-p 孔隙比計算；"
            "有效應力分布、地下水位變化及應力影響係數須先依 USACE Table 7-10 求得。"
            "未提供試驗曲線時，不應以單一 Cr/Cc 假設取代非線性卸載－再載重行為。"
        ),
    }
