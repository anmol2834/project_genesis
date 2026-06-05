"""
Storage - Workflow Repository
==============================
Enterprise repository for workflow state persistence.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from shared.database import get_db_session
from sqlalchemy import text
from app.observability import get_logger

logger = get_logger(__name__)

class WorkflowRepository:
    """Enterprise workflow persistence repository"""
    
    async def save_execution_state(
        self,
        execution_id: str,
        workflow_id: str,
        user_id: str,
        state: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Save workflow execution state"""
        query = text("""
            INSERT INTO workflow_executions 
            (execution_id, workflow_id, user_id, state, metadata, created_at, updated_at)
            VALUES (:execution_id, :workflow_id, :user_id, :state, :metadata, :created_at, :updated_at)
            ON CONFLICT (execution_id) 
            DO UPDATE SET 
                state = :state,
                metadata = :metadata,
                updated_at = :updated_at
        """)
        
        try:
            async with get_db_session() as session:
                await session.execute(query, {
                    "execution_id": execution_id,
                    "workflow_id": workflow_id,
                    "user_id": user_id,
                    "state": state,
                    "metadata": metadata,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save execution state", execution_id=execution_id, error=e)
            return False
    
    async def get_execution_state(
        self,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve workflow execution state"""
        query = text("""
            SELECT execution_id, workflow_id, user_id, state, metadata, created_at, updated_at
            FROM workflow_executions
            WHERE execution_id = :execution_id
        """)
        
        try:
            async with get_db_session() as session:
                result = await session.execute(query, {"execution_id": execution_id})
                row = result.fetchone()
                
                if row:
                    return {
                        "execution_id": row[0],
                        "workflow_id": row[1],
                        "user_id": row[2],
                        "state": row[3],
                        "metadata": row[4],
                        "created_at": row[5],
                        "updated_at": row[6]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get execution state", execution_id=execution_id, error=e)
            return None
    
    async def save_replay_snapshot(
        self,
        execution_id: str,
        snapshot_type: str,
        snapshot_data: Dict[str, Any]
    ) -> bool:
        """Save execution snapshot for replay"""
        query = text("""
            INSERT INTO execution_snapshots
            (execution_id, snapshot_type, snapshot_data, created_at)
            VALUES (:execution_id, :snapshot_type, :snapshot_data, :created_at)
        """)
        
        try:
            async with get_db_session() as session:
                await session.execute(query, {
                    "execution_id": execution_id,
                    "snapshot_type": snapshot_type,
                    "snapshot_data": snapshot_data,
                    "created_at": datetime.utcnow()
                })
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save replay snapshot", execution_id=execution_id, error=e)
            return False
    
    async def get_execution_history(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get execution history for user"""
        query = text("""
            SELECT execution_id, workflow_id, state, created_at, updated_at
            FROM workflow_executions
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        try:
            async with get_db_session() as session:
                result = await session.execute(query, {"user_id": user_id, "limit": limit})
                rows = result.fetchall()
                
                return [
                    {
                        "execution_id": row[0],
                        "workflow_id": row[1],
                        "state": row[2],
                        "created_at": row[3],
                        "updated_at": row[4]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get execution history", user_id=user_id, error=e)
            return []

workflow_repository = WorkflowRepository()

__all__ = ["WorkflowRepository", "workflow_repository"]
