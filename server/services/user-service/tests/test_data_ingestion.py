"""
Data Ingestion Test Suite
Tests: file parsing, column mapping, classification, normalization,
       deduplication, multi-tenancy isolation.

Run:
  cd server/services/user-service
  pytest tests/test_data_ingestion.py -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))


# ── Test 1: CSV parsing ───────────────────────────────────────────────────────

class TestFileParser:
    def test_csv_basic(self):
        from services.ingestion.file_parser import parse_file
        csv_content = b"Plan Name,Price,Features\nStarter,$29,Basic\nPro,$79,Advanced\n"
        rows, headers = parse_file(csv_content, "plans.csv")
        assert len(rows) == 2
        assert headers == ["Plan Name", "Price", "Features"]
        assert rows[0]["Plan Name"] == "Starter"
        assert rows[1]["Price"] == "$79"

    def test_csv_empty_rows_skipped(self):
        from services.ingestion.file_parser import parse_file
        csv_content = b"Name,Price\nPro,$79\n,,\nStarter,$29\n"
        rows, _ = parse_file(csv_content, "test.csv")
        assert len(rows) == 2

    def test_csv_too_large(self):
        from services.ingestion.file_parser import parse_file, FileParseError
        big = b"a,b\n" + b"x,y\n" * 1_000_000
        with pytest.raises(FileParseError, match="too large"):
            parse_file(big, "big.csv")

    def test_unsupported_extension(self):
        from services.ingestion.file_parser import parse_file, FileParseError
        with pytest.raises(FileParseError, match="Unsupported"):
            parse_file(b"data", "file.pdf")

    def test_csv_no_headers(self):
        from services.ingestion.file_parser import parse_file, FileParseError
        with pytest.raises(FileParseError):
            parse_file(b"", "empty.csv")

    def test_utf8_bom(self):
        from services.ingestion.file_parser import parse_file
        # UTF-8 BOM prefix
        content = b"\xef\xbb\xbfName,Price\nPro,$79\n"
        rows, headers = parse_file(content, "bom.csv")
        assert "Name" in headers
        assert len(rows) == 1


# ── Test 2: Column mapping ────────────────────────────────────────────────────

class TestColumnMapper:
    def test_obvious_mappings(self):
        from services.ingestion.column_mapper import map_columns
        headers = ["Product Name", "Monthly Price", "Email Address"]
        result = map_columns(headers, confidence_threshold=0.5)
        assert result["Product Name"]["mapped_to"] == "name"
        assert result["Monthly Price"]["mapped_to"] == "price"
        assert result["Email Address"]["mapped_to"] == "email"

    def test_alias_mapping(self):
        from services.ingestion.column_mapper import map_columns
        headers = ["Contact No", "Cost"]
        result = map_columns(headers, confidence_threshold=0.5)
        assert result["Contact No"]["mapped_to"] == "phone"
        assert result["Cost"]["mapped_to"] == "price"

    def test_confidence_scores_present(self):
        from services.ingestion.column_mapper import map_columns
        result = map_columns(["Name"], confidence_threshold=0.5)
        assert "confidence" in result["Name"]
        assert 0.0 <= result["Name"]["confidence"] <= 1.0

    def test_apply_mapping(self):
        from services.ingestion.column_mapper import map_columns, apply_mapping
        headers = ["Plan Name", "Cost"]
        rows = [{"Plan Name": "Pro", "Cost": "$79"}]
        mapping = map_columns(headers, confidence_threshold=0.5)
        mapped = apply_mapping(rows, mapping)
        assert len(mapped) == 1
        assert "name" in mapped[0] or "plan_name" in mapped[0]


# ── Test 3: Category classification ──────────────────────────────────────────

class TestClassifier:
    def test_pricing_classification(self):
        from services.ingestion.classifier import classify_row
        row = {"plan_name": "Pro", "price": "$79/month", "emails": "15000"}
        cat, score = classify_row(row)
        assert cat == "pricing"
        assert score > 0.5

    def test_faq_classification(self):
        from services.ingestion.classifier import classify_row
        row = {"question": "How do I reset my password?", "answer": "Click forgot password on login page"}
        cat, score = classify_row(row)
        assert cat == "faq"
        assert score > 0.5

    def test_contacts_classification(self):
        from services.ingestion.classifier import classify_row
        row = {"name": "John Smith", "email": "john@example.com", "phone": "+1-555-0100"}
        cat, score = classify_row(row)
        assert cat == "contacts"

    def test_batch_classification(self):
        from services.ingestion.classifier import classify_batch
        rows = [
            {"plan": "Starter", "price": "$29"},
            {"question": "What is your refund policy?", "answer": "30 days"},
        ]
        results = classify_batch(rows)
        assert len(results) == 2
        assert results[0][0] == "pricing"
        assert results[1][0] in ("faq", "policies")

    def test_empty_row_returns_custom(self):
        from services.ingestion.classifier import classify_row
        cat, score = classify_row({})
        assert cat == "custom"


# ── Test 4: Normalization ─────────────────────────────────────────────────────

class TestNormalizer:
    def test_basic_normalization(self):
        from services.ingestion.normalizer import normalize_row
        row = {"name": "  Pro Plan  ", "price": "  $79  ", "description": "Advanced features"}
        result = normalize_row(row, "pricing")
        assert result is not None
        assert result["name"] == "Pro Plan"
        assert result["price"] == "$79"

    def test_null_values_removed(self):
        from services.ingestion.normalizer import normalize_row
        row = {"name": "Pro", "price": "N/A", "description": "null"}
        result = normalize_row(row, "pricing")
        assert result is not None
        assert "price" not in result or result.get("price") is None
        assert "description" not in result or result.get("description") is None

    def test_sparse_row_rejected(self):
        from services.ingestion.normalizer import normalize_row
        row = {"name": ""}
        result = normalize_row(row, "pricing")
        assert result is None

    def test_quality_score_range(self):
        from services.ingestion.normalizer import build_entry_payload
        data = {"name": "Pro Plan", "price": "$79", "description": "Advanced features for teams"}
        payload = build_entry_payload(data, "pricing", "manual")
        assert 0 <= payload["quality_score"] <= 100

    def test_title_generation(self):
        from services.ingestion.normalizer import build_entry_payload
        data = {"name": "Holiday Deal", "discount": "40%"}
        payload = build_entry_payload(data, "offers", "manual")
        assert payload["title"] == "Holiday Deal"

    def test_search_text_contains_category(self):
        from services.ingestion.normalizer import build_entry_payload
        data = {"name": "Pro", "price": "$79"}
        payload = build_entry_payload(data, "pricing", "manual")
        assert "pricing" in payload["search_text"].lower()


# ── Test 5: Deduplication ─────────────────────────────────────────────────────

class TestDeduplication:
    """
    Deduplication is tested at the embedding_service level.
    These tests verify the threshold logic without requiring a live Qdrant.
    """

    def test_identical_texts_high_similarity(self):
        """Two identical texts should produce cosine similarity = 1.0"""
        from services.ingestion.embedding_service import embed_texts
        import numpy as np
        texts = ["Pro plan pricing $79 per month advanced features"]
        embs = embed_texts(texts * 2)
        sim = float(np.dot(embs[0], embs[1]))
        assert sim > 0.99

    def test_different_texts_low_similarity(self):
        """Completely different texts should have low similarity"""
        from services.ingestion.embedding_service import embed_texts
        import numpy as np
        embs = embed_texts([
            "Pro plan pricing $79 per month",
            "Contact: John Smith, email john@example.com, phone 555-0100",
        ])
        sim = float(np.dot(embs[0], embs[1]))
        assert sim < 0.85


# ── Test 6: Multi-tenancy isolation ──────────────────────────────────────────

class TestMultiTenancy:
    """
    Verify that user_id scoping is enforced at the schema/query level.
    These are structural tests — no live DB required.
    """

    def test_entry_has_user_id_field(self):
        from models.data_entry import UserDataEntry
        columns = [c.name for c in UserDataEntry.__table__.columns]
        assert "user_id" in columns

    def test_source_has_user_id_field(self):
        from models.data_entry import UserDataSource
        columns = [c.name for c in UserDataSource.__table__.columns]
        assert "user_id" in columns

    def test_version_has_user_id_field(self):
        from models.data_entry import UserDataVersion
        columns = [c.name for c in UserDataVersion.__table__.columns]
        assert "user_id" in columns

    def test_entry_indexes_include_user_id(self):
        from models.data_entry import UserDataEntry
        index_columns = []
        for idx in UserDataEntry.__table__.indexes:
            for col in idx.columns:
                index_columns.append(col.name)
        assert "user_id" in index_columns

    def test_source_indexes_include_user_id(self):
        from models.data_entry import UserDataSource
        index_columns = []
        for idx in UserDataSource.__table__.indexes:
            for col in idx.columns:
                index_columns.append(col.name)
        assert "user_id" in index_columns
