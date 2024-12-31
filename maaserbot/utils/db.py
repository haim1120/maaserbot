from sqlalchemy.orm import Session
from maaserbot.models.models import User, Income, Payment, CalculationType, Currency
from datetime import datetime

def get_or_create_user(db: Session, telegram_id: int) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def add_income(db: Session, user_id: int, amount: float, calc_type: CalculationType, description: str = None) -> Income:
    income = Income(
        user_id=user_id,
        amount=amount,
        calc_type=calc_type,
        description=description
    )
    db.add(income)
    db.commit()
    db.refresh(income)
    return income

def add_payment(db: Session, user_id: int, amount: float) -> Payment:
    payment = Payment(
        user_id=user_id,
        amount=amount
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

def get_user_balance(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
        
    total_income = 0
    total_maaser = 0
    total_paid = 0
    
    # Calculate total income and maaser
    for income in user.incomes:
        total_income += income.amount
        if income.calc_type == CalculationType.MAASER:
            total_maaser += income.amount * 0.1
        else:  # CHOMESH
            total_maaser += income.amount * 0.2
            
    # Calculate total paid
    for payment in user.payments:
        total_paid += payment.amount
        
    return {
        "total_income": total_income,
        "total_maaser": total_maaser,
        "total_paid": total_paid,
        "remaining": total_maaser - total_paid
    } 

def get_user_history(db: Session, user_id: int, limit: int = 10) -> dict:
    """Get user's income and payment history."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
        
    incomes = db.query(Income).filter(Income.user_id == user_id).order_by(Income.created_at.desc()).limit(limit).all()
    payments = db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).limit(limit).all()
    
    return {
        "incomes": incomes,
        "payments": payments,
        "currency": user.currency
    } 

def update_user_settings(db: Session, user_id: int, default_calc_type: CalculationType = None, currency: Currency = None) -> User:
    """Update user settings."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
        
    if default_calc_type is not None:
        user.default_calc_type = default_calc_type
    if currency is not None:
        user.currency = currency
        
    db.commit()
    db.refresh(user)
    return user 

def delete_all_user_data(db: Session, user_id: int) -> None:
    """Delete all data associated with a user."""
    try:
        # Delete all incomes
        db.query(Income).filter(Income.user_id == user_id).delete(synchronize_session=False)
        
        # Delete all payments
        db.query(Payment).filter(Payment.user_id == user_id).delete(synchronize_session=False)
        
        # Get user and reset settings
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.default_calc_type = CalculationType.MAASER
            user.currency = Currency.ILS
            
        # Commit all changes
        db.commit()
        
        # Refresh session
        db.expire_all()
    except Exception as e:
        db.rollback()
        raise e 