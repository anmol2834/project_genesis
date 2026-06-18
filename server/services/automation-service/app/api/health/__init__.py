from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=['health'])

@router.get('/live')
async def liveness():
    return {'status': 'alive', 'timestamp': datetime.utcnow().isoformat()}

@router.get('/ready')
async def readiness():
    try:
        from app.core.resource_management import get_resource_manager
        mgr = get_resource_manager()
        health = await mgr.health_check()
        redis_ok = health.get('redis', {}).get('status') == 'healthy'
        db_ok = health.get('database', {}).get('status') == 'healthy'
        ready = redis_ok and db_ok
        return {'status': 'ready' if ready else 'not_ready', 'checks': health,
                'timestamp': datetime.utcnow().isoformat()}
    except Exception as e:
        return {'status': 'not_ready', 'error': str(e), 'timestamp': datetime.utcnow().isoformat()}

@router.get('/deep')
async def deep_health():
    from app.core.health import get_health_system
    return await get_health_system().check_all()

__all__ = ['router']
