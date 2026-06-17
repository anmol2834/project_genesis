from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=['admin'])

@router.get('/status')
async def pipeline_status():
    from app.orchestration.execution_engine import execution_engine
    return {
        'service': 'automation-service',
        'active_executions': len(execution_engine.active_executions),
        'timestamp': datetime.utcnow().isoformat(),
    }

@router.get('/health')
async def admin_health():
    from app.core.health import get_health_system
    return await get_health_system().check_all()

__all__ = ['router']
