"""Layered primary consolidation from user-supplied total stress increments."""
from __future__ import annotations

from ._common import _finite
from .settlement import consolidation_settlement_1d


def consolidation_settlement_layers_from_stress_profile(*, layers):
    """Calculate primary consolidation from per-layer total Δσz after superposition.

    Each row must include Depth_center_m, Thickness_m, e0, Cc, Cr,
    Sigma0_kPa, SigmaP_kPa and Delta_sigma_kPa. Delta_sigma_kPa is the
    already-summed stress increment from all applicable loads (e.g. adjacent
    footings plus fill). This function intentionally does not infer load
    geometry or calculate Boussinesq influence factors.
    """
    if not layers:
        raise ValueError("至少需要一個逐層應力資料列")
    results = []
    for i, row in enumerate(layers, 1):
        required = {
            "Depth_center_m", "Thickness_m", "e0", "Cc", "Cr",
            "Sigma0_kPa", "SigmaP_kPa", "Delta_sigma_kPa",
        }
        missing = required - set(row)
        if missing:
            raise ValueError(f"第 {i} 層缺少欄位：" + ", ".join(sorted(missing)))
        z = _finite("Depth_center_m", row["Depth_center_m"])
        h = _finite("Thickness_m", row["Thickness_m"])
        e0 = _finite("e0", row["e0"])
        cc = _finite("Cc", row["Cc"])
        cr = _finite("Cr", row["Cr"])
        sigma0 = _finite("Sigma0_kPa", row["Sigma0_kPa"])
        sigmap = _finite("SigmaP_kPa", row["SigmaP_kPa"])
        delta = _finite("Delta_sigma_kPa", row["Delta_sigma_kPa"])
        if z <= 0 or h <= 0:
            raise ValueError(f"第 {i} 層中心深度與厚度必須大於 0")
        if delta < 0:
            raise ValueError(f"第 {i} 層總應力增量不可為負；卸載應使用開挖回彈方法")
        result = consolidation_settlement_1d(
            layer_thickness_m=h,
            initial_void_ratio=e0,
            compression_index=cc,
            recompression_index=cr,
            initial_effective_stress_kpa=sigma0,
            preconsolidation_stress_kpa=sigmap,
            stress_increase_kpa=delta,
        )
        results.append({
            "Layer": row.get("Layer", i),
            "Depth_center_m": z,
            "Thickness_m": h,
            "Delta_sigma_kPa": delta,
            "Sigma0_kPa": sigma0,
            "SigmaP_kPa": sigmap,
            "Final_sigma_kPa": sigma0 + delta,
            "Settlement_mm": result["settlement_mm"],
            "Regime": result["regime"],
        })
    results.sort(key=lambda item: item["Depth_center_m"])
    for i, row in enumerate(results):
        if row["Depth_center_m"] - row["Thickness_m"] / 2.0 < -1e-9:
            raise ValueError("壓縮層頂面不可位於基礎底以上")
        if i:
            previous_bottom = (
                results[i - 1]["Depth_center_m"]
                + results[i - 1]["Thickness_m"] / 2.0
            )
            if row["Depth_center_m"] - row["Thickness_m"] / 2.0 < previous_bottom - 1e-9:
                raise ValueError("分層厚度互相重疊；請檢查各層中心深度與厚度")
    return {
        "settlement_mm": sum(row["Settlement_mm"] for row in results),
        "layer_results": results,
        "method": "逐層一維主固結；使用使用者輸入之總應力增量 Δσz（已完成荷載疊加）",
        "limitations": (
            "本方法只計算輸入之逐層總應力增量所造成的主固結沉陷；"
            "不會自行計算各基礎、填土或其他荷載的 Boussinesq 應力影響係數。"
            "使用者須先依適用幾何與 USACE 第 6 章完成應力疊加，"
            "再將各層合計 Δσz 輸入；不得把單一荷載增量冒充總增量。"
        ),
    }
