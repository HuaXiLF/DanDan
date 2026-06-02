"""出租屋管理站 — FastAPI 主应用"""
import os
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware

from models import (
    init_db, get_db, Room, Tenant, Tenancy, TenantTenancy,
    RentPayment, UtilityBill, Repair, Transaction,
)

app = FastAPI(title="出租屋管理站")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dan-dan-secret-2024"))

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.cache = None
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

MONTH_NAMES = ["一月","二月","三月","四月","五月","六月",
               "七月","八月","九月","十月","十一月","十二月"]


def td():
    return date.today()


def login_required(request: Request):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=303, detail="请先登录")


def get_or_create_tx(db, payment):
    existing = db.query(Transaction).filter_by(related_payment_id=payment.id).first()
    if existing:
        return existing
    tx = Transaction(
        tx_type="income", category="rent", amount=payment.amount,
        tx_date=payment.paid_date or td(),
        description=f"租金 {payment.tenancy.room.room_number} ({payment.period_start}~{payment.period_end})",
        room_id=payment.tenancy.room_id, related_payment_id=payment.id,
    )
    db.add(tx)
    db.commit()
    return tx


def render_html(tpl, request, **kw):
    kw["request"] = request
    kw["today"] = td
    return templates.TemplateResponse(request, tpl, kw)


@app.on_event("startup")
def startup():
    init_db()


# ── 登录 ──

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render_html("login.html", request)


@app.post("/login")
def login_post(request: Request, password: str = Form(...)):
    pw = os.getenv("ADMIN_PASSWORD", "888888")
    if password == pw:
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)
    return render_html("login.html", request, error="密码错误")


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ── 仪表盘 ──

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    login_required(request)
    rooms = db.query(Room).all()
    total = len(rooms)
    occupied = sum(1 for r in rooms if r.status == "occupied")
    vacant = total - occupied
    now = td()
    ms = now.replace(day=1)
    nm = now.replace(year=now.year+1, month=1, day=1) if now.month == 12 else now.replace(month=now.month+1, day=1)
    expected = db.query(func.sum(RentPayment.amount)).filter(
        RentPayment.status == "pending", RentPayment.period_start >= ms, RentPayment.period_start < nm).scalar() or 0
    paid = db.query(func.sum(RentPayment.amount)).filter(
        RentPayment.status == "paid", RentPayment.paid_date >= ms, RentPayment.paid_date < nm).scalar() or 0
    wd = now + timedelta(days=7)
    expiring = db.query(Tenancy).filter(Tenancy.status == "active", Tenancy.end_date <= wd, Tenancy.end_date >= now).all()
    pending_r = db.query(Repair).filter(Repair.status == "pending").count()
    floors = {}
    for r in rooms:
        floors.setdefault(r.floor, []).append(r)
    return render_html("dashboard.html", request, floors=sorted(floors.items()),
                        total_rooms=total, occupied=occupied, vacant=vacant,
                        expected_rent=expected, paid_rent=paid,
                        expiring_leases=expiring, pending_repairs=pending_r)


# ── 房间 ──

@app.get("/rooms", response_class=HTMLResponse)
def rooms_page(request: Request, db: Session = Depends(get_db)):
    login_required(request)
    rooms = db.query(Room).order_by(Room.floor, Room.room_number).all()
    floors = {}
    for r in rooms:
        floors.setdefault(r.floor, []).append(r)
    return render_html("rooms.html", request, floors=sorted(floors.items()))


@app.get("/rooms/{room_id}", response_class=HTMLResponse)
def room_detail(request: Request, room_id: int, db: Session = Depends(get_db)):
    login_required(request)
    room = db.query(Room).get(room_id)
    if not room:
        raise HTTPException(404)
    tenancy = room.current_tenancy()
    bills = db.query(UtilityBill).filter_by(room_id=room_id).order_by(UtilityBill.month.desc()).limit(12).all()
    repairs = db.query(Repair).filter_by(room_id=room_id).order_by(Repair.reported_date.desc()).all()
    return render_html("room_detail.html", request, room=room, tenancy=tenancy, bills=bills, repairs=repairs)


