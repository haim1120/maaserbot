import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters, CallbackContext
import os
from dotenv import load_dotenv
from maaserbot.models import SessionLocal
from maaserbot.utils.db import get_or_create_user, add_income, add_payment, get_user_balance, get_user_history, update_user_settings, delete_all_user_data, delete_income, edit_income, delete_payment, edit_payment, approve_user, remove_user_approval, get_all_users, get_pending_access_requests, create_access_request, approve_access_request, reject_access_request
from maaserbot.models.models import CalculationType, Currency, Income, Payment, AccessRequest
from telegram.error import Conflict

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Default to 0 if not set

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
CHOOSING, TYPING_INCOME, TYPING_INCOME_DESCRIPTION, TYPING_PAYMENT, SETTINGS, AWAITING_DELETE_CONFIRMATION, EDIT_CHOOSING, EDIT_INCOME, EDIT_PAYMENT, EDIT_INCOME_DESCRIPTION, SELECTING_INCOME_ID, SELECTING_PAYMENT_ID, APPROVING_USER = range(13)

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error - multiple bot instances running")
        return
    
    error_message = "אירעה שגיאה בעת ביצוע הפעולה. נסה שוב מאוחר יותר."
    
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
    """Check if user is approved to use the bot."""
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id)
        if not user.is_approved:
            logger.warning(f"Unauthorized access attempt by user {update.effective_user.id}")
            return False
        return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
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

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user management for admins."""
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
    """Show list of approved users with remove option."""
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
    """Show list of pending access requests."""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        pending_requests = get_pending_access_requests(db)
        
        message = "*📝 בקשות ממתינות*\n\n"
        keyboard = []
        
        if pending_requests:
            for req in pending_requests:
                user_text = f"• ID: `{req.telegram_id}`"
                if req.username:
                    user_text += f" | @{req.username}"
                if req.first_name:
                    user_text += f" | {req.first_name}"
                if req.last_name:
                    user_text += f" {req.last_name}"
                message += user_text + "\n"
                
                # Add approve/reject buttons for each request
                keyboard.append([
                    InlineKeyboardButton(f"✅ אשר {req.telegram_id}", callback_data=f'approve_{req.id}'),
                    InlineKeyboardButton(f"❌ דחה {req.telegram_id}", callback_data=f'reject_{req.id}')
                ])
        else:
            message += "אין בקשות ממתינות כרגע."
            
        keyboard.append([InlineKeyboardButton("חזרה לניהול משתמשים", callback_data='manage_users')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    return CHOOSING

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle access request from user."""
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

