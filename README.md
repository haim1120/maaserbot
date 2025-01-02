# Maaser Bot

A Telegram bot for tracking income and maaser (charity) payments.

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your bot token from @BotFather
   - Set your Telegram ID as ADMIN_ID (you can get it from @userinfobot)
   - Configure database URL if needed (defaults to SQLite)

4. Run the bot:
```bash
python -m maaserbot.bot
```

## Features

- Track income and maaser payments
- Support for multiple currencies
- Gross/Net income calculation options
- User management system with approval process
- Interactive menu interface
- Full history tracking
- Data editing and deletion capabilities

## Usage

1. Start the bot with /start
2. Request access if you're a new user
3. Once approved, use the menu to:
   - Add income
   - Add payments
   - View balance
   - View history
   - Manage settings

## Admin Features

- Approve/reject user access requests
- View and manage approved users
- Monitor user activity 