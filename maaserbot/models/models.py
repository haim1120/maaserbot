from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .base import Base

class CalculationType(enum.Enum):
    MAASER = "מעשר"  # 10%
    CHOMESH = "חומש"  # 20%

class Currency(enum.Enum):
    ILS = "₪"
    USD = "$"
    EUR = "€"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    default_calc_type = Column(Enum(CalculationType), default=CalculationType.MAASER)
    currency = Column(Enum(Currency), default=Currency.ILS)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    incomes = relationship("Income", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class Income(Base):
    __tablename__ = "incomes"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    calc_type = Column(Enum(CalculationType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="incomes")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="payments") 