async def approve_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /approve_request command."""
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

async def reject_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /reject_request command."""
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

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    # Handle request_access callback
    if query.data == 'request_access':
        return await request_access(update, context)
    
    # Handle show approved users/pending requests
    if query.data == 'show_approved_users':
        return await show_approved_users(update, context)
    elif query.data == 'show_pending_requests':
        return await show_pending_requests(update, context)
    elif query.data == 'main_menu':
        return await handle_main_menu(update, context)
    
    # Handle approve/reject/remove callbacks
    if query.data.startswith(('approve_', 'reject_', 'remove_')):
        action, id_str = query.data.split('_')
        try:
            item_id = int(id_str)
            with SessionLocal() as db:
                if action == 'approve':
                    success = approve_access_request(db, query.from_user.id, item_id)
                    if success:
                        # Get the request to get the user's telegram_id
                        request = db.query(AccessRequest).filter(AccessRequest.id == item_id).first()
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
                        
                        await query.answer("✅ הבקשה אושרה בהצלחה")
                    else:
                        await query.answer("❌ שגיאה באישור הבקשה")
                elif action == 'reject':
                    success = reject_access_request(db, query.from_user.id, item_id)
                    if success:
                        await query.answer("✅ הבקשה נדחתה בהצלחה")
                    else:
                        await query.answer("❌ שגיאה בדחיית הבקשה")
                elif action == 'remove':
                    success = remove_user_approval(db, query.from_user.id, item_id)
                    if success:
                        await query.answer("✅ הגישה הוסרה בהצלחה")
                    else:
                        await query.answer("❌ שגיאה בהסרת הגישה")
                        
                # Return to the appropriate view
                if action in ['approve', 'reject']:
                    return await show_pending_requests(update, context)
                else:  # remove
                    return await show_approved_users(update, context)
                    
        except ValueError:
            await query.answer("❌ שגיאה בעיבוד הבקשה")
            return CHOOSING
    
    # Check user permission for all actions except manage_users
    if query.data != 'manage_users':
        with SessionLocal() as db:
            user = get_or_create_user(
                db,
                query.from_user.id,
                query.from_user.username,
                query.from_user.first_name,
                query.from_user.last_name
            )
            if not user.is_approved:
                keyboard = [
                    [InlineKeyboardButton("🔑 בקש גישה לבוט", callback_data='request_access')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "⚠️ אין לך הרשאה להשתמש בבוט.\n"
                    "אתה יכול לבקש גישה על ידי לחיצה על הכפתור למטה.",
                    reply_markup=reply_markup
                )
                return CHOOSING
    
    if query.data == 'manage_users':
        # Check if user is the main admin
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            if user.telegram_id != ADMIN_ID:
                await query.edit_message_text("❌ אין לך הרשאת מנהל")
                return CHOOSING
        return await manage_users(update, context)
    
    if query.data == 'add_income':
        keyboard = [
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the original message for later updates
        context.user_data['original_message'] = query.message
        
        await query.edit_message_text(
            "💰 הוספת הכנסה\n\n"
            "בבקשה הזן את סכום ההכנסה:",
            reply_markup=reply_markup
        )
        return TYPING_INCOME
    
    elif query.data == 'add_payment':
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            balance = get_user_balance(db, user.id)
            
        if balance and balance['remaining'] > 0:
            keyboard = [
                [InlineKeyboardButton(f"✅ סמן {balance['remaining']:.2f} {user.currency.value} כשולם", callback_data=f"pay_full_{balance['remaining']}")],
                [InlineKeyboardButton("💸 תשלום חלקי", callback_data='pay_partial')],
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"💸 תשלום מעשרות\n\n"
                f"📌 יתרה לתשלום: {balance['remaining']:.2f} {user.currency.value}\n\n"
                f"בחר אפשרות:",
                reply_markup=reply_markup
            )
        else:
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "אין יתרה לתשלום! 🎉",
                reply_markup=reply_markup
            )
        return CHOOSING
    
    elif query.data.startswith('pay_full_'):
        try:
            amount = float(query.data.split('_')[2])
            with SessionLocal() as db:
                user = get_or_create_user(db, query.from_user.id)
                payment = add_payment(db, user.id, amount)
                balance = get_user_balance(db, user.id)
                
                keyboard = [
                    [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"✅ התשלום נרשם בהצלחה!\n\n"
                    f"💸 סכום ששולם: {amount:.2f} {user.currency.value}\n"
                    f"📌 יתרה נוכחית: {balance['remaining']:.2f} {user.currency.value}",
                    reply_markup=reply_markup
                )
        except (ValueError, IndexError):
            await query.edit_message_text("❌ אירעה שגיאה. נסה שוב.")
        return CHOOSING
    
    elif query.data == 'pay_partial':
        keyboard = [
            [InlineKeyboardButton("ביטול", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the original message for later updates
        context.user_data['original_message'] = query.message
        
        await query.edit_message_text(
            "💸 תשלום חלקי\n\n"
            "בבקשה הזן את הסכום לתשלום:",
            reply_markup=reply_markup
        )
        return TYPING_PAYMENT
    
    elif query.data == 'status':
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            balance = get_user_balance(db, user.id)
        
        if balance:
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📊 מצב נוכחי\n\n"
                f"💵 סך כל ההכנסות: {balance['total_income']:.2f} {user.currency.value}\n"
                f"✨ סך הכל {user.default_calc_type.value}: {balance['total_maaser']:.2f} {user.currency.value}\n"
                f"💸 סך הכל שולם: {balance['total_paid']:.2f} {user.currency.value}\n"
                f"📌 יתרה לתשלום: {balance['remaining']:.2f} {user.currency.value}",
                reply_markup=reply_markup
            )
        else:
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "לא נמצאו נתונים בדיין.\n"
                "התחל על ידי הוספת הכנסה! 💪",
                reply_markup=reply_markup
            )
            
    elif query.data == 'history':
        await show_history(update, context, page=1)
    
    elif query.data.startswith('history_page_'):
        page = int(query.data.split('_')[2])
        await show_history(update, context, page)
    
    elif query.data == 'settings':
        keyboard = [
            [
                InlineKeyboardButton("🔄 שינוי סוג חישוב", callback_data='change_calc_type'),
                InlineKeyboardButton("💱 שינוי מטבע", callback_data='change_currency')
            ],
            [InlineKeyboardButton("🗑️ מחיקת כל המידע", callback_data='delete_all_data')],
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            await query.edit_message_text(
                f"⚙️ הגדרות\n\n"
                f"🔄 סוג חישוב נוכחי: {user.default_calc_type.value}\n"
                f"💱 מטבע נוכחי: {user.currency.value}",
                reply_markup=reply_markup
            )
            
    elif query.data == 'change_calc_type':
        keyboard = [
            [
                InlineKeyboardButton("מעשר - 10% מההכנסות", callback_data='set_maaser'),
                InlineKeyboardButton("חומש - 20% מההכנסות", callback_data='set_chomesh')
            ],
            [InlineKeyboardButton("חזרה להגדרות", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔄 בחר את סוג החישוב הרצוי:",
            reply_markup=reply_markup
        )
        
    elif query.data == 'change_currency':
        keyboard = [
            [
                InlineKeyboardButton("₪ - שקל", callback_data='set_ils'),
                InlineKeyboardButton("$ - דולר", callback_data='set_usd'),
                InlineKeyboardButton("€ - יורו", callback_data='set_eur')
            ],
            [InlineKeyboardButton("חזרה להגדרות", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💱 בחר את המטבע הרצוי:",
            reply_markup=reply_markup
        )
        
    elif query.data.startswith('set_'):
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            
            if query.data == 'set_maaser':
                user = update_user_settings(db, user.id, default_calc_type=CalculationType.MAASER)
                message = "✅ סוג החישוב שונה למעשר (10%)"
            elif query.data == 'set_chomesh':
                user = update_user_settings(db, user.id, default_calc_type=CalculationType.CHOMESH)
                message = "✅ סוג החישוב שונה לחומש (20%)"
            elif query.data == 'set_ils':
                user = update_user_settings(db, user.id, currency=Currency.ILS)
                message = "✅ המטבע שונה לשקל (₪)"
            elif query.data == 'set_usd':
                user = update_user_settings(db, user.id, currency=Currency.USD)
                message = "✅ המטבע שונה לדולר ($)"
            elif query.data == 'set_eur':
                user = update_user_settings(db, user.id, currency=Currency.EUR)
                message = "✅ המטבע שונה ליורו (€)"
                
            keyboard = [
                [InlineKeyboardButton("חזרה להגדרות", callback_data='settings')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
    
    elif query.data == 'delete_all_data':
        keyboard = [
            [InlineKeyboardButton("כן, אני בטוח - מחק הכל", callback_data='confirm_delete_all')],
            [InlineKeyboardButton("לא, חזור להגדרות", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ *אזהרה: מחיקת כל המידע*\n\n"
            "פעולה זו תמחק את כל ההיסטוריה שלך, כולל:\n"
            "• כל ההכנסות\n"
            "• כל התשלומים\n"
            "• כל ההגדרות האישיות\n\n"
            "האם אתה בטוח שברצונך למחוק את כל המידע?\n"
            "פעולה זו אינה ניתנת לביטול!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == 'confirm_delete_all':
        context.user_data['awaiting_delete_confirmation'] = True
        # Store the message for later updates
        context.user_data['delete_message'] = query.message
        
        keyboard = [
            [InlineKeyboardButton("ביטול", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "לאישור סופי, אנא הקלד את המילים:\n"
            "*מחק את כל המידע שלי*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return AWAITING_DELETE_CONFIRMATION

    elif query.data == 'help':
        help_text = (
            "*❓ עזרה ומידע*\n\n"
            "*📥 הוספת הכנסה*\n"
            "הוסף הכנסה חדשה למעקב. תוכל להזין את הסכום ולהוסיף תיאור אופציונלי.\n\n"
            "*💰 תשלום מעשרות*\n"
            "סמן תשלומי מעשרות שביצעת. תוכל לשלם את כל היתרה או סכום חלקי.\n\n"
            "*📊 מצב נוכחי*\n"
            "צפה בסיכום של ההכנסות, המעשרות והתשלומים שלך.\n\n"
            "*📖 היסטוריה*\n"
            "צפה בהיסטוריית ההכנסות והתשלומים שלך.\n\n"
            "*⚙️ הגדרות*\n"
            "• שנה את סוג החישוב (מעשר 10% או חומש 20%)\n"
            "• בחר את המטבע המועדף (₪, $, €)\n"
            "• מחק את כל המידע שלך מהמערכת\n\n"
            "לחזרה לתפריט הראשי, לחץ על הכפתור למטה."
        )
        
        keyboard = [
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    return CHOOSING

async def handle_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle income amount input."""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        logger.info(f"User {update.effective_user.id} adding income: {amount}")
        context.user_data['income_amount'] = amount
        
        # Delete user's message
        await update.message.delete()
            
        keyboard = [
            [
                InlineKeyboardButton("דלג", callback_data='skip_description'),
                InlineKeyboardButton("ביטול", callback_data='main_menu')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update the original message instead of sending a new one
        await context.user_data['original_message'].edit_text(
            f"💰 הוספת הכנסה\n\n"
            f"סכום: {amount}\n\n"
            "💭 אפשר להוסיף תיאור להכנסה (למשל: 'משכורת', 'בונוס' וכו')\n"
            "או ללחוץ על 'דלג' כדי להמשיך:",
            reply_markup=reply_markup
        )
        return TYPING_INCOME_DESCRIPTION
            
    except ValueError:
        # Delete user's message
        await update.message.delete()
        
        keyboard = [
            [InlineKeyboardButton("ביטול", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update the original message
        await context.user_data['original_message'].edit_text(
            "❌ אנא הזן מספר חיובי בלבד.\n\n"
            "💰 הוספת הכנסה\n\n"
            "בבקשה הזן את סכום ההכנסה:",
            reply_markup=reply_markup
        )
        return TYPING_INCOME

async def handle_income_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle income description input."""
    query = update.callback_query
    
    amount = context.user_data.get('income_amount')
    if not amount:
        return CHOOSING
        
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id if update.effective_user else query.from_user.id)
        
        description = None
        if query and query.data == 'skip_description':
            await query.answer()
        else:
            # Delete user's message
            await update.message.delete()
            description = update.message.text.strip()
            
        # Add the income with the user's default calculation type
        income = add_income(db, user.id, amount, user.default_calc_type, description)
        
        keyboard = [[InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"✅ נוספה הכנסה חדשה\n\n"
        message += f"💰 סכום: {amount:.2f} {user.currency.value}\n"
        message += f"📊 {user.default_calc_type.value}: {amount * (0.1 if user.default_calc_type == CalculationType.MAASER else 0.2):.2f} {user.currency.value}"
        if description:
            message += f"\n💭 תיאור: {description}"
            
        # Update the original message
        await context.user_data['original_message'].edit_text(message, reply_markup=reply_markup)
        
    return CHOOSING

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment amount input."""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        logger.info(f"User {update.effective_user.id} adding payment: {amount}")
        # Delete user's message
        await update.message.delete()
            
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
            balance = get_user_balance(db, user.id)
            
            if amount > balance['remaining']:
                keyboard = [
                    [InlineKeyboardButton("ביטול", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.user_data['original_message'].edit_text(
                    f"❌ לא ניתן לשלם יותר מהסכום שחייבים.\n\n"
                    f"💸 תשלום חלקי\n\n"
                    f"היתרה לתשלום היא {balance['remaining']:.2f} {user.currency.value}\n"
                    f"בבקשה הזן סכום קטן או שווה ליתרה:",
                    reply_markup=reply_markup
                )
                return TYPING_PAYMENT
            
            payment = add_payment(db, user.id, amount)
            balance = get_user_balance(db, user.id)
            
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Update the original message
            await context.user_data['original_message'].edit_text(
                f"✅ התשלום נרשם בהצלחה!\n\n"
                f"💸 סכום ששולם: {amount:.2f} {user.currency.value}\n"
                f"📌 יתרה נוכחית: {balance['remaining']:.2f} {user.currency.value}",
                reply_markup=reply_markup
            )
            
    except ValueError:
        # Delete user's message
        await update.message.delete()
        
        keyboard = [
            [InlineKeyboardButton("ביטול", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update the original message
        await context.user_data['original_message'].edit_text(
            "❌ אנא הזן מספר חיובי בלבד.\n\n"
            "💸 תשלום חלקי\n\n"
            "בבקשה הזן את הסכום לתשלום:",
            reply_markup=reply_markup
        )
        return TYPING_PAYMENT
        
    return CHOOSING

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu."""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        user = get_or_create_user(db, query.from_user.id)
        
        if not user.is_approved:
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
            
            keyboard = [
                [InlineKeyboardButton("🔑 בקש גישה לבוט", callback_data='request_access')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⚠️ אין לך הרשאה להשתמש בבוט.\n"
                "אתה יכול לבקש גישה על ידי לחיצה על הכפתור למטה.",
                reply_markup=reply_markup
            )
            return CHOOSING
    
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
        
        # Add manage users button for the main admin
        if user.telegram_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👥 ניהול משתמשים", callback_data='manage_users')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('במה אוכל לעזור?', reply_markup=reply_markup)
        
    return CHOOSING

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation for data deletion."""
    if not context.user_data.get('awaiting_delete_confirmation'):
        return CHOOSING
        
    if update.message.text.strip() == "מחק את כל המידע שלי":
        logger.warning(f"User {update.effective_user.id} deleting all their data")
        # Delete user's confirmation message
        await update.message.delete()
        
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
            try:
                delete_all_user_data(db, user.id)
                
                keyboard = [
                    [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Update the original message
                await context.user_data['delete_message'].edit_text(
                    "✅ כל המידע שלך נמחק בהצלחה.",
                    reply_markup=reply_markup
                )
            except Exception as e:
                keyboard = [
                    [InlineKeyboardButton("נסה שוב", callback_data='confirm_delete_all')],
                    [InlineKeyboardButton("ביטול", callback_data='settings')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.user_data['delete_message'].edit_text(
                    "❌ אירעה שגיאה במחיקת המידע. אנא נסה שוב.",
                    reply_markup=reply_markup
                )
    else:
        # Delete user's failed confirmation message
        await update.message.delete()
        
        keyboard = [
            [InlineKeyboardButton("נסה שוב", callback_data='confirm_delete_all')],
            [InlineKeyboardButton("ביטול", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update the original message
        await context.user_data['delete_message'].edit_text(
            "❌ הטקסט שהוקלד אינו תואם.\n\n"
            "לאישור סופי, אנא הקלד את המילים:\n"
            "*מחק את כל המידע שלי*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    # Clear the confirmation state
    if 'awaiting_delete_confirmation' in context.user_data:
        del context.user_data['awaiting_delete_confirmation']
    if 'delete_message' in context.user_data:
        del context.user_data['delete_message']
        
    return CHOOSING

async def handle_edit_delete_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit and delete callbacks for incomes and payments."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]  # edit/delete
    item_type = data[1]  # income/payment
    item_id = int(data[2])
    
    with SessionLocal() as db:
        user = get_or_create_user(db, query.from_user.id)
        
        if action == 'delete':
            if item_type == 'income':
                success = delete_income(db, item_id, user.id)
                message = "✅ ההכנסה נמחקה בהצלחה!" if success else "❌ לא נמצאה ההכנסה המבוקשת"
            else:  # payment
                success = delete_payment(db, item_id, user.id)
                message = "✅ התשלום נמחק בהצלחה!" if success else "❌ לא נמצא התשלום המבוקש"
                
            keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        elif action == 'edit':
            context.user_data['editing_item'] = {'type': item_type, 'id': item_id}
            context.user_data['original_message'] = query.message
            
            if item_type == 'income':
                # Get the income to check if it has a description
                income = db.query(Income).filter(Income.id == item_id, Income.user_id == user.id).first()
                keyboard = []
                
                # Always show edit amount button
                keyboard.append([InlineKeyboardButton("✏️ עריכת סכום", callback_data=f'edit_income_amount_{item_id}')])
                
                # Show edit description button if no description, or add description if none exists
                if income and not income.description:
                    keyboard.append([InlineKeyboardButton("➕ הוספת תיאור", callback_data=f'edit_income_desc_{item_id}')])
                elif income:
                    keyboard.append([InlineKeyboardButton("✏️ עריכת תיאור", callback_data=f'edit_income_desc_{item_id}')])
                
                keyboard.append([InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "✏️ מה ברצונך לערוך?",
                    reply_markup=reply_markup
                )
                return EDIT_CHOOSING
            else:  # payment
                # Check if the new amount would exceed the remaining balance
                balance = get_user_balance(db, user.id)
                payment = db.query(Payment).filter(Payment.id == item_id, Payment.user_id == user.id).first()
                
                if payment:
                    max_allowed = balance['remaining'] + payment.amount
                    context.user_data['max_payment'] = max_allowed
                    
                    keyboard = [[InlineKeyboardButton("ביטול", callback_data='main_menu')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        f"✏️ עריכת תשלום\n\n"
                        f"הסכום המקסימלי האפשרי הוא {max_allowed:.2f} {user.currency.value}\n"
                        f"הזן את הסכום החדש:",
                        reply_markup=reply_markup
                    )
                    return EDIT_PAYMENT
                else:
                    keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text("❌ לא נמצא התשלום המבוקש", reply_markup=reply_markup)
    
    return CHOOSING

async def handle_edit_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle editing payment amount."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        editing_item = context.user_data.get('editing_item')
        if not editing_item or editing_item['type'] != 'payment':
            return CHOOSING
            
        max_allowed = context.user_data.get('max_payment', 0)
        if amount > max_allowed:
            # Delete user's message
            await update.message.delete()
            
            keyboard = [[InlineKeyboardButton("ביטול", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.user_data['original_message'].edit_text(
                f"❌ לא ניתן לשלם יותר מהסכום שחייבים.\n\n"
                f"✏️ עריכת תשלום\n\n"
                f"הסכום המקסימלי האפשרי הוא {max_allowed:.2f}\n"
                f"הזן את הסכום החדש:",
                reply_markup=reply_markup
            )
            return EDIT_PAYMENT
            
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
            payment = edit_payment(db, editing_item['id'], user.id, amount)
            
            if payment:
                message = f"✅ התשלום עודכן בהצלחה לסכום {amount:.2f} {user.currency.value}"
            else:
                message = "❌ לא נמצא התשלום המבוקש"
                
        # Delete user's message
        await update.message.delete()
        
        keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.user_data['original_message'].edit_text(message, reply_markup=reply_markup)
            
    except ValueError:
        # Delete user's message
        await update.message.delete()
        
        keyboard = [[InlineKeyboardButton("ביטול", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.user_data['original_message'].edit_text(
            "❌ אנא הזן מספר חיובי בלבד.\n\n"
            "✏️ עריכת תשלום\n\n"
            "הזן את הסכום החדש:",
            reply_markup=reply_markup
        )
        return EDIT_PAYMENT
        
    return CHOOSING

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Show history with pagination - one operation at a time."""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as db:
        user = get_or_create_user(db, query.from_user.id)
        
        # Get all operations sorted by date
        incomes = db.query(Income).filter(Income.user_id == user.id).order_by(Income.created_at.desc()).all()
        payments = db.query(Payment).filter(Payment.user_id == user.id).order_by(Payment.created_at.desc()).all()
        
        # Combine and sort operations by date
        operations = []
        for income in incomes:
            operations.append(('income', income))
        for payment in payments:
            operations.append(('payment', payment))
        
        operations.sort(key=lambda x: x[1].created_at, reverse=True)
        
        if not operations:
            keyboard = [[InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📖 היסטוריית פעולות\n"
                "══════════════════\n\n"
                "לא נמצאו נתונים בהיסטוריה עדיין.\n"
                "התחל על ידי הוספת הכנסה! 💪",
                reply_markup=reply_markup
            )
            return
        
        # Calculate total pages and validate current page
        total_pages = len(operations)
        page = min(max(1, page), total_pages)
        
        # Get current operation
        op_type, operation = operations[page - 1]
        
        # Build message for current operation
        message = f"📖 היסטוריית פעולות (פעולה {page} מתוך {total_pages})\n"
        message += "══════════════════\n\n"
        
        if op_type == 'income':
            calc_amount = operation.amount * 0.1 if operation.calc_type == CalculationType.MAASER else operation.amount * 0.2
            message += "*📥 הכנסה*\n"
            message += "──────────────────\n"
            message += f"• מאריך: {operation.created_at.strftime('%d/%m/%Y')}\n"
            message += f"• סכום: {operation.amount:.2f} {user.currency.value}\n"
            message += f"• {operation.calc_type.value}: {calc_amount:.2f} {user.currency.value}"
            if operation.description:
                message += f"\n• תיאור: {operation.description}"
        else:  # payment
            message += "*💸 תשלום*\n"
            message += "──────────────────\n"
            message += f"• מאריך: {operation.created_at.strftime('%d/%m/%Y')}\n"
            message += f"• סכום: {operation.amount:.2f} {user.currency.value}"
        
        # Build keyboard with navigation and action buttons
        keyboard = []
        
        # Add edit/delete buttons
        if op_type == 'income':
            edit_buttons = [InlineKeyboardButton("✏️ עריכת סכום", callback_data=f'edit_income_amount_{operation.id}')]
            if operation.description:
                edit_buttons.append(InlineKeyboardButton("✏️ עריכת תיאור", callback_data=f'edit_income_desc_{operation.id}'))
            else:
                edit_buttons.append(InlineKeyboardButton("➕ הוספת תיאור", callback_data=f'edit_income_desc_{operation.id}'))
            keyboard.append(edit_buttons)
            keyboard.append([InlineKeyboardButton("🗑️ מחיקת הכנסה", callback_data=f'delete_income_{operation.id}')])
        else:  # payment
            keyboard.append([InlineKeyboardButton("✏️ עריכת סכום", callback_data=f'edit_payment_{operation.id}')])
            keyboard.append([InlineKeyboardButton("🗑️ מחיקת תשלום", callback_data=f'delete_payment_{operation.id}')])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("◀️ הקודם", callback_data=f'history_page_{page-1}'))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("הבא ▶️", callback_data=f'history_page_{page+1}'))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
            
        keyboard.append([InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_select_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle selection of edit/delete action."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['original_message'] = query.message
    
    # Add the request for ID to the history message
    current_text = query.message.text + "\n\n✏️ הזן את המספר המזהה של הפעולה שברצונך לערוך/למחוק:"
    
    keyboard = [[InlineKeyboardButton("ביטול", callback_data='history')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        current_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return SELECTING_INCOME_ID

async def handle_selected_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the selected ID for edit/delete operation."""
    try:
        item_id = int(update.message.text)
        
        # Delete user's message
        await update.message.delete()
        
        # Check if it's an income or payment
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
            income = db.query(Income).filter(Income.id == item_id, Income.user_id == user.id).first()
            payment = None if income else db.query(Payment).filter(Payment.id == item_id, Payment.user_id == user.id).first()
            
            if not income and not payment:
                keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.user_data['original_message'].edit_text(
                    "❌ לא נמצאה פעולה עם המזהה שהוזן",
                    reply_markup=reply_markup
                )
                return CHOOSING
            
            item_type = 'income' if income else 'payment'
            context.user_data['editing_item'] = {'type': item_type, 'id': item_id}
            
            if item_type == 'income':
                keyboard = [
                    [
                        InlineKeyboardButton("✏️ עריכת סכום", callback_data=f'edit_income_amount_{item_id}'),
                        InlineKeyboardButton("✏️ עריכת תיאור", callback_data=f'edit_income_desc_{item_id}')
                    ],
                    [InlineKeyboardButton("🗑️ מחיקת הכנסה", callback_data=f'delete_income_{item_id}')],
                    [InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]
                ]
            else:  # payment
                keyboard = [
                    [InlineKeyboardButton("✏️ עריכת סכום", callback_data=f'edit_payment_{item_id}')],
                    [InlineKeyboardButton("🗑️ מחיקת תשלום", callback_data=f'delete_payment_{item_id}')],
                    [InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]
                ]
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.user_data['original_message'].edit_text(
                f"בחר את הפעולה הרצויה עבור {('הכנסה' if item_type == 'income' else 'תשלום')} #{item_id}:",
                reply_markup=reply_markup
            )
            return EDIT_CHOOSING
            
    except ValueError:
        # Delete user's message
        await update.message.delete()
        
        # Get the original history message without the request for ID
        original_text = "\n".join(context.user_data['original_message'].text.split("\n")[:-2])
        
        keyboard = [[InlineKeyboardButton("ביטול", callback_data='history')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.user_data['original_message'].edit_text(
            original_text + "\n\n❌ אנא הזן מספר מזהה תקין בלבד.\n\n✏️ הזן את המספר המזהה של הפעולה שברצונך לערוך/למחוק:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SELECTING_INCOME_ID

async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit choice for income."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    edit_type = data[2]  # amount/desc
    item_id = int(data[3])
    
    context.user_data['editing_item'] = {'type': 'income', 'id': item_id}
    context.user_data['original_message'] = query.message
    
    keyboard = [[InlineKeyboardButton("ביטול", callback_data='history')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if edit_type == 'amount':
        await query.edit_message_text(
            "✏️ עריכת הכנסה\n\n"
            "הזן את הסכום החדש:",
            reply_markup=reply_markup
        )
        return EDIT_INCOME
    else:  # desc
        await query.edit_message_text(
            "✏️ עריכת הכנסה\n\n"
            "הזן את התיאור החדש:",
            reply_markup=reply_markup
        )
        return EDIT_INCOME_DESCRIPTION

async def handle_edit_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle editing income amount."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        editing_item = context.user_data.get('editing_item')
        if not editing_item or editing_item['type'] != 'income':
            return CHOOSING
            
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
            income = edit_income(db, editing_item['id'], user.id, amount=amount)
            
            if income:
                message = f"✅ ההכנסה עודכנה בהצלחה לסכום {amount:.2f} {user.currency.value}"
            else:
                message = "❌ לא נמצאה ההכנסה המבוקשת"
                
        # Delete user's message
        await update.message.delete()
        
        keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.user_data['original_message'].edit_text(message, reply_markup=reply_markup)
            
    except ValueError:
        # Delete user's message
        await update.message.delete()
        
        keyboard = [[InlineKeyboardButton("ביטול", callback_data='history')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.user_data['original_message'].edit_text(
            "❌ אנא הזן מספר חיובי בלבד.\n\n"
            "✏️ עריכת הכנסה\n\n"
            "הזן את הסכום החדש:",
            reply_markup=reply_markup
        )
        return EDIT_INCOME
        
    return CHOOSING

async def handle_edit_income_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle editing income description."""
    description = update.message.text
    
    editing_item = context.user_data.get('editing_item')
    if not editing_item or editing_item['type'] != 'income':
        return CHOOSING
        
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id)
        income = edit_income(db, editing_item['id'], user.id, description=description)
        
        if income:
            message = f"✅ תיאור ההכנסה עודכן בהצלחה"
        else:
            message = "❌ לא נמצאה ההכנסה המבוקשת"
            
    # Delete user's message
    await update.message.delete()
    
    keyboard = [[InlineKeyboardButton("חזרה להיסטוריה", callback_data='history')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.user_data['original_message'].edit_text(message, reply_markup=reply_markup)
    return CHOOSING

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add admin commands
    application.add_handler(CommandHandler("approve_request", approve_request_command))
    application.add_handler(CommandHandler("reject_request", reject_request_command))
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(request_access, pattern='^request_access$'),
                CallbackQueryHandler(handle_edit_choice, pattern=r'^edit_income_(amount|desc)_\d+$'),
                CallbackQueryHandler(handle_edit_delete_callbacks, pattern=r'^(edit|delete)_(income|payment)_\d+$'),
                CallbackQueryHandler(button),
            ],
            SELECTING_INCOME_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selected_id),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
            SELECTING_PAYMENT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selected_id),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
            EDIT_CHOOSING: [
                CallbackQueryHandler(handle_edit_choice, pattern=r'^edit_income_(amount|desc)_\d+$'),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
            TYPING_INCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            TYPING_INCOME_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_income_description),
                CallbackQueryHandler(handle_income_description, pattern='^skip_description$'),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            TYPING_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            SETTINGS: [
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
            AWAITING_DELETE_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_confirmation),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
            EDIT_INCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_income),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            EDIT_PAYMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_payment),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            EDIT_INCOME_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_income_description),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$')
            ],
            APPROVING_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selected_id),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    
    # Get port and webhook settings from environment variables
    port = int(os.getenv("PORT", "10000"))  # Changed default port to 10000
    webhook_url = os.getenv("WEBHOOK_URL")
    webhook_secret = os.getenv("WEBHOOK_SECRET", "your-secret-token")
    
    if not webhook_url:
        logger.error("WEBHOOK_URL environment variable is not set!")
        return
    
    # Extract path from webhook URL
    from urllib.parse import urlparse
    webhook_path = urlparse(webhook_url).path or "/webhook"
    
    logger.info(f"Starting webhook on port {port} with path {webhook_path}")
    
    # Delete existing webhook before setting a new one
    application.bot.delete_webhook()
    
    # Start the webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
        secret_token=webhook_secret,
        url_path=webhook_path,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main() 