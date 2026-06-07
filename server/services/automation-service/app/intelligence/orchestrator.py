"""
Intelligence - Enterprise Orchestrator (Complete Implementation)
============================
ENTERPRISE CONVERSATIONAL REASONING ENGINE - BRAIN #1
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import time
from openai import AsyncOpenAI
from app.core.config import get_config
from app.core.resource_management import get_resource_manager
from app.observability import get_logger
from app.intelligence.models.enterprise_intelligence import (
    EnterpriseIntelligenceResult,
    ConversationAnalysis,
    IntentDefinition,
    EntityExtraction,
    SearchPlan,
    RetrievalStrategy,
    BusinessReasoning,
    ResponseStrategy,
    ConversationStage,
    CustomerType,
    Sentiment,
    Urgency,
    IntentType,
    ResponseTone,
    PromptTemplate,
)

logger = get_logger(__name__)


class IntelligenceOrchestrator:
    """
    ENTERPRISE CONVERSATIONAL REASONING ENGINE
    
    Capabilities:
    - Deep conversational understanding (20+ dimensions)
    - Multi-intent decomposition
    - Entity extraction (12 categories)
    - Business context awareness
    - Customer journey tracking
    - Sentiment & urgency detection
    - Commercial opportunity identification
    - Escalation risk analysis
    - Dynamic query planning (6 strategies)
    - Prompt family routing (20 templates)
    """
    
    def __init__(self):
        self.config = get_config()
        self.resource_manager = get_resource_manager()
        self.openai_client = AsyncOpenAI(api_key=self.config.get_openai_api_key())
        # Access OPENAI_MODEL directly from shared config
        from shared.config import get_config as get_shared_config
        shared_config = get_shared_config()
        self.model = shared_config.OPENAI_MODEL
    
    async def understand_intent(
        self,
        message_content: str,
        subject: str,
        memory: Dict[str, Any],
        trace_id: str
    ) -> EnterpriseIntelligenceResult:
        """
        ENTERPRISE CONVERSATIONAL REASONING

        Step 1: Determine conversation state from memory (NEW vs ACTIVE vs FOLLOW_UP).
        Step 2: If new conversation OR no prior context → ALWAYS call Brain #1 (never fast-path).
        Step 3: If active conversation with confirmed context AND message is a short signal
                → use memory-aware continuation handler (inherits real intent/entity).
        Step 4: Otherwise → Brain #1 with full context.

        Returns: EnterpriseIntelligenceResult
        """
        start_time = time.perf_counter()

        try:
            is_new = self._is_new_conversation(memory)

            # ── GATE: never take the continuation fast-path on a new conversation ──
            # On a new conversation, "hello" / short messages MUST go to Brain #1
            # so they get classified as general_greeting / product_inquiry / etc.
            # and generate a real retrieval plan from the analytics layer.
            if not is_new and self._is_confirmed_continuation(message_content, memory):
                result = self._handle_continuation(message_content, memory)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                result.processing_latency_ms = elapsed_ms
                logger.info(
                    "Continuation fast-path | intent=%s entity=%s queries=%d latency=%.0fms",
                    result.primary_intents[0].type if result.primary_intents else "unknown",
                    result.entities.products[0] if result.entities.products else "",
                    len(result.search_plan.semantic_queries),
                    elapsed_ms,
                    trace_id=trace_id,
                )
                return result

            # ── Full Brain #1 path ────────────────────────────────────────────────
            context = self._prepare_enterprise_context(message_content, subject, memory)

            # Use the fast model (gpt-3.5-turbo) for simple first-turn messages
            # with short body and a single clear subject. Saves ~5-7s of latency.
            _use_fast_model = (
                is_new
                and len(message_content.strip()) < 80
                and not any(kw in message_content.lower() for kw in (
                    "technical", "complaint", "lawsuit", "refund", "breach",
                    "integration", "api", "enterprise", "contract",
                ))
            )

            raw_result = await self._call_openai_enterprise_intelligence(
                context, trace_id, is_new_conversation=is_new, fast_model=_use_fast_model
            )
            intelligence = self._parse_enterprise_intelligence(raw_result, memory)

            # ── Post-parse safety: block follow_up on new conversations ──────────
            if is_new:
                intelligence = self._enforce_new_conversation_intent(intelligence, message_content)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            intelligence.processing_latency_ms = elapsed_ms

            primary_type = intelligence.primary_intents[0].type if intelligence.primary_intents else "unknown"
            primary_conf = intelligence.primary_intents[0].confidence if intelligence.primary_intents else 0.0
            logger.info(
                "✅ Brain #1 | state=%s intent=%s conf=%.2f sentiment=%s urgency=%s "
                "queries=%d latency=%.0fms",
                "new" if is_new else "active",
                primary_type,
                primary_conf,
                intelligence.conversation_analysis.sentiment,
                intelligence.conversation_analysis.urgency,
                len(intelligence.search_plan.semantic_queries),
                elapsed_ms,
                trace_id=trace_id,
            )
            return intelligence

        except Exception as e:
            logger.error("Enterprise intelligence failed: %s", e, trace_id=trace_id, exc_info=True)
            return self._create_fallback_intelligence(message_content, memory, str(e))
    
    def _is_simple_continuation(self, message: str) -> bool:
        """Legacy — kept for backward compatibility. Use _is_confirmed_continuation instead."""
        message_lower = message.lower().strip()
        continuations = [
            "yes", "no", "okay", "ok", "sure", "thanks", "thank you",
            "continue", "go ahead", "tell me more", "what else",
            "please continue", "and then", "what about", "sounds good",
            "perfect", "great", "got it", "understood", "i see"
        ]
        return message_lower in continuations or len(message) < 15

    def _is_confirmed_continuation(self, message: str, memory: Dict) -> bool:
        """
        True ONLY when:
          1. Message is a short continuation signal (length/keyword check), AND
          2. There is confirmed prior context in memory (real last_intent + real entity/topic).

        Both conditions must be met. A new conversation with a short opener
        ("hello", "hi") fails condition 2 and goes to Brain #1 instead.
        """
        # Condition 1: short signal
        message_lower = message.lower().strip()
        short_signals = {
            "yes", "no", "okay", "ok", "sure", "thanks", "thank you",
            "continue", "go ahead", "tell me more", "what else",
            "please continue", "and then", "what about", "sounds good",
            "perfect", "great", "got it", "understood", "i see",
        }
        is_short = message_lower in short_signals or len(message.strip()) < 15

        if not is_short:
            return False

        # Condition 2: confirmed prior context
        last_intent = memory.get("last_intent", "unknown")
        active_topic = memory.get("active_topic", "")
        last_intents = memory.get("last_intents", [])
        has_real_intent = last_intent not in ("unknown", "", "follow_up", "general_inquiry")
        has_real_topic = bool(active_topic and active_topic not in ("unknown", ""))
        has_history = len(memory.get("history", [])) > 0

        return (has_real_intent or has_real_topic) and has_history

    def _is_new_conversation(self, memory: Dict) -> bool:
        """
        True when this is the first or near-first turn with no established context.
        """
        turn_count = memory.get("turn_count", 0)
        last_intent = memory.get("last_intent", "unknown")
        history = memory.get("history", [])
        active_topic = memory.get("active_topic", "")
        return (
            turn_count == 0
            or last_intent in ("unknown", "")
            or (len(history) == 0 and not active_topic)
        )

    def _enforce_new_conversation_intent(
        self,
        intelligence: EnterpriseIntelligenceResult,
        message_content: str,
    ) -> EnterpriseIntelligenceResult:
        """
        Post-parse safety guard for new conversations.

        If Brain #1 still returns follow_up on a new conversation, upgrade it to
        general_inquiry and ensure the search plan includes discovery queries
        so the analytics layer is triggered.
        """
        blocked_on_new = {IntentType.FOLLOW_UP}
        primary = intelligence.primary_intents[0] if intelligence.primary_intents else None

        if primary and primary.type in blocked_on_new:
            logger.warning(
                "Brain #1 returned '%s' on new conversation — upgrading to general_inquiry. "
                "message='%s'",
                primary.type, message_content[:80],
            )
            # Replace the blocked intent
            intelligence.primary_intents[0] = IntentDefinition(
                type=IntentType.GENERAL_INQUIRY,
                confidence=primary.confidence,
            )

        # Ensure the search plan has useful queries for analytics retrieval
        sp = intelligence.search_plan
        if not sp.semantic_queries and not sp.exact_search_queries:
            msg_words = message_content.strip()
            intelligence.search_plan = SearchPlan(
                semantic_queries=[msg_words, "products services overview", "business information"],
                exact_search_queries=[],
            )
            logger.debug(
                "Added discovery queries to empty search plan for new conversation"
            )

        return intelligence

    def _handle_continuation(
        self, message: str, memory: Dict
    ) -> EnterpriseIntelligenceResult:
        """
        Handle continuation with MEMORY-AWARE intent inheritance.

        Short messages ("yes", "tell me more", "pricing?") MUST inherit:
          - last intent from memory
          - active topic / entity
          - customer journey stage
          - unresolved questions as search queries

        NEVER returns a generic follow-up with empty search plan.
        """
        message_lower = message.lower().strip()
        is_negative   = message_lower in {"no", "nope", "not interested", "nahi", "na"}

        # ── Inherit from intelligence memory ────────────────────────────
        last_intent      = memory.get("last_intent", "general_inquiry")
        active_topic     = memory.get("active_topic", "")
        last_intents     = memory.get("last_intents", [])
        last_entities    = memory.get("already_shared_entities", [])
        journey_stage    = memory.get("customer_journey_stage", "discovery")
        sentiment_hist   = memory.get("sentiment_history", [])
        unresolved       = memory.get("unresolved_questions", [])

        # Best available entity
        best_entity = (
            active_topic
            or (last_entities[0] if last_entities else "")
            or (last_intents[0].get("entities", [None])[0]
                if last_intents and isinstance(last_intents[0], dict) else "")
        )

        # ── Build inherited search plan ──────────────────────────────────
        inherited_queries: List[str] = []

        if best_entity and not is_negative:
            from app.intelligence.query_decomposition import _intent_to_query_fragment
            fragment = _intent_to_query_fragment(last_intent)
            inherited_queries.append(f"{best_entity} {fragment}")

        # Add unresolved questions as queries
        if unresolved and not is_negative:
            inherited_queries.extend(q[:100] for q in unresolved[:2])

        if not inherited_queries and not is_negative:
            inherited_queries = [last_intent.replace("_", " ")]

        # Safety: if we still have no real queries, the continuation is effectively
        # a new-conversation opener — build discovery queries instead of "unknown"
        if not is_negative and (
            not inherited_queries
            or inherited_queries == ["unknown"]
            or inherited_queries == ["follow_up"]
        ):
            inherited_queries = [
                "products and services overview",
                "business information",
                "product catalog summary",
            ]
            logger.debug(
                "Continuation had no real context — using discovery queries instead"
            )

        # ── Map last intent string → IntentType enum ────────────────────
        from app.intelligence.models.enterprise_intelligence import IntentType
        _INTENT_MAP: Dict[str, str] = {
            "pricing_inquiry":           "pricing_inquiry",
            "product_inquiry":           "product_inquiry",
            "support_request":           "support_request",
            "technical_support_request": "technical_support_request",
            "complaint":                 "complaint",
            "refund_request":            "refund_request",
            "billing_inquiry":           "billing_inquiry",
            "general_inquiry":           "general_inquiry",
        }
        mapped_intent = _INTENT_MAP.get(last_intent, "general_inquiry")
        if is_negative:
            mapped_intent = "general_inquiry"

        try:
            intent_type = IntentType(mapped_intent)
        except ValueError:
            intent_type = IntentType.FOLLOW_UP

        # Map journey_stage → ConversationStage
        from app.intelligence.models.enterprise_intelligence import ConversationStage
        _STAGE_MAP = {
            "discovery": ConversationStage.AWARENESS,
            "awareness": ConversationStage.AWARENESS,
            "consideration": ConversationStage.CONSIDERATION,
            "decision": ConversationStage.DECISION,
            "escalation": ConversationStage.ESCALATION,
        }
        conv_stage = _STAGE_MAP.get(str(journey_stage).lower(), ConversationStage.INTEREST)

        # Map sentiment
        from app.intelligence.models.enterprise_intelligence import Sentiment
        last_sentiment = (sentiment_hist[0] if sentiment_hist else "neutral")
        _SENT_MAP = {
            "positive": Sentiment.POSITIVE, "neutral": Sentiment.NEUTRAL,
            "negative": Sentiment.NEGATIVE, "frustrated": Sentiment.FRUSTRATED,
            "angry": Sentiment.ANGRY, "urgent": Sentiment.URGENT,
        }
        sentiment = _SENT_MAP.get(str(last_sentiment).lower(), Sentiment.NEUTRAL)

        elapsed_ms = 0.0

        result = EnterpriseIntelligenceResult(
            conversation_analysis=ConversationAnalysis(
                stage=conv_stage,
                customer_type=CustomerType.UNKNOWN,
                sentiment=sentiment,
                urgency=Urgency.LOW,
                intent_confidence=0.90,
            ),
            primary_intents=[
                IntentDefinition(type=intent_type, confidence=0.90)
            ],
            entities=EntityExtraction(
                products=[best_entity] if best_entity else [],
                features=[],
            ),
            search_plan=SearchPlan(
                semantic_queries=inherited_queries,
                exact_search_queries=[best_entity] if best_entity else [],
            ),
            retrieval_strategy=RetrievalStrategy(
                cache_lookup_first=True,
                exact_match_priority=bool(best_entity),
                semantic_search=not is_negative,
                reranking_required=False,
            ),
            business_reasoning=BusinessReasoning(
                likely_goal=active_topic or last_intent,
                handoff_risk=is_negative,
            ),
            response_strategy=ResponseStrategy(
                tone=ResponseTone.FRIENDLY_SUPPORTIVE,
                prompt_template=PromptTemplate.SHORT_REPLY,
                response_depth="concise",
            ),
            turn_count=memory.get("turn_count", 0) + 1,
            is_continuation=True,
            requires_escalation=is_negative,
            processing_latency_ms=elapsed_ms,
        )

        logger.info(
            "Continuation resolved | intent=%s entity=%s queries=%d negative=%s",
            mapped_intent, best_entity, len(inherited_queries), is_negative,
        )
        return result
    
    def _prepare_enterprise_context(
        self,
        message: str,
        subject: str,
        memory: Dict
    ) -> str:
        """
        Build rich context for OpenAI Brain #1
        
        Includes:
        - Latest message + subject
        - Last 10 conversation turns
        - Memory summary (entities, stage, sentiment)
        - Previous intents
        - Customer indicators
        """
        context_parts = []
        
        # Current message
        if subject:
            context_parts.append(f"Subject: {subject}")
        context_parts.append(f"Message: {message}")
        
        # Conversation history (last 10 turns)
        history = memory.get("history", [])
        if history:
            history_text = "\n".join([
                f"Turn {i+1}: Intent={h.get('intent', 'unknown')} | Response={h.get('response', '')[:100]}"
                for i, h in enumerate(history[:10])
            ])
            context_parts.append(f"\nConversation History (last 10 turns):\n{history_text}")
        
        # Memory summary
        turn_count = memory.get("turn_count", 0)
        last_intent = memory.get("last_intent", "unknown")
        conversation_state = memory.get("conversation_state", "new")
        context_parts.append(f"\nTurn Count: {turn_count}")
        context_parts.append(f"Last Intent: {last_intent}")
        context_parts.append(f"Conversation State: {conversation_state}")
        
        # Shared entities
        entities = memory.get("shared_entities", {})
        if entities:
            context_parts.append(f"Known Entities: {json.dumps(entities)}")
        
        # Active topics
        active_topics = memory.get("active_topics", [])
        if active_topics:
            context_parts.append(f"Active Topics: {', '.join(active_topics)}")

        # Intelligence memory — already-shared context (repetition prevention)
        already_shared_entities = memory.get("already_shared_entities", [])
        if already_shared_entities:
            context_parts.append(f"Already Shared Entities: {', '.join(already_shared_entities[:10])}")

        pricing_shared = memory.get("pricing_already_shared", [])
        if pricing_shared:
            context_parts.append(f"Pricing Already Shared: {json.dumps(pricing_shared[:5])}")

        already_shared_products = memory.get("already_shared_products", [])
        if already_shared_products:
            context_parts.append(f"Products Already Shared: {', '.join(already_shared_products[:10])}")

        unresolved = memory.get("unresolved_questions", [])
        if unresolved:
            context_parts.append(f"Unresolved Questions: {', '.join(unresolved[:5])}")

        last_intents = memory.get("last_intents", [])
        if last_intents:
            context_parts.append(
                f"Intent History (last 3): {json.dumps(last_intents[:3])}"
            )

        customer_journey_stage = memory.get("customer_journey_stage", "")
        if customer_journey_stage:
            context_parts.append(f"Customer Journey Stage: {customer_journey_stage}")

        return "\n\n".join(context_parts)
    
    async def _call_openai_enterprise_intelligence(
        self,
        context: str,
        trace_id: str,
        is_new_conversation: bool = False,
        fast_model: bool = False,
    ) -> Dict[str, Any]:
        """
        Call OpenAI Brain #1 with ENTERPRISE PROMPT.

        When is_new_conversation=True, the prompt explicitly instructs Brain #1:
          - NEVER return follow_up as primary intent
          - Classify greetings as general_inquiry or product_inquiry
          - Generate discovery queries using analytics/business data
        """
        new_conv_instruction = ""
        if is_new_conversation:
            new_conv_instruction = """
