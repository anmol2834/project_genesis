"""
OAuth Configuration API
GET /email/oauth/config - Returns OAuth client configuration for frontend
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from shared.config import get_config
from shared.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/email/oauth", tags=["oauth"])

config = get_config()


class OAuthConfigResponse(BaseModel):
    clientId: str
    redirectUri: str
    scope: str
    authUrl: str


@router.get("/config", response_model=OAuthConfigResponse)
async def get_oauth_config(provider: str = Query(..., regex="^(gmail|outlook)$")):
    """
    Returns OAuth configuration for the specified provider.
    Frontend uses this to initiate OAuth flow.
    """
    if provider == "gmail":
        client_id = config.GOOGLE_CLIENT_ID_EMAIL
        if not client_id:
            raise HTTPException(
                status_code=500,
                detail="Gmail OAuth is not configured on the server"
            )
        
        return OAuthConfigResponse(
            clientId=client_id,
            redirectUri=config.GOOGLE_REDIRECT_URI_EMAIL or "http://localhost:3000/oauth/callback",
            scope=" ".join([
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ]),
            authUrl="https://accounts.google.com/o/oauth2/v2/auth",
        )
    
    elif provider == "outlook":
        client_id = config.MICROSOFT_CLIENT_ID_EMAIL
        if not client_id:
            raise HTTPException(
                status_code=500,
                detail="Outlook OAuth is not configured on the server"
            )
        
        tenant_id = config.MICROSOFT_TENANT_ID_EMAIL or "common"
        
        return OAuthConfigResponse(
            clientId=client_id,
            redirectUri=config.MICROSOFT_REDIRECT_URI_EMAIL or "http://localhost:3000/oauth/callback",
            scope=" ".join([
                "https://graph.microsoft.com/Mail.Send",
                "https://graph.microsoft.com/Mail.Read",
                "https://graph.microsoft.com/User.Read",
                "offline_access",
            ]),
            authUrl=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        )
    
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
