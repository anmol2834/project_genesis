from fastapi import APIRouter, Response
from app.observability import get_metrics_collector

router = APIRouter(tags=['metrics'])

@router.get('')
@router.get('/')
async def metrics_json():
    collector = get_metrics_collector()
    return collector.get_metric_summary()

@router.get('/counters')
async def counters():
    collector = get_metrics_collector()
    return {'counters': collector.counters, 'gauges': collector.gauges}

__all__ = ['router']
