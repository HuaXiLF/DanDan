"""
出租屋管理站 — Streamlit 版
支持手机端操作，一键部署到 Streamlit Cloud
"""
import sqlite3
import json
import os
import pandas as pd
from datetime import date, datetime, timedelta
import streamlit as st

st.set_page_config(page_title="出租屋管理站", page_icon="🏠", layout="wide",
                   initial_sidebar_state="collapsed")

# ── CSS 设计系统（移动端优先） ──
st.markdown("""
<style>
    /* === Reset & 基础 === */
    #MainMenu, footer, header {display: none !important;}
    .stApp {margin-top: -80px; padding-top: 0; background: #f5f6fa;}
    .block-container {padding: 0 12px 90px !important; max-width: 480px !important; margin: 0 auto;}
    div[data-testid="stVerticalBlock"] > div {gap: 6px;}
    .st-emotion-cache-1y4p8pa {padding: 1rem 0;}
    .row-widget.stButton {margin: 0;}

    /* === 顶部渐变标题 === */
    .app-header {
        background: linear-gradient(135deg, #1a237e 0%, #283593 40%, #3949ab 100%);
        color: white; border-radius: 0 0 24px 24px; padding: 24px 20px 20px;
        margin: -12px -12px 16px; position: relative; overflow: hidden;
    }
    .app-header::before {
        content: ''; position: absolute; top: -50%; right: -30%; width: 200px; height: 200px;
        background: rgba(255,255,255,0.05); border-radius: 50%;
    }
    .app-header::after {
        content: ''; position: absolute; bottom: -20%; left: -10%; width: 120px; height: 120px;
        background: rgba(255,255,255,0.04); border-radius: 50%;
    }
    .app-header h1 {font-size: 20px; font-weight: 700; margin: 0; position: relative; z-index: 1;}
    .app-header p {font-size: 12px; opacity: 0.75; margin: 2px 0 0; position: relative; z-index: 1;}
    .header-stat-row {display: flex; gap: 8px; margin-top: 14px; position: relative; z-index: 1;}
    .header-stat {background: rgba(255,255,255,0.12); backdrop-filter: blur(8px);
                  border-radius: 12px; padding: 10px 12px; flex: 1; text-align: center;}
    .header-stat .num {font-size: 22px; font-weight: 700; line-height: 1.2;}
    .header-stat .lbl {font-size: 10px; opacity: 0.7; margin-top: 2px;}

    /* === 底部导航栏 === */
    .bottom-nav {
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
        background: white; border-top: 1px solid #e8eaef;
        padding: 6px 0 max(6px, env(safe-area-inset-bottom, 6px));
        display: flex; justify-content: space-around; box-shadow: 0 -2px 12px rgba(0,0,0,0.06);
    }
    .nav-item {
        display: flex; flex-direction: column; align-items: center; gap: 1px;
        flex: 1; max-width: 72px; cursor: pointer; border: none; background: none;
        padding: 4px 0; transition: all 0.15s; -webkit-tap-highlight-color: transparent;
    }
    .nav-item .icon {font-size: 20px; line-height: 1;}
    .nav-item .label {font-size: 9px; color: #9ca3af; font-weight: 500; transition: color 0.15s;}
    .nav-item.active .label {color: #1a237e; font-weight: 600;}
    .nav-item.active .icon {transform: scale(1.05);}
    .nav-item:active {transform: scale(0.92);}

    /* === 卡片系统 === */
    .card {
        background: white; border-radius: 16px; padding: 16px; margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .card:active {transform: scale(0.99);}
    .stat-card {text-align: center; padding: 14px 8px;}
    .stat-card .val {font-size: 24px; font-weight: 800; letter-spacing: -0.5px;}
    .stat-card .lbl {font-size: 11px; color: #9ca3af; margin-top: 2px;}

    /* 进度条卡片 */
    .progress-card {background: white; border-radius: 16px; padding: 16px; margin-bottom: 10px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);}
    .progress-header {display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;}
    .progress-header .title {font-size: 13px; color: #6b7280; font-weight: 500;}
    .progress-header .amount {font-size: 18px; font-weight: 700;}
    .progress-header .amount .paid {color: #059669;}
    .progress-header .amount .sep {color: #d1d5db; margin: 0 3px;}
    .progress-header .amount .total {color: #1a237e;}
    .progress-bar {height: 6px; background: #e5e7eb; border-radius: 99px; overflow: hidden;}
    .progress-fill {height: 100%; background: linear-gradient(90deg, #059669, #10b981);
                    border-radius: 99px; transition: width 0.5s ease;}

    /* === 房间网格 === */
    .floor-label {font-size: 14px; font-weight: 600; color: #374151; margin: 12px 0 6px; display: flex;
                  align-items: center; gap: 6px; padding: 0 2px;}
    .room-grid {display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 10px;}
    .room-cell {
        border-radius: 12px; padding: 10px 2px; text-align: center; font-size: 12px; font-weight: 600;
        cursor: pointer; border: 1.5px solid; transition: all 0.12s;
        -webkit-tap-highlight-color: transparent; text-decoration: none; display: block;
    }
    .room-cell:active {transform: scale(0.93);}
    .room-cell.occupied {background: #ecfdf5; border-color: #a7f3d0; color: #065f46;}
    .room-cell.vacant {background: #f9fafb; border-color: #e5e7eb; color: #b0b7c3;}
    .room-cell .dot {display: inline-block; width: 5px; height: 5px; border-radius: 50%;
                     margin-top: 3px;}
    .room-cell.occupied .dot {background: #059669;}
    .room-cell.vacant .dot {background: #d1d5db;}

    /* === 标记 === */
    .tag {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 10px; font-weight: 600; letter-spacing: 0.3px;}
    .tag-green {background: #d1fae5; color: #065f46;}
    .tag-red {background: #fee2e2; color: #991b1b;}
    .tag-yellow {background: #fef3c7; color: #92400e;}
    .tag-blue {background: #dbeafe; color: #1a237e;}
    .tag-gray {background: #f3f4f6; color: #6b7280;}

    /* === Styled 表单元素 === */
    .stButton button {
        width: 100%; border-radius: 12px !important; padding: 12px 0 !important;
        font-size: 14px !important; font-weight: 600 !important;
        transition: all 0.12s !important; border: none !important;
    }
    .stButton button:active {transform: scale(0.96) !important;}
    .stButton button[kind="primary"] {background: linear-gradient(135deg, #1a237e, #3949ab) !important; color: white !important;}
    .stTextInput input, .stSelectbox > div, .stDateInput input, .stNumberInput input {
        border-radius: 12px !important; border: 1.5px solid #e5e7eb !important;
        font-size: 14px !important; padding: 12px 14px !important;
        background: #f9fafb !important; transition: all 0.12s !important;
    }
    .stTextInput input:focus, .stSelectbox > div:focus, .stDateInput input:focus, .stNumberInput input:focus {
        border-color: #3949ab !important; background: white !important; box-shadow: 0 0 0 3px rgba(57,73,171,0.1) !important;
    }
    div[data-testid="stForm"] {border: none !important; padding: 0 !important; background: none !important;}
    div[data-testid="stForm"] > div {gap: 10px;}
    .stSelectbox > div > div {padding: 8px 12px !important;}
    .stMultiSelect > div {border-radius: 12px !important; border: 1.5px solid #e5e7eb !important;}

    /* === 分割线 === */
    hr {margin: 8px 0 !important; border-color: #f0f0f5 !important;}

    /* === Tab 容器 === */
    .stTabs [data-baseweb="tab-list"] {gap: 4px; background: #f3f4f6; border-radius: 12px; padding: 3px; margin-bottom: 12px;}
    .stTabs [data-baseweb="tab"] {border-radius: 10px; padding: 8px 16px; font-size: 12px; font-weight: 500; border: none !important;}
    .stTabs [aria-selected="true"] {background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.08);}

    /* === 展开器 === */
    .stExpander {border: none !important; border-radius: 16px !important; overflow: hidden;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 10px;}
    .stExpander > div:first-child {background: white; border: none; padding: 12px 16px; font-weight: 600; font-size: 13px;}
    .stExpander > div:last-child {background: white; border: none; border-top: 1px solid #f3f4f6; padding: 16px;}

    /* === Infobox === */
    .stAlert {border-radius: 12px !important; font-size: 13px !important; padding: 10px 14px !important; border: none !important;}

    /* === DataFrame === */
    .stDataFrame {border-radius: 12px; overflow: hidden; border: 1px solid #f0f0f5; margin-bottom: 10px;}

    /* === Section Header === */
    .section-title {font-size: 15px; font-weight: 700; color: #1a237e; margin: 14px 0 8px; padding-left: 2px;}

    /* === 安全区 === */
    .safe-bottom {height: 20px;}
</style>
""", unsafe_allow_html=True)

