"""
LLM - Orchestrator
==================
ChatGPT Brain #2: Response generation with grounding, hallucination guard,
and a 5-tier fallback chain that prevents pipeline collapse.

Fallback tiers (executed in order on any OpenAI failure):
  T1: OpenAI GPT           — primary path
  T2: Cached intelligence  — Redis pattern cache
  T3: Retrieval-only mode  — structured context without LLM
  T4: Rule-based emergency — deterministic intent templates
  T5: Human handoff        — guaranteed escalation, zero I/O
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from openai import AsyncOpenAI
from app.core.config import get_config
from app.observability import get_logger
from app.core.utf8_enforcement import sanitize_openai_response
from app.llm.providers.fallback_chain import FallbackChain

logger = get_logger(__name__)


class LLMOrchestrator:
    """
    LLM orchestration engine.
    Generates grounded responses and validates against hallucination.
    """

    def __init__(self):
        self.config = get_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.get_openai_api_key())
        self.model = self.config.shared.OPENAI_MODEL
        self.max_tokens = 500
        self._fallback_chain: Optional[FallbackChain] = None

    def _get_fallback_chain(self) -> FallbackChain:
        """Return (and lazily create) the multi-tier fallback chain."""
        if self._fallback_chain is None:
            try:
                from app.core.resource_management import get_resource_manager
                redis = get_resource_manager().get_redis()
            except Exception:
                redis = None
            self._fallback_chain = FallbackChain(
                openai_client=self.openai_client,
                redis_client=redis,
                model=self.model,
                max_tokens=self.max_tokens,
            )
        return self._fallback_chain

    async def generate_response(
        self,
        intelligence: Dict[str, Any],
        retrieval: Dict[str, Any],
        memory: Dict[str, Any],
        message_content: str,
        subject: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Generate AI response with L10 fact-graph grounding, hallucination guard,
        and enterprise 5-tier fallback chain (never collapses).

        FLOW:
        1. Pre-generation grounding validation
        2. L10 Fact graph compression
        3. Grounded prompt builder
        4. Brain #2 generation (with fallback chain: T1->T2->T3->T4->T5)
        5. UTF-8 sanitization
        6. Post-generation hallucination check
        7. Catalog response validation
        8. Confidence calculation
        """
        import time
        start = time.perf_counter()

        try:
            from app.llm.hallucination_guard import get_grounding_validator

            # -- PRE-GENERATION GROUNDING VALIDATION --
            validator = get_grounding_validator()
            grounding_result = validator.validate(
                chunks=retrieval.get("chunks", []),
                intelligence=intelligence,
                user_id=memory.get("user_id", ""),
                query=message_content,
            )

            if grounding_result.escalate:
                logger.warning(
                    "Grounding failed catastrophically | confidence=%.3f accepted=0",
                    grounding_result.overall_confidence,
                    trace_id=trace_id,
                )

            # -- L10: Fact Graph Compression (validated chunks only) --
            prompt, prompt_obs, fact_graph = await self._build_grounded_prompt_async(
                intelligence=intelligence,
                retrieval_chunks=grounding_result.validated_chunks,
                memory=memory,
                message=message_content,
                subject=subject,
                grounding_confidence=grounding_result.overall_confidence,
            )

            # -- Brain #2 Generation (with FALLBACK CHAIN) --
            chain = self._get_fallback_chain()
            fallback_result = await chain.execute(
                prompt=prompt,
                intelligence=intelligence,
                retrieval=retrieval,
                memory=memory,
                message_content=message_content,
                subject=subject,
                trace_id=trace_id,
                grounding_result=grounding_result,
            )

            # -- UTF-8 Sanitization --
            response_text = sanitize_openai_response(fallback_result.response_text)

            # -- Post-generation Hallucination Guard --
            hallucination_check = self._check_hallucination(
                response_text=response_text,
                validated_chunks=grounding_result.validated_chunks,
                rejected_chunks=grounding_result.rejected_chunks,
                intelligence=intelligence,
                grounding_result=grounding_result,
            )

            # -- Catalog Response Validation --
            # When customer asks about products/services and catalog data was
            # retrieved, verify the response contains actual catalog content.
            response_text = self._validate_catalog_response(
                response_text=response_text,
                retrieval=retrieval,
                intelligence=intelligence,
                grounding_result=grounding_result,
                message_content=message_content,
                fact_graph=fact_graph,
            )

            # -- Confidence Calculation --
            confidence = self._calculate_generation_confidence(
                retrieval_confidence=retrieval["retrieval_confidence"],
                grounding_confidence=grounding_result.overall_confidence,
                post_gen_grounding_score=hallucination_check["grounding_score"],
                intent_confidence=(
                    intelligence.get("confidence", 0.5)
                    if isinstance(intelligence, dict)
                    else getattr(
                        getattr(intelligence, "conversation_analysis", None),
                        "intent_confidence", 0.5
                    )
                ),
                fallback_confidence=fallback_result.confidence,
            )

            elapsed = (time.perf_counter() - start) * 1000

            result = {
                "response_text":          response_text,
                "confidence":             confidence,
                "hallucination_detected": hallucination_check["hallucination_detected"],
                "grounding_score":        hallucination_check["grounding_score"],
                "tokens_used":            fallback_result.tokens_used,
                "generation_latency_ms":  elapsed,
                "model":                  fallback_result.model,
                "fallback_tier":          fallback_result.tier_used,
                "fallback_tier_name":     fallback_result.tier_name,
                "fallback_error_chain":   fallback_result.error_chain,
                "escalate_to_human":      fallback_result.escalate_to_human,
                "prompt_route":           prompt_obs.get("prompt_route", ""),
                "prompt_tokens_est":      prompt_obs.get("prompt_tokens_est", 0),
                "fact_graph_sections":    prompt_obs.get("fact_graph_sections", 0),
                "compression_ratio":      prompt_obs.get("compression_ratio", 1.0),
                "prompt_layers":          prompt_obs.get("layers_applied", []),
                "pre_gen_grounding": {
                    "overall_confidence": grounding_result.overall_confidence,
                    "accepted_chunks":    grounding_result.accepted_count,
                    "rejected_chunks":    grounding_result.rejected_count,
                    "pricing_conflicts":  len(grounding_result.pricing_conflicts),
                    "tenant_violations":  grounding_result.tenant_violations,
                    "category_violations": grounding_result.category_violations,
                    "escalate":           grounding_result.escalate or fallback_result.escalate_to_human,
                },
            }

            logger.info(
                "Response generated | confidence=%.2f tier=%d(%s) grounding_pre=%.2f "
                "grounding_post=%.2f hallucination=%s accepted=%d rejected=%d tokens=%d",
                confidence, fallback_result.tier_used, fallback_result.tier_name,
                grounding_result.overall_confidence,
                hallucination_check["grounding_score"],
                hallucination_check["hallucination_detected"],
                grounding_result.accepted_count, grounding_result.rejected_count,
                fallback_result.tokens_used, trace_id=trace_id,
            )

            return result

        except Exception as e:
            logger.error("Response generation catastrophic failure: %s", e,
                         trace_id=trace_id, exc_info=True)
            elapsed = (time.perf_counter() - start) * 1000
            return {
                "response_text":          "We apologise for the inconvenience. Our systems are currently experiencing a temporary issue.\n\nHere is what we are doing:\n\n- Our technical team has been notified.\n- A team member will personally review your message and respond shortly.\n- For urgent matters, please reply to this email.\n\nThank you for your patience.",
                "confidence":             0.05,
                "hallucination_detected": False,
                "grounding_score":        0.0,
                "tokens_used":            0,
                "generation_latency_ms":  elapsed,
                "error":                  str(e),
                "fallback_tier":          6,
                "fallback_tier_name":     "catastrophic_failure",
                "fallback_error_chain":   [str(e)],
                "escalate_to_human":      True,
                "prompt_route":           "catastrophic",
                "prompt_tokens_est":      0,
                "fact_graph_sections":    0,
                "compression_ratio":      1.0,
                "prompt_layers":          [],
                "pre_gen_grounding":      {"escalate": True},
            }

    async def _build_grounded_prompt_async(
        self,
        intelligence: Any,
        retrieval_chunks: List[Dict],
        memory: Dict,
        message: str,
        subject: str,
        grounding_confidence: float,
    ) -> tuple[str, dict]:
        """
        Build grounded prompt using PromptRouter (modular) + L10 Fact Graph.

        Returns (assembled_prompt_str, prompt_observability_dict)

        NEVER injects raw chunks — all context flows through:
          validated_chunks -> FactGraphCompressor -> PromptRouter
        """
        from app.llm.grounding.fact_graph_compressor import get_fact_graph_compressor
        from app.llm.prompt_builder import get_prompt_router

        compressor    = get_fact_graph_compressor()
        prompt_router = get_prompt_router()
        user_id       = memory.get("user_id", "")

        # -- L10: Fact Graph Compression --
        try:
            # Pass intelligence directly — compress_to_fact_graph handles both
            # dataclass (Pydantic model) and dict. Using __dict__ on a Pydantic v2
            # model does NOT produce a plain dict and corrupts nested objects.
            fact_graph = await compressor.compress_to_fact_graph(
                retrieval_chunks=retrieval_chunks,
                intelligence=intelligence,
                user_id=user_id,
                grounding_confidence=grounding_confidence,
            )
        except Exception as e:
            logger.warning("Fact graph compression failed: %s", e)
            fact_graph = None

        # -- Format fact graph -> context string --
        # CRITICAL: The context must be formatted so the LLM treats it as authoritative
        # ground truth. The VERIFIED CONTEXT section must contain explicit product names
        # and prices exactly as stored — no numbered generic placeholders.
        if fact_graph and (
            fact_graph.get("products") or fact_graph.get("pricing")
            or fact_graph.get("support") or fact_graph.get("features")
            or fact_graph.get("policies") or fact_graph.get("analytics")
        ):
            fact_graph_context = compressor.format_for_llm(fact_graph)
        elif retrieval_chunks:
            # IMPORTANT: Do NOT inject numbered [1] [2] [3] items here — the LLM
            # interprets these as "Product 1", "Product 2", "Product 3" and hallucinates
            # generic placeholder names.  Instead, try to build a minimal named product
            # list directly from the chunk payloads before giving up.
            named_lines = []
            for c in retrieval_chunks[:8]:
                meta = c.get("metadata", {})
                if not isinstance(meta, dict):
                    meta = {}
                # Extract name from any available field
                item_name = (
                    meta.get("name", "")
                    or meta.get("title", "")
                    or (meta.get("attributes") or {}).get("name", "")
                    or (meta.get("structured_data") or {}).get("product_name", "")
                    or (meta.get("structured_data") or {}).get("offer_title", "")
                    or (meta.get("structured_data") or {}).get("name", "")
                ).strip()
                if not item_name:
                    # last resort: first Title Case sequence from content
                    import re as _re_fb
                    m = _re_fb.search(
                        r"\b([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){1,4})\b",
                        c.get("content", ""),
                    )
                    if m:
                        item_name = m.group(1)
                if not item_name:
                    continue
                # Extract price
                attrs   = meta.get("attributes") or {}
                sd      = meta.get("structured_data") or {}
                price   = attrs.get("price") or sd.get("price") or ""
                content = c.get("content", "")
                # currency from content
                import re as _re_c
                if "\u20b9" in content or "INR" in content.upper():
                    sym = "\u20b9"
                elif "\u20ac" in content:
                    sym = "\u20ac"
                elif "\u00a3" in content:
                    sym = "\u00a3"
                else:
                    sym = "$"
                try:
                    numeric = _re_c.sub(r"[^\d.]", "", str(price).replace(",", ""))
                    price_str = f"{sym}{int(float(numeric))}" if numeric else ""
                except Exception:
                    price_str = ""
                line = f"- {item_name}"
                if price_str:
                    line += f"  (Price: {price_str})"
                named_lines.append(line)
            if named_lines:
                fact_graph_context = "AVAILABLE ITEMS:\n" + "\n".join(named_lines)
            else:
                fact_graph_context = "No specific verified information available for this query."
        else:
            fact_graph_context = "No specific verified information available for this query."

        # -- Detect price conflicts for risk layer --
        has_price_conflict = bool(
            fact_graph and any(p.get("price_conflict") for p in fact_graph.get("products", []))
        )

        # -- PromptRouter: assemble layered prompt --
        build_result = prompt_router.build(
            intelligence=intelligence,
            fact_graph_context=fact_graph_context,
            memory=memory,
            message=message,
            subject=subject,
            grounding_confidence=grounding_confidence,
            has_price_conflict=has_price_conflict,
        )

        # -- Final OpenAI messages format --
        final_prompt = (
            build_result.system_prompt
            + "\n\n---\nCUSTOMER MESSAGE:\n"
            + build_result.user_message
            + "\n\nYour response:"
        )

        prompt_obs = {
            "prompt_route":        build_result.prompt_route,
            "prompt_tokens_est":   build_result.estimated_total_tokens,
            "fact_graph_sections": build_result.fact_graph_sections,
            "compression_ratio":   build_result.compression_ratio,
            "removed_duplicates":  build_result.removed_duplicates,
            "layers_applied":      build_result.layers_applied,
            "role_selected":       build_result.role_selected,
            "has_risk_warning":    build_result.has_risk_warning,
            "multilingual":        build_result.has_multilingual,
        }

        return final_prompt, prompt_obs, fact_graph

    async def _call_openai_generation(
        self,
        prompt: str,
        trace_id: str
    ) -> tuple[str, int]:
        """Call OpenAI for response generation (used internally by FallbackChain T1)."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=self.max_tokens,
                timeout=30.0,
            )
            response_text = sanitize_openai_response(
                response.choices[0].message.content.strip()
            )
            tokens_used = response.usage.total_tokens
            return response_text, tokens_used

        except Exception as e:
            logger.error("OpenAI generation failed: %s", e, trace_id=trace_id)
            raise

    def _validate_catalog_response(
        self,
        response_text: str,
        retrieval: Dict,
        intelligence: Any,
        grounding_result: Any,
        message_content: str,
        fact_graph: Optional[Dict] = None,
    ) -> str:
        """
        Post-generation validation gate.

        Catches three classes of LLM failure:
          1. Spec hallucination — LLM assigns wrong specs to real product names
             (e.g. "IngenAI Gamer 15: 8GB RAM" when Gamer 15 has 16GB RAM)
          2. Generic placeholders — "Product 1", "Service A", etc.
          3. Placeholder brackets — [Product Name A], [Price], etc.

        When any violation is detected AND the fact_graph has real products,
        the response is rebuilt deterministically from the fact_graph — NOT
        from the LLM output. This guarantees accuracy.

        For all other catalog responses, a lightweight catalog-content check
        ensures the response contains actual product/service information.
        """
        import re as _re_llm

        # ─── Build fact-graph product registry for spec validation ────────────────
        # Maps product_name_lower → {price, currency, specs, category}
        # Used to detect when the LLM assigns wrong specs to a real product name.
        _fg_products: Dict[str, Dict] = {}
        if fact_graph and fact_graph.get("products"):
            for p in fact_graph["products"]:
                n = (p.get("name") or "").strip()
                if n:
                    _fg_products[n.lower()] = p

        # Helper: build a full product listing from fact_graph (authoritative)
        def _build_from_fact_graph(fg: Optional[Dict], header: str = "") -> str:
            """Build a deterministic, accurate response from the fact graph.

            Priority order:
            1. support section (contact info, support articles, issue resolution)
            2. products section (product/service catalog)
            3. analytics section (catalog overview — NEVER renders raw internal titles)
            4. policies section
            5. features section
            """
            if not fg:
                return ""

            sections: List[str] = []
            sym_map = {"INR": "\u20b9", "EUR": "\u20ac", "GBP": "\u00a3", "USD": "$"}

            # Support section — contact details, issue resolution, FAQs
            if fg.get("support"):
                sup_lines: List[str] = []
                for s in fg["support"]:
                    topic = s.get("topic") or s.get("department") or ""
                    solution = s.get("solution") or ""
                    email = s.get("contact_email") or ""
                    phone = s.get("contact_phone") or ""
                    avail = s.get("availability") or ""
                    if topic:
                        line = f"- **{topic}**"
                        if solution and solution != topic:
                            line += f"\n   {solution[:200]}"
                        if email:
                            line += f"\n   Email: {email}"
                        if phone:
                            line += f"\n   Phone: {phone}"
                        if avail:
                            line += f"\n   Hours: {avail}"
                        sup_lines.append(line)
                    elif email or phone:
                        line = "- Contact"
                        if email:
                            line += f"\n   Email: {email}"
                        if phone:
                            line += f"\n   Phone: {phone}"
                        sup_lines.append(line)
                    elif solution:
                        sup_lines.append(f"- {solution[:200]}")
                if sup_lines:
                    hdr = header or "Here is the contact information:"
                    sections.append(hdr + "\n\n" + "\n\n".join(sup_lines))

            # Products section
            if fg.get("products"):
                prod_lines: List[str] = []
                for p in fg["products"]:
                    name = p.get("name", "Unknown")
                    line = f"- **{name}**"
                    price = p.get("price")
                    if price and not p.get("price_conflict"):
                        currency_val = p.get("currency") or "USD"
                        sym = sym_map.get(currency_val.upper() if currency_val else "USD", "\u20b9")
                        line += f"\n   - Price: {sym}{price}"
                    cat = p.get("category")
                    if cat:
                        line += f"\n   - Category: {cat}"
                    specs = p.get("specifications") or {}
                    spec_parts = [f"{k.title()}: {v}" for k, v in list(specs.items())[:4] if v]
                    if spec_parts:
                        line += "\n   - Specs: " + ", ".join(spec_parts)
                    feats = p.get("features") or []
                    if feats:
                        line += "\n   - Features: " + ", ".join(str(f) for f in feats[:3])
                    prod_lines.append(line)
                if prod_lines:
                    hdr = header if header and not sections else (
                        "Here are the available options in our catalog:" if not sections else ""
                    )
                    block = ("\n\n" if sections else "") + (hdr + "\n\n" if hdr else "") + "\n\n".join(prod_lines)
                    sections.append(block.strip())

            # Analytics section — ONLY use intelligence_summary, price_range, all_item_names
            # NEVER use the analytics chunk title (which is an internal filename like
            # "Analytics: ingenai_delivery_shipping_mock_data") as a display name.
            if fg.get("analytics") and not sections:
                ana_parts: List[str] = []
                for a in fg["analytics"]:
                    summary = a.get("intelligence_summary") or a.get("summary") or ""
                    # Strip internal filename prefixes from summaries
                    import re as _re_ana
                    summary = _re_ana.sub(
                        r"^Analytics:\s+\S+\s*\|?\s*", "", summary, flags=_re_ana.IGNORECASE
                    ).strip()
                    if summary and len(summary) > 20:
                        ana_parts.append(summary)
                    price_range = a.get("price_range")
                    if price_range:
                        ana_parts.append(f"Price range: {price_range}")
                    all_names = a.get("all_item_names") or []
                    if all_names:
                        ana_parts.append("Items: " + ", ".join(str(n) for n in all_names[:10]))
                if ana_parts:
                    hdr = header or "Here is what we have available:"
                    sections.append(hdr + "\n\n" + "\n\n".join(f"- {p}" for p in ana_parts))

            # Policies section
            if fg.get("policies") and not sections:
                pol_lines = []
                for pol in fg["policies"][:3]:
                    pt = pol.get("policy_type", "Policy").replace("_", " ").title()
                    sm = pol.get("summary", "")[:200]
                    pol_lines.append(f"- **{pt}**: {sm}")
                if pol_lines:
                    hdr = header or "Here is the relevant policy information:"
                    sections.append(hdr + "\n\n" + "\n".join(pol_lines))

            return "\n\n".join(s for s in sections if s.strip())

        # Helper: build from raw chunks (fallback when fact_graph unavailable)
        def _build_from_chunks(chunks: List[Dict]) -> str:
            product_lines: List[str] = []
            seen: set = set()
            _re_g = _re_llm
            for c in chunks[:8]:
                meta = c.get("metadata", {}) if isinstance(c, dict) else {}
                if not isinstance(meta, dict):
                    meta = {}
                attrs = meta.get("attributes") or {}
                sd    = meta.get("structured_data") or {}
                item_name = (
                    meta.get("name", "") or meta.get("title", "")
                    or attrs.get("name", "") or sd.get("product_name", "")
                    or sd.get("offer_title", "") or sd.get("service_name", "")
                    or sd.get("item_name", "")
                ).strip()
                if not item_name:
                    m = _re_g.search(
                        r"\b([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){1,4})\b",
                        c.get("content", ""),
                    )
                    if m:
                        item_name = m.group(1)
                if not item_name or item_name.lower() in seen:
                    continue
                seen.add(item_name.lower())
                raw_price = attrs.get("price") or sd.get("price") or ""
                content_text = c.get("content", "") if isinstance(c, dict) else ""
                if "\u20b9" in content_text or "INR" in content_text.upper():
                    sym = "\u20b9"
                elif "\u20ac" in content_text:
                    sym = "\u20ac"
                elif "\u00a3" in content_text:
                    sym = "\u00a3"
                else:
                    sym = "$"
                try:
                    numeric = _re_g.sub(r"[^\d.]", "", str(raw_price).replace(",", ""))
                    price_str = f"{sym}{int(float(numeric))}" if numeric else ""
                except Exception:
                    price_str = ""
                line = f"- **{item_name}**"
                if price_str:
                    line += f"\n   - Price: {price_str}"
                spec_parts = []
                for sk in ("ram", "storage", "processor", "gpu", "display"):
                    v = sd.get(sk) or attrs.get(sk)
                    if v:
                        spec_parts.append(f"{sk.title()}: {v}")
                if spec_parts:
                    line += "\n   - Specs: " + ", ".join(spec_parts[:3])
                product_lines.append(line)
            return "\n".join(product_lines)

        # ─── Gather available chunks ──────────────────────────────────────────────
        chunks = retrieval.get("chunks", [])
        product_chunks = [
            c for c in chunks
            if str(c.get("chunk_type", "")).lower() in (
                "product_service", "data_analytics", "offers_promotions"
            )
        ]
        has_real_products = bool(product_chunks) or bool(_fg_products)

        # ─── 1. Spec hallucination detection ─────────────────────────────────────
        # The LLM assigns specs from the CUSTOMER'S REQUEST to real product names.
        # E.g. customer asks "8GB RAM" → LLM writes "IngenAI Gamer 15: 8GB RAM"
        # but Gamer 15 actually has 16GB RAM. This is the most dangerous failure.
        #
        # Detection: for each product name that appears in the response AND in the
        # fact_graph, check if the response mentions a spec value that contradicts
        # the fact_graph spec for that product.
        if _fg_products and has_real_products:
            _spec_val_pat = _re_llm.compile(
                r"\b(\d+)\s*(gb|tb|mb|ghz|mhz)\b",
                _re_llm.IGNORECASE,
            )
            spec_hallucination_found = False
            response_lower = response_text.lower()

            for prod_name_lower, prod_data in _fg_products.items():
                # Only check if this product name appears in the response
                if prod_name_lower not in response_lower:
                    continue
                fg_specs = prod_data.get("specifications") or {}

                # Find spec claims in the response text near this product name
                # Look for the product's occurrence and extract the paragraph/line around it
                idx = response_lower.find(prod_name_lower)
                while idx != -1:
                    # Extract a ~200-char window around the product mention
                    window = response_text[max(0, idx - 20):min(len(response_text), idx + 200)].lower()
                    # Find all spec values in this window
                    for m in _spec_val_pat.finditer(window):
                        resp_num  = m.group(1)    # e.g. "8"
                        resp_unit = m.group(2).lower()  # e.g. "gb"
                        # Check if this contradicts a known spec for this product
                        # Map unit to spec key
                        unit_to_key = {"gb": ["ram", "storage"], "tb": ["storage"]}
                        keys_to_check = unit_to_key.get(resp_unit, [])
                        for spec_key in keys_to_check:
                            fg_val = str(fg_specs.get(spec_key) or "").lower()
                            if not fg_val:
                                continue
                            # Extract the number from the fact_graph spec value
                            fg_num_m = _re_llm.search(r"\b(\d+)\b", fg_val)
                            if fg_num_m and fg_num_m.group(1) != resp_num:
                                # Mismatch! LLM said {resp_num}GB but fact_graph says {fg_val}
                                logger.warning(
                                    "spec_hallucination_detected | product=%s "
                                    "response_claims=%s%s fact_graph_says=%s | "
                                    "rebuilding from fact_graph",
                                    prod_name_lower, resp_num, resp_unit, fg_val,
                                )
                                spec_hallucination_found = True
                                break
                        if spec_hallucination_found:
                            break
                    if spec_hallucination_found:
                        break
                    idx = response_lower.find(prod_name_lower, idx + 1)
                if spec_hallucination_found:
                    break

            if spec_hallucination_found:
                # Rebuild entirely from fact_graph — the LLM's product listing is wrong
                rebuilt = _build_from_fact_graph(
                    fact_graph,
                    "Here are the available options in our catalog:"
                )
                if rebuilt:
                    response_text = (
                        rebuilt
                        + "\n\nFeel free to reply if you have any questions or would like more details!"
                    )
                    logger.info("spec_hallucination_corrected | rebuilt from fact_graph")

        # ─── 2. Spec refusal detection ────────────────────────────────────────────
        _SPEC_REFUSAL_PAT = _re_llm.compile(
            r"(?:while\s+(?:i|we)\s+don[''`]?t\s+have\s+(?:products?|any(?:thing)?|items?)"
            r"|don[''`]?t\s+have\s+(?:any\s+)?(?:specific\s+)?(?:products?|items?|laptops?)"
            r"|none\s+of\s+(?:our|the)\s+(?:products?|items?|laptops?)"
            r"|no\s+(?:products?|items?|laptops?)\s+(?:that\s+)?(?:specifically\s+)?(?:match|meet)"
            r"|unfortunately[,\s]+(?:i|we)\s+don[''`]?t\s+have)"
            r".*?(?:specifications?|specs?|exact|specifically|those)",
            _re_llm.IGNORECASE | _re_llm.DOTALL,
        )

        if has_real_products and _SPEC_REFUSAL_PAT.search(response_text):
            logger.warning(
                "spec_refusal_detected | rebuilding from fact_graph | msg='%s'",
                message_content[:80],
            )
            # Always rebuild from fact_graph when spec refusal detected.
            # The lossy "strip opener + keep tail" approach is NEVER used because
            # the tail may list wrong products or hallucinated specs.
            rebuilt = _build_from_fact_graph(
                fact_graph,
                "Here are the available options in our catalog:"
            )
            if rebuilt:
                response_text = (
                    rebuilt
                    + "\n\nFeel free to reply if you have any questions or would like more details!"
                )
            else:
                # fact_graph empty — use raw chunks
                chunk_list = _build_from_chunks(product_chunks)
                if chunk_list:
                    response_text = (
                        "Here are the available options in our catalog:\n\n"
                        + chunk_list
                        + "\n\nFeel free to reply if you'd like more details on any of these!"
                    )

        # ─── 3. No-pricing detection ──────────────────────────────────────────────
        # The LLM says "I don't have pricing details" despite prices being in context.
        # This happens when grounding_confidence < 0.60 and the risk prompt fires
        # _RISK_PROMPT_NO_PRICING_DATA which blocks all price quoting.
        # Fix: if fact_graph has products WITH prices and the response says no pricing,
        # rebuild from fact_graph which always includes verified prices.
        _NO_PRICING_PAT = _re_llm.compile(
            r"(?:don[''`]?t\s+have\s+(?:specific\s+)?pricing\s+details?"
            r"|no\s+(?:specific\s+)?pricing\s+(?:details?|information)"
            r"|pricing\s+(?:details?|information)\s+(?:is\s+)?not\s+available"
            r"|unable\s+to\s+(?:provide|confirm)\s+(?:specific\s+)?pricing"
            r"|cannot\s+(?:provide|confirm)\s+(?:specific\s+)?pricing)",
            _re_llm.IGNORECASE,
        )
        if _NO_PRICING_PAT.search(response_text) and _fg_products:
            # Check if any fact_graph product actually has a price
            has_fg_prices = any(p.get("price") for p in _fg_products.values())
            if has_fg_prices:
                logger.warning(
                    "no_pricing_claim_detected | fact_graph has prices | rebuilding | "
                    "msg='%s'", message_content[:80],
                )
                rebuilt = _build_from_fact_graph(
                    fact_graph,
                    "Here are the available options in our catalog:"
                )
                if rebuilt:
                    response_text = (
                        rebuilt
                        + "\n\nFeel free to reply if you have any questions or would like more details!"
                    )

        # ─── 4. Generic product name detection ───────────────────────────────────
        _GENERIC_PRODUCT_PAT = _re_llm.compile(
            r"\*{0,2}(?:Product|Service|Option|Item|Model|Solution|Package|Plan|Tier)\s+"
            r"(?:\d+|[A-Z])\*{0,2}",
            _re_llm.IGNORECASE,
        )
        if _GENERIC_PRODUCT_PAT.search(response_text) and has_real_products:
            logger.warning(
                "generic_product_names_detected | rebuilding from fact_graph | msg='%s'",
                message_content[:80],
            )
            rebuilt = _build_from_fact_graph(
                fact_graph,
                "Here are the available options in our catalog:"
            )
            if rebuilt:
                response_text = (
                    rebuilt
                    + "\n\nFeel free to reply if you have any questions or would like more details on any of these!"
                )
            else:
                chunk_list = _build_from_chunks(product_chunks)
                if chunk_list:
                    response_text = (
                        "Here are the available options in our catalog:\n\n"
                        + chunk_list
                        + "\n\nFeel free to reply if you have any questions or would like more details on any of these!"
                    )

        # ─── 5. Placeholder bracket detection ────────────────────────────────────
        _PLACEHOLDER_PAT = _re_llm.compile(
            r'\[(?:Product Name|GPU Details|Price|Contact|TBD|Name|Details|Info|'
            r'Category|Description|Feature|Spec|Model|Brand|SKU|ID|Email|Phone|'
            r'Address|Date|Time|Amount|Quantity)[^\]]*\]',
            _re_llm.IGNORECASE,
        )
        if _PLACEHOLDER_PAT.search(response_text):
            logger.warning("placeholder_text_detected | msg='%s'", message_content[:80])
            rebuilt = _build_from_fact_graph(fact_graph)
            if rebuilt:
                response_text = (
                    "Here are the available options in our catalog:\n\n"
                    + rebuilt
                    + "\n\nFeel free to reply if you'd like more details!"
                )
            elif product_chunks:
                response_text = (
                    "Thank you for your inquiry. We have options available that may meet your "
                    "requirements. Please reply and a team member will provide precise details!"
                )

        # ─── 6. Catalog content sanity check ─────────────────────────────────────
        _CATALOG_REQUEST_SIGNALS = {
            "product", "products", "service", "services", "catalog", "offer",
            "offers", "deal", "deals", "discount", "discounts", "promotion",
            "promotions", "promo", "offerings", "solution", "solutions",
            "wanna about", "want to know", "what do you", "what you have",
            "what you offer",
        }
        msg_lower = message_content.lower()
        is_catalog_request = any(s in msg_lower for s in _CATALOG_REQUEST_SIGNALS)

        if is_catalog_request and has_real_products:
            response_lower = response_text.lower()
            _GENERIC_ONLY_SIGNALS = [
                "what discounts", "can you tell me", "how does", "would you like to know",
                "what would you like", "what are you looking for", "could you clarify",
                "please let me know what", "feel free to ask about",
            ]
            _CATALOG_CONTENT_SIGNALS = [
                "price", "inr", "rs.", "rs ", "\u20b9", "$",
                "model", "laptop", "gaming", "pro", "available",
                "category", "categories", "range", "offer", "product",
                "total", "we offer", "we have", "our products",
            ]
            has_catalog_content = any(s in response_lower for s in _CATALOG_CONTENT_SIGNALS)
            generic_count = sum(1 for s in _GENERIC_ONLY_SIGNALS if s in response_lower)
            if not has_catalog_content and generic_count >= 2:
                logger.warning(
                    "catalog_response_validation_failed | only generic content | "
                    "chunks=%d message='%s'", len(chunks), message_content[:80],
                )

        return response_text

    def _check_hallucination(
        self,
        response_text: str,
        validated_chunks: List[Dict],
        rejected_chunks: List[Dict],
        intelligence: Any,
        grounding_result: Any,
    ) -> Dict[str, Any]:
        """
        Post-generation hallucination check.

        Grounding score seeded from pre-gen validation (most reliable signal).
        Word-overlap is a secondary adjustment, never the sole arbiter.

        Hallucination is only flagged when confirmed violations exist:
        - Response invents specific $prices with NO price in ANY context
        - Response makes specific entity claims with ZERO context supporting them
        A generic helpful greeting/engagement response is NEVER hallucination.
        """
        context_chunks = validated_chunks
        if not context_chunks and rejected_chunks:
            context_chunks = [c for c in rejected_chunks if c.get("content", "")]

        all_context = " ".join(
            c.get("content", "") for c in (validated_chunks + rejected_chunks)
        ).lower()
        context_text = " ".join(
            chunk.get("content", "") for chunk in context_chunks
        ).lower()

        response_lower = response_text.lower()
        violations: List[str] = []

        # Check for invented pricing in ANY currency not present in context.
        # CRITICAL FIX: structured_data payloads may contain "$699" strings even
        # when the business operates in INR (₹). We must check the CANONICAL currency
        # symbol that was actually used in the response against what appears in the
        # content text (search_text / title fields), NOT the raw payload string.
        # Strategy: if the context contains ₹/INR signals, treat as INR business
        # and never flag ₹ prices as invented. Only flag if the response invents
        # a price in a currency that has NO numeric value in the context at all.
        _CURRENCY_PATTERNS = [
            ("\u20b9", r"\u20b9\s*\d"),   # INR ₹
            ("\u20ac", r"\u20ac\s*\d"),   # EUR €
            ("\u00a3", r"\u00a3\s*\d"),   # GBP £
            ("$",      r"\$\s*\d"),        # USD $ — check LAST
        ]
        import re as _re

        # Determine if context is an INR/non-USD business by checking content fields.
        # We specifically check only the search_text/content/title portions of context,
        # NOT raw payload JSON strings (which may have "$" from CSV structured_data).
        # A chunk with "₹699" in its search_text is INR regardless of structured_data.
        context_is_inr = "\u20b9" in all_context or "inr" in all_context.lower()
        context_is_eur = "\u20ac" in all_context or "eur" in all_context.lower()
        context_is_gbp = "\u00a3" in all_context or "gbp" in all_context.lower()

        for sym, pat in _CURRENCY_PATTERNS:
            if not _re.search(pat, response_text):
                continue  # response doesn't use this currency symbol at all
            # Response uses this symbol — check if it's plausible given the context
            if sym == "\u20b9" and context_is_inr:
                continue  # INR in response, INR in context — correct
            if sym == "\u20ac" and context_is_eur:
                continue
            if sym == "\u00a3" and context_is_gbp:
                continue
            if sym == "$":
                # $ in response is only a violation if context has ZERO numeric price
                # data AND context is clearly a non-USD business (has ₹/INR signals).
                # If context_is_inr, the business uses ₹ — $ in response is a
                # formatting error from fact_graph, not actual hallucination.
                # Only flag if context has truly no price data at all.
                if context_is_inr or context_is_eur or context_is_gbp:
                    continue  # non-USD business — $ in response is a formatting issue, not hallucination
                if sym not in all_context:
                    violations.append(f"invented_pricing_{sym}")
            else:
                if sym not in all_context:
                    violations.append(f"invented_pricing_{sym}")

        hallucination_keywords = ["our price is", "costs $", "we charge", "launching on", "released in"]
        if all_context and any(kw in response_lower for kw in hallucination_keywords):
            if not any(kw.replace(" ", "") in all_context.replace(" ", "") for kw in hallucination_keywords):
                violations.append("specific_claims_without_context")

        accepted = grounding_result.accepted_count if grounding_result else 0
        pre_gen_conf = grounding_result.overall_confidence if grounding_result else 0.0

        if accepted > 0:
            response_words = set(response_lower.split())
            context_words  = set(context_text.split())
            if response_words and context_words:
                overlap = len(response_words & context_words) / len(response_words)
                adjustment = (overlap - 0.10) * 0.10
            else:
                adjustment = 0.0
            grounding_score = min(0.95, max(0.40, pre_gen_conf + adjustment))
        elif context_chunks:
            response_words = set(response_lower.split())
            context_words  = set(context_text.split())
            if response_words and context_words:
                overlap = len(response_words & context_words) / len(response_words)
                grounding_score = min(0.75, 0.45 + overlap * 0.35)
            else:
                grounding_score = 0.45
        else:
            grounding_score = 0.45

        if violations:
            grounding_score = min(grounding_score, 0.40)

        hallucination_detected = bool(violations)

        return {
            "hallucination_detected": hallucination_detected,
            "grounding_score":        grounding_score,
            "violations":             violations,
        }

    def _calculate_generation_confidence(
        self,
        retrieval_confidence: float,
        grounding_confidence: float,
        post_gen_grounding_score: float,
        intent_confidence: float,
        fallback_confidence: float = 1.0,
    ) -> float:
        """
        Calculate overall generation confidence (pre+post grounding aware).
        fallback_confidence penalizes results from lower tiers (T2->T5 < 1.0).
        """
        base = (
            retrieval_confidence     * 0.25 +
            grounding_confidence     * 0.30 +
            post_gen_grounding_score * 0.30 +
            intent_confidence        * 0.15
        )
        return min(0.95, max(0.05, base * fallback_confidence))


# Global instance
_llm_orchestrator: Optional[LLMOrchestrator] = None


def get_llm_orchestrator() -> LLMOrchestrator:
    """Get global LLM orchestrator"""
    global _llm_orchestrator
    if _llm_orchestrator is None:
        _llm_orchestrator = LLMOrchestrator()
    return _llm_orchestrator


__all__ = ["LLMOrchestrator", "get_llm_orchestrator"]
