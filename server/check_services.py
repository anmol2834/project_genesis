"""
Service Status Checker
Checks if all services are running and healthy
"""

import asyncio
import httpx
import sys
from datetime import datetime


SERVICES = [
    ("Gateway", 8000),
    ("Auth", 8001),
    ("User", 8002),
    ("Business", 8003),
    ("Email", 8004),
    ("Inbox", 8005),
    ("Campaign", 8006),
    ("Leads", 8007),
    ("Analytics", 8008),
    ("Automation", 8009),
    ("Research", 8010),
    ("Notification", 8011),
]


async def check_service(name: str, port: int):
    """Check if a service is running and healthy"""
    url = f"http://localhost:{port}/health"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": name,
                    "port": port,
                    "status": "HEALTHY",
                    "data": data
                }
            else:
                return {
                    "name": name,
                    "port": port,
                    "status": "UNHEALTHY",
                    "error": f"Status {response.status_code}"
                }
    except httpx.ConnectError:
        return {
            "name": name,
            "port": port,
            "status": "DOWN",
            "error": "Connection refused"
        }
    except Exception as e:
        return {
            "name": name,
            "port": port,
            "status": "ERROR",
            "error": str(e)
        }


async def check_all_services():
    """Check all services"""
    tasks = [check_service(name, port) for name, port in SERVICES]
    results = await asyncio.gather(*tasks)
    return results


def print_results(results):
    """Print service status results"""
    print("\n" + "="*80)
    print(f"SERVICE STATUS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    healthy_count = 0
    
    for result in results:
        name = result["name"]
        port = result["port"]
        status = result["status"]
        
        if status == "HEALTHY":
            symbol = "[OK]"
            healthy_count += 1
            data = result.get("data", {})
            checks = data.get("checks", {})
            db_status = checks.get("database", "N/A")
            redis_status = checks.get("redis", "N/A")
            
            print(f"{symbol} {name:15} Port {port:5} - {status}")
            print(f"    Database: {db_status}, Redis: {redis_status}")
        else:
            symbol = "[!!]"
            error = result.get("error", "Unknown error")
            print(f"{symbol} {name:15} Port {port:5} - {status}")
            print(f"    Error: {error}")
        
        print()
    
    print("="*80)
    print(f"SUMMARY: {healthy_count}/{len(results)} services healthy")
    print("="*80)
    
    return healthy_count == len(results)


async def main():
    """Main function"""
    print("\nChecking all microservices...")
    
    results = await check_all_services()
    all_healthy = print_results(results)
    
    if all_healthy:
        print("\nALL SERVICES ARE HEALTHY!")
        return 0
    else:
        print("\nSOME SERVICES ARE NOT HEALTHY")
        print("Please check the service logs for details")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
