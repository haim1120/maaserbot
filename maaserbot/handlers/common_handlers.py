"""Common handlers for MaaserBot."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Conflict, TelegramError
from maaserbot.models import SessionLocal
from maaserbot.utils.db import get_or_create_user
from maaserbot.utils.errors import MaaserBotError, AuthorizationError, send_error_message

# הגדרת לוגר
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log the error and send a message to the user.
    
    Args:
        update: The update that triggered the error
        context: Context with error information
    """
    error = context.error
    
    # Log the error
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Different handling for specific errors
    if isinstance(error, Conflict):
        logger.warning("Conflict error - multiple bot instances running")
        return
    elif isinstance(error, TelegramError):
        error_message = f"טלגרם שגיאה: {str(error)}"
    elif isinstance(error, MaaserBotError):
        error_message = error.user_message
    else:
        error_message = "אירעה שגיאה בעת ביצוע הפעולה. נסה שוב מאוחר יותר."
    
    # Send the error message to the user
    if update and update.effective_message:
        if update.callback_query:
            await update.callback_query.answer()
            await update.effective_message.edit_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')
                ]])
            )
        else:
            await update.effective_message.reply_text(error_message)

async def check_user_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if user is approved to use the bot.
    
    Args:
        update: The update containing user information
        context: The context object
        
    Returns:
        bool: True if the user is approved, False otherwise
        
    Raises:
        AuthorizationError: If the user is not approved
    """
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id)
        if not user.is_approved:
            logger.warning(f"Unauthorized access attempt by user {update.effective_user.id}")
            raise AuthorizationError(
                f"User {update.effective_user.id} attempted to access without approval",
                "אין לך הרשאה להשתמש בבוט. אנא בקש גישה מהמנהל."
            )
        return True 