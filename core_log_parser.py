"""Extract 1 m core-row crops and row labels from the project's DOCX/PDF log exports.

The reference exporter embeds each 4-row core box as one raster image. Each
row is a horizontal band (1 m) and its sequential row number is placed beside
that band. The page header is also a raster image, so start depth is supplied
once by the user; row numbering then provides the per-row sequence.
"""
from __future__ import annotations

from io import BytesIO
import re
from typing import Any

from PIL import Image

ROWS_PER_BOX = 4


class CoreRowRecord:
    """Plain Python record; no runtime decorator dependency."""
    def __init__(self, page: int, box_index: int, row_in_box: int,
                 row_number: int | None, depth_start_m: float | None,
                 depth_end_m: float | None, width_px: int, height_px: int,
                 image: Image.Image, source: str, warnings: list[str],
                 page_bbox_px: tuple[int, int, int, int] | None = None):
        self.page = page
        self.box_index = box_index
        self.row_in_box = row_in_box
        self.row_number = row_number
        self.depth_start_m = depth_start_m
        self.depth_end_m = depth_end_m
        self.width_px = width_px
        self.height_px = height_px
        self.image = image
        self.source = source
        self.warnings = warnings
        self.page_bbox_px = page_bbox_px

    def metadata(self) -> dict[str, Any]:
        return {
            "page": self.page, "box_index": self.box_index,
            "row_in_box": self.row_in_box, "row_number": self.row_number,
            "depth_start_m": self.depth_start_m, "depth_end_m": self.depth_end_m,
            "width_px": self.width_px, "height_px": self.height_px,
            "source": self.source, "warnings": list(self.warnings),
            "page_bbox_px": list(self.page_bbox_px) if self.page_bbox_px else None,
        }


def _row_number_list(text: str) -> list[int]:
    values = []
    for line in (text or "").splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,5}", s):
            values.append(int(s))
    return values