@app.post("/rooms/{room_id}/rent")
def update_rent(room_id: int, monthly_rent: float = Form(...), db: Session = Depends(get_db)):
    room = db.query(Room).get(room_id)
    if room:
        room.monthly_rent = monthly_rent
        db.commit()
    return RedirectResponse(f"/rooms/{room_id}", status_code=303)


# ── 租客 ──

@app.get("/tenants", response_class=HTMLResponse)
def tenants_page(request: Request, q: str = "", db: Session = Depends(get_db)):
    login_required(request)
    query = db.query(Tenant).order_by(Tenant.created_at.desc())
    if q:
        query = query.filter(Tenant.name.contains(q) | Tenant.phone.contains(q))
    return render_html("tenants.html", request, tenants=query.all(), q=q)


@app.get("/tenants/create", response_class=HTMLResponse)
def tenant_create_page(request: Request):
    login_required(request)
    return render_html("tenant_form.html", request, tenant=None)


@app.post("/tenants/create")
def tenant_create(request: Request, name: str = Form(...), id_number: str = Form(""),
                  phone: str = Form(""), db: Session = Depends(get_db)):
    login_required(request)
    db.add(Tenant(name=name, id_number=id_number, phone=phone))
    db.commit()
    return RedirectResponse("/tenants", status_code=303)


# ── 租约 ──

@app.get("/leases", response_class=HTMLResponse)
def leases_page(request: Request, status: str = "active", db: Session = Depends(get_db)):
    login_required(request)
    query = db.query(Tenancy).order_by(Tenancy.start_date.desc())
    if status != "all":
        query = query.filter(Tenancy.status == status)
    rooms = db.query(Room).order_by(Room.floor, Room.room_number).all()
    tenants = db.query(Tenant).order_by(Tenant.name).all()
    return render_html("leases.html", request, leases=query.all(), rooms=rooms, tenants=tenants, status=status)


@app.post("/leases/create")
def lease_create(request: Request, room_id: int = Form(...), tenant_ids: str = Form(...),
                 lease_type: str = Form("monthly"), monthly_rent: float = Form(...),
                 deposit: float = Form(...), deposit_paid: bool = Form(False),
                 start_date: str = Form(...), end_date: str = Form(""), notes: str = Form(""),
                 db: Session = Depends(get_db)):
    login_required(request)
    ids = [int(x) for x in tenant_ids.split(",") if x.strip()]
    tenancy = Tenancy(room_id=room_id, lease_type=lease_type, monthly_rent=monthly_rent,
                      deposit=deposit, deposit_paid=deposit_paid,
                      start_date=date.fromisoformat(start_date),
                      end_date=date.fromisoformat(end_date) if end_date else None, notes=notes)
    db.add(tenancy)
    db.flush()
    for tid in ids:
        db.add(TenantTenancy(tenancy_id=tenancy.id, tenant_id=tid))
    room = db.query(Room).get(room_id)
    if room:
        room.status = "occupied"
        room.monthly_rent = monthly_rent
    db.commit()
    return RedirectResponse("/leases", status_code=303)


@app.post("/leases/{lease_id}/terminate")
def lease_terminate(lease_id: int, db: Session = Depends(get_db)):
    tenancy = db.query(Tenancy).get(lease_id)
    if tenancy:
        tenancy.status = "terminated"
        tenancy.end_date = td()
        room = tenancy.room
        if room:
            room.status = "vacant"
        db.commit()
    return RedirectResponse("/leases", status_code=303)


# ── 租金 ──

@app.get("/payments", response_class=HTMLResponse)
def payments_page(request: Request, status: str = "pending", month: str = "", db: Session = Depends(get_db)):
    login_required(request)
    query = db.query(RentPayment).order_by(RentPayment.period_start.desc())
    if status != "all":
        query = query.filter(RentPayment.status == status)
    if month:
        query = query.filter(RentPayment.period_start.startswith(f"{month}-"))
    leases = db.query(Tenancy).filter_by(status="active").all()
    return render_html("payments.html", request, payments=query.all(), leases=leases, status=status, month=month)


