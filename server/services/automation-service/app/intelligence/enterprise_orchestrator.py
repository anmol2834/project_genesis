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
from app.intelligence.continuation_resolution import (
    get_short_message_detector,
    get_continuation_resolver,
    get_active_topic_memory,
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
        self.model = self.config.shared.OPENAI_MODEL
        
        # Short message contextual reasoning components
        self.short_message_detector = get_short_message_detector()
        self.continuation_resolver = get_continuation_resolver()
        self.active_topic_memory = get_active_topic_memory()
    
    async def understand_intent(
        self,
        message_content: str,
        subject: str,
        memory: Dict[str, Any],
        trace_id: str
    ) -> EnterpriseIntelligenceResult:
        """
        ENTERPRISE CONVERSATIONAL REASONING
        
        Analyzes:
        - Conversation stage & customer journey
        - Multi-dimensional intent classification
        - Comprehensive entity extraction
        - Business goal & commercial opportunity
        - Sentiment, urgency & escalation risk
        - Follow-up context resolution
        - Dynamic query planning (6 strategies)
        - Prompt family selection (20 templates)
        
        Returns: EnterpriseIntelligenceResult with 100+ structured fields
        """
        start_time = time.perf_counter()
        conversation_id = trace_id  # Use trace_id as conversation_id
        
        try:
            # CRITICAL: Short Message Contextual Reasoning (FAST PATH)
            # Detect if this is a context-dependent short message
            is_contextual, reason, confidence = self.short_message_detector.is_short_contextual_message(
                message_content
            )
            
            if is_contextual:
                logger.info(
                    f"🔍 Short contextual message detected | reason={reason} confidence={confidence:.2f}",
                    trace_id=trace_id
                )
                
                # Get continuation type
                continuation_type = self.short_message_detector.get_continuation_type(message_content)
                
                # Resolve context from conversation history
                continuation_context = self.continuation_resolver.resolve_continuation_context(
                    message_content,
                    continuation_type,
                    memory
                )
                
                logger.info(
                    f"📚 Context resolved | source={continuation_context['context_source']} "
                    f"intent={continuation_context['resolved_intent']} "
                    f"topic={continuation_context['active_topic']}",
                    trace_id=trace_id
                )
                
                # Check if we can skip retrieval using memory
                skip_retrieval = self.active_topic_memory.should_skip_retrieval(
                    conversation_id,
                    continuation_context
                )
                
                if skip_retrieval:
                    logger.info(
                        f"⚡ MEMORY-FIRST PATH | Skipping retrieval - using cached context",
                        trace_id=trace_id
                    )
                    return self._handle_contextual_continuation(
                        message_content,
                        continuation_type,
                        continuation_context,
                        memory,
                        conversation_id
                    )
                else:
                    logger.info(
                        f"🔄 Retrieval required | reason={continuation_context['context_source']}",
                        trace_id=trace_id
                    )
            
            # Check for simple continuations first (fast path)
            if self._is_simple_continuation(message_content):
                return self._handle_continuation(message_content, memory)
            
            # Prepare rich context
            context = self._prepare_enterprise_context(message_content, subject, memory)
            
            # Call OpenAI Brain #1 with enterprise prompt
            raw_result = await self._call_openai_enterprise_intelligence(context, trace_id)
            
            # Parse and structure enterprise intelligence
            intelligence = self._parse_enterprise_intelligence(raw_result, memory)
            
            # Record latency
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            intelligence.processing_latency_ms = elapsed_ms
            
            logger.info(
                f"✅ Enterprise Intelligence | stage={intelligence.conversation_analysis.stage} "
                f"intent={intelligence.primary_intents[0].type if intelligence.primary_intents else 'unknown'} "
                f"confidence={intelligence.primary_intents[0].confidence if intelligence.primary_intents else 0:.2f} "
                f"sentiment={intelligence.conversation_analysis.sentiment} "
                f"urgency={intelligence.conversation_analysis.urgency} "
                f"queries={len(intelligence.search_plan.semantic_queries)} "
                f"latency={elapsed_ms:.0f}ms",
                trace_id=trace_id
            )
            
            return intelligence
            
        except Exception as e:
            logger.error(f"Enterprise intelligence failed: {e}", trace_id=trace_id, exc_info=True)
            # Return safe fallback with enterprise structure
            return self._create_fallback_intelligence(message_content, memory, str(e))
    
    def _is_simple_continuation(self, message: str) -> bool:
        """Check if message is a simple continuation (fast path)"""
        message_lower = message.lower().strip()
        continuations = [
            "yes", "no", "okay", "ok", "sure", "thanks", "thank you",
            "continue", "go ahead", "tell me more", "what else",
            "please continue", "and then", "what about", "sounds good",
            "perfect", "great", "got it", "understood", "i see"
        ]
        return message_lower in continuations or len(message) < 15
    
    def _handle_continuation(self, message: str, memory: Dict) -> EnterpriseIntelligenceResult:
        """Handle simple continuation with enterprise structure (fast path)"""
        message_lower = message.lower().strip()
        is_agreement = message_lower in ["yes", "okay", "sure", "sounds good", "perfect"]
        
        return EnterpriseIntelligenceResult(
            conversation_analysis=ConversationAnalysis(
                stage=ConversationStage.INTEREST,
                customer_type=CustomerType.UNKNOWN,
                sentiment=Sentiment.POSITIVE if is_agreement else Sentiment.NEUTRAL,
                urgency=Urgency.LOW,
                intent_confidence=0.95
            ),
            primary_intents=[
                IntentDefinition(type=IntentType.FOLLOW_UP, confidence=0.95)
            ],
            entities=EntityExtraction(),
            search_plan=SearchPlan(),  # No retrieval needed
            retrieval_strategy=RetrievalStrategy(
                cache_lookup_first=False,
                semantic_search=False,
                reranking_required=False
            ),
            business_reasoning=BusinessReasoning(
                likely_goal="continuation of previous conversation"
            ),
            response_strategy=ResponseStrategy(
                tone=ResponseTone.FRIENDLY_SUPPORTIVE,
                prompt_template=PromptTemplate.SHORT_REPLY,
                response_depth="concise"
            ),
            turn_count=memory.get("turn_count", 0) + 1,
            is_continuation=True,
            requires_escalation=False
        )
    
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
        
        return "\n\n".join(context_parts)
    
    async def _call_openai_enterprise_intelligence(
        self,
        context: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Call OpenAI Brain #1 with ENTERPRISE PROMPT
        
        Returns STRICT JSON with all enterprise fields
        """
        
        system_prompt = """You are an ENTERPRISE AI CONVERSATION ANALYST for a business automation system.

Your task: DEEPLY ANALYZE the customer email and extract COMPREHENSIVE intelligence.

IMPORTANT: You MUST ONLY use these EXACT values (case-sensitive):

INTENT TYPES (choose from ONLY these):
- pricing_inquiry, product_inquiry, support_request, technical_support_request, technical_assistance
- feature_request, complaint, refund_request, customization_request, bulk_purchase
- partnership_inquiry, technical_question, billing_inquiry, account_issue
- general_inquiry, follow_up, greeting, unknown

PROMPT TEMPLATES (choose from ONLY these):
- sales_pricing_consultative, sales_product_discovery, sales_product_inquiry
- support_technical_troubleshooting, support_technical, support_general_inquiry
- product_inquiry_response, technical_support_response, general_followup, general_engagement
- escalation_complaint_handling, escalation_refund_request, onboarding_guidance, retention_upsell
- follow_up_continuation, short_reply_continuation, multi_intent_enterprise, default_professional

You MUST analyze and extract:

1. CONVERSATION STAGE (awareness/interest/consideration/decision/retention/escalation)
2. CUSTOMER TYPE (b2b/b2c/enterprise/smb/individual)
3. SENTIMENT (positive/neutral/negative/frustrated/angry/urgent)
4. URGENCY (low/medium/high/critical)
5. PRIMARY INTENT with confidence score 0-1
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
    - semantic_queries: conceptual/topic searches
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
{
  "conversation_analysis": {
    "stage": "consideration",
    "customer_type": "b2b",
    "sentiment": "positive",
    "urgency": "medium",
    "intent_confidence": 0.94
  },
  "primary_intents": [
    {"type": "pricing_inquiry", "confidence": 0.97}
  ],
  "secondary_intents": [
    {"type": "customization_request", "confidence": 0.88}
  ],
  "support_intents": [],
  "sales_intents": ["bulk_purchase", "commercial_use"],
  "entities": {
    "products": ["commercial drone"],
    "features": ["customization", "thermal imaging"],
    "industries": ["construction"],
    "quantities": ["10 units"],
    "pricing_terms": [],
    "technical_terms": [],
    "competitors": [],
    "locations": [],
    "timelines": ["delivery in 2 weeks"],
    "budget_indicators": []
  },
  "search_plan": {
    "exact_search_queries": ["commercial drone price", "drone customization options"],
    "semantic_queries": ["construction site drone solutions", "industrial drone applications", "thermal imaging drones"],
    "metadata_queries": ["product_category:drones", "use_case:construction"],
    "support_queries": [],
    "pricing_queries": ["commercial drone pricing tiers", "bulk order discounts", "customization costs"],
    "followup_queries": ["drone delivery timeline", "customization lead time", "warranty coverage"]
  },
  "retrieval_strategy": {
    "cache_lookup_first": true,
    "exact_match_priority": true,
    "semantic_search": true,
    "reranking_required": true,
    "metadata_filtering": true,
    "fusion_required": true
  },
  "business_reasoning": {
    "likely_goal": "Purchase commercial drones for construction company with customization requirements",
    "possible_objections": ["price too high for budget", "customization timeline too long", "technical complexity"],
    "upsell_opportunities": ["premium support plan", "training package", "bulk discount", "extended warranty"],
    "handoff_risk": false
  },
  "response_strategy": {
    "tone": "professional_consultative",
    "prompt_template": "sales_pricing_consultative",
    "response_depth": "detailed"
  }
}
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=1500,  # Increased for comprehensive response
                timeout=20.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON response
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"OpenAI returned invalid JSON: {e} | content={content[:200]}", trace_id=trace_id)
            raise
        except Exception as e:
            logger.error(f"OpenAI Brain #1 call failed: {e}", trace_id=trace_id)
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
            
            # Parse response strategy
            response_strategy_data = raw_result.get("response_strategy", {})
            response_strategy = ResponseStrategy(
                tone=ResponseTone(response_strategy_data.get("tone", "professional_consultative")),
                prompt_template=PromptTemplate(response_strategy_data.get("prompt_template", "default_professional")),
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
    
    def _handle_contextual_continuation(
        self,
        message: str,
        continuation_type: str,
        continuation_context: Dict,
        memory: Dict,
        conversation_id: str
    ) -> EnterpriseIntelligenceResult:
        """
        Handle contextual continuation with MEMORY-FIRST approach.
        
        Uses active topic memory instead of retrieval when possible.
        This is the FASTEST path - target <300ms latency.
        """
        # Get active context from memory
        active_context = self.active_topic_memory.get_active_context(conversation_id)
        
        # Map continuation type to response strategy
        if continuation_type == "affirmative":
            # "yes", "sure", "okay"
            sentiment = Sentiment.POSITIVE
            intent = IntentType.FOLLOW_UP
            prompt_template = PromptTemplate.FOLLOW_UP
            response_depth = "balanced"
            
        elif continuation_type == "negative":
            # "no", "not interested"
            sentiment = Sentiment.NEUTRAL
            intent = IntentType.FOLLOW_UP
            prompt_template = PromptTemplate.SHORT_REPLY
            response_depth = "concise"
            
        elif continuation_type == "interest":
            # "tell me more", "interested"
            sentiment = Sentiment.POSITIVE
            intent = IntentType.PRODUCT_INQUIRY if continuation_context.get("active_topic") else IntentType.GENERAL_INQUIRY
            prompt_template = PromptTemplate.FOLLOW_UP
            response_depth = "detailed"
            
        elif continuation_type == "question":
            # Short questions needing context
            sentiment = Sentiment.NEUTRAL
            resolved_intent = continuation_context.get("resolved_intent", "general_inquiry")
            intent = self._map_string_to_intent_type(resolved_intent)
            prompt_template = PromptTemplate.GENERAL_FOLLOWUP
            response_depth = "balanced"
            
        elif continuation_type == "confirmation":
            # "thanks", "got it"
            sentiment = Sentiment.POSITIVE
            intent = IntentType.FOLLOW_UP
            prompt_template = PromptTemplate.SHORT_REPLY
            response_depth = "concise"
            
        else:
            # Unknown - safe defaults
            sentiment = Sentiment.NEUTRAL
            intent = IntentType.GENERAL_INQUIRY
            prompt_template = PromptTemplate.DEFAULT
            response_depth = "balanced"
        
        # Extract entities from continuation context
        entities_list = continuation_context.get("relevant_entities", [])
        entities = EntityExtraction(
            products=entities_list[:3] if entities_list else []  # First 3 as products
        )
        
        # Determine retrieval strategy based on context
        requires_retrieval = continuation_context.get("requires_retrieval", False)
        
        # Build search plan if retrieval needed
        if requires_retrieval:
            search_plan = SearchPlan(
                semantic_queries=[message[:100]],
                exact_search_queries=[continuation_context.get("active_topic", "")][:1]
            )
        else:
            search_plan = SearchPlan()  # Empty - no retrieval
        
        # Build intelligence result
        return EnterpriseIntelligenceResult(
            conversation_analysis=ConversationAnalysis(
                stage=ConversationStage.INTEREST,
                customer_type=CustomerType.UNKNOWN,
                sentiment=sentiment,
                urgency=Urgency.MEDIUM,
                intent_confidence=0.85
            ),
            primary_intents=[
                IntentDefinition(type=intent, confidence=0.85)
            ],
            entities=entities,
            search_plan=search_plan,
            retrieval_strategy=RetrievalStrategy(
                cache_lookup_first=not requires_retrieval,
                semantic_search=requires_retrieval,
                reranking_required=requires_retrieval
            ),
            business_reasoning=BusinessReasoning(
                likely_goal=continuation_context.get("active_topic", "conversation continuation"),
                handoff_risk=False  # Contextual continuations are safe
            ),
            response_strategy=ResponseStrategy(
                tone=ResponseTone.FRIENDLY_SUPPORTIVE,
                prompt_template=prompt_template,
                response_depth=response_depth
            ),
            turn_count=memory.get("turn_count", 0) + 1,
            is_continuation=True,
            requires_escalation=False
        )
    
    def _map_string_to_intent_type(self, intent_string: str) -> IntentType:
        """Map string intent to IntentType enum."""
        # Try direct mapping
        intent_lower = intent_string.lower().replace("_continuation", "").replace("_clarification", "")
        
        intent_map = {
            "pricing_inquiry": IntentType.PRICING_INQUIRY,
            "pricing": IntentType.PRICING_INQUIRY,
            "product_inquiry": IntentType.PRODUCT_INQUIRY,
            "product": IntentType.PRODUCT_INQUIRY,
            "support_request": IntentType.SUPPORT_REQUEST,
            "support": IntentType.SUPPORT_REQUEST,
            "technical_support": IntentType.TECHNICAL_SUPPORT_REQUEST,
            "technical_assistance": IntentType.TECHNICAL_ASSISTANCE,
            "feature_inquiry": IntentType.FEATURE_REQUEST,
            "feature": IntentType.FEATURE_REQUEST,
            "demo_request": IntentType.GENERAL_INQUIRY,
            "demo": IntentType.GENERAL_INQUIRY,
            "delivery_inquiry": IntentType.GENERAL_INQUIRY,
            "delivery": IntentType.GENERAL_INQUIRY,
            "availability_inquiry": IntentType.GENERAL_INQUIRY,
            "availability": IntentType.GENERAL_INQUIRY,
        }
        
        return intent_map.get(intent_lower, IntentType.GENERAL_INQUIRY)
    
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
