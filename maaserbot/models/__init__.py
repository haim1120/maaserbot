from .base import Base, engine, SessionLocal
from .models import User, Income, Payment, CalculationType, Currency

# Create all tables
Base.metadata.create_all(bind=engine) 