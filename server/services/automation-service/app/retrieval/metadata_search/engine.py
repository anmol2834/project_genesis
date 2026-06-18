"""
L3 Metadata Search Engine
==========================
Structured field filtering on categories, prices, features, departments.

Performance: <50ms
"""

import logging
from typing import List, Dict, Optional, Any

from app.retrieval.schemas import RetrievedChunk, ChunkType, RetrievalSource

# ── Attribute compatibility shim ──────────────────────────────────────────────
# The schemas.RetrievalSource enum uses L4_METADATA for the metadata-filter layer.
# Older code in this file was written against app.models.enums.RetrievalSource
# which used L3_METADATA.  The canonical attribute in schemas is L4_METADATA.
_METADATA_SOURCE = RetrievalSource.L4_METADATA

logger = logging.getLogger(__name__)


class MetadataSearchEngine:
    """
    L3 metadata filtering on structured fields.
    
    Filters:
    - category (drones, cameras, training)
    - price range (min/max)
    - features (4K, GPS, thermal)
    - department (sales, support)
    - availability (in_stock, pre_order)
    """
    
    def __init__(self, qdrant_repository):
        """
        Initialize metadata search engine.
        
        Args:
            qdrant_repository: Qdrant repository for vector DB access
        """
        self.qdrant = qdrant_repository
    
    async def search_metadata(
        self,
        user_id: str,
        filters: Dict[str, Any],
        top_k: int = 10
    ) -> List[RetrievedChunk]:
        """
        Search by metadata filters.
        
        Args:
            user_id: Tenant ID (mandatory)
            filters: Metadata filters
                {
                    "category": "drones",
                    "price_min": 1000,
                    "price_max": 50000,
                    "features": ["4K", "GPS"],
                    "chunk_type": "product_service"
                }
            top_k: Maximum results
            
        Returns:
            List of matching chunks
        """
        if not user_id or not filters:
            return []
        
        try:
            # Scroll Qdrant with metadata filters
            # Note: user_id filter is enforced by repository
            results = await self.qdrant.scroll(
                user_id=user_id,
                filters=filters,
                limit=top_k
            )
            
            # Convert to RetrievedChunk
            chunks = []
            for result in results:
                payload = result.get("payload", {})
                
                # Calculate metadata match score
                score = self._calculate_metadata_score(payload, filters)
                
                chunk = RetrievedChunk(
                    content=payload.get("content", ""),
                    score=score,
                    chunk_type=ChunkType(payload.get("chunk_type", "general")),
                    chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                    source=_METADATA_SOURCE,
                    user_id=user_id,
                    metadata=payload,
                    retrieval_layer="L4"
                )
                chunks.append(chunk)
            
            # Sort by score
            chunks.sort(key=lambda c: c.score, reverse=True)
            
            logger.info(f"L3 metadata: filters={filters} found={len(chunks)}")
            
            return chunks[:top_k]
            
        except Exception as e:
            logger.error(f"L3 metadata search error: {e}")
            return []
    
    def _calculate_metadata_score(
        self,
        payload: Dict,
        filters: Dict
    ) -> float:
        """
        Calculate match score based on metadata filters.
        
        Score components:
        - Category match: +0.5
        - Price in range: +0.3
        - Features match: +0.2 per feature
        """
        score = 0.0
        
        # Category match
        if "category" in filters:
            if payload.get("category", "").lower() == filters["category"].lower():
                score += 0.5
        
        # Price range match
        price = payload.get("price")
        if price:
            in_range = True
            
            if "price_min" in filters and price < filters["price_min"]:
                in_range = False
            
            if "price_max" in filters and price > filters["price_max"]:
                in_range = False
            
            if in_range:
                score += 0.3
        
        # Features match
        if "features" in filters:
            required_features = set(f.lower() for f in filters["features"])
            chunk_features = set(f.lower() for f in payload.get("features", []))
            
            matched_features = required_features & chunk_features
            feature_match_ratio = len(matched_features) / len(required_features) if required_features else 0
            
            score += 0.2 * feature_match_ratio
        
        # Normalize to [0, 1]
        return min(1.0, score)
    
    def build_filters_from_entities(
        self,
        entities: Dict,
        intent: str
    ) -> Dict[str, Any]:
        """
        Build Qdrant filters from extracted entities.
        Handles structured hardware specs (CPU, RAM, Storage, GPU, Brand, Generation)
        extracted by Brain #1 into technical_terms and features.
        """
        filters = {}

        # Category filter
        if entities.get("category"):
            filters["category"] = entities["category"]

        # Price range filter
        if "price_min" in entities:
            filters["price_min"] = entities["price_min"]
        if "price_max" in entities:
            filters["price_max"] = entities["price_max"]

        # Features filter
        if entities.get("features"):
            filters["features"] = entities["features"]

        # ── Structured hardware/spec attribute extraction ──────────────
        # Brain #1 puts CPU/RAM/Storage/GPU into technical_terms and features.
        # Extract them into structured spec filters so L4 metadata search works.
        tech_terms = list(entities.get("technical_terms", []) or [])
        feat_terms = list(entities.get("features", []) or [])
        all_terms  = tech_terms + feat_terms

        specs = self._extract_hardware_specs(all_terms)
        if specs:
            filters.update(specs)

        # Chunk type filter based on intent
        # Values must match exact "category" strings in user_data_entries.
        # The 8 real Qdrant categories are:
        #   product_service, offers_promotions, delivery_shipping, company_info,
        #   educational_content, contact_support, policies_legal, issue_resolution
        # pricing_inquiry uses NO category filter (empty filters) because pricing data
        # spans product_service, offers_promotions, AND delivery_shipping.
        _INTENT_TO_CHUNK = {
            "support_request":           "contact_support",
            "technical_support_request": "issue_resolution",
            "technical_assistance":      "issue_resolution",
            "complaint":                 "contact_support",
            "pricing_inquiry":           None,   # no filter — prices span multiple categories
            "product_inquiry":           "product_service",
            "feature_request":           "product_service",
            "general_inquiry":           "product_service",
            "offers_inquiry":            "offers_promotions",
            "shipping_inquiry":          "delivery_shipping",
            "company_inquiry":           "company_info",
            "educational_inquiry":       "educational_content",
            "refund_request":            "policies_legal",
            "billing_inquiry":           "policies_legal",
            "issue_inquiry":             "issue_resolution",
            "issue_resolution":          "issue_resolution",
        }
        mapped_type = _INTENT_TO_CHUNK.get(intent)
        if mapped_type:
            filters["chunk_type"] = mapped_type
        # if mapped_type is None (pricing_inquiry) or missing → no chunk_type filter added

        return filters

    def _extract_hardware_specs(self, terms: list) -> Dict[str, Any]:
        """
        Parse hardware specification strings into structured filter fields.
        Handles patterns like: 'i5', '8GB RAM', '512GB SSD', 'RTX 3050', 'Intel', '11th Gen'.
        """
        import re
        specs: Dict[str, Any] = {}

        for term in terms:
            if not term:
                continue
            t = term.strip().lower()

            # CPU: i3/i5/i7/i9, Ryzen 3/5/7/9, M1/M2/M3
            if re.search(r'\bi[3579]\b', t) or re.search(r'ryzen\s*[3579]', t) or re.search(r'\bm[123]\b', t):
                specs["cpu"] = term.strip()

            # RAM: 4GB/8GB/16GB/32GB
            elif re.search(r'(\d+)\s*gb\s*(ram|memory)?', t) and not re.search(r'(ssd|hdd|nvme|storage)', t):
                m = re.search(r'(\d+)\s*gb', t)
                if m:
                    specs["ram_gb"] = int(m.group(1))

            # Storage: 256GB SSD / 512GB HDD / 1TB
            elif re.search(r'(\d+)\s*(gb|tb)\s*(ssd|hdd|nvme|storage)?', t) and re.search(r'(ssd|hdd|nvme|storage|tb)', t):
                m = re.search(r'(\d+)\s*(gb|tb)', t)
                if m:
                    val = int(m.group(1))
                    unit = m.group(2).lower()
                    specs["storage_gb"] = val * 1024 if unit == "tb" else val
                    specs["storage_type"] = "ssd" if "ssd" in t or "nvme" in t else "hdd"

            # GPU: RTX/GTX/RX + model number
            elif re.search(r'(rtx|gtx|rx)\s*\d+', t):
                specs["gpu"] = term.strip()

            # Generation: 11th Gen, 12th Gen, Gen 4
            elif re.search(r'(\d+)(st|nd|rd|th)\s*gen', t) or re.search(r'gen\s*(\d+)', t):
                m = re.search(r'(\d+)', t)
                if m:
                    specs["generation"] = int(m.group(1))

            # Brand: Intel, AMD, Apple, Dell, HP, Lenovo, Asus, Acer
            elif t in {"intel", "amd", "apple", "dell", "hp", "lenovo", "asus", "acer",
                       "samsung", "microsoft", "lg", "msi", "gigabyte"}:
                specs["brand"] = term.strip()

        return specs
    
    def has_meaningful_filters(self, filters: Dict) -> bool:
        """
        Check if filters are meaningful enough for L4 search.
        Now includes hardware spec filters (cpu, ram_gb, storage_gb, gpu, brand, generation).
        """
        if not filters:
            return False

        spec_keys = {"category", "price_min", "price_max", "features",
                     "cpu", "ram_gb", "storage_gb", "storage_type",
                     "gpu", "brand", "generation", "chunk_type"}
        return any(k in filters for k in spec_keys)
