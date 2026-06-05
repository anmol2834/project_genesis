"""
Core - Runtime Kernel
======================
Enterprise runtime infrastructure for automation-service.
"""

# Runtime
from app.core.runtime import (
    AutomationServiceRuntime,
    get_runtime,
    run_application
)

# Lifecycle
from app.core.startup import StartupEngine, create_startup_sequence
from app.core.shutdown import ShutdownEngine, create_shutdown_sequence, setup_signal_handlers

# Dependency Injection
from app.core.dependency_injection import (
    DIContainer,
    ServiceScope,
    get_container,
    reset_container
)

# Execution Context
from app.core.execution_context import (
    ExecutionContext,
    set_execution_context,
    get_execution_context,
    clear_execution_context,
    ensure_execution_context,
    execution_context
)

# Resource Management
from app.core.resource_management import (
    ResourceManager,
    get_resource_manager,
    initialize_resources,
    shutdown_resources
)

# Health
from app.core.health import (
    HealthCheckSystem,
    HealthStatus,
    HealthCheck,
    get_health_system
)

# Exceptions - only import what exists
from app.core.exceptions import (
    ConfigurationError,
    PipelineError,
    ValidationError
)


__all__ = [
    # Runtime
    "AutomationServiceRuntime",
    "get_runtime",
    "run_application",
    
    # Lifecycle
    "StartupEngine",
    "create_startup_sequence",
    "ShutdownEngine",
    "create_shutdown_sequence",
    "setup_signal_handlers",
    
    # DI
    "DIContainer",
    "ServiceScope",
    "get_container",
    "reset_container",
    
    # Context
    "ExecutionContext",
    "set_execution_context",
    "get_execution_context",
    "clear_execution_context",
    "ensure_execution_context",
    "execution_context",
    
    # Resources
    "ResourceManager",
    "get_resource_manager",
    "initialize_resources",
    "shutdown_resources",
    
    # Health
    "HealthCheckSystem",
    "HealthStatus",
    "HealthCheck",
    "get_health_system",
    
    # Exceptions
    "ConfigurationError",
    "PipelineError",
    "ValidationError",
]