CRITICAL — NEW CONVERSATION RULES:
- This is the FIRST message in a new conversation. There is NO prior context.
- The primary intent MUST NOT be "follow_up". "follow_up" is only valid when continuing
  an established conversation.
- For greetings (hello, hi, hey) or short openers with no specific product/service request:
  use "general_inquiry" as primary intent.
- Generate semantic_queries that retrieve business overview, product catalog,
  and service descriptions so the AI can give an informed introduction.
- Example discovery queries: "products and services overview", "business information",
  "product catalog summary", "available services", "pricing overview"
"""

        system_prompt = f"""You are an ENTERPRISE AI CONVERSATION ANALYST for a business automation system.

Your task: DEEPLY ANALYZE the customer email and extract COMPREHENSIVE intelligence.
{new_conv_instruction}
You MUST analyze and extract:

1. CONVERSATION STAGE (awareness/interest/consideration/decision/retention/escalation)
2. CUSTOMER TYPE (b2b/b2c/enterprise/smb/individual)
3. SENTIMENT (positive/neutral/negative/frustrated/angry/urgent)
4. URGENCY (low/medium/high/critical)
5. PRIMARY INTENT with confidence score 0-1
   Valid values: pricing_inquiry, product_inquiry, support_request, technical_support_request,
   feature_request, complaint, refund_request, customization_request, bulk_purchase,
   partnership_inquiry, billing_inquiry, account_issue, general_inquiry, onboarding, unknown
   NOTE: "follow_up" is only valid when Turn Count > 0 and prior context exists.
