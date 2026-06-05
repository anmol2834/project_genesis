"""
Global Models - Serialization System
=====================================
Enterprise-safe serialization for Redis, Qdrant, and event replay.
"""
import json
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.enums import ChunkType

class SerializationError(Exception):
    """Serialization operation failed"""
    pass

class Serializer:
    """Enterprise serializer with Redis and Qdrant compatibility"""
    
    @staticmethod
    def to_redis(obj: Any) -> str:
        """Serialize for Redis storage"""
        if isinstance(obj, BaseModel):
            return obj.model_dump_json()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return json.dumps(obj, default=Serializer._json_default)
        return str(obj)
    
    @staticmethod
    def from_redis(data: str, model_class: Optional[type] = None) -> Any:
        """Deserialize from Redis"""
        if not data:
            return None
        if model_class and issubclass(model_class, BaseModel):
            return model_class.model_validate_json(data)
        return json.loads(data)
    
    @staticmethod
    def to_qdrant_payload(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare payload for Qdrant storage"""
        payload = {}
        for key, value in obj.items():
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                payload[key] = json.dumps(value) if len(str(value)) > 1000 else value
            elif isinstance(value, BaseModel):
                payload[key] = value.model_dump()
            else:
                payload[key] = value
        return payload
    
    @staticmethod
    def from_qdrant_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize from Qdrant payload"""
        return payload
    
    @staticmethod
    def _json_default(obj: Any) -> Any:
        """Custom JSON serializer"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)

__all__ = ["Serializer", "SerializationError"]
