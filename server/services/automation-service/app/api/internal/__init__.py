from fastapi import APIRouter, Request
from typing import Any, Dict

router = APIRouter(tags=['internal'])

@router.post('/process')
async def process_event(request: Request) -> Dict[str, Any]:
    body = await request.json()
    return {'received': True, 'keys': list(body.keys())}

@router.get('/ping')
async def ping():
    return {'pong': True}

__all__ = ['router']
