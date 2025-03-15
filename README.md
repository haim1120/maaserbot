# Maaser Bot

A Telegram bot for tracking income and maaser (charity) payments.

## What is Maaser?

Maaser (מעשר) is a Jewish practice of donating 10% of one's income to charity. Some follow a stricter practice called Chomesh (חומש), donating 20%. This bot helps manage both types of charitable giving.

## Features

- **Income & Payment Tracking**: Record income and charitable donations
- **Multiple Calculation Methods**: Support for both Maaser (10%) and Chomesh (20%)
- **User Management**: Admin approval system for new users
- **Detailed Reporting**: View balance and detailed history
- **Data Management**: Edit or delete past entries
- **Interactive Interface**: Intuitive Telegram menu system

## Architecture

The bot is built with:

- **Python-Telegram-Bot**: For Telegram integration
- **SQLAlchemy**: For database ORM
- **Poetry**: For dependency management
- **pytest**: For automated testing

The code structure follows a modular approach:

```
maaserbot/
├── handlers/        # Telegram command and callback handlers
├── models/          # Database models and ORM
├── utils/           # Utility functions and error handling
├── bot.py           # Main bot entry point
tests/
├── test_models.py   # Model tests
└── test_db_utils.py # Database utility tests
```

## Setup

1. Clone the repository
2. Install dependencies:
```bash
# Using Poetry (recommended)
poetry install

# Using pip
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your bot token from @BotFather
   - Set your Telegram ID as ADMIN_ID (you can get it from @userinfobot)
   - Configure database URL if needed (defaults to SQLite)

4. Initialize the database:
```bash
python -m maaserbot.models.base
```

5. Run the bot:
```bash
python -m maaserbot.bot
```

## Running Tests

The project includes automated tests. To run them:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models.py

# Run with coverage report
pytest --cov=maaserbot
```

## Usage

1. Start the bot with `/start`
2. Request access if you're a new user
3. Once approved, use the menu to:
   - Add income
   - Add payments
   - View balance
   - View history
   - Manage settings

### Admin Commands

- `/approve_request [request_id]` - Approve a user access request
- `/reject_request [request_id]` - Reject a user access request

## Development

### Project Structure

- **models**: Database models for users, income, payments, and access requests
- **handlers**: Telegram handlers for user interactions
- **utils**: Helper functions for database operations and error handling

### Adding New Features

1. Create handlers in the appropriate module
2. Add database models for any new data structures
3. Update utility functions as needed
4. Add tests for new functionality
5. Update documentation

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 