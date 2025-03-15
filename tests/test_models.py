"""Tests for the database models."""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from maaserbot.models.base import Base
from maaserbot.models.models import User, Income, Payment, AccessRequest, CalculationType
from datetime import datetime, timedelta

# Create test database
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_user_creation(db_session: Session):
    """Test that a user can be created and retrieved."""
    # Create a test user
    user = User(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User",
        default_calc_type=CalculationType.MAASER.value,
        is_approved=True,
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    
    # Retrieve the user
    retrieved_user = db_session.query(User).filter_by(telegram_id=123456789).first()
    
    # Check that the user was created correctly
    assert retrieved_user is not None
    assert retrieved_user.telegram_id == 123456789
    assert retrieved_user.username == "test_user"
    assert retrieved_user.first_name == "Test"
    assert retrieved_user.last_name == "User"
    assert retrieved_user.default_calc_type == CalculationType.MAASER.value
    assert retrieved_user.is_approved is True
    assert retrieved_user.is_admin is False

def test_income_creation(db_session: Session):
    """Test that income can be created and associated with a user."""
    # Create a test user
    user = User(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create income for the user
    income = Income(
        user_id=user.id,
        amount=1000.0,
        description="Salary",
        calc_type=CalculationType.MAASER.value
    )
    db_session.add(income)
    db_session.commit()
    
    # Retrieve the income
    retrieved_income = db_session.query(Income).filter_by(user_id=user.id).first()
    
    # Check that the income was created correctly
    assert retrieved_income is not None
    assert retrieved_income.user_id == user.id
    assert retrieved_income.amount == 1000.0
    assert retrieved_income.description == "Salary"
    assert retrieved_income.calc_type == CalculationType.MAASER.value
    assert retrieved_income.created_at is not None

def test_payment_creation(db_session: Session):
    """Test that payment can be created and associated with a user."""
    # Create a test user
    user = User(
        telegram_id=123456789,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create payment for the user
    payment = Payment(
        user_id=user.id,
        amount=100.0
    )
    db_session.add(payment)
    db_session.commit()
    
    # Retrieve the payment
    retrieved_payment = db_session.query(Payment).filter_by(user_id=user.id).first()
    
    # Check that the payment was created correctly
    assert retrieved_payment is not None
    assert retrieved_payment.user_id == user.id
    assert retrieved_payment.amount == 100.0
    assert retrieved_payment.created_at is not None

def test_access_request(db_session: Session):
    """Test that access request can be created and retrieved."""
    # Create a test access request
    request = AccessRequest(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User",
        status="pending"
    )
    db_session.add(request)
    db_session.commit()
    
    # Retrieve the access request
    retrieved_request = db_session.query(AccessRequest).filter_by(telegram_id=123456789).first()
    
    # Check that the access request was created correctly
    assert retrieved_request is not None
    assert retrieved_request.telegram_id == 123456789
    assert retrieved_request.username == "test_user"
    assert retrieved_request.first_name == "Test"
    assert retrieved_request.last_name == "User"
    assert retrieved_request.status == "pending"
    assert retrieved_request.created_at is not None

def test_user_income_relationship(db_session: Session):
    """Test the relationship between users and incomes."""
    # Create a test user
    user = User(
        telegram_id=123456789,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    
    # Create several incomes for the user
    incomes = [
        Income(user_id=user.id, amount=1000.0, description="Salary 1"),
        Income(user_id=user.id, amount=2000.0, description="Salary 2"),
        Income(user_id=user.id, amount=3000.0, description="Bonus")
    ]
    db_session.add_all(incomes)
    db_session.commit()
    
    # Retrieve the user with incomes
    retrieved_user = db_session.query(User).filter_by(telegram_id=123456789).first()
    
    # Check the relationship
    assert len(retrieved_user.incomes) == 3
    assert sum(income.amount for income in retrieved_user.incomes) == 6000.0
    
    # Verify that deleting the user also deletes associated incomes
    db_session.delete(retrieved_user)
    db_session.commit()
    
    # Check that incomes were deleted
    remaining_incomes = db_session.query(Income).all()
    assert len(remaining_incomes) == 0 