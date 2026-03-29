"""
Webhook API - Email Event Receivers
Endpoints for receiving push notifications from Gmail (Pub/Sub) and Outlook (Graph).

IMPORTANT — ngrok setup:
  The endpoint URL in Google Cloud Console must NOT include the port:
    ✅  https://<subdomain>.ngrok-free.app/webhooks/gmail
    ❌  https://<subdomain>.ngrok-free.app:8004/webhooks/gmail

  ngrok already forwards to localhost:8004 — the port in the URL is wrong.
"""

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.responses import PlainTextResponse

from shared.logger import get_logger
from provider.receivers.gmail_receiver import GmailReceiver
from provider.receivers.outlook_receiver import OutlookReceiver

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

gmail_receiver   = GmailReceiver()
outlook_receiver = OutlookReceiver()


@router.post("/gmail")
async def gmail_webhook(request: Request):
    """
    Gmail Pub/Sub push endpoint.
    MUST always return HTTP 200 — any other status causes Pub/Sub to retry.
    All error handling is done inside GmailReceiver.receive_notification().
    """
    try:
        result = await gmail_receiver.receive_notification(request)
        logger.info(f"Gmail webhook: {result.get('status')} | {result.get('message_id', result.get('history_id', ''))}")
        return result
    except Exception as e:
        # Last-resort catch — should never reach here given receiver's own try/except
        logger.error(f"Unhandled Gmail webhook error: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@router.get("/gmail")
async def gmail_webhook_probe():
    """GET probe — health checkers and Google validation."""
    return {"status": "ok", "endpoint": "gmail_webhook"}


@router.get("/debug/account/{email}")
async def debug_account_lookup(email: str):
    """
    Debug endpoint: check if an email account exists in the DB.
    Use this to diagnose 'Email account not found' errors.
    GET /webhooks/debug/account/you@gmail.com
    """
    try:
        from shared.database import get_db_session
        from models.email_account import EmailAccount
        from sqlalchemy import select, text

        async with get_db_session() as session:
            # Check the account
            result = await session.execute(
                select(
                    EmailAccount.id,
                    EmailAccount.email_address,
                    EmailAccount.provider,
                    EmailAccount.connection_status,
                    EmailAccount.is_active,
                    EmailAccount.automation_enabled,
                ).where(EmailAccount.email_address == email)
            )
            row = result.first()

            # Also count all accounts
            count_result = await session.execute(
                select(EmailAccount.email_address, EmailAccount.provider, EmailAccount.connection_status)
            )
            all_accounts = [
                {"email": r[0], "provider": r[1], "status": str(r[2])}
                for r in count_result.all()
            ]

        if row:
            return {
                "found": True,
                "id":     str(row[0]),
                "email":  row[1],
                "provider": str(row[2]),
                "connection_status": str(row[3]),
                "is_active": row[4],
                "automation_enabled": row[5],
                "all_accounts": all_accounts,
            }
        else:
            return {
                "found": False,
                "queried_email": email,
                "all_accounts": all_accounts,
                "hint": "Account not in DB. Connect it via POST /email/connect first.",
            }
    except Exception as e:
        return {"error": str(e)}


@router.post("/outlook")
async def outlook_webhook(request: Request):
    """
    Outlook Graph push endpoint.
    Handles both the one-time validation handshake (POST with ?validationToken)
    and live notifications (POST with JSON body).

    Microsoft validation flow:
      1. You register a subscription → Microsoft sends POST ?validationToken=xxx
      2. We must respond with 200 + plain text token within 10 seconds
      3. Only then does Microsoft confirm the subscription
    """
    # ── Validation handshake (query param, not body) ──────────────────────────
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        logger.info("Outlook webhook validation handshake received")
        return PlainTextResponse(
            content=validation_token,
            status_code=200,
            media_type="text/plain"
        )

    try:
        result = await outlook_receiver.receive_notification(request)

        if isinstance(result, dict) and "validationToken" in result:
            return PlainTextResponse(
                content=result["validationToken"],
                status_code=200,
                media_type="text/plain"
            )

        logger.info(f"Outlook webhook processed: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook webhook error: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@router.get("/outlook")
async def outlook_webhook_get(request: Request):
    """
    GET handler for Outlook validation probe.
    Microsoft sometimes sends a GET with ?validationToken during subscription setup.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        logger.info("Outlook GET validation probe received")
        return PlainTextResponse(
            content=validation_token,
            status_code=200,
            media_type="text/plain"
        )
    return {"status": "ok", "endpoint": "outlook_webhook"}


@router.get("/health")
async def webhook_health():
    """Health check — also useful to verify ngrok tunnel is working."""
    return {
        "status": "healthy",
        "endpoints": {
            "gmail":   "/webhooks/gmail",
            "outlook": "/webhooks/outlook",
        }
    }


@router.post("/gmail/test")
async def gmail_webhook_test(request: Request):
    """
    Manual test endpoint — simulates a Pub/Sub push for a connected Gmail account.
    Body: { "email_address": "you@gmail.com", "history_id": "12345" }
    Use this to verify the full pipeline without waiting for a real email.
    """
    import base64, json
    try:
        body = await request.json()
        email_address = body.get("email_address")
        history_id    = body.get("history_id", "1")

        if not email_address:
            raise HTTPException(status_code=400, detail="email_address required")

        # Build a fake Pub/Sub envelope
        data_payload = json.dumps({
            "emailAddress": email_address,
            "historyId":    history_id
        }).encode()

        fake_request_body = {
            "message": {
                "data":        base64.b64encode(data_payload).decode(),
                "messageId":   f"test_{int(__import__('time').time())}",
                "publishTime": __import__('datetime').datetime.utcnow().isoformat() + "Z"
            },
            "subscription": "projects/test/subscriptions/test"
        }

        from fastapi import Request as FastAPIRequest
        from starlette.testclient import TestClient
        import json as _json

        # Inject the fake body into a new request object
        scope = dict(request.scope)
        body_bytes = _json.dumps(fake_request_body).encode()

        async def receive():
            return {"type": "http.request", "body": body_bytes}

        fake_req = FastAPIRequest(scope, receive)
        result = await gmail_receiver.receive_notification(fake_req)
        return {"status": "test_sent", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail test webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
