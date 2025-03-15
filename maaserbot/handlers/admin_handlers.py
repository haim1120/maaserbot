"""Admin handlers for MaaserBot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from maaserbot.models import SessionLocal
from maaserbot.utils.db import approve_access_request, reject_access_request
from maaserbot.models.models import AccessRequest
from maaserbot.utils.logging_utils import log_admin_action
from maaserbot.utils.errors import wrap_errors, AuthorizationError

# הגדרת לוגר
logger = logging.getLogger(__name__)

@log_admin_action
@wrap_errors
async def approve_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /approve_request command.
    
    Args:
        update: The update containing command data
        context: The context object with command arguments
    """
    if not context.args:
        await update.message.reply_text("❌ נא לציין מזהה בקשה")
        return
        
    try:
        request_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ מזהה בקשה לא תקין")
        return
        
    with SessionLocal() as db:
        success = approve_access_request(db, update.effective_user.id, request_id)
        if success:
            # Get the request to get the user's telegram_id
            request = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
            if request:
                # Send message to the approved user
                try:
                    await context.bot.send_message(
                        chat_id=request.telegram_id,
                        text="✅ בקשת הגישה שלך לבוט אושרה!\n"
                             "אתה יכול להתחיל להשתמש בבוט על ידי לחיצה על /start"
                    )
                except Exception as e:
                    logger.error(f"Failed to send approval message to user {request.telegram_id}: {str(e)}")
            
            await update.message.reply_text(f"✅ בקשת גישה {request_id} אושרה בהצלחה")
        else:
            await update.message.reply_text("❌ שגיאה באישור הבקשה")

@log_admin_action
@wrap_errors
async def reject_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /reject_request command.
    
    Args:
        update: The update containing command data
        context: The context object with command arguments
    """
    if not context.args:
        await update.message.reply_text("❌ נא לציין מזהה בקשה")
        return
        
    try:
        request_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ מזהה בקשה לא תקין")
        return
        
    with SessionLocal() as db:
        success = reject_access_request(db, update.effective_user.id, request_id)
        if success:
            await update.message.reply_text(f"✅ בקשת גישה {request_id} נדחתה בהצלחה")
        else:
            await update.message.reply_text("❌ שגיאה בדחיית הבקשה") 