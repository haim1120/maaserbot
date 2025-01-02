from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .base import Base

class CalculationType(str, enum.Enum):
    MAASER = "MAASER"
    CHOMESH = "CHOMESH"

class Currency(enum.Enum):
    ILS = "₪"
    USD = "$"
    EUR = "€"

class AccessRequest(Base):
    """Model for access requests."""
    __tablename__ = 'access_requests'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    status = Column(String, default='pending')  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AccessRequest(telegram_id={self.telegram_id}, status={self.status})>"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    default_calc_type = Column(String, default=CalculationType.MAASER)
    currency = Column(String, default="ILS")
    is_approved = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    incomes = relationship("Income", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

class Income(Base):
    __tablename__ = "incomes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    calc_type = Column(String, default=CalculationType.MAASER)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="incomes")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="payments") 