"""Tests for database utility functions."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from maaserbot.models.base import Base
from maaserbot.models.models import User, Income, Payment, AccessRequest, CalculationType
from maaserbot.utils.db import (
    get_or_create_user, add_income, add_payment, get_user_balance,
    get_user_history, create_access_request, approve_access_request,
    reject_access_request
)

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

@pytest.fixture
def mock_admin_id():
    """Set a mock admin ID for testing."""
    with patch('maaserbot.utils.db.ADMIN_ID', 12345):
        yield 12345

def test_get_or_create_user_new(db_session: Session, mock_admin_id):
    """Test creating a new user."""
    telegram_id = 98765
    user = get_or_create_user(db_session, telegram_id, "test_user", "Test", "User")
    
    assert user is not None
    assert user.telegram_id == telegram_id
    assert user.username == "test_user"
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.is_approved is False  # Not admin, so not auto-approved
    assert user.is_admin is False

def test_get_or_create_user_existing(db_session: Session):
    """Test retrieving an existing user."""
    # First create a user
    telegram_id = 98765
    user1 = User(
        telegram_id=telegram_id,
        username="existing_user",
        first_name="Existing",
        last_name="User",
        is_approved=True,
        is_admin=False
    )
    db_session.add(user1)
    db_session.commit()
    
    # Now try to get or create the same user
    user2 = get_or_create_user(db_session, telegram_id)
    
    assert user2 is not None
    assert user2.id == user1.id
    assert user2.username == "existing_user"
    assert user2.is_approved is True

def test_add_income(db_session: Session):
    """Test adding income for a user."""
    # Create a test user
    user = User(
        telegram_id=98765,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    
    # Add income
    income = add_income(db_session, user.id, 1000.0, "Test income", CalculationType.MAASER.value)
    
    # Check the income was added
    assert income is not None
    assert income.user_id == user.id
    assert income.amount == 1000.0
    assert income.description == "Test income"
    assert income.calc_type == CalculationType.MAASER.value

def test_add_payment(db_session: Session):
    """Test adding payment for a user."""
    # Create a test user
    user = User(
        telegram_id=98765,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    
    # Add payment
    payment = add_payment(db_session, user.id, 100.0)
    
    # Check the payment was added
    assert payment is not None
    assert payment.user_id == user.id
    assert payment.amount == 100.0

def test_get_user_balance_maaser(db_session: Session):
    """Test getting user balance with maaser calculation."""
    # Create a test user
    user = User(
        telegram_id=98765,
        username="test_user",
        default_calc_type=CalculationType.MAASER.value
    )
    db_session.add(user)
    db_session.commit()
    
    # Add incomes
    add_income(db_session, user.id, 1000.0, "Income 1", CalculationType.MAASER.value)
    add_income(db_session, user.id, 2000.0, "Income 2", CalculationType.MAASER.value)
    
    # Add payment
    add_payment(db_session, user.id, 150.0)
    
    # Calculate expected balance
    total_income = 1000.0 + 2000.0
    maaser_amount = total_income * 0.1  # 10% for maaser
    expected_balance = maaser_amount - 150.0
    
    # Get balance
    balance = get_user_balance(db_session, user.id)
    
    # Check balance
    assert balance['total_income'] == total_income
    assert balance['maaser_percentage'] == 10
    assert balance['maaser_amount'] == maaser_amount
    assert balance['total_paid'] == 150.0
    assert balance['remaining'] == expected_balance

def test_get_user_balance_chomesh(db_session: Session):
    """Test getting user balance with chomesh calculation."""
    # Create a test user
    user = User(
        telegram_id=98765,
        username="test_user",
        default_calc_type=CalculationType.CHOMESH.value
    )
    db_session.add(user)
    db_session.commit()
    
    # Add incomes
    add_income(db_session, user.id, 1000.0, "Income 1", CalculationType.CHOMESH.value)
    add_income(db_session, user.id, 2000.0, "Income 2", CalculationType.CHOMESH.value)
    
    # Add payment
    add_payment(db_session, user.id, 400.0)
    
    # Calculate expected balance
    total_income = 1000.0 + 2000.0
    maaser_amount = total_income * 0.2  # 20% for chomesh
    expected_balance = maaser_amount - 400.0
    
    # Get balance
    balance = get_user_balance(db_session, user.id)
    
    # Check balance
    assert balance['total_income'] == total_income
    assert balance['maaser_percentage'] == 20
    assert balance['maaser_amount'] == maaser_amount
    assert balance['total_paid'] == 400.0
    assert balance['remaining'] == expected_balance

def test_get_user_history(db_session: Session):
    """Test getting user history."""
    # Create a test user
    user = User(
        telegram_id=98765,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    
    # Add incomes and payments
    add_income(db_session, user.id, 1000.0, "Income 1")
    add_income(db_session, user.id, 2000.0, "Income 2")
    add_payment(db_session, user.id, 150.0)
    add_payment(db_session, user.id, 250.0)
    
    # Get history
    history = get_user_history(db_session, user.id)
    
    # Check history
    assert len(history['incomes']) == 2
    assert len(history['payments']) == 2
    assert history['incomes'][0].amount == 1000.0
    assert history['incomes'][1].amount == 2000.0
    assert history['payments'][0].amount == 150.0
    assert history['payments'][1].amount == 250.0

def test_create_access_request(db_session: Session):
    """Test creating an access request."""
    request = create_access_request(db_session, 98765, "test_user", "Test", "User")
    
    assert request is not None
    assert request.telegram_id == 98765
    assert request.username == "test_user"
    assert request.status == "pending"

def test_approve_access_request(db_session: Session, mock_admin_id):
    """Test approving an access request."""
    # Create an access request
    request = AccessRequest(
        telegram_id=98765,
        username="test_user",
        status="pending"
    )
    db_session.add(request)
    db_session.commit()
    
    # Create a user record (this would normally be created when the user first interacts with the bot)
    user = User(
        telegram_id=98765,
        username="test_user",
        is_approved=False
    )
    db_session.add(user)
    db_session.commit()
    
    # Approve the request
    success = approve_access_request(db_session, mock_admin_id, request.id)
    
    # Check result
    assert success is True
    
    # Check request status
    updated_request = db_session.query(AccessRequest).filter_by(id=request.id).first()
    assert updated_request.status == "approved"
    
    # Check user approval status
    updated_user = db_session.query(User).filter_by(telegram_id=98765).first()
    assert updated_user.is_approved is True

def test_reject_access_request(db_session: Session, mock_admin_id):
    """Test rejecting an access request."""
    # Create an access request
    request = AccessRequest(
        telegram_id=98765,
        username="test_user",
        status="pending"
    )
    db_session.add(request)
    db_session.commit()
    
    # Reject the request
    success = reject_access_request(db_session, mock_admin_id, request.id)
    
    # Check result
    assert success is True
    
    # Check request status
    updated_request = db_session.query(AccessRequest).filter_by(id=request.id).first()
    assert updated_request.status == "rejected" 