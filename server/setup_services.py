"""
Setup script for all microservices
Creates isolated virtual environments and installs dependencies
"""

import os
import subprocess
import sys
from pathlib import Path

# Service configurations
SERVICES = [
    {
        "name": "gateway-service",
        "port": 8000,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings", 
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
    {
        "name": "auth-service",
        "port": 8001,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "redis", "python-jose[cryptography]",
                        "passlib[bcrypt]", "httpx"]
    },
    {
        "name": "user-service",
        "port": 8002,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "redis", "httpx"]
    },
    {
        "name": "business-service",
        "port": 8003,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
    {
        "name": "email-service",
        "port": 8004,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "celery",
                        "httpx", "google-auth", "google-auth-oauthlib", "google-auth-httplib2"]
    },
    {
        "name": "inbox-service",
        "port": 8005,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
    {
        "name": "campaign-service",
        "port": 8006,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "redis", "celery", "httpx"]
    },
    {
        "name": "leads-service",
        "port": 8007,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "redis", "httpx"]
    },
    {
        "name": "analytics-service",
        "port": 8008,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
    {
        "name": "automation-service",
        "port": 8009,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "redis", "celery", "httpx"]
    },
    {
        "name": "research-service",
        "port": 8010,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
    {
        "name": "notification-service",
        "port": 8011,
        "dependencies": ["fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
                        "python-dotenv", "sqlalchemy", "asyncpg", "motor", "redis", "httpx"]
    },
]


def create_requirements_file(service_name: str, dependencies: list):
    """Create requirements.txt for a service"""
    service_path = Path(f"services/{service_name}")
    requirements_path = service_path / "requirements.txt"
    
    with open(requirements_path, 'w') as f:
        for dep in dependencies:
            f.write(f"{dep}\n")
    
    print(f"  Created requirements.txt for {service_name}")


def create_run_script(service_name: str, port: int):
    """Create run script for a service"""
    service_path = Path(f"services/{service_name}")
    
    # Windows batch script
    run_bat = service_path / "run.bat"
    with open(run_bat, 'w') as f:
        f.write(f"""@echo off
echo Starting {service_name} on port {port}...
cd /d %~dp0
set PYTHONPATH=%~dp0\\..\\..
python main.py
""")
    
    # Unix shell script
    run_sh = service_path / "run.sh"
    with open(run_sh, 'w') as f:
        f.write(f"""#!/bin/bash
echo "Starting {service_name} on port {port}..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
""")
    
    print(f"  Created run scripts for {service_name}")


def setup_service(service: dict):
    """Setup a single service"""
    name = service["name"]
    port = service["port"]
    dependencies = service["dependencies"]
    
    print(f"\nSetting up {name}...")
    
    # Create requirements.txt
    create_requirements_file(name, dependencies)
    
    # Create run scripts
    create_run_script(name, port)
    
    print(f"{name} setup complete!")


def main():
    """Main setup function"""
    print("="*80)
    print("MICROSERVICES SETUP")
    print("="*80)
    print("\nThis will create isolated dependency files for each service")
    print("Each service will have its own requirements.txt and run scripts\n")
    
    # Setup each service
    for service in SERVICES:
        setup_service(service)
    
    print("\n" + "="*80)
    print("ALL SERVICES SETUP COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Run a service: cd services/gateway-service && python main.py")
    print("  3. Or use run scripts: cd services/gateway-service && ./run.sh")
    print("\nEach service now has isolated dependencies!")


if __name__ == "__main__":
    main()
