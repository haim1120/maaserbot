"""Error handling utilities for MaaserBot."""

import logging
from typing import Optional, Type, Dict, Any, Callable, Awaitable
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.exc import SQLAlchemyError
import traceback

# הגדרת לוגר
logger = logging.getLogger(__name__)

class MaaserBotError(Exception):
    """Base exception class for MaaserBot."""
    def __init__(self, message: str, user_message: str = None):
        self.message = message
        self.user_message = user_message or "אירעה שגיאה בעת ביצוע הפעולה. נסה שוב מאוחר יותר."
        super().__init__(self.message)

class DatabaseError(MaaserBotError):
    """Exception raised for database errors."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message,
            user_message or "אירעה שגיאה בגישה למסד הנתונים. נסה שוב מאוחר יותר."
        )

class AuthorizationError(MaaserBotError):
    """Exception raised for authorization errors."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message,
            user_message or "אין לך הרשאה לבצע פעולה זו."
        )

class ValidationError(MaaserBotError):
    """Exception raised for validation errors."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message,
            user_message or "הנתונים שהוזנו אינם תקינים. אנא בדוק את הנתונים ונסה שוב."
        )

class ResourceNotFoundError(MaaserBotError):
    """Exception raised when requested resource was not found."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(
            message,
            user_message or "המשאב המבוקש לא נמצא."
        )

# מיפוי בין סוגי שגיאות חיצוניות לשגיאות המערכת
ERROR_MAPPING: Dict[Type[Exception], Type[MaaserBotError]] = {
    SQLAlchemyError: DatabaseError,
    ValueError: ValidationError,
    KeyError: ResourceNotFoundError,
    IndexError: ResourceNotFoundError,
    PermissionError: AuthorizationError
}

def wrap_errors(func: Callable[[Update, ContextTypes.DEFAULT_TYPE, Any], Awaitable[Any]]):
    """
    Decorator to wrap handler functions with standardized error handling.
    
    Args:
        func: The handler function to wrap
        
    Returns:
        The wrapped function with error handling
    """
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except MaaserBotError as e:
            # Already a MaaserBot error, use its user message
            logger.error(f"MaaserBotError in {func.__name__}: {e.message}")
            await send_error_message(update, e.user_message)
        except Exception as e:
            # Map standard exceptions to MaaserBot errors
            error_class = next((err_cls for exc_cls, err_cls in ERROR_MAPPING.items() 
                               if isinstance(e, exc_cls)), MaaserBotError)
            
            error = error_class(f"Error in {func.__name__}: {str(e)}")
            logger.error(error.message)
            logger.error(traceback.format_exc())
            await send_error_message(update, error.user_message)
    
    return wrapped

async def send_error_message(update: Update, message: str) -> None:
    """
    Send an error message to the user.
    
    Args:
        update: The Telegram update
        message: The error message to send
    """
    if update and update.effective_message:
        if update.callback_query:
            await update.callback_query.answer()
            await update.effective_message.reply_text(message)
        else:
            await update.effective_message.reply_text(message) 