"""
User Model - PostgreSQL
Stores user account and business context data
NOTE: This is a copy from auth-service for foreign key resolution
"""

from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from shared.database.postgres import Base


class User(Base):
    __tablename__ = "users"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    full_name = Column(String(255), nullable=False)
    profile_pic = Column(String(500), nullable=True, default="https://api.dicebear.com/7.x/initials/svg?seed=")
    
    # Business information
    business_name = Column(String(255), nullable=False)
    business_type = Column(String(100), nullable=False)
    industry = Column(JSON, nullable=True)  # Array of industries
    country = Column(String(100), nullable=False)
    timezone = Column(String(100), nullable=False)
    
    # AI Context
    business_description = Column(Text, nullable=True)
    target_audience = Column(Text, nullable=True)
    communication_tone = Column(String(50), nullable=True)
    use_cases = Column(JSON, nullable=True)  # Array of use case keys
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<User {self.email}>"
