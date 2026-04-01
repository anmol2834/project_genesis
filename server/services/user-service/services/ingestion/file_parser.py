"""
File Parser — CSV / Excel
Safe, streaming-capable parser for uploaded files.

Supports:
  - .csv  (UTF-8, UTF-16, latin-1 with auto-detection)
  - .xlsx / .xls  (openpyxl / xlrd)

Returns a list of raw row dicts: [{col: value, ...}, ...]
Rejects files that are too large, malformed, or empty.
"""

import io
import csv
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS            = 10_000
MAX_COLUMNS         = 100


class FileParseError(Exception):
    """Raised when a file cannot be parsed safely."""


def parse_file(
    content: bytes,
    filename: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse a CSV or Excel file into a list of row dicts.

    Args:
        content:  Raw file bytes.
        filename: Original filename (used to detect extension).

    Returns:
        (rows, headers)
        rows    — list of {header: value} dicts (max MAX_ROWS)
        headers — ordered list of column names

    Raises:
        FileParseError on any unrecoverable issue.
    """
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise FileParseError(
            f"File too large: {len(content) / 1024 / 1024:.1f} MB (max 10 MB)"
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        return _parse_csv(content)
    elif ext in ("xlsx", "xls"):
        return _parse_excel(content, ext)
    else:
        raise FileParseError(f"Unsupported file type: .{ext}. Only .csv and .xlsx/.xls are accepted.")


# ── CSV ───────────────────────────────────────────────────────────────────────

def _parse_csv(content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Try multiple encodings; return first that succeeds."""
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            text = content.decode(encoding)
            return _csv_text_to_rows(text)
        except (UnicodeDecodeError, FileParseError):
            continue
    raise FileParseError("Could not decode CSV file. Ensure it is UTF-8 or Latin-1 encoded.")


def _csv_text_to_rows(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise FileParseError("CSV file has no headers.")

    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]

    if len(headers) == 0:
        raise FileParseError("CSV file has no valid column headers.")
    if len(headers) > MAX_COLUMNS:
        raise FileParseError(f"Too many columns: {len(headers)} (max {MAX_COLUMNS}).")

    rows: List[Dict[str, Any]] = []
    skipped = 0

    for i, raw_row in enumerate(reader):
        if i >= MAX_ROWS:
            logger.warning(f"CSV truncated at {MAX_ROWS} rows")
            break

        row = {
            h.strip(): (raw_row.get(h) or "").strip()
            for h in reader.fieldnames
            if h and h.strip()
        }

        # Skip completely empty rows
        if all(v == "" for v in row.values()):
            skipped += 1
            continue

        rows.append(row)

    if not rows:
        raise FileParseError("CSV file contains no data rows.")

    logger.info(f"CSV parsed: {len(rows)} rows, {skipped} empty rows skipped, {len(headers)} columns")
    return rows, headers


# ── Excel ─────────────────────────────────────────────────────────────────────

def _parse_excel(content: bytes, ext: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        import openpyxl
    except ImportError:
        raise FileParseError("openpyxl is required for Excel file parsing. Install it with: pip install openpyxl")

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active

        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as e:
        raise FileParseError(f"Failed to read Excel file: {e}")

    if not all_rows:
        raise FileParseError("Excel file is empty.")

    # First non-empty row is the header
    header_row = None
    data_start = 0
    for idx, row in enumerate(all_rows):
        if any(cell is not None and str(cell).strip() for cell in row):
            header_row = row
            data_start = idx + 1
            break

    if header_row is None:
        raise FileParseError("Excel file has no header row.")

    headers = [str(h).strip() for h in header_row if h is not None and str(h).strip()]

    if len(headers) > MAX_COLUMNS:
        raise FileParseError(f"Too many columns: {len(headers)} (max {MAX_COLUMNS}).")

    rows: List[Dict[str, Any]] = []
    skipped = 0

    for raw_row in all_rows[data_start:]:
        if len(rows) >= MAX_ROWS:
            logger.warning(f"Excel truncated at {MAX_ROWS} rows")
            break

        values = [str(v).strip() if v is not None else "" for v in raw_row]
        # Pad or trim to match header count
        while len(values) < len(headers):
            values.append("")
        values = values[: len(headers)]

        row = dict(zip(headers, values))

        if all(v == "" for v in row.values()):
            skipped += 1
            continue

        rows.append(row)

    if not rows:
        raise FileParseError("Excel file contains no data rows.")

    logger.info(f"Excel parsed: {len(rows)} rows, {skipped} empty rows skipped, {len(headers)} columns")
    return rows, headers
