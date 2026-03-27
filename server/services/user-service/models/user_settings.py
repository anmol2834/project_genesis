"""
User Settings Model - PostgreSQL
Stores user preferences and settings for the application
"""

from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from sqlalchemy import DateTime
import uuid

from shared.database.postgres import Base


class UserSettings(Base):
    __tablename__ = "user_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    
    # Email Settings
    auto_sync_replies = Column(Boolean, default=True, nullable=False)
    sync_sent_folder = Column(Boolean, default=True, nullable=False)
    sync_frequency = Column(String(10), default='5m', nullable=False)
    
    # AI Settings
    automation_level = Column(String(20), default='assist', nullable=False)
    learn_from_edits = Column(Boolean, default=True, nullable=False)
    personalize_per_lead = Column(Boolean, default=True, nullable=False)
    avoid_repetition = Column(Boolean, default=True, nullable=False)
    max_reply_length = Column(String(10), default='medium', nullable=False)
    
    # Automation Settings
    automation_enabled = Column(Boolean, default=True, nullable=False)
    pause_on_weekends = Column(Boolean, default=True, nullable=False)
    respect_sending_hours = Column(Boolean, default=True, nullable=False)
    delay_between_steps = Column(String(10), default='3d', nullable=False)
    stop_on_reply = Column(Boolean, default=True, nullable=False)
    max_emails_per_lead = Column(Integer, default=5, nullable=False)
    
    # Notification Settings
    email_new_reply = Column(Boolean, default=True, nullable=False)
    email_campaign_complete = Column(Boolean, default=True, nullable=False)
    email_lead_status = Column(Boolean, default=False, nullable=False)
    email_weekly_digest = Column(Boolean, default=True, nullable=False)
    inapp_realtime_replies = Column(Boolean, default=True, nullable=False)
    inapp_ai_actions = Column(Boolean, default=True, nullable=False)
    inapp_team_activity = Column(Boolean, default=False, nullable=False)
    inapp_system_alerts = Column(Boolean, default=True, nullable=False)
    notification_batching = Column(String(10), default='instant', nullable=False)
    
    # Security Settings
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    require_2fa_for_team = Column(Boolean, default=False, nullable=False)
    
    # Team Settings
    workspace_name = Column(String(255), nullable=True)
    default_member_role = Column(String(20), default='member', nullable=False)
    invite_by_domain = Column(Boolean, default=False, nullable=False)
    require_admin_approval = Column(Boolean, default=True, nullable=False)
    
    # Data & Privacy Settings
    analytics_improvement = Column(Boolean, default=True, nullable=False)
    personalization_data = Column(Boolean, default=True, nullable=False)
    third_party_integrations = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    @classmethod
    def create_default_settings(cls, user_id: str):
        """
        Create a UserSettings instance with default values
        """
        return cls(
            user_id=user_id,
            # Email Settings
            auto_sync_replies=True,
            sync_sent_folder=True,
            sync_frequency='5m',
            # AI Settings
            automation_level='assist',
            learn_from_edits=True,
            personalize_per_lead=True,
            avoid_repetition=True,
            max_reply_length='medium',
            # Automation Settings
            automation_enabled=True,
            pause_on_weekends=True,
            respect_sending_hours=True,
            delay_between_steps='3d',
            stop_on_reply=True,
            max_emails_per_lead=5,
            # Notification Settings
            email_new_reply=True,
            email_campaign_complete=True,
            email_lead_status=False,
            email_weekly_digest=True,
            inapp_realtime_replies=True,
            inapp_ai_actions=True,
            inapp_team_activity=False,
            inapp_system_alerts=True,
            notification_batching='instant',
            # Security Settings
            two_factor_enabled=False,
            require_2fa_for_team=False,
            # Team Settings
            workspace_name=None,
            default_member_role='member',
            invite_by_domain=False,
            require_admin_approval=True,
            # Data & Privacy Settings
            analytics_improvement=True,
            personalization_data=True,
            third_party_integrations=False,
        )
    
    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"
