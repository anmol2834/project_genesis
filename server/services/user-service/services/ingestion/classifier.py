"""
Category Classifier + Subtype Detector
Uses intfloat/e5-base-v2 to classify each data row into category + subtype.

Confidence merge (enforced at pipeline):
  ai_confidence > 0.75  -> ai_category wins
  elif user_category    -> user_category wins
  else                  -> "uncategorized"
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

AI_CONFIDENCE_THRESHOLD = 0.75

CATEGORY_PROTOTYPES: Dict[str, List[str]] = {
    "product_service": [
        "product catalog item with name features and specifications",
        "product SKU description availability stock variants size color",
        "service offering description usage instructions demo",
        "software product SaaS tool platform features availability",
    ],
    "issue_resolution": [
        "problem error bug troubleshooting steps fix resolution solution",
        "issue reported root cause diagnosed resolved fixed workaround",
        "technical problem device failure login error integration not working",
        "customer complaint issue raised resolved support ticket closed",
        "hardware damaged software crash payment failed order not delivered",
        "account locked access denied connection refused error code",
    ],
    "contact_support": [
        "contact phone number email address support hours",
        "live chat WhatsApp office location customer support",
        "team member employee role department contact information",
        "business contact details phone number email timezone",
    ],
    "offers_promotions": [
        "special offer discount promotion deal promo code coupon",
        "seasonal offer festival clearance sale loyalty program",
        "referral bonus limited time deal reward incentive",
        "holiday deal percentage off new users only valid until",
    ],
    "delivery_shipping": [
        "delivery timeline shipping charges serviceable locations",
        "tracking options return replacement process logistics",
        "free shipping above order value nationwide delivery days",
        "return window refund shipping policy courier partner",
    ],
    "company_info": [
        "company about us brand story mission certifications",
        "founded team size headquarters media mentions awards",
        "company overview values culture history milestones",
        "business profile about company credentials recognition",
    ],
    "policies_legal": [
        "privacy policy terms conditions warranty return refund",
        "legal information governing law compliance data usage",
        "cancellation policy warranty period refund timeline",
        "terms of service user agreement intellectual property",
    ],
    "educational_content": [
        "frequently asked question answer FAQ guide tutorial",
        "knowledge base article troubleshooting steps how to",
        "support documentation onboarding walkthrough help",
        "common question customer support answer solution",
    ],
}

SUBTYPE_PROTOTYPES: Dict[str, Dict[str, List[str]]] = {
    "issue_resolution": {
        "hardware":     ["hardware damage physical device broken screen battery"],
        "software":     ["software crash bug error application not opening frozen"],
        "account":      ["login failed account locked password reset access denied"],
        "integration":  ["integration not working API connection failed webhook error"],
        "payment":      ["payment failed deducted charged refund not processed"],
        "order":        ["order not delivered missing shipment tracking issue"],
        "network":      ["network connectivity internet connection timeout unreachable"],
        "general":      ["general issue miscellaneous problem unclassified error"],
    },
    "pricing_payment": {
        "plan":           ["subscription plan tier starter pro enterprise pricing"],
        "one_time":       ["one time payment purchase fee charge single"],
        "discount":       ["discount coupon promo code reduction savings"],
        "refund_policy":  ["refund policy money back guarantee cancellation"],
        "payment_method": ["payment method UPI card EMI bank transfer"],
    },
    "contact_support": {
        "support": ["customer support helpdesk technical help ticket"],
        "sales":   ["sales team business development contact sales"],
        "general": ["general contact office address phone email"],
        "social":  ["social media twitter linkedin instagram facebook"],
    },
    "product_service": {
        "product":  ["physical product item SKU catalog inventory"],
        "service":  ["service offering consulting implementation"],
        "software": ["software SaaS platform tool application feature"],
        "digital":  ["digital download ebook course content"],
    },
    "offers_promotions": {
        "seasonal": ["seasonal festival holiday sale limited time"],
        "referral": ["referral bonus invite friend reward"],
        "loyalty":  ["loyalty program points reward membership"],
        "flash":    ["flash sale limited hours today only urgent"],
    },
    "educational_content": {
        "faq":          ["frequently asked question answer FAQ"],
        "tutorial":     ["tutorial guide step by step how to"],
        "troubleshoot": ["troubleshooting error fix problem solution"],
        "onboarding":   ["onboarding getting started setup first time"],
    },
    "policies_legal": {
        "privacy":  ["privacy policy data protection GDPR"],
        "terms":    ["terms of service user agreement conditions"],
        "refund":   ["refund return policy money back"],
        "warranty": ["warranty guarantee product coverage"],
    },
    "delivery_shipping": {
        "domestic":      ["domestic shipping local delivery within country"],
        "international": ["international shipping global worldwide"],
        "return":        ["return policy exchange replacement process"],
        "tracking":      ["tracking order status shipment courier"],
    },
    "company_info": {
        "about":       ["about us company story founding history"],
        "team":        ["team members employees founders leadership"],
        "achievement": ["awards certifications media mentions recognition"],
        "mission":     ["mission vision values culture purpose"],
    },
}

CATEGORIES = list(CATEGORY_PROTOTYPES.keys())

_model = None
_proto_embeddings: Dict[str, np.ndarray] = {}
_subtype_embeddings: Dict[str, Dict[str, np.ndarray]] = {}


def _get_model():
    global _model
    if _model is None:
        from services.ingestion.model_singleton import get_shared_model
        _model = get_shared_model()
        logger.info("Classifier: e5-base-v2 loaded")
    return _model


def _get_proto_embeddings() -> Dict[str, np.ndarray]:
    global _proto_embeddings
    if not _proto_embeddings:
        model = _get_model()
        for cat, phrases in CATEGORY_PROTOTYPES.items():
            encoded = [f"passage: {p}" for p in phrases]
            embs = model.encode(encoded, normalize_embeddings=True, batch_size=32)
            mean_emb = embs.mean(axis=0)
            norm = np.linalg.norm(mean_emb)
            _proto_embeddings[cat] = mean_emb / norm if norm > 0 else mean_emb
        logger.info(f"Classifier: {len(_proto_embeddings)} category prototypes computed")
    return _proto_embeddings


def _get_subtype_embeddings() -> Dict[str, Dict[str, np.ndarray]]:
    global _subtype_embeddings
    if not _subtype_embeddings:
        model = _get_model()
        for cat, subtypes in SUBTYPE_PROTOTYPES.items():
            _subtype_embeddings[cat] = {}
            for subtype, phrases in subtypes.items():
                encoded = [f"passage: {p}" for p in phrases]
                embs = model.encode(encoded, normalize_embeddings=True, batch_size=32)
                mean_emb = embs.mean(axis=0)
                norm = np.linalg.norm(mean_emb)
                _subtype_embeddings[cat][subtype] = mean_emb / norm if norm > 0 else mean_emb
        logger.info(f"Classifier: subtype embeddings computed for {len(_subtype_embeddings)} categories")
    return _subtype_embeddings


def _classify_subtype(query_emb: np.ndarray, category: str) -> Optional[str]:
    subtype_embs = _get_subtype_embeddings()
    cat_subtypes = subtype_embs.get(category)
    if not cat_subtypes:
        return None
    best_subtype, best_score = None, -1.0
    for subtype, proto_emb in cat_subtypes.items():
        score = float(np.dot(query_emb, proto_emb))
        if score > best_score:
            best_score = score
            best_subtype = subtype
    return best_subtype


def _row_to_text(row: Dict[str, Any]) -> str:
    parts = []
    for k, v in row.items():
        if v and str(v).strip():
            parts.append(f"{k.replace('_', ' ')}: {str(v).strip()}")
    return ". ".join(parts)


def classify_text(text: str) -> Tuple[str, Optional[str], float]:
    """
    Classify free-form text into (category, subtype, confidence).
    """
    if not text.strip():
        return "uncategorized", None, 0.0

    model = _get_model()
    proto_embs = _get_proto_embeddings()

    query_emb = model.encode([f"query: {text[:512]}"], normalize_embeddings=True)[0]

    best_cat, best_score = "uncategorized", -1.0
    for cat, proto_emb in proto_embs.items():
        score = float(np.dot(query_emb, proto_emb))
        if score > best_score:
            best_score = score
            best_cat = cat

    subtype = _classify_subtype(query_emb, best_cat)
    logger.debug(f"Classified: '{best_cat}/{subtype}' conf={best_score:.3f}: {text[:80]}")
    return best_cat, subtype, round(best_score, 4)


def classify_row(row: Dict[str, Any]) -> Tuple[str, Optional[str], float]:
    return classify_text(_row_to_text(row))


def classify_batch(rows: List[Dict[str, Any]]) -> List[Tuple[str, Optional[str], float]]:
    """
    Batch classify rows — single model.encode call for performance.
    Returns list of (category, subtype, confidence).
    """
    if not rows:
        return []

    model = _get_model()
    proto_embs = _get_proto_embeddings()

    texts = [f"query: {_row_to_text(r)[:512]}" for r in rows]
    embs = model.encode(texts, normalize_embeddings=True, batch_size=32)

    results = []
    for emb in embs:
        best_cat, best_score = "uncategorized", -1.0
        for cat, proto_emb in proto_embs.items():
            score = float(np.dot(emb, proto_emb))
            if score > best_score:
                best_score = score
                best_cat = cat
        subtype = _classify_subtype(emb, best_cat)
        results.append((best_cat, subtype, round(best_score, 4)))

    logger.info(f"Batch classified {len(rows)} rows")
    return results


def merge_category(
    ai_category: str,
    ai_confidence: float,
    user_category: Optional[str],
) -> Tuple[str, str]:
    """
    Category merge logic.

    Rule: the user explicitly selected a category in the UI before uploading.
    That selection is ALWAYS respected as the final category.
    AI classification is used ONLY as a fallback when the user did NOT select
    a category (i.e. user_category is None/"uncategorized"/"").

    This prevents the AI from overriding explicit user intent — the #1 cause
    of miscategorised entries.

    Returns (final_category, decision_reason).
    """
    # User explicitly chose a category — always honour it
    if user_category and user_category not in ("uncategorized", ""):
        return user_category, f"user_selected (ai_was={ai_category} conf={ai_confidence:.2f})"

    # No user category — trust AI only if confidence is high enough
    if ai_confidence > AI_CONFIDENCE_THRESHOLD and ai_category not in ("uncategorized", ""):
        return ai_category, f"ai_classified (conf={ai_confidence:.2f})"

    return "uncategorized", f"low_confidence_no_user_category (conf={ai_confidence:.2f})"
