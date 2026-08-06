from database import engine, Base
from models import Customer

Base.metadata.create_all(bind=engine)

print("Database created successfully!")