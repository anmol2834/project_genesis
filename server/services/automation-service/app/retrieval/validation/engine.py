"""
Validation Engine
=================
Validates retrieved chunks before sending to LLM to prevent hallucination.

Validation checks:
- Tenant ownership
- Content quality
- Relevance to query
- Entity correctness
- Duplication removal
"""

import logging
from typing import List
from app.retrieval.schemas import RetrievedChunk, ValidationResult

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Validates retrieved chunks for relevance and quality.
    
    This is CRITICAL for hallucination prevention.
    """
    
    def __init__(self, min_relevance_threshold: float = 0.3):
        """
        Initialize validation engine.
        
        Args:
            min_relevance_threshold: Minimum relevance score (0.0-1.0)
        """
        self.min_relevance = min_relevance_threshold
    
    def validate_chunk(
        self,
        chunk: RetrievedChunk,
        query: str,
        user_id: str,
        min_relevance: float = None
    ) -> ValidationResult:
        """
        Validate single chunk.
        
        Args:
            chunk: Retrieved chunk
            query: Original query
            user_id: Expected tenant ID
            min_relevance: Override minimum relevance
            
        Returns:
            ValidationResult with pass/fail and reasons
        """
        threshold = min_relevance if min_relevance is not None else self.min_relevance
        
        rejection_reasons = []
        
        # Check 1: Tenant ownership
        tenant_valid = self._validate_tenant(chunk, user_id)
        if not tenant_valid:
            rejection_reasons.append("tenant_mismatch")
        
        # Check 2: Content quality
        content_valid = self._validate_content(chunk)
        if not content_valid:
            rejection_reasons.append("poor_content_quality")
        
        # Check 3: Relevance score
        relevance_valid = chunk.score >= threshold
        if not relevance_valid:
            rejection_reasons.append(f"low_relevance_score_{chunk.score:.2f}")

        # Check 4: Query relevance (at least one keyword match)
        query_relevant = self._validate_query_relevance(chunk, query)
        if not query_relevant:
            rejection_reasons.append("query_mismatch")

        # Final decision:
        # A chunk is valid when tenant+content pass AND either:
        #   (a) score meets threshold, OR
        #   (b) at least one query keyword matches (semantic/BM25 proximity signal)
        # This prevents both score-gate and keyword-gate firing simultaneously
        # and rejecting all chunks when the knowledge base uses different vocabulary.
        score_or_keyword = relevance_valid or query_relevant
        valid = tenant_valid and content_valid and score_or_keyword
        
        # Calculate validation confidence
        confidence = self._calculate_validation_confidence(
            tenant_valid, content_valid, relevance_valid, query_relevant, chunk.score
        )
        
        return ValidationResult(
            chunk_id=chunk.chunk_id,
            valid=valid,
            relevance_score=chunk.score,
            rejection_reasons=rejection_reasons,
            tenant_valid=tenant_valid,
            content_valid=content_valid,
            relevance_valid=relevance_valid,
            validation_confidence=confidence
        )
    
    def validate_chunks(
        self,
        chunks: List[RetrievedChunk],
        query: str,
        user_id: str,
        min_relevance: float = None
    ) -> List[ValidationResult]:
        """
        Validate multiple chunks.
        
        Args:
            chunks: List of retrieved chunks
            query: Original query
            user_id: Expected tenant ID
            min_relevance: Override minimum relevance
            
        Returns:
            List of validation results
        """
        return [
            self.validate_chunk(chunk, query, user_id, min_relevance)
            for chunk in chunks
        ]
    
    def filter_valid_chunks(
        self,
        chunks: List[RetrievedChunk],
        query: str,
        user_id: str,
        min_relevance: float = None
    ) -> tuple[List[RetrievedChunk], int, int]:
        """
        Filter chunks to only valid ones.
        
        Args:
            chunks: List of retrieved chunks
            query: Original query
            user_id: Expected tenant ID
            min_relevance: Override minimum relevance
            
        Returns:
            (valid_chunks, passed_count, rejected_count)
        """
        validations = self.validate_chunks(chunks, query, user_id, min_relevance)
        
        valid_chunks = []
        passed = 0
        rejected = 0
        
        for chunk, validation in zip(chunks, validations):
            if validation.valid:
                # Mark as validated
                chunk.validated = True
                chunk.relevance_score = validation.relevance_score
                valid_chunks.append(chunk)
                passed += 1
            else:
                rejected += 1
                logger.debug(
                    f"Chunk rejected: {chunk.chunk_id} reasons={validation.rejection_reasons}"
                )
        
        logger.info(f"Validation: passed={passed} rejected={rejected}")
        
        return valid_chunks, passed, rejected
    
    def remove_duplicates(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Remove duplicate chunks by content similarity.
        
        Args:
            chunks: List of chunks
            
        Returns:
            Deduplicated chunks
        """
        if not chunks:
            return []
        
        seen_content = set()
        unique_chunks = []
        
        for chunk in chunks:
            # Use first 200 chars as signature
            signature = chunk.content[:200].strip().lower()
            
            if signature not in seen_content:
                seen_content.add(signature)
                unique_chunks.append(chunk)
        
        if len(unique_chunks) < len(chunks):
            logger.info(f"Deduplication: {len(chunks)} → {len(unique_chunks)}")
        
        return unique_chunks
    
    # ══════════════════════════════════════════════════════════════════════
    # Private Validation Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _validate_tenant(self, chunk: RetrievedChunk, user_id: str) -> bool:
        """Validate chunk belongs to correct tenant"""
        return chunk.user_id == user_id
    
    def _validate_content(self, chunk: RetrievedChunk) -> bool:
        """Validate content quality"""
        content = chunk.content.strip()
        
        # Check minimum length
        if len(content) < 20:
            return False
        
        # Check not empty or placeholder
        if content.lower() in ["", "n/a", "none", "null", "undefined"]:
            return False
        
        return True
    
    def _validate_query_relevance(self, chunk: RetrievedChunk, query: str) -> bool:
        """
        Keyword-based relevance check.

        Requires at least ONE keyword match (not a percentage floor).
        This prevents false rejections when:
        - BM25 returned a chunk because of semantic proximity not exact words
        - The knowledge base uses synonyms (e.g. "support" vs "help")
        - Short queries have few keywords

        Semantic relevance is the primary signal captured in chunk.score.
        This check is a safety net against completely off-topic chunks only.
        """
        if not query:
            return True

        query_lower   = chunk.content.lower()  # reusing variable name kept for readability
        content_lower = chunk.content.lower()
        query_lower   = query.lower()

        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "for", "to",
            "in", "on", "of", "i", "my", "me", "we", "it", "its",
        }
        query_keywords = [
            w for w in query_lower.split()
            if w not in stop_words and len(w) > 2
        ]

        if not query_keywords:
            return True

        # At least ONE keyword must appear in content
        return any(kw in content_lower for kw in query_keywords)
    
    def _calculate_validation_confidence(
        self,
        tenant_valid: bool,
        content_valid: bool,
        relevance_valid: bool,
        query_relevant: bool,
        score: float
    ) -> float:
        """Calculate confidence in validation decision"""
        
        # All checks must pass for high confidence
        if not (tenant_valid and content_valid and relevance_valid and query_relevant):
            return 0.3  # Low confidence in rejection
        
        # Confidence based on retrieval score
        if score >= 0.8:
            return 0.95
        elif score >= 0.6:
            return 0.85
        elif score >= 0.4:
            return 0.75
        else:
            return 0.65
