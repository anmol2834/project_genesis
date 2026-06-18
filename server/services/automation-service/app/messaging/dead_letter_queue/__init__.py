import json
import time
from typing import Dict, Any

async def send_to_dlq(redis_client, message: Dict[str, Any], reason: str) -> None:
    payload = {
        'original_message': {k: v for k, v in message.items() if not k.startswith('_')},
        'failure_reason': reason,
        'retry_count': message.get('_retry_count', 0),
        'timestamp': time.time(),
    }
    await redis_client.xadd('automation_dlq', {'data': json.dumps(payload)}, maxlen=10000, approximate=True)

__all__ = ['send_to_dlq']
