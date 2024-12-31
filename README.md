# MaaserBot - בוט מעשרות לטלגרם

בוט טלגרם לניהול ומעקב אחר הכנסות ותשלומי מעשרות.

## תכונות

- ניהול הכנסות ותשלומי מעשרות
- תמיכה במעשר (10%) וחומש (20%)
- מעקב אחר היסטוריית הכנסות ותשלומים
- תמיכה במספר מטבעות (₪, $, €)
- ממשק משתמש ידידותי בעברית

## התקנה

1. התקן את התלויות:
```bash
poetry install
```

2. צור קובץ `.env` עם הפרטים הבאים:
```
BOT_TOKEN=your_bot_token_here
DATABASE_URL=sqlite:///maaser.db
```

3. הפעל את הבוט:
```bash
poetry run python maaserbot/bot.py
```

## שימוש

1. התחל שיחה עם הבוט בטלגרם
2. השתמש בפקודת `/start` להתחלת השימוש
3. השתמש בתפריט הכפתורים לניווט בין האפשרויות השונות

## רישיון

MIT License 