def _crop_box_rows(image: Image.Image, visible_rows: int = 4,
                   image_is_pre_cropped: bool = False) -> list[Image.Image]:
    """Split a box image into visible row strips.

    Some PDF exporters crop a final partial box to the rows that actually exist;
    others retain a full four-row image while printing fewer row labels. The
    caller determines which representation is present from same-page geometry.
    """
    im = image.convert("RGB")
    visible_rows = max(1, min(ROWS_PER_BOX, int(visible_rows)))
    out = []
    usable = im.height if image_is_pre_cropped else round(im.height * visible_rows / ROWS_PER_BOX)
    usable = max(visible_rows, usable)
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
    """Parse PDF and retain complete rendered pages for in-place visual review.

    Each extracted row keeps its corresponding rectangle in the rendered page
    coordinate system, allowing the app to place analysis overlays on the
    original full-page view rather than showing disconnected crops only.
    """
    import fitz

    records: list[CoreRowRecord] = []
    warnings: list[str] = []
    page_views: list[dict[str, Any]] = []
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        for page_index, page in enumerate(pdf):
            page_words = page.get_text("words")
            header_text = " ".join(str(w[4]) for w in page_words if float(w[1]) <= page.rect.height * 0.16)
            # Read only selectable/vector text. Rasterized header OCR is deliberately
            # not guessed here; the UI will request a start depth when unavailable.
            borehole_match = re.search(
                r"(?:鑽孔編號|鑽孔號|孔號|BH\s*No\.?)[：:\s]*([A-Za-z0-9_-]+)",
                header_text, re.IGNORECASE,
            )
            depth_match = re.search(
                r"(?:深度|Depth)[^0-9]{0,16}(\d+(?:\.\d+)?)\s*[~～至–—-]\s*(\d+(?:\.\d+)?)\s*m?",
                header_text, re.IGNORECASE,
            )
            header_depth_range = (float(depth_match.group(1)), float(depth_match.group(2))) if depth_match else None
            placements = []
            for info in page.get_image_info(xrefs=True):
                xref = int(info.get("xref") or 0)
                bbox = fitz.Rect(info["bbox"])
                if not xref or bbox.width <= 0 or bbox.height <= 0:
                    continue
                placements.append((bbox.y0, bbox, xref))
            placements.sort(key=lambda x: (x[0], x[1].x0))
            # Do not use a 16% page-height cutoff: this report places its first
            # core box at y=118.5 pt (14.1% of page height), so that cutoff
            # silently drops the first four metres on every page. Exclude the
            # header by its upper-page placement and require a large box image.
            box_placements = [p for p in placements
                              if p[1].y0 > page.rect.height * 0.12
                              and p[1].x0 > page.rect.width * 0.07
                              and p[1].width > page.rect.width * 0.60
                              and p[1].height > page.rect.height * 0.025]
            # Determine the normal four-row embedded-image height for this page.
            # A final image much shorter than that is already cropped to the
            # remaining visible rows and must not be cropped a second time.
            extracted_sizes = []
            for _, candidate_bbox, candidate_xref in box_placements:
                try:
                    candidate_data = pdf.extract_image(candidate_xref)
                    candidate_im = Image.open(BytesIO(candidate_data["image"]))
                    extracted_sizes.append((candidate_xref, candidate_im.size))
                except Exception:
                    continue
            full_heights = [size[1] for _, size in extracted_sizes if size[1] >= 0.72 * max((v[1] for _, v in extracted_sizes), default=1)]
            typical_box_height = sorted(full_heights)[len(full_heights)//2] if full_heights else None
            page_records: list[CoreRowRecord] = []
            # Keep the complete page, including its header, depth scale, labels,
            # and original image placement. Embedded box images are separately
            # extracted below at their original embedded pixel dimensions.
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False, annots=True)
            page_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            sx = pix.width / max(float(page.rect.width), 1e-9)
            sy = pix.height / max(float(page.rect.height), 1e-9)

            for box_idx, (_, bbox, xref) in enumerate(box_placements):
                try:
                    extracted = pdf.extract_image(xref)
                    box_image = Image.open(BytesIO(extracted["image"])).convert("RGB")
                    candidates = []
                    for word in page_words:
                        x0, y0, x1, y1, txt = word[:5]
                        center_y = (y0 + y1) / 2
                        if (bbox.x1 - 1 <= x0 <= bbox.x1 + page.rect.width * 0.13
                                and bbox.y0 <= center_y <= bbox.y1
                                and re.fullmatch(r"\d{1,5}", str(txt))):
                            candidates.append((center_y, int(txt)))
                    candidates.sort()
                    labels = [v for _, v in candidates]
                    visible = max(1, min(ROWS_PER_BOX, len(labels) if labels else ROWS_PER_BOX))
                    image_is_pre_cropped = bool(typical_box_height and box_image.height < typical_box_height * 0.72)
                    row_images = _crop_box_rows(box_image, visible, image_is_pre_cropped=image_is_pre_cropped)
                    # Align page overlay geometry with the same crop decision.
                    visible_y1 = bbox.y1 if image_is_pre_cropped else bbox.y0 + bbox.height * visible / ROWS_PER_BOX
                    for j, row_image in enumerate(row_images):
                        row_no = labels[j] if j < len(labels) else None
                        row_warnings = []
                        if row_no is None:
                            row_warnings.append("PDF 未擷取到列號；深度索引需人工確認。")
                        y0_pt = bbox.y0 + (visible_y1 - bbox.y0) * j / visible
                        y1_pt = bbox.y0 + (visible_y1 - bbox.y0) * (j + 1) / visible
                        page_bbox_px = (
                            max(0, int(round(bbox.x0 * sx))),
                            max(0, int(round(y0_pt * sy))),
                            min(pix.width, int(round(bbox.x1 * sx))),
                            min(pix.height, int(round(y1_pt * sy))),
                        )
                        page_records.append(CoreRowRecord(
                            page=page_index + 1, box_index=box_idx + 1,
                            row_in_box=j + 1, row_number=row_no,
                            depth_start_m=None, depth_end_m=None,
                            width_px=row_image.width, height_px=row_image.height,
                            image=row_image, source="PDF 內嵌箱照裁切",
                            warnings=row_warnings, page_bbox_px=page_bbox_px,
                        ))
                except Exception as exc:
                    warnings.append(f"第 {page_index + 1} 頁第 {box_idx + 1} 箱：照片解析失敗（{exc}）。")
            if page_records:
                records.extend(page_records)
            elif placements:
                warnings.append(f"第 {page_index + 1} 頁有圖片，但未找到符合格式的岩心箱照片。")
            page_views.append({
                "page": page_index + 1,
                "image": page_image,
                "width_px": pix.width,
                "height_px": pix.height,
                "row_count": len(page_records),
                "header_text": header_text,
                "borehole_id": borehole_match.group(1) if borehole_match else None,
                "header_depth_range_m": header_depth_range,
            })
    finally:
        pdf.close()

    if not records:
        raise ValueError("PDF 中沒有找到符合格式的岩心箱照片。請確認是由岩心柱狀圖工具輸出的 PDF。")
    depth_source = "使用者輸入" if start_depth_m is not None else None
    if start_depth_m is None and records:
        first_record = records[0]
        first_page = next((v for v in page_views if v.get("page") == first_record.page), None)
        inferred = _infer_start_depth_from_header(
            first_page.get("header_depth_range_m") if first_page else None,
            first_record.row_number,
            row_length_m,
        )
        if inferred is not None:
            start_depth_m = inferred
            depth_source = "PDF 頁首深度範圍與列號推定"
    _attach_depths(records, start_depth_m, row_length_m)
    _validate_row_sequence(records, warnings)
    borehole_ids = [v["borehole_id"] for v in page_views if v.get("borehole_id")]
    depth_ranges = [v["header_depth_range_m"] for v in page_views if v.get("header_depth_range_m")]
    metadata_warnings = []
    if len(set(borehole_ids)) > 1:
        metadata_warnings.append("不同頁面讀取到不同鑽孔編號，請人工核對。")
    if depth_ranges and any(b != depth_ranges[0] for b in depth_ranges[1:]):
        # Page ranges normally differ; retain them per page and do not flag.
        pass
    return {"records": records, "page_views": page_views,
            "pages_detected": len(page_views), "rows_detected": len(records),
            "borehole_id": borehole_ids[0] if borehole_ids else None,
            "header_depth_range_m": depth_ranges[0] if depth_ranges else None,
            "depth_source": depth_source,
            "warnings": warnings, "metadata_warnings": metadata_warnings,
            "format": "pdf"}


def _infer_start_depth_from_header(
    header_depth_range_m: tuple[float, float] | None,
    first_row_number: int | None,
    row_length_m: float,
) -> float | None:
    """Infer the depth origin from a readable PDF page range and global row number."""
    if not header_depth_range_m or first_row_number is None:
        return None
    row_length = float(row_length_m)
    if not math.isfinite(row_length) or row_length <= 0:
        raise ValueError("row_length_m 必須是有限且大於 0 的數值。")
    return float(header_depth_range_m[0]) - (int(first_row_number) - 1) * row_length


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
