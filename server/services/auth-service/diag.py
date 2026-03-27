import sys, os, asyncio, traceback
sys.path.insert(0, os.path.abspath('../..'))

async def main():
    print("=== DB TEST ===")
    try:
        from shared.database import get_db_session
        from models.user import User
        from sqlalchemy import select
        async with get_db_session() as session:
            result = await session.execute(select(User).limit(1))
            print("DB OK")
    except Exception:
        traceback.print_exc()

    print("\n=== JWT TEST ===")
    try:
        from utils.jwt import create_access_token, create_refresh_token, decode_token
        at = create_access_token("test-id", "test@test.com")
        rt = create_refresh_token("test-id", "test@test.com")
        decoded = decode_token(at)
        print(f"Access token OK: sub={decoded['sub']}, type={decoded['type']}")
        decoded_r = decode_token(rt)
        print(f"Refresh token OK: sub={decoded_r['sub']}, type={decoded_r['type']}")
    except Exception:
        traceback.print_exc()

    print("\n=== PASSWORD TEST ===")
    try:
        from utils.password import hash_password, verify_password
        h = hash_password("TestPass123!")
        ok = verify_password("TestPass123!", h)
        print(f"Password hash/verify OK: {ok}")
    except Exception:
        traceback.print_exc()

    print("\n=== REDIS TEST ===")
    try:
        from shared.cache import get_redis_client
        client = get_redis_client()
        await client.set("diag_test", "ok", ex=10)
        val = await client.get("diag_test")
        print(f"Redis OK: {val}")
    except Exception:
        traceback.print_exc()

    print("\n=== CELERY TEST ===")
    try:
        from shared.celery import get_celery_app
        app = get_celery_app()
        print(f"Celery app OK: broker={app.conf.broker_url[:40]}...")
        # Check broker connection
        conn = app.connection_for_read()
        conn.ensure_connection(max_retries=2)
        print("Celery broker connection OK")
        conn.close()
    except Exception:
        traceback.print_exc()

    print("\n=== QDRANT TEST ===")
    try:
        from shared.vector_db import get_qdrant_client
        client = get_qdrant_client()
        cols = client.get_collections()
        print(f"Qdrant OK: {len(cols.collections)} collections")
    except Exception:
        traceback.print_exc()

    print("\n=== SIGNUP FLOW TEST ===")
    try:
        from shared.database import get_db_session
        from models.user import User
        from utils.password import hash_password
        from utils.jwt import create_access_token, create_refresh_token
        from sqlalchemy import select
        import uuid

        test_email = f"diag_{uuid.uuid4().hex[:8]}@test.com"
        async with get_db_session() as session:
            result = await session.execute(select(User).where(User.email == test_email))
            existing = result.scalar_one_or_none()
            if not existing:
                user = User(
                    email=test_email,
                    password_hash=hash_password("TestPass123!"),
                    full_name="Diag User",
                    business_name="Diag Corp",
                    business_type="SaaS",
                    industry=["Technology"],
                    country="India",
                    timezone="UTC",
                    business_description="Diagnostic test user for enterprise auth",
                    target_audience="SMBs",
                    communication_tone="professional",
                    use_cases=["email_outreach"],
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"User created OK: {user.id}")
                at = create_access_token(str(user.id), user.email)
                rt = create_refresh_token(str(user.id), user.email)
                print(f"Tokens generated OK")
    except Exception:
        traceback.print_exc()

asyncio.run(main())
