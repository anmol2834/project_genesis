"""
Intelligence Layer - Interface Contracts
=========================================
Defines contracts for intent understanding and query planning.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Intent(str, Enum):
    """User intent classification"""
    INTEREST = "interest"
    PRICING = "pricing"
    SUPPORT = "support"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    NEGOTIATION = "negotiation"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


@dataclass
class QueryUnderstanding:
    """Result of query understanding"""
    intent: Intent
    sub_intent: str
    confidence: float
    language: str
    
    # Query transformation
    rewritten_query: str
    keywords: list[str]
    
    # Extracted entities
    entities: dict = field(default_factory=dict)
    
    # Calculation requirements
    calculation_type: str = "none"
    requires_calculation: bool = False
    
    # Feature matching
    strict_requirements: list[str] = field(default_factory=list)
    use_case: str = ""
    
    # Metadata
    source: str = "unknown"


@dataclass
class QueryPlan:
    """Retrieval strategy plan"""
    retrieval_strategy: str  # exact, semantic, hybrid, hierarchical
    memory_dependency: str   # none, low, high
    needs_new_retrieval: bool
    secondary_queries: list[str] = field(default_factory=list)
    expected_chunk_types: list[str] = field(default_factory=list)
    cached_entities_reusable: list[str] = field(default_factory=list)


class IIntentClassifier(ABC):
    """Interface for intent classification"""
    
    @abstractmethod
    async def classify(
        self, 
        content: str, 
        context: Optional[dict] = None
    ) -> tuple[Intent, float]:
        """
        Classify user intent.
        
        Args:
            content: Message content
            context: Optional conversation context
            
        Returns:
            (intent, confidence)
        """
        pass


class IEntityExtractor(ABC):
    """Interface for entity extraction"""
    
    @abstractmethod
    async def extract(
        self,
        content: str,
        intent: Intent
    ) -> dict:
        """
        Extract entities from message.
        
        Args:
            content: Message content
            intent: Classified intent
            
        Returns:
            Dictionary of extracted entities
        """
        pass


class IQueryPlanner(ABC):
    """Interface for retrieval planning"""
    
    @abstractmethod
    def plan(
        self,
        query_understanding: QueryUnderstanding,
        memory: Optional[Any] = None
    ) -> QueryPlan:
        """
        Plan retrieval strategy.
        
        Args:
            query_understanding: Understood query
            memory: Conversation memory
            
        Returns:
            Query plan for retrieval
        """
        pass


class IConfidenceAnalyzer(ABC):
    """Interface for confidence analysis"""
    
    @abstractmethod
    def analyze(
        self,
        query_understanding: QueryUnderstanding,
        retrieval_results: list,
        llm_response: Any
    ) -> float:
        """
        Compute final confidence score.
        
        Args:
            query_understanding: QU result
            retrieval_results: Retrieved chunks
            llm_response: LLM generation
            
        Returns:
            Final confidence score (0.0-1.0)
        """
        pass


class IRiskAnalyzer(ABC):
    """Interface for risk analysis"""
    
    @abstractmethod
    def analyze(
        self,
        query_understanding: QueryUnderstanding,
        content: str
    ) -> tuple[bool, str]:
        """
        Analyze query for high-risk scenarios.
        
        Args:
            query_understanding: QU result
            content: Original message
            
        Returns:
            (is_high_risk, reason)
        """
        pass
