from sqlalchemy import Column, Integer, String, Float
from database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    usage = Column(Float)
    tickets = Column(Integer)
    nps = Column(Integer)
    renewal_status = Column(String)