@app.post("/payments/create")
def payment_create(request: Request, tenancy_id: int = Form(...),
                   period_start: str = Form(...), period_end: str = Form(...),
                   amount: float = Form(...), paid: bool = Form(False), db: Session = Depends(get_db)):
    login_required(request)
    p = RentPayment(tenancy_id=tenancy_id, period_start=date.fromisoformat(period_start),
                    period_end=date.fromisoformat(period_end), amount=amount,
                    status="paid" if paid else "pending", paid_date=td() if paid else None)
    db.add(p)
    db.flush()
    if paid:
        get_or_create_tx(db, p)
    db.commit()
    return RedirectResponse("/payments", status_code=303)


@app.post("/payments/{pid}/pay")
def payment_pay(pid: int, db: Session = Depends(get_db)):
    p = db.query(RentPayment).get(pid)
    if p:
        p.status = "paid"
        p.paid_date = td()
        get_or_create_tx(db, p)
        db.commit()
    return RedirectResponse("/payments", status_code=303)


@app.post("/payments/{pid}/unpay")
def payment_unpay(pid: int, db: Session = Depends(get_db)):
    p = db.query(RentPayment).get(pid)
    if p:
        p.status = "pending"
        p.paid_date = None
        db.query(Transaction).filter_by(related_payment_id=pid).delete()
        db.commit()
    return RedirectResponse("/payments", status_code=303)


@app.get("/payments/batch")
def batch_payment(request: Request, db: Session = Depends(get_db)):
    login_required(request)
    now = td()
    ms = now.replace(day=1)
    nm = now.replace(year=now.year+1, month=1, day=1) if now.month == 12 else now.replace(month=now.month+1, day=1)
    created = skipped = 0
    for lease in db.query(Tenancy).filter_by(status="active").all():
        if db.query(RentPayment).filter(RentPayment.tenancy_id == lease.id, RentPayment.period_start == ms).first():
            skipped += 1
            continue
        db.add(RentPayment(tenancy_id=lease.id, period_start=ms, period_end=nm - timedelta(days=1),
                           amount=lease.monthly_rent, status="pending"))
        created += 1
    db.commit()
    return JSONResponse({"created": created, "skipped": skipped})


# ── 水电 ──

@app.get("/utilities", response_class=HTMLResponse)
def utilities_page(request: Request, month: str = "", db: Session = Depends(get_db)):
    login_required(request)
    query = db.query(UtilityBill).order_by(UtilityBill.month.desc())
    if month:
        query = query.filter(UtilityBill.month == month)
    rooms = db.query(Room).order_by(Room.floor, Room.room_number).all()
    months = [m[0] for m in db.query(UtilityBill.month).distinct().order_by(UtilityBill.month.desc()).all()]
    return render_html("utilities.html", request, bills=query.all(), rooms=rooms, months=months, current_month=month)


@app.post("/utilities/create")
def utility_create(request: Request, room_id: int = Form(...), month: str = Form(...),
                   electricity_reading: float = Form(0), electricity_usage: float = Form(0),
                   tenant_count: int = Form(0), db: Session = Depends(get_db)):
    login_required(request)
    ec = electricity_usage * 1.0
    wc = tenant_count * 70
    db.add(UtilityBill(room_id=room_id, month=month, electricity_reading=electricity_reading,
                       electricity_usage=electricity_usage, electricity_cost=ec,
                       tenant_count=tenant_count, water_cost=wc, total=ec + wc))
    db.commit()
    return RedirectResponse("/utilities", status_code=303)


@app.post("/utilities/{bid}/pay")
def utility_pay(bid: int, db: Session = Depends(get_db)):
    bill = db.query(UtilityBill).get(bid)
    if bill:
        bill.paid = True
        bill.paid_date = td()
        db.add(Transaction(tx_type="income", category="electricity" if bill.electricity_cost > 0 else "water",
                           amount=bill.total, tx_date=td(),
                           description=f"水电费 {bill.room.room_number} ({bill.month})", room_id=bill.room_id))
        db.commit()
    return RedirectResponse("/utilities", status_code=303)


