"""Logging utilities for MaaserBot."""

import logging
import os
import json
from datetime import datetime
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import traceback

# יצירת תיקיה ללוגים אם לא קיימת
os.makedirs('logs', exist_ok=True)

# הגדרת לוגר עיקרי
logger = logging.getLogger('maaserbot')

def setup_logging(log_level=logging.INFO):
    """
    Setup detailed logging configuration.
    
    Args:
        log_level: The logging level to use
    """
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
    
    # Configure SQLAlchemy logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    logger.info("Logging system initialized")

def log_action(action_type):
    """
    Decorator to log user actions with detailed information.
    
    Args:
        action_type: The type of action being performed (e.g., 'income_add', 'payment_delete')
        
    Returns:
        Decorated function with logging
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            user_info = {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            
            start_time = datetime.now()
            log_data = {
                'timestamp': start_time.isoformat(),
                'action': action_type,
                'user': user_info,
                'success': False,
                'duration_ms': 0
            }
            
            try:
                # Call the original function
                result = await func(update, context, *args, **kwargs)
                log_data['success'] = True
                return result
            except Exception as e:
                log_data['error'] = str(e)
                log_data['stacktrace'] = traceback.format_exc()
                raise
            finally:
                # Calculate duration
                duration = datetime.now() - start_time
                log_data['duration_ms'] = duration.total_seconds() * 1000
                
                # Log to security log file
                with open(f'logs/security_{datetime.now().strftime("%Y%m%d")}.log', 'a') as f:
                    f.write(json.dumps(log_data) + '\n')
                
                # Also log a summary to the main logger
                action_str = f"{action_type} by user {user.id}"
                if log_data['success']:
                    logger.info(f"SUCCESS: {action_str} ({log_data['duration_ms']:.2f}ms)")
                else:
                    logger.warning(f"FAILED: {action_str} - {log_data.get('error', 'Unknown error')}")
        
        return wrapper
    return decorator

def log_admin_action(func):
    """
    Special decorator for logging admin actions with high detail.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function with admin action logging
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        
        # Log the admin action with all available context
        logger.info(f"ADMIN ACTION: {func.__name__} initiated by admin {user.id} ({user.username})")
        
        if hasattr(update, 'callback_query') and update.callback_query:
            logger.info(f"Admin context: callback_data={update.callback_query.data}")
        
        if context.args:
            logger.info(f"Admin command args: {context.args}")
            
        # Call the original function
        return await func(update, context, *args, **kwargs)
    
    return wrapper 