6. SECONDARY INTENTS if customer has multiple goals
7. SALES INTENTS if commercial opportunity exists
8. SUPPORT INTENTS if technical assistance needed
9. ENTITIES (extract ALL mentioned):
   - products: specific product names, models
   - features: capabilities, specifications requested
   - industries: customer's business sector
   - quantities: bulk orders, team sizes, numbers
   - pricing_terms: budget mentions, payment plans
   - technical_terms: APIs, integrations, tech specs
   - competitors: alternative solutions mentioned
   - locations: geographic requirements
   - timelines: delivery dates, urgency indicators
   - budget_indicators: price sensitivity signals
10. SEARCH PLAN (generate 6-12 search queries):
    - exact_search_queries: specific product/feature lookups
    - semantic_queries: conceptual/topic searches (MUST be non-empty with meaningful queries)
    - metadata_queries: filter-based searches
    - support_queries: troubleshooting, how-to
    - pricing_queries: cost, plans, discounts
    - followup_queries: related topics
11. BUSINESS REASONING:
    - likely_goal: what customer wants to achieve
    - possible_objections: concerns they might have
    - upsell_opportunities: premium features, add-ons
    - handoff_risk: needs human escalation?
12. RESPONSE STRATEGY:
    - tone: professional_consultative, friendly_supportive, technical_detailed, etc.
    - prompt_template: sales_pricing, support_technical, escalation_complaint, etc.
    - response_depth: concise, balanced, detailed

