"""
Google Sheets Webhook Handler
Validates and processes real-time updates pushed by Google Apps Script.

Architecture:
  Google Sheet updated
    → Apps Script onEdit trigger fires
    → Apps Script POSTs to: POST /data/webhook/google-sheets/{source_id}
    → This handler validates HMAC secret + processes rows
    → Runs full ingestion pipeline on changed rows

Apps Script template (deploy in the connected sheet):
─────────────────────────────────────────────────────
  const WEBHOOK_URL = "https://your-api.com/user-service/data/webhook/google-sheets/<SOURCE_ID>";
  const SECRET      = "<WEBHOOK_SECRET>";

  function onEdit(e) {
    const sheet = e.source.getActiveSheet();
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const lastRow = sheet.getLastRow();
    const allData = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();

    const rows = allData.map(row => {
      const obj = {};
      headers.forEach((h, i) => { obj[h] = row[i]; });
      return obj;
    });

    const payload = {
      secret:    SECRET,
      sheet_id:  e.source.getId(),
      timestamp: new Date().toISOString(),
      rows:      rows,
    };

    UrlFetchApp.fetch(WEBHOOK_URL, {
      method:      "post",
      contentType: "application/json",
      payload:     JSON.stringify(payload),
      muteHttpExceptions: true,
    });
  }
─────────────────────────────────────────────────────
"""

import hashlib
import hmac
import logging
import secrets
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

WEBHOOK_SECRET_LENGTH = 32   # bytes → 64 hex chars


def generate_webhook_secret() -> str:
    """Generate a cryptographically secure webhook secret for a new sheet source."""
    return secrets.token_hex(WEBHOOK_SECRET_LENGTH)


def validate_webhook_secret(provided: str, stored: str) -> bool:
    """
    Constant-time comparison of provided vs stored webhook secret.
    Prevents timing attacks.
    """
    if not provided or not stored:
        return False
    return hmac.compare_digest(provided.encode(), stored.encode())


def extract_headers_from_rows(rows: List[Dict[str, Any]]) -> List[str]:
    """
    Extract column headers from the first row of webhook payload.
    Handles both dict-of-dicts and list-of-dicts formats.
    """
    if not rows:
        return []
    return list(rows[0].keys())


def filter_empty_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove rows where all values are empty/None."""
    return [
        row for row in rows
        if any(v is not None and str(v).strip() for v in row.values())
    ]


def normalize_webhook_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize rows from Apps Script:
    - Convert all values to strings
    - Strip whitespace
    - Remove None values
    """
    normalized = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if k and str(k).strip():
                val = str(v).strip() if v is not None else ""
                clean[str(k).strip()] = val
        normalized.append(clean)
    return normalized
