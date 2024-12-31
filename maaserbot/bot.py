import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
import os
from dotenv import load_dotenv
from maaserbot.models import SessionLocal
from maaserbot.utils.db import get_or_create_user, add_income, add_payment, get_user_balance, get_user_history, update_user_settings, delete_all_user_data
from maaserbot.models.models import CalculationType, Currency

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
CHOOSING, TYPING_INCOME, TYPING_INCOME_DESCRIPTION, TYPING_PAYMENT, SETTINGS, AWAITING_DELETE_CONFIRMATION = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id)
    
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("במה אוכל לעזור?", reply_markup=reply_markup)
    return CHOOSING

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
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
        with SessionLocal() as db:
            user = get_or_create_user(db, query.from_user.id)
            history = get_user_history(db, user.id)
            
        if history and (history['incomes'] or history['payments']):
            message = "📖 היסטוריית פעולות\n"
            message += "══════════════════\n\n"
            
            if history['incomes']:
                message += "*📥 הכנסות אחרונות:*\n"
                message += "──────────────────\n"
                for income in history['incomes']:
                    calc_amount = income.amount * 0.1 if income.calc_type == CalculationType.MAASER else income.amount * 0.2
                    message += (f"• {income.created_at.strftime('%d/%m/%Y')}\n"
                              f"  סכום: {income.amount:.2f} {history['currency'].value}\n"
                              f"  {income.calc_type.value}: {calc_amount:.2f} {history['currency'].value}"
                              f"{f'\n  תיאור: {income.description}' if income.description else ''}\n"
                              f"──────────────────\n")
                
            if history['payments']:
                if history['incomes']:
                    message += "\n"
                message += "*💸 תשלומים אחרונים:*\n"
                message += "──────────────────\n"
                for payment in history['payments']:
                    message += (f"• {payment.created_at.strftime('%d/%m/%Y')}\n"
                              f"  סכום: {payment.amount:.2f} {history['currency'].value}\n"
                              f"──────────────────\n")
                              
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            keyboard = [
                [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📖 היסטוריית פעולות\n"
                "══════════════════\n\n"
                "לא נמצאו נתונים בהיסטוריה עדיין.\n"
                "התחל על ידי הוספת הכנסה! 💪",
                reply_markup=reply_markup
            )
            
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
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        # Store amount in context for later use
        context.user_data['temp_income_amount'] = amount
        
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
    
    amount = context.user_data.get('temp_income_amount')
    if not amount:
        # Something went wrong, return to main menu
        return await handle_main_menu(update, context)
        
    description = None
    if query and query.data == 'skip_description':
        await query.answer()
    else:
        description = update.message.text
        # Delete user's message
        await update.message.delete()
        
    with SessionLocal() as db:
        user = get_or_create_user(db, update.effective_user.id if update.message else query.from_user.id)
        income = add_income(db, user.id, amount, user.default_calc_type, description)
        
        calc_amount = amount * 0.1 if user.default_calc_type == CalculationType.MAASER else amount * 0.2
        
        keyboard = [
            [InlineKeyboardButton("חזרה לתפריט הראשי", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"✅ ההכנסה נרשמה בהצלחה!\n\n"
            f"💰 סכום: {amount:.2f} {user.currency.value}\n"
            f"✨ סכום {user.default_calc_type.value}: {calc_amount:.2f} {user.currency.value}"
        )
        if description:
            message += f"\n💭 תיאור: {description}"
            
        # Update the original message
        await context.user_data['original_message'].edit_text(message, reply_markup=reply_markup)
            
    # Clear temporary data
    if 'temp_income_amount' in context.user_data:
        del context.user_data['temp_income_amount']
        
    return CHOOSING

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment amount input."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        # Delete user's message
        await update.message.delete()
            
        with SessionLocal() as db:
            user = get_or_create_user(db, update.effective_user.id)
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
            InlineKeyboardButton("⚙️ הגדרות", callback_data='settings')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        'במה אוכל לעזור?',
        reply_markup=reply_markup
    )
    return CHOOSING

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation for data deletion."""
    if not context.user_data.get('awaiting_delete_confirmation'):
        return CHOOSING
        
    if update.message.text.strip() == "מחק את כל המידע שלי":
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

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button),
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
            AWAITING_DELETE_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_confirmation),
                CallbackQueryHandler(handle_main_menu, pattern='^main_menu$'),
                CallbackQueryHandler(button)
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(conv_handler)

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main() 