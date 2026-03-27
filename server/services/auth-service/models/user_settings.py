"""
User Settings Model - PostgreSQL
Stores user preferences and settings for the application
Automatically initialized with defaults on user signup
"""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from datetime import datetime
from sqlalchemy import DateTime
import uuid

from shared.database.postgres import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Foreign key to users table
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    
    # ── Email Settings ──────────────────────────────────────────────────────
    auto_sync_replies = Column(Boolean, default=True, nullable=False)
    sync_sent_folder = Column(Boolean, default=True, nullable=False)
    sync_frequency = Column(String(10), default='5m', nullable=False)  # '5m', '15m', '30m'
    
    # ── AI Settings ─────────────────────────────────────────────────────────
    # Note: communication_tone is stored in users table, not here
    automation_level = Column(String(20), default='assist', nullable=False)  # 'off', 'assist', 'auto'
    learn_from_edits = Column(Boolean, default=True, nullable=False)
    personalize_per_lead = Column(Boolean, default=True, nullable=False)
    avoid_repetition = Column(Boolean, default=True, nullable=False)
    max_reply_length = Column(String(10), default='medium', nullable=False)  # 'short', 'medium', 'long'
    
    # ── Automation Settings ─────────────────────────────────────────────────
    automation_enabled = Column(Boolean, default=True, nullable=False)
    pause_on_weekends = Column(Boolean, default=True, nullable=False)
    respect_sending_hours = Column(Boolean, default=True, nullable=False)
    delay_between_steps = Column(String(10), default='3d', nullable=False)  # '1d', '3d', '7d'
    stop_on_reply = Column(Boolean, default=True, nullable=False)
    max_emails_per_lead = Column(Integer, default=5, nullable=False)  # 3, 5, 7
    
    # ── Notification Settings ───────────────────────────────────────────────
    # Email Alerts
    email_new_reply = Column(Boolean, default=True, nullable=False)
    email_campaign_complete = Column(Boolean, default=True, nullable=False)
    email_lead_status = Column(Boolean, default=False, nullable=False)
    email_weekly_digest = Column(Boolean, default=True, nullable=False)
    
    # In-App Alerts
    inapp_realtime_replies = Column(Boolean, default=True, nullable=False)
    inapp_ai_actions = Column(Boolean, default=True, nullable=False)
    inapp_team_activity = Column(Boolean, default=False, nullable=False)
    inapp_system_alerts = Column(Boolean, default=True, nullable=False)
    
    # Notification Frequency
    notification_batching = Column(String(10), default='instant', nullable=False)  # 'instant', 'hourly', 'daily'
    
    # ── Security Settings ───────────────────────────────────────────────────
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    require_2fa_for_team = Column(Boolean, default=False, nullable=False)
    
    # ── Team Settings ───────────────────────────────────────────────────────
    workspace_name = Column(String(255), nullable=True)
    default_member_role = Column(String(20), default='member', nullable=False)  # 'viewer', 'member', 'admin'
    invite_by_domain = Column(Boolean, default=False, nullable=False)
    require_admin_approval = Column(Boolean, default=True, nullable=False)
    
    # ── Data & Privacy Settings ─────────────────────────────────────────────
    analytics_improvement = Column(Boolean, default=True, nullable=False)
    personalization_data = Column(Boolean, default=True, nullable=False)
    third_party_integrations = Column(Boolean, default=False, nullable=False)
    
    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"
    
    @classmethod
    def create_default_settings(cls, user_id: str):
        """
        Factory method to create default settings for a new user
        All defaults are set via Column definitions above
        """
        return cls(user_id=user_id)
