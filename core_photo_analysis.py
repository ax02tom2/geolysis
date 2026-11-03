"""岩芯照片分析第一階段：影像檢查、比例校正與 RQD 基礎計算。

注意：本模組不宣稱能僅憑未校正照片自動辨識天然斷裂。
RQD 必須使用可追溯的實際岩芯段長度，且需排除機械斷裂。
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageOps


@dataclass
class ImageInfo:
    width_px: int
    height_px: int
    format: str
    mode: str
    file_size_bytes: int


def inspect_image(data: bytes) -> tuple[Image.Image, ImageInfo]:
    """安全地解碼圖片並回傳 EXIF 校正後影像與基本資訊。"""
    with Image.open(BytesIO(data)) as raw:
        raw.verify()
    with Image.open(BytesIO(data)) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        info = ImageInfo(
            width_px=image.width,
            height_px=image.height,
            format=(raw.format or "unknown").upper(),
            mode=raw.mode,
            file_size_bytes=len(data),
        )
    return image, info


def pixel_scale_mm_per_px(reference_length_mm: float, reference_length_px: float) -> float:
    if reference_length_mm <= 0 or reference_length_px <= 0:
        raise ValueError("比例尺的實際長度與像素長度都必須大於 0。")
    return reference_length_mm / reference_length_px


def parse_piece_lengths(raw: str) -> list[float]:
    """解析以逗號、空白、分號或換行分隔的岩芯段長度（mm）。"""
    tokens = [x for x in __import__("re").split(r"[,，;；\s]+", raw.strip()) if x]
    values = []
    for token in tokens:
        try:
            value = float(token)
        except ValueError as exc:
            raise ValueError(f"無法辨識岩芯段長度：{token}") from exc
        if value <= 0:
            raise ValueError("岩芯段長度必須全部大於 0。")
        values.append(value)
    return values


def calculate_core_indices(
    drilled_interval_m: float,
    recovered_lengths_mm: Iterable[float],
    rqd_threshold_mm: float = 100.0,
) -> dict:
    """依輸入的實際岩芯段長度計算回收率與 RQD。

    回收率 = 回收岩芯總長 / 鑽進長度
    RQD = 長度 >= 100 mm 的完整岩芯段總長 / 鑽進長度
    """
    if drilled_interval_m <= 0:
        raise ValueError("鑽進深度區間必須大於 0。")
    lengths = [float(x) for x in recovered_lengths_mm]
    if any(x <= 0 for x in lengths):
        raise ValueError("岩芯段長度必須全部大於 0。")

    drilled_mm = drilled_interval_m * 1000.0
    recovered_mm = sum(lengths)
    rqd_mm = sum(x for x in lengths if x >= rqd_threshold_mm)

    return {
        "drilled_length_mm": drilled_mm,
        "recovered_length_mm": recovered_mm,
        "recovery_percent": recovered_mm / drilled_mm * 100.0,
        "rqd_length_mm": rqd_mm,
        "rqd_percent": rqd_mm / drilled_mm * 100.0,
        "piece_count": len(lengths),
        "qualifying_piece_count": sum(x >= rqd_threshold_mm for x in lengths),
        "over_recovery": recovered_mm > drilled_mm,
        "lengths_mm": lengths,
    }


def detect_tray_rows(image: Image.Image, max_rows: int = 12) -> dict:
    """以水平邊界梯度找出岩芯箱列界候選；只做定位輔助，不辨識岩芯段或斷裂。

    回傳 row_bounds（像素座標）及 row_bands。演算法使用全寬垂直灰階差，
    對清楚的橫向隔板較敏感；文字、陰影、反光也可能形成假候選。
    """
    import numpy as np

    if max_rows < 2 or max_rows > 30:
        raise ValueError("max_rows 必須介於 2 至 30。")
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    if h < 80 or w < 80:
        return {"row_bounds": [0, h], "row_bands": [(0, h)], "candidates": [], "method": "image_too_small"}

    # 降低文字與局部岩芯紋理的影響：以全寬平均垂直差作為橫向隔板分數。
    diff = np.abs(np.diff(gray, axis=0))
    score = diff.mean(axis=1)
    smooth_n = max(3, int(round(h * 0.004)) | 1)
    kernel = np.ones(smooth_n, dtype=np.float32) / smooth_n
    smooth = np.convolve(score, kernel, mode="same")

    med = float(np.median(smooth))
    mad = float(np.median(np.abs(smooth - med)))
    threshold = max(float(np.percentile(smooth, 82)), med + 2.0 * mad)
    min_distance = max(12, int(h / (max_rows + 1)))
    peaks = []
    edge_margin = max(8, int(h * 0.07))  # 排除照片最外緣的箱體外框
    for y in range(edge_margin, h - edge_margin):
        if smooth[y] >= threshold and smooth[y] >= smooth[y - 1] and smooth[y] >= smooth[y + 1]:
            peaks.append((float(smooth[y]), int(y)))
    # 強峰優先，並限制相鄰候選過近；最後依 y 排序。
    selected = []
    for strength, y in sorted(peaks, reverse=True):
        if all(abs(y - old_y) >= min_distance for _, old_y in selected):
            selected.append((strength, y))
        if len(selected) >= max_rows - 1:
            break
    selected.sort(key=lambda item: item[1])
    bounds = [0] + [y for _, y in selected] + [h]
    bands = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] - bounds[i] >= 12]
    candidates = [
        {"y_px": y, "strength": round(strength, 3)}
        for strength, y in selected
    ]
    return {
        "row_bounds": bounds,
        "row_bands": bands,
        "candidates": candidates,
        "threshold": round(threshold, 3),
        "method": "horizontal_gradient_candidate_v1",
        "warning": "列界候選可能包含文字、陰影或反光；需人工確認，不能直接視為岩芯段界。",
    }


def draw_row_candidates(image: Image.Image, detection: dict) -> Image.Image:
    """繪製水平列界候選，供使用者目視覆核。"""
    from PIL import ImageDraw

    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for i, y in enumerate(detection.get("row_bounds", [])[1:-1], start=1):
        draw.line((0, y, out.width, y), fill=(255, 40, 40), width=max(2, out.width // 1200))
        draw.text((8, min(y + 3, out.height - 18)), f"candidate {i}: y={y}px", fill=(255, 40, 40), stroke_width=1, stroke_fill=(255, 255, 255))
    return out
