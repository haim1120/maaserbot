from sqlalchemy.orm import Session
from maaserbot.models.models import User, Income, Payment, CalculationType, Currency, AccessRequest
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

# Load environment variables
load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Default to 0 if not set

# הגדרת לוגר
logger = logging.getLogger(__name__)

def get_or_create_user(db: Session, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    """Get or create a user."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            default_calc_type=CalculationType.MAASER.value,
            currency=Currency.ILS.value,
            is_approved=telegram_id == ADMIN_ID,
            is_admin=telegram_id == ADMIN_ID
        )
        db.add(user)
        db.commit()
    return user

def create_access_request(db: Session, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> AccessRequest:
    """Create a new access request."""
    try:
        # Check if there's already a pending request
        existing_request = db.query(AccessRequest).filter(
            AccessRequest.telegram_id == telegram_id,
            AccessRequest.status == "pending"
        ).first()
        
        if existing_request:
            return existing_request
            
        request = AccessRequest(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        logger.info(f"Created new access request for user {telegram_id}")
        return request
    except SQLAlchemyError as e:
        logger.error(f"Database error in create_access_request: {str(e)}")
        db.rollback()
        raise

def get_pending_access_requests(db: Session) -> list[AccessRequest]:
    """Get all pending access requests."""
    try:
        return db.query(AccessRequest).filter(AccessRequest.status == "pending").all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_pending_access_requests: {str(e)}")
        raise

def approve_access_request(db: Session, admin_id: int, request_id: int) -> bool:
    """Approve an access request."""
    try:
        admin = db.query(User).filter(User.telegram_id == admin_id).first()
        if not admin or not admin.is_admin:
            logger.warning(f"Non-admin user {admin_id} tried to approve access request")
            return False
            
        request = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
        if not request or request.status != "pending":
            return False
            
        # Update request status
        request.status = "approved"
        
        # Create or update user
        user = get_or_create_user(
            db, 
            request.telegram_id,
            request.username,
            request.first_name,
            request.last_name
        )
        user.is_approved = True
        
        db.commit()
        logger.info(f"Access request {request_id} approved by admin {admin_id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database error in approve_access_request: {str(e)}")
        db.rollback()
        raise

def reject_access_request(db: Session, admin_id: int, request_id: int) -> bool:
    """Reject an access request."""
    try:
        admin = db.query(User).filter(User.telegram_id == admin_id).first()
        if not admin or not admin.is_admin:
            logger.warning(f"Non-admin user {admin_id} tried to reject access request")
            return False
            
        request = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
        if not request or request.status != "pending":
            return False
            
        request.status = "rejected"
        db.commit()
        logger.info(f"Access request {request_id} rejected by admin {admin_id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database error in reject_access_request: {str(e)}")
        db.rollback()
        raise

def add_income(db: Session, user_id: int, amount: float, calc_type: CalculationType = None, description: str = None) -> Income:
    """Add a new income."""
    if calc_type is None:
        user = db.query(User).filter(User.id == user_id).first()
        calc_type = user.default_calc_type
    income = Income(
        user_id=user_id,
        amount=amount,
        calc_type=calc_type.value if isinstance(calc_type, CalculationType) else calc_type,
        description=description
    )
    db.add(income)
    db.commit()
    logger.info(f"Added income for user {user_id}: {amount}")
    return income

def add_payment(db: Session, user_id: int, amount: float) -> Payment:
    """Add a new payment."""
    try:
        payment = Payment(
            user_id=user_id,
            amount=amount
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        logger.info(f"Added payment for user {user_id}: {amount}")
        return payment
    except SQLAlchemyError as e:
        logger.error(f"Database error in add_payment: {str(e)}")
        db.rollback()
        raise

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

def get_user_history(db: Session, user_id: int, page: int = 1, items_per_page: int = 5) -> dict:
    """Get user's income and payment history with pagination."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
        
    # Get total counts
    total_incomes = db.query(Income).filter(Income.user_id == user_id).count()
    total_payments = db.query(Payment).filter(Payment.user_id == user_id).count()
    
    # Calculate offset
    offset = (page - 1) * items_per_page
        
    incomes = db.query(Income).filter(Income.user_id == user_id).order_by(Income.created_at.desc()).offset(offset).limit(items_per_page).all()
    payments = db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).offset(offset).limit(items_per_page).all()
    
    # Calculate total pages
    total_items = max(total_incomes, total_payments)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    return {
        "incomes": incomes,
        "payments": payments,
        "currency": user.currency,
        "current_page": page,
        "total_pages": total_pages,
        "total_incomes": total_incomes,
        "total_payments": total_payments
    } 

