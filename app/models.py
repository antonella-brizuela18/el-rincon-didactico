"""Version-one persistence; money uses integer ARS cents."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship
Base = declarative_base()

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(512), nullable=False)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(80), nullable=False)
    age = Column(String(80), nullable=False, default="")
    kind = Column(String(10), nullable=False, default="digital")
    price_cents = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    published = Column(Boolean, nullable=False, default=False)
    image = Column(String(80))
    digital_file = Column(String(80))
    created_at = Column(DateTime, nullable=False, default=now)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    checkout_key = Column(String(64), unique=True, nullable=False)
    customer_name = Column(String(120), nullable=False)
    email = Column(String(254), nullable=False)
    notes = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    total_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)
    paid_at = Column(DateTime)
    payment_reference = Column(String(200))
    confirmed_by = Column(Integer, ForeignKey("admins.id"))
    preference_url = Column(Text)
    payment_id = Column(String(80), unique=True)
    items = relationship("OrderItem", cascade="all, delete-orphan", lazy="selectin")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    title = Column(String(160), nullable=False)
    kind = Column(String(10), nullable=False)
    unit_cents = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    digital_file = Column(String(80))

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True)
    identity = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=now, index=True)


class MailOutbox(Base):
    __tablename__ = "mail_outbox"
    id = Column(Integer, primary_key=True)
    event_key = Column(String(100), unique=True, nullable=False)
    recipient = Column(String(254), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime)
