"""
Global Models - Validation Engine
==================================
Enterprise schema validation and tenant isolation enforcement.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError
from app.models.base import BaseTenant

class ValidationResult(BaseModel):
    """Validation result"""
    valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    
class TenantIsolationError(Exception):
    """Tenant isolation violation"""
    pass

class SchemaValidator:
    """Enterprise schema validator"""
    
    @staticmethod
    def validate_model(data: Dict[str, Any], model_class: type[BaseModel]) -> ValidationResult:
        """Validate data against Pydantic model"""
        try:
            model_class.model_validate(data)
            return ValidationResult(valid=True)
        except ValidationError as e:
            errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            return ValidationResult(valid=False, errors=errors)
    
    @staticmethod
    def validate_tenant_isolation(obj: Any, expected_user_id: str) -> None:
        """Enforce tenant isolation"""
        if not hasattr(obj, 'user_id'):
            raise TenantIsolationError("Object missing user_id field")
        
        if obj.user_id != expected_user_id:
            raise TenantIsolationError(
                f"Tenant mismatch: expected {expected_user_id}, got {obj.user_id}"
            )
    
    @staticmethod
    def validate_trace_context(obj: Any) -> bool:
        """Validate trace context presence"""
        required = ['trace_id', 'user_id']
        return all(hasattr(obj, field) and getattr(obj, field) for field in required)
    
    @staticmethod
    def validate_event_schema(event: Dict[str, Any]) -> ValidationResult:
        """Validate event structure"""
        required_fields = ['event_id', 'event_type', 'user_id', 'trace_id']
        missing = [f for f in required_fields if f not in event]
        
        if missing:
            return ValidationResult(
                valid=False,
                errors=[f"Missing required field: {f}" for f in missing]
            )
        return ValidationResult(valid=True)

__all__ = ["SchemaValidator", "ValidationResult", "TenantIsolationError"]