# ── 维修 ──

@app.get("/repairs", response_class=HTMLResponse)
def repairs_page(request: Request, status: str = "all", db: Session = Depends(get_db)):
    login_required(request)
    query = db.query(Repair).order_by(Repair.reported_date.desc())
    if status != "all":
        query = query.filter(Repair.status == status)
    rooms = db.query(Room).order_by(Room.floor, Room.room_number).all()
    return render_html("repairs.html", request, repairs=query.all(), rooms=rooms, status=status)


@app.post("/repairs/create")
def repair_create(request: Request, room_id: int = Form(...), description: str = Form(...),
                  cost: float = Form(0), db: Session = Depends(get_db)):
    login_required(request)
    db.add(Repair(room_id=room_id, description=description, reported_date=td(), cost=cost))
    db.commit()
    return RedirectResponse("/repairs", status_code=303)


@app.post("/repairs/{rid}/complete")
def repair_complete(rid: int, cost: float = Form(0), notes: str = Form(""), db: Session = Depends(get_db)):
    r = db.query(Repair).get(rid)
    if r:
        r.status = "completed"
        r.completed_date = td()
        r.cost = cost
        r.notes = notes
        if cost > 0:
            db.add(Transaction(tx_type="expense", category="repair", amount=cost, tx_date=td(),
                               description=f"维修 {r.room.room_number}: {r.description}", room_id=r.room_id))
        db.commit()
    return RedirectResponse("/repairs", status_code=303)


# ── 财务报表 ──

@app.get("/finance", response_class=HTMLResponse)
def finance_page(request: Request, year: int = 0, db: Session = Depends(get_db)):
    login_required(request)
    if not year:
        year = td().year
    monthly = []
    for m in range(1, 13):
        ms = f"{year}-{m:02d}"
        inc = db.query(func.sum(Transaction.amount)).filter(
            Transaction.tx_type == "income", func.strftime("%Y-%m", Transaction.tx_date) == ms).scalar() or 0
        exp = db.query(func.sum(Transaction.amount)).filter(
            Transaction.tx_type == "expense", func.strftime("%Y-%m", Transaction.tx_date) == ms).scalar() or 0
        monthly.append({"month": MONTH_NAMES[m-1], "income": inc, "expense": exp, "profit": inc - exp})
    ys = str(year)
    ti = db.query(func.sum(Transaction.amount)).filter(
        Transaction.tx_type == "income", func.strftime("%Y", Transaction.tx_date) == ys).scalar() or 0
    te = db.query(func.sum(Transaction.amount)).filter(
        Transaction.tx_type == "expense", func.strftime("%Y", Transaction.tx_date) == ys).scalar() or 0
    ri = db.query(func.sum(Transaction.amount)).filter(
        Transaction.tx_type == "income", Transaction.category == "rent",
        func.strftime("%Y", Transaction.tx_date) == ys).scalar() or 0
    ui = db.query(func.sum(Transaction.amount)).filter(
        Transaction.tx_type == "income", Transaction.category.in_(["electricity", "water"]),
        func.strftime("%Y", Transaction.tx_date) == ys).scalar() or 0
    years = [r[0] for r in db.query(func.strftime("%Y", Transaction.tx_date)).distinct().order_by(
        func.strftime("%Y", Transaction.tx_date).desc()).all()]
    return render_html("finance.html", request, year=year, years=years, monthly_data=monthly,
                        total_income=ti, total_expense=te, total_profit=ti - te,
                        rent_income=ri, utility_income=ui)


# ── 账单导出 ──

@app.get("/export/{payment_id}", response_class=HTMLResponse)
def export_bill(request: Request, payment_id: int, db: Session = Depends(get_db)):
    login_required(request)
    payment = db.query(RentPayment).get(payment_id)
    if not payment:
        raise HTTPException(404)
    return render_html("bill.html", request, p=payment)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
