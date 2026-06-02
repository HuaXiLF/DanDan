"""出租屋管理站 — 数据库模型"""
import os
from datetime import date, datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    Text, Date, DateTime, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ── 数据库 ───────────────────────────────────────────────
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "rental.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ══════════════════════════════════════════════════════════
#  模型
# ══════════════════════════════════════════════════════════

class Room(Base):
    """房间"""
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    room_number = Column(String(20), nullable=False, unique=True)
    floor = Column(Integer, nullable=False)
    monthly_rent = Column(Float, default=0)
    status = Column(String(20), default="vacant")  # vacant | occupied
    created_at = Column(DateTime, default=datetime.now)

    tenancies = relationship("Tenancy", back_populates="room", cascade="all, delete-orphan")
    utility_bills = relationship("UtilityBill", back_populates="room", cascade="all, delete-orphan")
    repairs = relationship("Repair", back_populates="room", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="room")

    def current_tenancy(self):
        active = [t for t in self.tenancies if t.status == "active"]
        return active[0] if active else None

    def tenant_count(self):
        ten = self.current_tenancy()
        return len(ten.tenants) if ten and ten.tenants else 0

    def __repr__(self):
        return f"<Room {self.room_number}>"


class Tenant(Base):
    """租客"""
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    id_number = Column(String(30), default="")
    phone = Column(String(20), default="")
    created_at = Column(DateTime, default=datetime.now)

    tenancies = relationship("TenantTenancy", back_populates="tenant", cascade="all, delete-orphan")


class Tenancy(Base):
    """租约"""
    __tablename__ = "tenancies"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    lease_type = Column(String(20), nullable=False)  # monthly | yearly | weekly
    monthly_rent = Column(Float, nullable=False)
    deposit = Column(Float, default=0)
    deposit_paid = Column(Boolean, default=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    status = Column(String(20), default="active")  # active | expired | terminated
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)

    room = relationship("Room", back_populates="tenancies")
    tenants = relationship("TenantTenancy", back_populates="tenancy", cascade="all, delete-orphan")
    payments = relationship("RentPayment", back_populates="tenancy", cascade="all, delete-orphan")

    @property
    def tenant_list(self):
        return [tt.tenant for tt in self.tenants]

    @property
    def display_name(self):
        names = ", ".join(t.name for t in self.tenant_list)
        return f"{self.room.room_number} - {names}" if names else self.room.room_number


class TenantTenancy(Base):
    """租客-租约关联（N:N）"""
    __tablename__ = "tenant_tenancies"
    id = Column(Integer, primary_key=True)
    tenancy_id = Column(Integer, ForeignKey("tenancies.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    tenancy = relationship("Tenancy", back_populates="tenants")
    tenant = relationship("Tenant", back_populates="tenancies")


class RentPayment(Base):
    """租金支付记录"""
    __tablename__ = "rent_payments"
    id = Column(Integer, primary_key=True)
    tenancy_id = Column(Integer, ForeignKey("tenancies.id"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    paid_date = Column(Date)
    status = Column(String(20), default="pending")  # pending | paid | overdue
    notes = Column(Text, default="")

    tenancy = relationship("Tenancy", back_populates="payments")


class UtilityBill(Base):
    """水电费账单（按房间按月）"""
    __tablename__ = "utility_bills"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    month = Column(String(7), nullable=False)  # YYYY-MM
    electricity_reading = Column(Float, default=0)  # 本月电表读数
    electricity_usage = Column(Float, default=0)    # 用电量 (kWh)
    electricity_cost = Column(Float, default=0)     # 电费
    tenant_count = Column(Integer, default=0)       # 本月该房间租客数
    water_cost = Column(Float, default=0)           # 水费
    total = Column(Float, default=0)                # 合计
    paid = Column(Boolean, default=False)
    paid_date = Column(Date)

    room = relationship("Room", back_populates="utility_bills")


class Repair(Base):
    """维修报修记录"""
    __tablename__ = "repairs"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    description = Column(Text, nullable=False)
    reported_date = Column(Date, nullable=False)
    status = Column(String(20), default="pending")  # pending | completed
    cost = Column(Float, default=0)
    completed_date = Column(Date)
    notes = Column(Text, default="")

    room = relationship("Room", back_populates="repairs")


class Transaction(Base):
    """财务流水"""
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    tx_type = Column(String(10), nullable=False)   # income | expense
    category = Column(String(30), nullable=False)  # rent | deposit | electricity | water | repair | other
    amount = Column(Float, nullable=False)
    tx_date = Column(Date, nullable=False)
    description = Column(Text, default="")
    room_id = Column(Integer, ForeignKey("rooms.id"))
    related_payment_id = Column(Integer)  # 关联的租金/水电ID

    room = relationship("Room", back_populates="transactions")


# ══════════════════════════════════════════════════════════
#  初始化 & 种子数据
# ══════════════════════════════════════════════════════════

def init_db():
    """建表 + 插入默认房间数据"""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(Room).count() == 0:
            rooms = [
                # 4F
                ("4018", 4), ("4028", 4), ("4058", 4), ("4068", 4), ("4088", 4),
                # 5F
                ("5010", 5), ("5028", 5), ("5058", 5), ("5068", 5), ("5088", 5),
                # 6F
                ("601", 6), ("602", 6), ("603", 6), ("605", 6), ("606", 6),
                ("608", 6), ("609", 6), ("610", 6), ("611", 6), ("612", 6),
            ]
            for num, fl in rooms:
                db.add(Room(room_number=num, floor=fl))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