def update_user_settings(db: Session, user_id: int, default_calc_type: CalculationType = None, currency: Currency = None) -> User:
    """Update user settings."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if default_calc_type is not None:
            user.default_calc_type = default_calc_type.value
        if currency is not None:
            user.currency = currency.value
        db.commit()
    return user

def delete_all_user_data(db: Session, user_id: int) -> bool:
    """Delete all data for a user."""
    try:
        db.query(Income).filter(Income.user_id == user_id).delete()
        db.query(Payment).filter(Payment.user_id == user_id).delete()
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.default_calc_type = CalculationType.MAASER.value
            user.currency = Currency.ILS.value
        db.commit()
        logger.warning(f"Deleted all data for user {user_id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database error in delete_all_user_data: {str(e)}")
        db.rollback()
        return False

def delete_income(db: Session, income_id: int, user_id: int) -> bool:
    """מחיקת הכנסה ספציפית."""
    try:
        income = db.query(Income).filter(Income.id == income_id, Income.user_id == user_id).first()
        if not income:
            logger.warning(f"ניסיון למחוק הכנסה {income_id} שלא קיימת או לא שייכת למשתמש {user_id}")
            return False
            
        db.delete(income)
        db.commit()
        logger.info(f"הכנסה {income_id} נמחקה בהצלחה")
        return True
    except Exception as e:
        logger.error(f"שגיאה במחיקת הכנסה {income_id}: {str(e)}")
        db.rollback()
        raise

def delete_payment(db: Session, payment_id: int, user_id: int) -> bool:
    """מחיקת תשלום ספציפי."""
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user_id).first()
        if not payment:
            logger.warning(f"ניסיון למחוק תשלום {payment_id} שלא קיים או לא שייך למשתמש {user_id}")
            return False
            
        db.delete(payment)
        db.commit()
        logger.info(f"תשלום {payment_id} נמחק בהצלחה")
        return True
    except Exception as e:
        logger.error(f"שגיאה במחיקת תשלום {payment_id}: {str(e)}")
        db.rollback()
        raise

def edit_income(db: Session, income_id: int, user_id: int, amount: float = None, description: str = None, calc_type: CalculationType = None) -> Income:
    """עריכת הכנסה קיימת."""
    try:
        income = db.query(Income).filter(Income.id == income_id, Income.user_id == user_id).first()
        if not income:
            logger.warning(f"ניסיון לערוך הכנסה {income_id} שלא קיימת או לא שייכת למשתמש {user_id}")
            return None
            
        if amount is not None:
            income.amount = amount
        if description is not None:
            income.description = description
        if calc_type is not None:
            income.calc_type = calc_type
            
        db.commit()
        db.refresh(income)
        logger.info(f"הכנסה {income_id} עודכנה בהצלחה")
        return income
    except Exception as e:
        logger.error(f"שגיאה בעריכת הכנסה {income_id}: {str(e)}")
        db.rollback()
        raise

def edit_payment(db: Session, payment_id: int, user_id: int, amount: float) -> Payment:
    """עריכת תשלום קיים."""
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user_id).first()
        if not payment:
            logger.warning(f"ניסיון לערוך תשלום {payment_id} שלא קיים או לא שייך למשתמש {user_id}")
            return None
            
        payment.amount = amount
        db.commit()
        db.refresh(payment)
        logger.info(f"תשלום {payment_id} עודכן בהצלחה")
        return payment
    except Exception as e:
        logger.error(f"שגיאה בעריכת תשלום {payment_id}: {str(e)}")
        db.rollback()
        raise 

def approve_user(db: Session, admin_id: int, user_telegram_id: int) -> bool:
    """Approve a user. Only admins can approve users."""
    try:
        admin = db.query(User).filter(User.telegram_id == admin_id, User.is_admin == True).first()
        if not admin:
            logger.warning(f"Non-admin user {admin_id} tried to approve user {user_telegram_id}")
            return False
            
        user = db.query(User).filter(User.telegram_id == user_telegram_id).first()
        if not user:
            logger.warning(f"Tried to approve non-existent user {user_telegram_id}")
            return False
            
        user.is_approved = True
        db.commit()
        logger.info(f"User {user_telegram_id} approved by admin {admin_id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database error in approve_user: {str(e)}")
        db.rollback()
        return False

def remove_user_approval(db: Session, admin_id: int, user_telegram_id: int) -> bool:
    """Remove user approval. Only admins can remove approval."""
    try:
        admin = db.query(User).filter(User.telegram_id == admin_id, User.is_admin == True).first()
        if not admin:
            logger.warning(f"Non-admin user {admin_id} tried to remove approval from user {user_telegram_id}")
            return False
            
        user = db.query(User).filter(User.telegram_id == user_telegram_id).first()
        if not user:
            logger.warning(f"Tried to remove approval from non-existent user {user_telegram_id}")
            return False
            
        if user.is_admin:
            logger.warning(f"Tried to remove approval from admin user {user_telegram_id}")
            return False
            
        user.is_approved = False
        db.commit()
        logger.info(f"User {user_telegram_id} approval removed by admin {admin_id}")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database error in remove_user_approval: {str(e)}")
        db.rollback()
        return False

def get_all_users(db: Session, admin_id: int) -> list:
    """Get all users. Only admins can see all users."""
    try:
        admin = db.query(User).filter(User.telegram_id == admin_id, User.is_admin == True).first()
        if not admin:
            logger.warning(f"Non-admin user {admin_id} tried to get all users")
            return None
            
        users = db.query(User).all()
        return users
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_all_users: {str(e)}")
        db.rollback()
        return None 