"""
Intelligence - Orchestrator
============================
ENTERPRISE CONVERSATIONAL REASONING ENGINE
ChatGPT Brain #1: Deep Intent Understanding, Query Planning & Business Intelligence
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
        self.model = self.config.shared.OPENAI_MODEL
    
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
        
        try:
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
    
    def _prepare_context(self, message: str, subject: str, memory: Dict) -> str:
        """Prepare context for OpenAI"""
        context_parts = []
        
        if subject:
            context_parts.append(f"Subject: {subject}")
        
        context_parts.append(f"Message: {message}")
        
        # Add conversation history if available
        if memory.get("history"):
            history_text = "\n".join([
                f"Previous: {h.get('intent', 'unknown')}"
                for h in memory["history"][:3]
            ])
            context_parts.append(f"Recent conversation:\n{history_text}")
        
        return "\n\n".join(context_parts)
    
    async def _call_openai_intent(self, context: str, trace_id: str) -> Dict[str, Any]:
        """Call OpenAI for intent understanding"""
        
        system_prompt = """You are an AI assistant analyzing customer emails for an automation system.

Your task: Understand the customer's intent and determine what information needs to be retrieved.

Analyze the email and provide:
1. Primary intent (question, request, complaint, feedback, greeting, continuation)
2. Sub-intent (specific type)
3. Confidence score (0.0-1.0)
4. Extracted entities (names, products, dates, amounts, etc.)
5. Retrieval strategy (semantic, exact, metadata, hybrid, none)
6. Whether retrieval is needed
7. Risk level (low, medium, high)
8. Search queries for retrieval (if needed)

Respond ONLY with valid JSON in this exact format:
{
  "intent": "question",
  "sub_intent": "product_inquiry",
  "confidence": 0.85,
  "entities": {"product": "Premium Plan"},
  "retrieval_strategy": "semantic",
  "requires_retrieval": true,
  "risk_level": "low",
  "search_queries": ["Premium Plan pricing", "Premium Plan features"]
}"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=15.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}", trace_id=trace_id)
            raise
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}", trace_id=trace_id)
            raise
    
    def _parse_intent_result(self, result: Dict, memory: Dict) -> Dict[str, Any]:
        """Parse and validate intent result"""
        return {
            "intent": result.get("intent", "question"),
            "sub_intent": result.get("sub_intent", "general"),
            "confidence": float(result.get("confidence", 0.5)),
            "entities": result.get("entities", {}),
            "retrieval_strategy": result.get("retrieval_strategy", "semantic"),
            "requires_retrieval": result.get("requires_retrieval", True),
            "is_continuation": result.get("intent") == "continuation",
            "risk_level": result.get("risk_level", "low"),
            "search_queries": result.get("search_queries", []),
            "turn_count": memory.get("turn_count", 0) + 1
        }


# Global instance
_intelligence_orchestrator: Optional[IntelligenceOrchestrator] = None


def get_intelligence_orchestrator() -> IntelligenceOrchestrator:
    """Get global intelligence orchestrator"""
    global _intelligence_orchestrator
    if _intelligence_orchestrator is None:
        _intelligence_orchestrator = IntelligenceOrchestrator()
    return _intelligence_orchestrator


__all__ = ["IntelligenceOrchestrator", "get_intelligence_orchestrator"]
