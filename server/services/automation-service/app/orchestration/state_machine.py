"""
Orchestration - State Machine
==============================
Enterprise workflow state machine with transition validation.
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
from app.observability import get_logger

logger = get_logger(__name__)

class WorkflowState:
    """Workflow state definitions"""
    CREATED = "created"
    MEMORY_LOADING = "memory_loading"
    MEMORY_LOADED = "memory_loaded"
    INTELLIGENCE_RUNNING = "intelligence_running"
    INTELLIGENCE_COMPLETED = "intelligence_completed"
    RETRIEVAL_RUNNING = "retrieval_running"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    LLM_GENERATING = "llm_generating"
    LLM_COMPLETED = "llm_completed"
    VALIDATING = "validating"
    VALIDATION_COMPLETED = "validation_completed"
    DECIDING = "deciding"
    DECISION_MADE = "decision_made"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPENSATING = "compensating"

class StateTransition:
    """State transition definition"""
    def __init__(self, from_state: str, to_state: str, condition: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition

class WorkflowStateMachine:
    """Enterprise workflow state machine"""
    
    # Valid state transitions
    TRANSITIONS: Dict[str, List[str]] = {
        WorkflowState.CREATED: [WorkflowState.MEMORY_LOADING, WorkflowState.FAILED],
        WorkflowState.MEMORY_LOADING: [WorkflowState.MEMORY_LOADED, WorkflowState.FAILED, WorkflowState.RETRY_SCHEDULED],
        WorkflowState.MEMORY_LOADED: [WorkflowState.INTELLIGENCE_RUNNING, WorkflowState.FAILED],
        WorkflowState.INTELLIGENCE_RUNNING: [WorkflowState.INTELLIGENCE_COMPLETED, WorkflowState.FAILED, WorkflowState.RETRY_SCHEDULED],
        WorkflowState.INTELLIGENCE_COMPLETED: [WorkflowState.RETRIEVAL_RUNNING, WorkflowState.FAILED],
        WorkflowState.RETRIEVAL_RUNNING: [WorkflowState.RETRIEVAL_COMPLETED, WorkflowState.FAILED, WorkflowState.RETRY_SCHEDULED],
        WorkflowState.RETRIEVAL_COMPLETED: [WorkflowState.LLM_GENERATING, WorkflowState.FAILED],
        WorkflowState.LLM_GENERATING: [WorkflowState.LLM_COMPLETED, WorkflowState.FAILED, WorkflowState.RETRY_SCHEDULED],
        WorkflowState.LLM_COMPLETED: [WorkflowState.VALIDATING, WorkflowState.FAILED],
        WorkflowState.VALIDATING: [WorkflowState.VALIDATION_COMPLETED, WorkflowState.FAILED],
        WorkflowState.VALIDATION_COMPLETED: [WorkflowState.DECIDING, WorkflowState.FAILED],
        WorkflowState.DECIDING: [WorkflowState.DECISION_MADE, WorkflowState.FAILED],
        WorkflowState.DECISION_MADE: [WorkflowState.DISPATCHING, WorkflowState.FAILED],
        WorkflowState.DISPATCHING: [WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.COMPENSATING],
        WorkflowState.FAILED: [WorkflowState.RETRY_SCHEDULED, WorkflowState.COMPENSATING],
        WorkflowState.RETRY_SCHEDULED: [WorkflowState.MEMORY_LOADING],
        WorkflowState.COMPENSATING: [WorkflowState.FAILED],
    }
    
    def __init__(self, workflow_id: str, initial_state: str = WorkflowState.CREATED):
        self.workflow_id = workflow_id
        self.current_state = initial_state
        self.state_history: List[Dict[str, any]] = []
        self.transitions_count = 0
        self._record_state(initial_state)
    
    def transition(self, to_state: str, metadata: Optional[Dict] = None) -> bool:
        """Attempt state transition"""
        if not self.can_transition(to_state):
            logger.warning(
                f"Invalid state transition attempted",
                workflow_id=self.workflow_id,
                from_state=self.current_state,
                to_state=to_state
            )
            return False
        
        logger.debug(
            f"State transition",
            workflow_id=self.workflow_id,
            from_state=self.current_state,
            to_state=to_state
        )
        
        self.current_state = to_state
        self.transitions_count += 1
        self._record_state(to_state, metadata)
        return True
    
    def can_transition(self, to_state: str) -> bool:
        """Check if transition is valid"""
        allowed_states = self.TRANSITIONS.get(self.current_state, [])
        return to_state in allowed_states
    
    def _record_state(self, state: str, metadata: Optional[Dict] = None):
        """Record state in history"""
        self.state_history.append({
            "state": state,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        })
    
    def get_state_duration(self, state: str) -> Optional[float]:
        """Get duration spent in a specific state (ms)"""
        state_entries = [s for s in self.state_history if s["state"] == state]
        if not state_entries:
            return None
        
        start = datetime.fromisoformat(state_entries[0]["timestamp"])
        end = datetime.fromisoformat(state_entries[-1]["timestamp"]) if len(state_entries) > 1 else datetime.utcnow()
        return (end - start).total_seconds() * 1000
    
    def is_terminal_state(self) -> bool:
        """Check if in terminal state"""
        return self.current_state in [WorkflowState.COMPLETED, WorkflowState.FAILED]
    
    def get_state_path(self) -> List[str]:
        """Get complete state path"""
        return [s["state"] for s in self.state_history]

__all__ = ["WorkflowStateMachine", "WorkflowState", "StateTransition"]