# ── 数据库 ───────────────────────────────────────────────
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "rental.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL UNIQUE,
            floor INTEGER NOT NULL,
            monthly_rent REAL DEFAULT 0,
            status TEXT DEFAULT 'vacant'
        );
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            id_number TEXT DEFAULT '',
            phone TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS tenancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            lease_type TEXT NOT NULL,
            monthly_rent REAL NOT NULL,
            deposit REAL DEFAULT 0,
            deposit_paid INTEGER DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        );
        CREATE TABLE IF NOT EXISTS tenant_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenancy_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL,
            FOREIGN KEY (tenancy_id) REFERENCES tenancies(id),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenancy_id INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (tenancy_id) REFERENCES tenancies(id)
        );
        CREATE TABLE IF NOT EXISTS utility_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            electricity_reading REAL DEFAULT 0,
            electricity_usage REAL DEFAULT 0,
            electricity_cost REAL DEFAULT 0,
            tenant_count INTEGER DEFAULT 0,
            water_cost REAL DEFAULT 0,
            total REAL DEFAULT 0,
            paid INTEGER DEFAULT 0,
            paid_date TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        );
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            reported_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            cost REAL DEFAULT 0,
            completed_date TEXT,
            notes TEXT DEFAULT '',
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_type TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            tx_date TEXT NOT NULL,
            description TEXT DEFAULT '',
            room_id INTEGER,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        );
    """)
    # 种子数据
    if c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        rooms = [("4018",4),("4028",4),("4058",4),("4068",4),("4088",4),
                 ("5010",5),("5028",5),("5058",5),("5068",5),("5088",5),
                 ("601",6),("602",6),("603",6),("605",6),("606",6),
                 ("608",6),("609",6),("610",6),("611",6),("612",6)]
        for num, fl in rooms:
            c.execute("INSERT INTO rooms (room_number, floor) VALUES (?,?)", (num, fl))
    conn.commit()
    conn.close()


# ── 辅助函数 ──

def today():
    return date.today().isoformat()

def parse_date(d):
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return date.fromisoformat(d)
    return d

def month_range(d=None):
    d = d or date.today()
    ms = d.replace(day=1)
    if d.month == 12:
        me = d.replace(year=d.year+1, month=1, day=1) - timedelta(days=1)
    else:
        me = d.replace(month=d.month+1, day=1) - timedelta(days=1)
    return ms, me

def fmt_money(v):
    return f"{v:,.0f}"

def dict_from_row(row):
    return dict(row) if row else {}

# ── 初始化 ──
init_db()

# ── 导航 ──
NAV_ITEMS = [
    ("📊", "首页", "📊 首页"),
    ("🚪", "房间", "🚪 房间"),
    ("📄", "租约", "📄 租约"),
    ("💰", "收租", "💰 收租"),
    ("📈", "报表", "📈 报表"),
]
if "page" not in st.session_state:
    st.session_state.page = "📊 首页"

# 页面切换回调（通过底部导航）
nav_cols = st.columns(len(NAV_ITEMS))
for i, (icon, label, page_key) in enumerate(NAV_ITEMS):
    with nav_cols[i]:
        is_active = st.session_state.page == page_key
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"{icon}\n{label}", key=f"nav_{page_key}",
                     use_container_width=True, type=btn_type):
            st.session_state.page = page_key
            st.rerun()

# 隐藏第1行分割线
st.markdown("<hr style='margin:2px 0;opacity:0;'>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
#  1. 首页
# ══════════════════════════════════════════════════════════

if st.session_state.page == "📊 首页":
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms").fetchall()
    total = len(rooms)
    occupied = sum(1 for r in rooms if r["status"] == "occupied")
    vacant = total - occupied

    ms, me = month_range()
    pending = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='pending' AND period_start>=? AND period_start<=?",
                           (ms.isoformat(), me.isoformat())).fetchone()[0]
    paid_amt = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_date>=? AND paid_date<=?",
                           (ms.isoformat(), me.isoformat())).fetchone()[0]
    total_amt = paid_amt + pending
    pct = min(100, int((paid_amt / total_amt * 100) if total_amt > 0 else 0))

    pending_r = conn.execute("SELECT COUNT(*) FROM repairs WHERE status='pending'").fetchone()[0]
    expiring = conn.execute("""
        SELECT t.*, r.room_number FROM tenancies t JOIN rooms r ON t.room_id=r.id
        WHERE t.status='active' AND t.end_date IS NOT NULL
        AND t.end_date <= ? AND t.end_date >= ?
        ORDER BY t.end_date""",
        ((date.today() + timedelta(days=7)).isoformat(), today())).fetchall()

    # Header
    st.markdown(f'''<div class="app-header">
        <h1>🏠 出租屋管理站</h1>
        <p>{date.today().strftime("%Y年%m月%d日 %A")}</p>
        <div class="header-stat-row">
            <div class="header-stat"><div class="num">{total}</div><div class="lbl">总房间</div></div>
            <div class="header-stat"><div class="num" style="color:#6ee7b7;">{occupied}</div><div class="lbl">已出租</div></div>
            <div class="header-stat"><div class="num" style="color:#fcd34d;">{vacant}</div><div class="lbl">空房</div></div>
        </div>
    </div>''', unsafe_allow_html=True)

    # 快捷入口
    quick_cols = st.columns(4)
    quick_items = [("💰", "收租", "💰 收租"), ("📄", "租约", "📄 租约"), ("⚡", "水电", "⚡ 水电"), ("🔧", "维修", "🔧 维修")]
    for i, (icon, label, page) in enumerate(quick_items):
        with quick_cols[i]:
            if st.button(f"{icon}\n{label}", key=f"quick_{page}", use_container_width=True):
                st.session_state.page = page
                st.rerun()

    # 租金进度
    st.markdown(f'''<div class="progress-card">
        <div class="progress-header">
            <span class="title">本月租金</span>
            <span class="amount">
                <span class="paid">{fmt_money(paid_amt)}</span>
                <span class="sep">/</span>
                <span class="total">{fmt_money(total_amt)}</span>
            </span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div></div>
        <div style="font-size:11px;color:#9ca3af;text-align:right;margin-top:4px;">已收 {pct}%</div>
    </div>''', unsafe_allow_html=True)

    # 楼层房间预览
    floors = {}
    for r in rooms:
        floors.setdefault(r["floor"], []).append(r)
    st.markdown('<div class="section-title">🏘️ 房间状态</div>', unsafe_allow_html=True)
    for fl in sorted(floors.keys()):
        fl_rooms = floors[fl]
        cells = "".join(
            f'<a class="room-cell {"occupied" if r["status"]=="occupied" else "vacant"}">'
            f'{r["room_number"]}<div class="dot"></div></a>'
            for r in fl_rooms
        )
        st.markdown(f'<div class="floor-label">{fl}F</div><div class="room-grid">{cells}</div>', unsafe_allow_html=True)

    # 到期提醒 & 维修
    if expiring:
        st.markdown('<div class="section-title">⏰ 即将到期</div>', unsafe_allow_html=True)
        for e in expiring:
            days = (date.fromisoformat(e["end_date"]) - date.today()).days
            st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<div><b>{e["room_number"]}</b></div>'
                        f'<span class="tag tag-yellow">剩 {days} 天</span></div></div>', unsafe_allow_html=True)
    if pending_r:
        st.markdown('<div class="section-title">🔧 待处理</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span>维修报修</span><span class="tag tag-red">{pending_r} 项待处理</span></div></div>', unsafe_allow_html=True)
    conn.close()


# ══════════════════════════════════════════════════════════
#  2. 房间
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "🚪 房间":
    st.markdown('<div class="section-title">🚪 房间管理</div>', unsafe_allow_html=True)
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()
    floors = {}
    for r in rooms:
        floors.setdefault(r["floor"], []).append(r)

    for fl in sorted(floors.keys()):
        fl_rooms = floors[fl]
        cells = "".join(
            f'<div class="room-cell {"occupied" if r["status"]=="occupied" else "vacant"}">'
            f'{r["room_number"]}<div class="dot"></div></div>'
            for r in fl_rooms
        )
        st.markdown(f'<div class="floor-label">{fl}F</div><div class="room-grid">{cells}</div>', unsafe_allow_html=True)

    # 房间详情
    st.markdown('<div class="section-title">🔍 房间详情</div>', unsafe_allow_html=True)
    room_ids = {f"{r['floor']}F {r['room_number']}": r["id"] for r in rooms}
    sel = st.selectbox("选择房间", list(room_ids.keys()), key="room_select", label_visibility="collapsed")
    rid = room_ids[sel]
    room = conn.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()

    if room:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"<span style='font-size:18px;font-weight:700;'>{room['room_number']}</span>", unsafe_allow_html=True)
            with c2:
                tag = "tag-green" if room["status"] == "occupied" else "tag-gray"
                lbl = "已租" if room["status"] == "occupied" else "空房"
                st.markdown(f'<span class="tag {tag}">{lbl}</span>', unsafe_allow_html=True)

            rent = st.number_input("月租(元)", value=float(room["monthly_rent"] or 0), step=50.0, key="room_rent")
            if st.button("保存房租", key="save_rent", use_container_width=True):
                conn.execute("UPDATE rooms SET monthly_rent=? WHERE id=?", (rent, rid))
                conn.commit()
                st.success("已保存")
                st.rerun()

            tenancy = conn.execute("""
                SELECT t.*, GROUP_CONCAT(tn.name,', ') as tenant_names
                FROM tenancies t
                LEFT JOIN tenant_links tl ON tl.tenancy_id=t.id
                LEFT JOIN tenants tn ON tn.id=tl.tenant_id
                WHERE t.room_id=? AND t.status='active'
                GROUP BY t.id""", (rid,)).fetchone()
            if tenancy:
                st.markdown(f'<div style="background:#f9fafb;border-radius:10px;padding:10px;margin-top:8px;">'
                            f'<div style="font-size:13px;font-weight:600;margin-bottom:4px;">当前租客</div>'
                            f'<div style="font-size:14px;">{tenancy["tenant_names"] or "—"}</div>'
                            f'<div style="font-size:12px;color:#6b7280;margin-top:4px;">'
                            f'{fmt_money(tenancy["monthly_rent"])}元/月 | 押金{fmt_money(tenancy["deposit"])}元</div>'
                            f'</div>', unsafe_allow_html=True)
        conn.close()


# ══════════════════════════════════════════════════════════
#  3. 租客
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "👤 租客":
    st.markdown("### 👤 租客管理")
    conn = get_conn()
    tenants = conn.execute("SELECT * FROM tenants ORDER BY id DESC").fetchall()

    with st.expander("➕ 新增租客", expanded=not tenants):
        with st.form("tenant_form"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("姓名*")
            with c2:
                phone = st.text_input("电话")
            id_no = st.text_input("身份证号")
            if st.form_submit_button("保存", use_container_width=True, type="primary"):
                if name:
                    conn.execute("INSERT INTO tenants (name, id_number, phone) VALUES (?,?,?)", (name, id_no, phone))
                    conn.commit()
                    st.success(f"已添加{name}")
                    st.rerun()

    for t in tenants:
        links = conn.execute("""
            SELECT r.room_number, t2.lease_type FROM tenant_links tl
            JOIN tenancies t2 ON t2.id=tl.tenancy_id
            JOIN rooms r ON r.id=t2.room_id
            WHERE tl.tenant_id=? AND t2.status='active'""", (t["id"],)).fetchall()
        rooms_str = ", ".join([f"{l['room_number']}({l['lease_type']})" for l in links]) or "无"
        st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;">'
                    f'<div><b>{t["name"]}</b><br><span style="font-size:12px;color:#9ca3af;">{t["phone"] or "—"}</span></div>'
                    f'<div style="text-align:right;font-size:12px;color:#6b7280;">{rooms_str}</div>'
                    f'</div></div>', unsafe_allow_html=True)
    conn.close()


# ══════════════════════════════════════════════════════════
#  4. 租约
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "📄 租约":
    st.markdown("### 📄 租约管理")
    conn = get_conn()

    tab1, tab2 = st.tabs(["📋 租约列表", "➕ 新建租约"])

    with tab2:
        rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()
        tenants = conn.execute("SELECT * FROM tenants ORDER BY name").fetchall()
        with st.form("lease_form"):
            room_opts = {f"{r['floor']}F {r['room_number']}": r["id"] for r in rooms}
            rid = st.selectbox("房间", list(room_opts.keys()))
            tenant_sel = st.multiselect("租客", [t["name"] for t in tenants])
            c1, c2 = st.columns(2)
            with c1:
                lt = st.selectbox("租赁类型", ["monthly", "yearly", "weekly"],
                                  format_func=lambda x: {"monthly":"月租","yearly":"年租","weekly":"周租"}[x])
            with c2:
                mrent = st.number_input("月租金(元)", min_value=0, step=100)
            c3, c4 = st.columns(2)
            with c3:
                dep = st.number_input("押金(元)", min_value=0, step=100)
            with c4:
                dep_paid = st.checkbox("押金已付")
            sd = st.date_input("开始日期", date.today())
            ed = st.date_input("结束日期(选填)", value=None)
            notes = st.text_area("备注")
            if st.form_submit_button("创建租约", use_container_width=True, type="primary"):
                if not tenant_sel:
                    st.error("请选择至少一个租客")
                else:
                    cur = conn.execute("INSERT INTO tenancies (room_id, lease_type, monthly_rent, deposit, deposit_paid, start_date, end_date, notes) VALUES (?,?,?,?,?,?,?,?)",
                                       (room_opts[rid], lt, mrent, dep, int(dep_paid), sd.isoformat(), ed.isoformat() if ed else None, notes))
                    tid = cur.lastrowid
                    for tn in tenant_sel:
                        t = conn.execute("SELECT id FROM tenants WHERE name=?", (tn,)).fetchone()
                        if t:
                            conn.execute("INSERT INTO tenant_links (tenancy_id, tenant_id) VALUES (?,?)", (tid, t["id"]))
                    conn.execute("UPDATE rooms SET status='occupied', monthly_rent=? WHERE id=?", (mrent, room_opts[rid]))
                    conn.commit()
                    st.success("租约已创建")
                    st.rerun()

    with tab1:
        status_filter = st.selectbox("状态", ["active", "expired", "terminated", "all"],
                                     format_func=lambda x: {"active":"生效中","expired":"已到期","terminated":"已终止","all":"全部"}[x])
        query = "SELECT t.*, r.room_number, GROUP_CONCAT(tn.name,', ') as tenant_names FROM tenancies t JOIN rooms r ON r.id=t.room_id LEFT JOIN tenant_links tl ON tl.tenancy_id=t.id LEFT JOIN tenants tn ON tn.id=tl.tenant_id"
        if status_filter != "all":
            query += f" WHERE t.status='{status_filter}'"
        query += " GROUP BY t.id ORDER BY t.start_date DESC"
        leases = conn.execute(query).fetchall()

        for l in leases:
            nd = f"到期: {l['end_date']}" if l["end_date"] else "未设到期"
            with st.container(border=True):
                st.markdown(f"**{l['room_number']}** {' | ' + l['tenant_names'] if l['tenant_names'] else ''}")
                c1, c2, c3 = st.columns(3)
                c1.caption(f"💰 {fmt_money(l['monthly_rent'])}/月")
                c2.caption(f"🏷️ {l['lease_type']}")
                c3.caption(f"📅 {nd}")
                if l["status"] == "active" and l["end_date"]:
                    days = (date.fromisoformat(l["end_date"]) - date.today()).days
                    if days <= 7:
                        st.warning(f"⚠️ 距到期还有 {days} 天")
                if l["status"] == "active":
                    if st.button(f"终止 #{l['id']}", key=f"term_{l['id']}", use_container_width=True):
                        conn.execute("UPDATE tenancies SET status='terminated', end_date=? WHERE id=?", (today(), l["id"]))
                        conn.execute("UPDATE rooms SET status='vacant' WHERE id=?", (l["room_id"],))
                        conn.commit()
                        st.rerun()
    conn.close()


# ══════════════════════════════════════════════════════════
#  5. 收租
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "💰 收租":
    st.markdown("### 💰 租金管理")
    conn = get_conn()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 一键生成本月账单", use_container_width=True):
            ms, me = month_range()
            active = conn.execute("SELECT * FROM tenancies WHERE status='active'").fetchall()
            created = 0
            for l in active:
                exists = conn.execute("SELECT id FROM payments WHERE tenancy_id=? AND period_start=?",
                                      (l["id"], ms.isoformat())).fetchone()
                if not exists:
                    conn.execute("INSERT INTO payments (tenancy_id, period_start, period_end, amount, status) VALUES (?,?,?,?,?)",
                                 (l["id"], ms.isoformat(), me.isoformat(), l["monthly_rent"], "pending"))
                    created += 1
            conn.commit()
            st.success(f"已生成 {created} 条账单")
            st.rerun()

    sf = st.selectbox("筛选", ["pending", "paid", "overdue", "all"],
                      format_func=lambda x: {"pending":"待收","paid":"已收","overdue":"逾期","all":"全部"}[x])
    query = """SELECT p.*, r.room_number, GROUP_CONCAT(tn.name,', ') as tenant_names
               FROM payments p JOIN tenancies t ON t.id=p.tenancy_id
               JOIN rooms r ON r.id=t.room_id
               LEFT JOIN tenant_links tl ON tl.tenancy_id=t.id
               LEFT JOIN tenants tn ON tn.id=tl.tenant_id"""
    if sf != "all":
        query += f" WHERE p.status='{sf}'"
    query += " GROUP BY p.id ORDER BY p.period_start DESC LIMIT 50"
    payments = conn.execute(query).fetchall()

    # 快速统计
    paid_sum = sum(p["amount"] for p in payments if p["status"] == "paid")
    pending_sum = sum(p["amount"] for p in payments if p["status"] == "pending")
    st.markdown(f'<div style="display:flex;gap:8px;margin-bottom:8px;">'
                f'<div class="card" style="flex:1;text-align:center;"><div style="color:#059669;font-size:20px;font-weight:700;">{fmt_money(paid_sum)}</div><div style="font-size:11px;color:#9ca3af;">已收</div></div>'
                f'<div class="card" style="flex:1;text-align:center;"><div style="color:#dc2626;font-size:20px;font-weight:700;">{fmt_money(pending_sum)}</div><div style="font-size:11px;color:#9ca3af;">待收</div></div>'
                f'</div>', unsafe_allow_html=True)

    for p in payments:
        with st.container(border=True):
            st.markdown(f"**{p['room_number']}** {p['tenant_names'] or ''}")
            st.caption(f"{p['period_start']} ~ {p['period_end']}  |  {fmt_money(p['amount'])}元")
            if p["status"] == "pending":
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"✅ 标记已收 #{p['id']}", key=f"pay_{p['id']}", use_container_width=True):
                        conn.execute("UPDATE payments SET status='paid', paid_date=? WHERE id=?", (today(), p["id"]))
                        conn.execute("INSERT INTO transactions (tx_type, category, amount, tx_date, description, room_id) VALUES (?,?,?,?,?,?)",
                                     ("income", "rent", p["amount"], today(),
                                      f"租金 {p['room_number']} ({p['period_start']}~{p['period_end']})",
                                      p["room_id"] if "room_id" in p.keys() else None))
                        conn.commit()
                        st.rerun()
                with c2:
                    st.markdown(f'<span class="badge badge-yellow">待收</span>', unsafe_allow_html=True)
            elif p["status"] == "paid":
                st.markdown(f'<span class="badge badge-green">已收 {p["paid_date"]}</span>', unsafe_allow_html=True)
    conn.close()


# ══════════════════════════════════════════════════════════
#  6. 水电
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "⚡ 水电":
    st.markdown("### ⚡ 水电费管理")
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()

    st.info("💡 电费 1元/度 | 水费 70元/人/月")
    with st.expander("➕ 抄表录入"):
        with st.form("utility_form"):
            room_opts = {f"{r['floor']}F {r['room_number']}": r["id"] for r in rooms}
            rid = st.selectbox("房间", list(room_opts.keys()))
            mth = st.text_input("月份(YYYY-MM)", value=date.today().strftime("%Y-%m"))
            c1, c2 = st.columns(2)
            with c1:
                elec_read = st.number_input("电表读数", step=0.1)
            with c2:
                elec_usage = st.number_input("用电量(度)", step=0.1)
            tc = st.number_input("本月租客人数", min_value=0, max_value=4, step=1)
            if st.form_submit_button("保存", use_container_width=True, type="primary"):
                ec = elec_usage * 1.0
                wc = tc * 70
                conn.execute("INSERT INTO utility_bills (room_id, month, electricity_reading, electricity_usage, electricity_cost, tenant_count, water_cost, total) VALUES (?,?,?,?,?,?,?,?)",
                             (room_opts[rid], mth, elec_read, elec_usage, ec, tc, wc, ec + wc))
                conn.commit()
                st.success("已保存")
                st.rerun()

    bills = conn.execute("""SELECT u.*, r.room_number FROM utility_bills u JOIN rooms r ON r.id=u.room_id
                            ORDER BY u.month DESC LIMIT 50""").fetchall()
    for b in bills:
        with st.container(border=True):
            st.markdown(f"**{b['room_number']}**  {b['month']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.caption(f"⚡{fmt_money(b['electricity_usage'])}度")
            c2.caption(f"💧{fmt_money(b['water_cost'])}元")
            c3.caption(f"💰合计{fmt_money(b['total'])}元")
            if b["paid"]:
                c4.markdown(f'<span class="badge badge-green">已缴</span>', unsafe_allow_html=True)
            else:
                if c4.button(f"标记已缴 #{b['id']}", key=f"util_{b['id']}", use_container_width=True):
                    conn.execute("UPDATE utility_bills SET paid=1, paid_date=? WHERE id=?", (today(), b["id"]))
                    conn.execute("INSERT INTO transactions (tx_type, category, amount, tx_date, description, room_id) VALUES (?,?,?,?,?,?)",
                                 ("income", "electricity", b["total"], today(), f"水电 {b['room_number']}({b['month']})", b["room_id"]))
                    conn.commit()
                    st.rerun()
    conn.close()


# ══════════════════════════════════════════════════════════
#  7. 维修
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "🔧 维修":
    st.markdown("### 🔧 维修报修")
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()

    with st.expander("➕ 报修"):
        with st.form("repair_form"):
            room_opts = {f"{r['floor']}F {r['room_number']}": r["id"] for r in rooms}
            rid = st.selectbox("房间", list(room_opts.keys()))
            desc = st.text_area("问题描述")
            est_cost = st.number_input("预计费用(元)", step=10)
            if st.form_submit_button("提交", use_container_width=True, type="primary"):
                conn.execute("INSERT INTO repairs (room_id, description, reported_date, cost) VALUES (?,?,?,?)",
                             (room_opts[rid], desc, today(), est_cost))
                conn.commit()
                st.success("已提交")
                st.rerun()

    sf = st.selectbox("状态", ["pending", "completed", "all"],
                      format_func=lambda x: {"pending":"待处理","completed":"已完成","all":"全部"}[x])
    query = "SELECT r.*, rm.room_number FROM repairs r JOIN rooms rm ON rm.id=r.room_id"
    if sf != "all":
        query += f" WHERE r.status='{sf}'"
    query += " ORDER BY r.reported_date DESC"
    repairs = conn.execute(query).fetchall()

    for r in repairs:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{r['room_number']}** | {r['description']}")
                st.caption(f"报修: {r['reported_date']} | 费用: {fmt_money(r['cost'])}元")
            with c2:
                if r["status"] == "pending":
                    if st.button(f"✅ 完成 #{r['id']}", key=f"rep_{r['id']}", use_container_width=True):
                        conn.execute("UPDATE repairs SET status='completed', completed_date=? WHERE id=?", (today(), r["id"]))
                        conn.commit()
                        st.rerun()
                    st.markdown(f'<span class="badge badge-yellow">待处理</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="badge badge-green">已完成</span>', unsafe_allow_html=True)
    conn.close()


# ══════════════════════════════════════════════════════════
#  8. 报表
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "📈 报表":
    st.markdown("### 📈 财务报表")
    conn = get_conn()

    year = st.selectbox("年份", range(date.today().year, 2023, -1), index=0)

    monthly = []
    for m in range(1, 13):
        ms = f"{year}-{m:02d}"
        inc = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tx_type='income' AND strftime('%Y-%m',tx_date)=?", (ms,)).fetchone()[0]
        exp = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tx_type='expense' AND strftime('%Y-%m',tx_date)=?", (ms,)).fetchone()[0]
        monthly.append({"month": f"{m}月", "income": inc, "expense": exp, "profit": inc - exp})

    m_names = [m["month"] for m in monthly]
    incomes = [m["income"] for m in monthly]
    expenses = [m["expense"] for m in monthly]

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Bar(name="收入", x=m_names, y=incomes, marker_color="#22c55e"))
    fig.add_trace(go.Bar(name="支出", x=m_names, y=expenses, marker_color="#ef4444"))
    fig.update_layout(barmode="group", height=250, margin=dict(l=10, r=10, t=20, b=10),
                      font=dict(size=11), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    yr = str(year)
    ti = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tx_type='income' AND strftime('%Y',tx_date)=?", (yr,)).fetchone()[0]
    te = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tx_type='expense' AND strftime('%Y',tx_date)=?", (yr,)).fetchone()[0]
    ri = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE tx_type='income' AND category='rent' AND strftime('%Y',tx_date)=?", (yr,)).fetchone()[0]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="color:#059669;font-size:20px;font-weight:700;">{fmt_money(ti)}</div><div style="font-size:11px;color:#9ca3af;">总收入</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="color:#dc2626;font-size:20px;font-weight:700;">{fmt_money(te)}</div><div style="font-size:11px;color:#9ca3af;">总支出</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="color:#1e40af;font-size:20px;font-weight:700;">{fmt_money(ti-te)}</div><div style="font-size:11px;color:#9ca3af;">净利润</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;font-size:14px;">'
                f'<span>租金收入</span><span style="font-weight:700;color:#059669;">{fmt_money(ri)}元</span></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:14px;margin-top:6px;">'
                f'<span>其他收入</span><span style="font-weight:700;color:#059669;">{fmt_money(ti-ri)}元</span></div>'
                f'</div>', unsafe_allow_html=True)

    # 月度明细
    st.markdown("#### 月度明细")
    for m in monthly:
        color = "text-green-600" if m["profit"] >= 0 else "text-red-600"
        st.markdown(f'<div class="card" style="display:flex;justify-content:space-between;font-size:13px;padding:10px;">'
                    f'<span style="font-weight:500;">{m["month"]}</span>'
                    f'<span><span style="color:#059669;">+{fmt_money(m["income"])}</span>'
                    f' <span style="color:#dc2626;">-{fmt_money(m["expense"])}</span>'
                    f' <span style="color:#1e40af;font-weight:600;">{fmt_money(m["profit"])}</span></span>'
                    f'</div>', unsafe_allow_html=True)
    conn.close()


# ── 页脚 ──
st.markdown('<div class="mb-safe"></div>', unsafe_allow_html=True)
st.caption("🏠 出租屋管理站 v1.0 | 数据本地存储")
