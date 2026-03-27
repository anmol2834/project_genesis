"""
User Settings Schemas
Pydantic models for settings request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Get Settings Response ────────────────────────────────────────────────────

class UserSettingsResponse(BaseModel):
    # Email Settings
    auto_sync_replies: bool
    sync_sent_folder: bool
    sync_frequency: str  # '5m', '15m', '30m'
    
    # AI Settings
    automation_level: str  # 'off', 'assist', 'auto'
    learn_from_edits: bool
    personalize_per_lead: bool
    avoid_repetition: bool
    max_reply_length: str  # 'short', 'medium', 'long'
    
    # Automation Settings
    automation_enabled: bool
    pause_on_weekends: bool
    respect_sending_hours: bool
    delay_between_steps: str  # '1d', '3d', '7d'
    stop_on_reply: bool
    max_emails_per_lead: int
    
    # Notification Settings
    email_new_reply: bool
    email_campaign_complete: bool
    email_lead_status: bool
    email_weekly_digest: bool
    inapp_realtime_replies: bool
    inapp_ai_actions: bool
    inapp_team_activity: bool
    inapp_system_alerts: bool
    notification_batching: str  # 'instant', 'hourly', 'daily'
    
    # Security Settings
    two_factor_enabled: bool
    require_2fa_for_team: bool
    
    # Team Settings
    workspace_name: Optional[str]
    default_member_role: str  # 'viewer', 'member', 'admin'
    invite_by_domain: bool
    require_admin_approval: bool
    
    # Data & Privacy Settings
    analytics_improvement: bool
    personalization_data: bool
    third_party_integrations: bool
    
    class Config:
        from_attributes = True


# ── Update Settings Request ──────────────────────────────────────────────────

class UpdateUserSettingsRequest(BaseModel):
    # Email Settings
    auto_sync_replies: Optional[bool] = None
    sync_sent_folder: Optional[bool] = None
    sync_frequency: Optional[str] = Field(None, pattern='^(5m|15m|30m)$')
    
    # AI Settings
    automation_level: Optional[str] = Field(None, pattern='^(off|assist|auto)$')
    learn_from_edits: Optional[bool] = None
    personalize_per_lead: Optional[bool] = None
    avoid_repetition: Optional[bool] = None
    max_reply_length: Optional[str] = Field(None, pattern='^(short|medium|long)$')
    
    # Automation Settings
    automation_enabled: Optional[bool] = None
    pause_on_weekends: Optional[bool] = None
    respect_sending_hours: Optional[bool] = None
    delay_between_steps: Optional[str] = Field(None, pattern='^(1d|3d|7d)$')
    stop_on_reply: Optional[bool] = None
    max_emails_per_lead: Optional[int] = Field(None, ge=1, le=10)
    
    # Notification Settings
    email_new_reply: Optional[bool] = None
    email_campaign_complete: Optional[bool] = None
    email_lead_status: Optional[bool] = None
    email_weekly_digest: Optional[bool] = None
    inapp_realtime_replies: Optional[bool] = None
    inapp_ai_actions: Optional[bool] = None
    inapp_team_activity: Optional[bool] = None
    inapp_system_alerts: Optional[bool] = None
    notification_batching: Optional[str] = Field(None, pattern='^(instant|hourly|daily)$')
    
    # Security Settings
    two_factor_enabled: Optional[bool] = None
    require_2fa_for_team: Optional[bool] = None
    
    # Team Settings
    workspace_name: Optional[str] = Field(None, max_length=255)
    default_member_role: Optional[str] = Field(None, pattern='^(viewer|member|admin)$')
    invite_by_domain: Optional[bool] = None
    require_admin_approval: Optional[bool] = None
    
    # Data & Privacy Settings
    analytics_improvement: Optional[bool] = None
    personalization_data: Optional[bool] = None
    third_party_integrations: Optional[bool] = None
