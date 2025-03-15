"""User management handlers for MaaserBot."""

import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from maaserbot.models import SessionLocal
from maaserbot.utils.db import (
    get_or_create_user, get_pending_access_requests, get_all_users,
    create_access_request
)
from maaserbot.models.models import AccessRequest

# Load environment variables
load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Default to 0 if not set

# הגדרת לוגר
logger = logging.getLogger(__name__)

# Conversation states
CHOOSING, TYPING_INCOME, TYPING_INCOME_DESCRIPTION, TYPING_PAYMENT, SETTINGS, AWAITING_DELETE_CONFIRMATION, EDIT_CHOOSING, EDIT_INCOME, EDIT_PAYMENT, EDIT_INCOME_DESCRIPTION, SELECTING_INCOME_ID, SELECTING_PAYMENT_ID, APPROVING_USER = range(13)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Send a message when the command /start is issued.
    
    Args:
        update: The update containing message data
        context: The context object
        
    Returns:
        int: The next conversation state
    """
    logger.info(f"User {update.effective_user.id} started the bot")
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id)
        
        if not user.is_approved:
            # Check if user already has a pending request
            existing_requests = get_pending_access_requests(db)
            user_has_request = any(req.telegram_id == update.effective_user.id for req in existing_requests)
            
            if user_has_request:
                await update.message.reply_text(
                    "⏳ בקשת הגישה שלך נמצאת בבדיקה.\n"
                    "אנא המתן לאישור מנהל המערכת.\n\n"
                    "לאחר שבקשתך תאושר, תקבל הודעה ותוכל להתחיל להשתמש בבוט."
                )
                return CHOOSING
            
            keyboard = [
                [InlineKeyboardButton("🔑 בקש גישה לבוט", callback_data='request_access')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ אין לך הרשאה להשתמש בבוט.\n"
                "אתה יכול לבקש גישה על ידי לחיצה על הכפתור למטה.",
                reply_markup=reply_markup
            )
            return CHOOSING
    
    # First send welcome message without buttons
    welcome_message = (
        f"ברוך הבא {update.effective_user.first_name}! 🙏\n\n"
        "הבוט יעזור לך לנהל את המעשרות שלך בקלות ובנוחות:\n"
        "📥 הוספת הכנסות חדשות\n"
        "💰 מעקב אחר תשלומי מעשרות\n"
        "📊 צפייה במצב הנוכחי\n"
        "📖 היסטוריית הכנסות ותשלומים\n"
        "⚙️ הגדרות אישיות\n\n"
        "איך להתחיל?\n"
        "1️⃣ בחר 'הגדרות' כדי לקבוע את סוג החישוב (מעשר/חומש) והמטבע המועדף\n"
        "2️⃣ הוסף את ההכנסות שלך\n"
        "3️⃣ סמן תשלומי מעשרות כשאתה מבצע אותם\n\n"
        "לעזרה נוספת, לחץ על כפתור ה-❓"
    )
    
    await update.message.reply_text(welcome_message)
    
    # Then send menu message with buttons
    keyboard = [
        [
            InlineKeyboardButton("📥 הוספת הכנסה", callback_data='add_income'),
            InlineKeyboardButton("💰 תשלום מעשרות", callback_data='add_payment')
        ],
        [
            InlineKeyboardButton("📊 מצב נוכחי", callback_data='status'),
            InlineKeyboardButton("📖 היסטוריה", callback_data='history')
        ],
        [
            InlineKeyboardButton("⚙️ הגדרות", callback_data='settings'),
            InlineKeyboardButton("❓ עזרה", callback_data='help')
        ]
    ]
    
    # Add manage users button only for the main admin
    if user.telegram_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👥 ניהול משתמשים", callback_data='manage_users')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("במה אוכל לעזור?", reply_markup=reply_markup)
    return CHOOSING

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle access request from user.
    
    Args:
        update: The update containing callback query data
        context: The context object
        
    Returns:
        int: The next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    try:
        with SessionLocal() as db:
            # Check if user already has a pending request
            existing_requests = get_pending_access_requests(db)
            user_has_request = any(req.telegram_id == query.from_user.id for req in existing_requests)
            
            if user_has_request:
                await query.edit_message_text(
                    "⏳ בקשת הגישה שלך נמצאת בבדיקה.\n"
                    "אנא המתן לאישור מנהל המערכת.\n\n"
                    "לאחר שבקשתך תאושר, תקבל הודעה ותוכל להתחיל להשתמש בבוט."
                )
                return CHOOSING
            
            request = create_access_request(
                db,
                query.from_user.id,
                query.from_user.username,
                query.from_user.first_name,
                query.from_user.last_name
            )
            
            if request:
                await query.edit_message_text(
                    "✅ בקשת הגישה שלך נשלחה בהצלחה!\n"
                    "אנא המתן לאישור מנהל המערכת.\n\n"
                    "לאחר שבקשתך תאושר, תקבל הודעה ותוכל להתחיל להשתמש בבוט."
                )
            else:
                await query.edit_message_text(
                    "❌ אירעה שגיאה בשליחת בקשת הגישה.\n"
                    "אנא נסה שוב מאוחר יותר."
                )
    except Exception as e:
        logger.error(f"Error in request_access: {str(e)}")
        await query.edit_message_text(
            "❌ אירעה שגיאה בשליחת בקשת הגישה.\n"
            "אנא נסה שוב מאוחר יותר."
        )
    
    return CHOOSING

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle user management for admins.
    
    Args:
        update: The update containing callback query data
        context: The context object
        
    Returns:
        int: The next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        user = get_or_create_user(
            db, 
            query.from_user.id,
            query.from_user.username,
            query.from_user.first_name,
            query.from_user.last_name
        )
        if not user.is_admin:
            await query.edit_message_text("❌ אין לך הרשאת מנהל")
            return CHOOSING

        # Get pending requests count
        pending_requests = get_pending_access_requests(db)
        pending_count = len(pending_requests) if pending_requests else 0
        
        # Get approved users count
        users = get_all_users(db, user.telegram_id)
        approved_count = sum(1 for u in users if u.is_approved) if users else 0
        
        message = "*👥 ניהול משתמשים*\n\n"
        
        keyboard = [
            [InlineKeyboardButton(f"👤 משתמשים מאושרים ({approved_count})", callback_data='show_approved_users')],
            [InlineKeyboardButton(f"📝 בקשות ממתינות ({pending_count})", callback_data='show_pending_requests')],
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    return CHOOSING

async def show_approved_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show list of approved users with remove option.
    
    Args:
        update: The update containing callback query data
        context: The context object
        
    Returns:
        int: The next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        users = get_all_users(db, query.from_user.id)
        
        message = "*👤 משתמשים מאושרים*\n\n"
        keyboard = []
        
        if users:
            approved_users = [u for u in users if u.is_approved]
            if approved_users:
                for u in approved_users:
                    if not u.is_admin:  # Don't show remove button for admin
                        user_info = []
                        if u.first_name:
                            user_info.append(u.first_name)
                        if u.last_name:
                            user_info.append(u.last_name)
                        name = " ".join(user_info) if user_info else "ללא שם"
                        
                        message += f"👤 *{name}*\n"
                        if u.username:
                            message += f"• @{u.username}\n"
                        message += f"• מזהה: `{u.telegram_id}`\n"
                        message += "──────────────\n"
                        
                        keyboard.append([InlineKeyboardButton(f"🚫 הסר גישה ל-{name}", callback_data=f'remove_{u.telegram_id}')])
            else:
                message += "אין משתמשים מאושרים כרגע."
        else:
            message += "אין משתמשים מאושרים כרגע."
            
        keyboard.append([InlineKeyboardButton("חזרה לניהול משתמשים", callback_data='manage_users')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    return CHOOSING

async def show_pending_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show pending access requests.
    
    Args:
        update: The update containing callback query data
        context: The context object
        
    Returns:
        int: The next conversation state
    """
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        pending_requests = db.query(AccessRequest).filter(AccessRequest.status == 'pending').all()
        
        if not pending_requests:
            keyboard = [[InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "אין בקשות ממתינות 🎉",
                reply_markup=reply_markup
            )
            return CHOOSING
        
        message = "📝 <b>בקשות ממתינות לאישור:</b>\n\n"
        
        for request in pending_requests:
            message += "👤 <b>משתמש חדש</b>\n"
            message += f"• מזהה: <code>{request.telegram_id}</code>\n"
            if request.username:
                message += f"• שם משתמש: @{request.username}\n"
            if request.first_name:
                message += f"• שם פרטי: {request.first_name}\n"
            if request.last_name:
                message += f"• שם משפחה: {request.last_name}\n"
            message += f"• תאריך בקשה: {request.created_at.strftime('%d/%m/%Y')}\n"
            message += "──────────────────\n"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ אשר", callback_data=f'approve_{request.id}'),
                InlineKeyboardButton("❌ דחה", callback_data=f'reject_{request.id}')
            ],
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    return CHOOSING 