RESPOND WITH VALID JSON ONLY (no markdown, no extra text):
{{
  "conversation_analysis": {{
    "stage": "awareness",
    "customer_type": "unknown",
    "sentiment": "positive",
    "urgency": "low",
    "intent_confidence": 0.85
  }},
  "primary_intents": [
    {{"type": "general_inquiry", "confidence": 0.85}}
  ],
  "secondary_intents": [],
  "support_intents": [],
  "sales_intents": [],
  "entities": {{
    "products": [],
    "features": [],
    "industries": [],
    "quantities": [],
    "pricing_terms": [],
    "technical_terms": [],
    "competitors": [],
    "locations": [],
    "timelines": [],
    "budget_indicators": []
  }},
  "search_plan": {{
    "exact_search_queries": [],
    "semantic_queries": ["products and services overview", "business information", "product catalog"],
    "metadata_queries": [],
    "support_queries": [],
    "pricing_queries": [],
    "followup_queries": []
  }},
  "retrieval_strategy": {{
    "cache_lookup_first": false,
    "exact_match_priority": false,
    "semantic_search": true,
    "reranking_required": false,
    "metadata_filtering": false,
    "fusion_required": false
  }},
  "business_reasoning": {{
    "likely_goal": "Exploring what the business offers",
    "possible_objections": [],
    "upsell_opportunities": [],
    "handoff_risk": false
  }},
  "response_strategy": {{
    "tone": "friendly_supportive",
    "prompt_template": "general_engagement",
    "response_depth": "balanced"
  }}
}}
"""

        # Use a fast model for short/simple first-turn messages to cut latency ~3-5x.
        # Falls back to the configured model for complex multi-intent messages.
        model_to_use = "gpt-3.5-turbo" if fast_model else self.model

        try:
            response = await self.openai_client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=600 if fast_model else 800,
                timeout=15.0 if fast_model else 20.0,
            )

            content = response.choices[0].message.content.strip()

            # Strip markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error("OpenAI returned invalid JSON: %s | content=%s", e, content[:200], trace_id=trace_id)
            raise
        except Exception as e:
            logger.error("OpenAI Brain #1 call failed: %s", e, trace_id=trace_id)
            raise
    
    def _parse_enterprise_intelligence(
        self,
        raw_result: Dict,
        memory: Dict
    ) -> EnterpriseIntelligenceResult:
        """
        Parse OpenAI response into EnterpriseIntelligenceResult
        """
        try:
            # Parse conversation analysis
            conv_analysis_data = raw_result.get("conversation_analysis", {})
            conversation_analysis = ConversationAnalysis(
                stage=ConversationStage(conv_analysis_data.get("stage", "interest")),
                customer_type=CustomerType(conv_analysis_data.get("customer_type", "unknown")),
                sentiment=Sentiment(conv_analysis_data.get("sentiment", "neutral")),
                urgency=Urgency(conv_analysis_data.get("urgency", "medium")),
                intent_confidence=float(conv_analysis_data.get("intent_confidence", 0.5))
            )
            
            # Parse primary intents
            primary_intents = [
                IntentDefinition(
                    type=IntentType(intent["type"]),
                    confidence=float(intent["confidence"])
                )
                for intent in raw_result.get("primary_intents", [])
            ]
            
            # Fallback if no intents parsed
            if not primary_intents:
                primary_intents = [IntentDefinition(type=IntentType.GENERAL_INQUIRY, confidence=0.5)]
            
            # Parse secondary intents
            secondary_intents = [
                IntentDefinition(
                    type=IntentType(intent["type"]),
                    confidence=float(intent["confidence"])
                )
                for intent in raw_result.get("secondary_intents", [])
            ]
            
            # Parse entities
            entities_data = raw_result.get("entities", {})
            entities = EntityExtraction(**entities_data)
            
            # Parse search plan
            search_plan_data = raw_result.get("search_plan", {})
            search_plan = SearchPlan(**search_plan_data)
            
            # Parse retrieval strategy
            retrieval_strategy_data = raw_result.get("retrieval_strategy", {})
            retrieval_strategy = RetrievalStrategy(**retrieval_strategy_data)
            
            # Parse business reasoning
            business_reasoning_data = raw_result.get("business_reasoning", {})
            business_reasoning = BusinessReasoning(**business_reasoning_data)
            
            # Parse response strategy — safe enum lookup: unknown values fall back to DEFAULT
            response_strategy_data = raw_result.get("response_strategy", {})
            raw_tone     = response_strategy_data.get("tone", "professional_consultative")
            raw_template = response_strategy_data.get("prompt_template", "default_professional")

            # Safe tone lookup
            try:
                tone = ResponseTone(raw_tone)
            except ValueError:
                tone = ResponseTone.PROFESSIONAL_CONSULTATIVE

            # Safe template lookup — GPT often returns short aliases (e.g. "sales_pricing")
            # that don't match the full enum values. Fall back to DEFAULT gracefully.
            try:
                prompt_template = PromptTemplate(raw_template)
            except ValueError:
                # Try a prefix match against enum values
                matched = next(
                    (pt for pt in PromptTemplate if raw_template in pt.value or pt.value.startswith(raw_template)),
                    PromptTemplate.DEFAULT,
                )
                prompt_template = matched

            response_strategy = ResponseStrategy(
                tone=tone,
                prompt_template=prompt_template,
                response_depth=response_strategy_data.get("response_depth", "balanced")
            )
            
            # Build result
            return EnterpriseIntelligenceResult(
                conversation_analysis=conversation_analysis,
                primary_intents=primary_intents,
                secondary_intents=secondary_intents,
                support_intents=raw_result.get("support_intents", []),
                sales_intents=raw_result.get("sales_intents", []),
                entities=entities,
                search_plan=search_plan,
                retrieval_strategy=retrieval_strategy,
                business_reasoning=business_reasoning,
                response_strategy=response_strategy,
                turn_count=memory.get("turn_count", 0) + 1,
                is_continuation=False,
                requires_escalation=business_reasoning.handoff_risk
            )
            
        except Exception as e:
            logger.error(f"Failed to parse enterprise intelligence: {e}")
            raise
    
    def _create_fallback_intelligence(
        self,
        message: str,
        memory: Dict,
        error: str
    ) -> EnterpriseIntelligenceResult:
        """
        Create safe fallback intelligence on error
        """
        return EnterpriseIntelligenceResult(
            conversation_analysis=ConversationAnalysis(
                stage=ConversationStage.INTEREST,
                customer_type=CustomerType.UNKNOWN,
                sentiment=Sentiment.NEUTRAL,
                urgency=Urgency.MEDIUM,
                intent_confidence=0.3
            ),
            primary_intents=[
                IntentDefinition(type=IntentType.GENERAL_INQUIRY, confidence=0.3)
            ],
            entities=EntityExtraction(),
            search_plan=SearchPlan(
                semantic_queries=[message[:200]]  # Fallback to basic search
            ),
            retrieval_strategy=RetrievalStrategy(
                semantic_search=True
            ),
            business_reasoning=BusinessReasoning(
                likely_goal="unknown - intelligence failed",
                handoff_risk=True  # Safe default: escalate on error
            ),
            response_strategy=ResponseStrategy(
                tone=ResponseTone.PROFESSIONAL_CONSULTATIVE,
                prompt_template=PromptTemplate.DEFAULT,
                response_depth="balanced"
            ),
            turn_count=memory.get("turn_count", 0) + 1,
            requires_escalation=True  # Escalate on intelligence failure
        )


# Global instance
_intelligence_orchestrator: Optional[IntelligenceOrchestrator] = None


def get_intelligence_orchestrator() -> IntelligenceOrchestrator:
    """Get global intelligence orchestrator"""
    global _intelligence_orchestrator
    if _intelligence_orchestrator is None:
        _intelligence_orchestrator = IntelligenceOrchestrator()
    return _intelligence_orchestrator


__all__ = ["IntelligenceOrchestrator", "get_intelligence_orchestrator"]
