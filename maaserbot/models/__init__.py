from .base import Base, engine, SessionLocal
from .models import User, Income, Payment, CalculationType

# Create all tables
Base.metadata.create_all(bind=engine) 