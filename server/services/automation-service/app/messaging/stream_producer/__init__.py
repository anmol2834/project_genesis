import json
from typing import Dict, Any

async def publish_response(redis_client, payload: Dict[str, Any]) -> None:
    pipe = redis_client.pipeline(transaction=False)
    pipe.xadd('automation_responses', {'data': json.dumps(payload)}, maxlen=10000, approximate=True)
    pipe.publish('automation:response:wake', '1')
    await pipe.execute()

__all__ = ['publish_response']
