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
