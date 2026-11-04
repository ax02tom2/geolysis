"""Extract 1 m core-row crops and row labels from the project's DOCX/PDF log exports.

The reference exporter embeds each 4-row core box as one raster image. Each
row is a horizontal band (1 m) and its sequential row number is placed beside
that band. The page header is also a raster image, so start depth is supplied
once by the user; row numbering then provides the per-row sequence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from io import BytesIO
import re
from typing import Any

from PIL import Image

ROWS_PER_BOX = 4


@dataclass
class CoreRowRecord:
    page: int
    box_index: int
    row_in_box: int
    row_number: int | None
    depth_start_m: float | None
    depth_end_m: float | None
    width_px: int
    height_px: int
    image: Image.Image
    source: str
    warnings: list[str]

    def metadata(self) -> dict[str, Any]:
        return {
            "page": self.page, "box_index": self.box_index,
            "row_in_box": self.row_in_box, "row_number": self.row_number,
            "depth_start_m": self.depth_start_m, "depth_end_m": self.depth_end_m,
            "width_px": self.width_px, "height_px": self.height_px,
            "source": self.source, "warnings": list(self.warnings),
        }


def _row_number_list(text: str) -> list[int]:
    values = []
    for line in (text or "").splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,5}", s):
            values.append(int(s))
    return values


def _crop_box_rows(image: Image.Image, visible_rows: int = 4) -> list[Image.Image]:
    """Split a 4-row box image into top-to-bottom equal row strips."""
    im = image.convert("RGB")
    visible_rows = max(1, min(ROWS_PER_BOX, int(visible_rows)))
    out = []
    # The exporter keeps the complete box image on the final partial page;
    # only the first N row labels are visible. Crop only the corresponding top
    # N/4 fraction, then split that fraction into N equal bands.
    visible_bottom = round(im.height * visible_rows / ROWS_PER_BOX)
    usable = max(visible_rows, visible_bottom)
    for i in range(visible_rows):
        y0 = round(usable * i / visible_rows)
        y1 = round(usable * (i + 1) / visible_rows)
        out.append(im.crop((0, y0, im.width, max(y0 + 1, y1))))
    return out


def _attach_depths(records: list[CoreRowRecord], start_depth_m: float | None, row_length_m: float):
    if start_depth_m is None:
        return
    for rec in records:
        if rec.row_number is not None:
            rec.depth_start_m = float(start_depth_m) + (rec.row_number - 1) * row_length_m
            rec.depth_end_m = rec.depth_start_m + row_length_m


def parse_docx_core_log(data: bytes, start_depth_m: float | None = None,
                        row_length_m: float = 1.0) -> dict[str, Any]:
    """Parse a DOCX produced by Core-photo-depth-matching-alignment."""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(BytesIO(data))
    records: list[CoreRowRecord] = []
    warnings: list[str] = []
    page_no = 0
    for table in doc.tables:
        if not table.rows:
            page_no += 1
            continue
        current_page = page_no + 1
        # Export format: first row is the header image; following rows contain
        # one box image in cell 0 and four row-number paragraphs in cell 1.
        page_records: list[CoreRowRecord] = []
        for box_idx, row in enumerate(table.rows[1:]):
            if len(row.cells) < 2:
                warnings.append(f"第 {current_page} 頁第 {box_idx + 1} 箱：表格欄位不足，略過。")
                continue
            blips = row.cells[0]._tc.xpath('.//a:blip')
            if not blips:
                warnings.append(f"第 {current_page} 頁第 {box_idx + 1} 箱：找不到內嵌岩心照片。")
                continue
            rel_id = blips[0].get(qn("r:embed"))
            part = doc.part.related_parts.get(rel_id)
            if part is None:
                warnings.append(f"第 {current_page} 頁第 {box_idx + 1} 箱：照片關聯資料遺失。")
                continue
            try:
                box_image = Image.open(BytesIO(part.blob)).convert("RGB")
                labels = _row_number_list("\n".join(p.text for p in row.cells[1].paragraphs))
                visible = len(labels) if labels else ROWS_PER_BOX
                visible = max(1, min(ROWS_PER_BOX, visible))
                row_images = _crop_box_rows(box_image, visible)
                for j, row_image in enumerate(row_images):
                    row_no = labels[j] if j < len(labels) else None
                    row_warnings = []
                    if row_no is None:
                        row_warnings.append("未能讀取列號；深度索引需人工確認。")
                    page_records.append(CoreRowRecord(
                        page=current_page, box_index=box_idx + 1,
                        row_in_box=j + 1, row_number=row_no,
                        depth_start_m=None, depth_end_m=None,
                        width_px=row_image.width, height_px=row_image.height,
                        image=row_image, source="DOCX 內嵌箱照裁切",
                        warnings=row_warnings,
                    ))
            except Exception as exc:
                warnings.append(f"第 {current_page} 頁第 {box_idx + 1} 箱：照片解析失敗（{exc}）。")
        if page_records:
            records.extend(page_records)
        page_no += 1

    if not records:
        raise ValueError("文件中沒有找到符合格式的岩心箱照片表格。請確認是由岩心柱狀圖工具輸出的 DOCX。")
    _attach_depths(records, start_depth_m, row_length_m)
    _validate_row_sequence(records, warnings)
    return {"records": records, "warnings": warnings,
            "pages_detected": page_no, "rows_detected": len(records),
            "borehole_id": None, "format": "docx"}


def parse_pdf_core_log(data: bytes, start_depth_m: float | None = None,
                       row_length_m: float = 1.0) -> dict[str, Any]:
    """Parse the matching PDF export; image placements and vector row labels are used."""
    import fitz

    pdf = fitz.open(stream=data, filetype="pdf")
    records: list[CoreRowRecord] = []
    warnings: list[str] = []
    for page_index, page in enumerate(pdf):
        page_words = page.get_text("words")
        # Find embedded image placements in top-to-bottom order. The first
        # image on a generated page is the header; box images follow it.
        placements = []
        for info in page.get_image_info(xrefs=True):
            xref = int(info.get("xref") or 0)
            bbox = fitz.Rect(info["bbox"])
            if not xref or bbox.width <= 0 or bbox.height <= 0:
                continue
            # Preserve repeated placements even when the PDF reuses one xref.
            placements.append((bbox.y0, bbox, xref))
        placements.sort(key=lambda x: (x[0], x[1].x0))
        # Ignore the top header image. Restrict box images to the left/main
        # column and discard small decorative images.
        box_placements = [p for p in placements
                          if p[1].y0 > page.rect.height * 0.16
                          and p[1].width > page.rect.width * 0.35
                          and p[1].height > page.rect.height * 0.025]
        page_records: list[CoreRowRecord] = []
        for box_idx, (_, bbox, xref) in enumerate(box_placements):
            try:
                extracted = pdf.extract_image(xref)
                box_image = Image.open(BytesIO(extracted["image"])).convert("RGB")
                # Row labels are vector text in the narrow column immediately
                # right of each box image. Group by vertical center.
                candidates = []
                for word in page_words:
                    x0, y0, x1, y1, txt = word[:5]
                    if (bbox.x1 - 1 <= x0 <= bbox.x1 + page.rect.width * 0.13
                            and bbox.y0 <= (y0 + y1) / 2 <= bbox.y1
                            and re.fullmatch(r"\d{1,5}", str(txt))):
                        candidates.append(((y0 + y1) / 2, int(txt)))
                candidates.sort()
                labels = [v for _, v in candidates]
                # A box can show only the final 1-3 rows on the last page.
                visible = max(1, min(ROWS_PER_BOX, len(labels) if labels else ROWS_PER_BOX))
                row_images = _crop_box_rows(box_image, visible)
                for j, row_image in enumerate(row_images):
                    row_no = labels[j] if j < len(labels) else None
                    row_warnings = []
                    if row_no is None:
                        row_warnings.append("PDF 未擷取到列號；深度索引需人工確認。")
                    page_records.append(CoreRowRecord(
                        page=page_index + 1, box_index=box_idx + 1,
                        row_in_box=j + 1, row_number=row_no,
                        depth_start_m=None, depth_end_m=None,
                        width_px=row_image.width, height_px=row_image.height,
                        image=row_image, source="PDF 內嵌箱照裁切",
                        warnings=row_warnings,
                    ))
            except Exception as exc:
                warnings.append(f"第 {page_index + 1} 頁第 {box_idx + 1} 箱：照片解析失敗（{exc}）。")
        if page_records:
            records.extend(page_records)
        elif placements:
            warnings.append(f"第 {page_index + 1} 頁有圖片，但未找到符合格式的岩心箱照片。")
    pdf.close()
    if not records:
        raise ValueError("PDF 中沒有找到符合格式的岩心箱照片。請確認是由岩心柱狀圖工具輸出的 PDF。")
    _attach_depths(records, start_depth_m, row_length_m)
    _validate_row_sequence(records, warnings)
    return {"records": records, "warnings": warnings,
            "pages_detected": len({r.page for r in records}),
            "rows_detected": len(records), "borehole_id": None, "format": "pdf"}


def _validate_row_sequence(records: list[CoreRowRecord], warnings: list[str]):
    nums = [r.row_number for r in records if r.row_number is not None]
    if not nums:
        warnings.append("未讀取到任何列號；目前只能檢視照片，不能自動建立深度索引。")
        return
    if len(nums) != len(records):
        warnings.append(f"列號辨識不完整：辨識到 {len(nums)} / {len(records)} 列。")
    if len(nums) > 1:
        for a, b in zip(nums, nums[1:]):
            if b != a + 1:
                warnings.append(f"列號不連續或順序異常：{a} → {b}。請檢查是否缺列、重複或頁序錯誤。")
                break


def parse_core_log(data: bytes, filename: str, start_depth_m: float | None = None,
                   row_length_m: float = 1.0) -> dict[str, Any]:
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    if ext == "docx":
        return parse_docx_core_log(data, start_depth_m, row_length_m)
    if ext == "pdf":
        return parse_pdf_core_log(data, start_depth_m, row_length_m)
    raise ValueError("僅支援 DOCX 與 PDF 檔案。")
