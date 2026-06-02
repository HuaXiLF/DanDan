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

# ── CSS 定制（手机端优化） ──
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {margin-top: -60px; padding-top: 0;}
    .block-container {padding-top: 0.5rem; padding-bottom: 0.5rem; max-width: 100%;}

    /* 导航标签 */
    .nav-tabs {display: flex; overflow-x: auto; gap: 4px; padding: 4px 0; margin-bottom: 8px;
               -webkit-overflow-scrolling: touch; scrollbar-width: none;}
    .nav-tabs::-webkit-scrollbar {display: none;}
    .nav-tab {flex-shrink: 0; padding: 8px 14px; border-radius: 10px; font-size: 13px;
              font-weight: 500; white-space: nowrap; cursor: pointer; border: none;
              background: #f3f4f6; color: #6b7280; transition: all 0.15s;}
    .nav-tab.active {background: #1e40af; color: white;}
    .nav-tab:active {transform: scale(0.95);}

    /* 卡片 */
    .card {background: white; border-radius: 14px; padding: 14px; margin-bottom: 10px;
           box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
           border: 1px solid #f3f4f6;}
    .card-title {font-size: 13px; color: #6b7280; margin-bottom: 6px; font-weight: 500;}
    .card-value {font-size: 22px; font-weight: 700; color: #1e3a8a;}
    .stat-grid {display: grid; gap: 8px; margin-bottom: 12px;}

    /* 房间格子 */
    .room-grid {display: grid; gap: 6px;}
    .room-cell {padding: 8px 4px; border-radius: 8px; text-align: center; font-size: 12px; font-weight: 600;
                cursor: pointer; border: 1px solid #e5e7eb; text-decoration: none; display: block;}
    .room-cell.occupied {background: #ecfdf5; border-color: #a7f3d0; color: #065f46;}
    .room-cell.vacant {background: #f9fafb; border-color: #e5e7eb; color: #9ca3af;}

    /* 标记 */
    .badge {display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500;}
    .badge-green {background: #d1fae5; color: #065f46;}
    .badge-red {background: #fee2e2; color: #991b1b;}
    .badge-yellow {background: #fef3c7; color: #92400e;}
    .badge-blue {background: #dbeafe; color: #1e40af;}
    .badge-gray {background: #f3f4f6; color: #6b7280;}

    /* 表单按钮 */
    .stButton button {width: 100%; border-radius: 10px; padding: 8px 0; font-size: 14px; font-weight: 500;}
    .stTextInput input, .stSelectbox div, .stDateInput input, .stNumberInput input {
        border-radius: 10px !important; font-size: 14px !important;}
    div[data-testid="stForm"] {border: none !important; padding: 0 !important;}

    /* 弹窗覆盖 */
    .modal-overlay {position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1000;
                    display: flex; align-items: flex-end; justify-content: center;}
    .modal-content {background: white; border-radius: 20px 20px 0 0; width: 100%; max-width: 500px;
                    max-height: 85vh; overflow-y: auto; padding: 20px; animation: slideUp 0.25s ease;}
    @keyframes slideUp {from {transform: translateY(100%);} to {transform: translateY(0);}}

    /* 底部安全区 */
    .mb-safe {margin-bottom: 20px;}
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
PAGES = ["📊 首页", "🚪 房间", "👤 租客", "📄 租约", "💰 收租", "⚡ 水电", "🔧 维修", "📈 报表"]
if "page" not in st.session_state:
    st.session_state.page = "📊 首页"

# 顶部导航
nav_html = '<div class="nav-tabs">'
for p in PAGES:
    active = "active" if st.session_state.page == p else ""
    nav_html += f'<button class="nav-tab {active}" onclick="alert(\'nav_{p}\')">{p}</button>'
nav_html += "</div>"
st.markdown(nav_html, unsafe_allow_html=True)

# 导航回调
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    if st.button("📊 首页", use_container_width=True, type="secondary" if st.session_state.page != "📊 首页" else "primary"):
        st.session_state.page = "📊 首页"; st.rerun()
with col2:
    if st.button("🚪 房间", use_container_width=True, type="secondary" if st.session_state.page != "🚪 房间" else "primary"):
        st.session_state.page = "🚪 房间"; st.rerun()
with col3:
    if st.button("👤 租客", use_container_width=True, type="secondary" if st.session_state.page != "👤 租客" else "primary"):
        st.session_state.page = "👤 租客"; st.rerun()
with col4:
    if st.button("📄 租约", use_container_width=True, type="secondary" if st.session_state.page != "📄 租约" else "primary"):
        st.session_state.page = "📄 租约"; st.rerun()
with col5:
    if st.button("💰 收租", use_container_width=True, type="secondary" if st.session_state.page != "💰 收租" else "primary"):
        st.session_state.page = "💰 收租"; st.rerun()
col6, col7, col8 = st.columns(3)
with col6:
    if st.button("⚡ 水电", use_container_width=True, type="secondary" if st.session_state.page != "⚡ 水电" else "primary"):
        st.session_state.page = "⚡ 水电"; st.rerun()
with col7:
    if st.button("🔧 维修", use_container_width=True, type="secondary" if st.session_state.page != "🔧 维修" else "primary"):
        st.session_state.page = "🔧 维修"; st.rerun()
with col8:
    if st.button("📈 报表", use_container_width=True, type="secondary" if st.session_state.page != "📈 报表" else "primary"):
        st.session_state.page = "📈 报表"; st.rerun()

st.divider()


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
    pending_r = conn.execute("SELECT COUNT(*) FROM repairs WHERE status='pending'").fetchone()[0]
    expiring = conn.execute("""
        SELECT t.*, r.room_number FROM tenancies t JOIN rooms r ON t.room_id=r.id
        WHERE t.status='active' AND t.end_date IS NOT NULL
        AND t.end_date <= ? AND t.end_date >= ?
        ORDER BY t.end_date""",
        ((date.today() + timedelta(days=7)).isoformat(), today())).fetchall()

    st.markdown(f'<div style="background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;border-radius:16px;padding:20px;margin-bottom:16px;">'
                f'<div style="font-size:20px;font-weight:700;">🏠 出租屋管理站</div>'
                f'<div style="font-size:13px;opacity:0.8;margin-top:4px;">{date.today().strftime("%Y年%m月%d日")}</div>'
                f'</div>', unsafe_allow_html=True)

    # 统计
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="font-size:28px;font-weight:700;color:#1e40af;">{total}</div><div style="font-size:12px;color:#9ca3af;">总房间</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="font-size:28px;font-weight:700;color:#059669;">{occupied}</div><div style="font-size:12px;color:#9ca3af;">已出租</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card" style="text-align:center;"><div style="font-size:28px;font-weight:700;color:#d97706;">{vacant}</div><div style="font-size:12px;color:#9ca3af;">空房</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:13px;color:#6b7280;">本月租金</span>'
                f'<span><span style="color:#059669;font-weight:700;font-size:20px;">{fmt_money(paid_amt)}</span>'
                f'<span style="color:#d1d5db;margin:0 4px;">/</span>'
                f'<span style="font-weight:700;font-size:20px;">{fmt_money(paid_amt+pending)}</span>元</span>'
                f'</div></div>', unsafe_allow_html=True)

    # 到期提醒
    if expiring:
        st.markdown("### ⏰ 即将到期")
        for e in expiring:
            days = (date.fromisoformat(e["end_date"]) - date.today()).days
            st.markdown(f'<div class="card" style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span><b>{e["room_number"]}</b></span>'
                        f'<span class="badge badge-yellow">剩 {days} 天</span></div>', unsafe_allow_html=True)

    if pending_r:
        st.markdown(f'<div class="card" style="display:flex;justify-content:space-between;align-items:center;border-left:3px solid #ef4444;">'
                    f'<span>🔧 待处理维修</span><span class="badge badge-red">{pending_r} 项</span></div>', unsafe_allow_html=True)

    conn.close()


# ══════════════════════════════════════════════════════════
#  2. 房间
# ══════════════════════════════════════════════════════════

elif st.session_state.page == "🚪 房间":
    st.markdown("### 🚪 房间管理")
    conn = get_conn()
    rooms = conn.execute("SELECT * FROM rooms ORDER BY floor, room_number").fetchall()
    floors = {}
    for r in rooms:
        floors.setdefault(r["floor"], []).append(r)

    for fl in sorted(floors.keys()):
        st.markdown(f"<div style='font-size:14px;font-weight:600;color:#374151;margin:8px 0 4px;'>{fl}F</div>", unsafe_allow_html=True)
        cols = st.columns(5)
        for i, room in enumerate(floors[fl]):
            with cols[i % 5]:
                cls = "occupied" if room["status"] == "occupied" else "vacant"
                st.markdown(f'<div class="room-cell {cls}" onclick="alert(\'room_{room["id"]}\')">'
                            f'{room["room_number"]}<br><span style="font-size:10px;">{"●" if room["status"]=="occupied" else "○"}</span>'
                            f'</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 房间详情")
    room_ids = {f"{r['floor']}F {r['room_number']}": r["id"] for r in rooms}
    sel = st.selectbox("选择房间", list(room_ids.keys()), key="room_select")
    rid = room_ids[sel]
    room = conn.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()

    if room:
        st.markdown(f'<div class="card"><div style="display:flex;justify-content:space-between;">'
                    f'<span style="font-size:18px;font-weight:700;">{room["room_number"]}</span>'
                    f'<span class="badge {"badge-green" if room["status"]=="occupied" else "badge-gray"}">'
                    f'{"已租" if room["status"]=="occupied" else "空房"}</span></div>', unsafe_allow_html=True)

        rent = st.number_input("月租(元)", value=room["monthly_rent"], step=50, key="room_rent")
        if st.button("保存房租", key="save_rent", use_container_width=True):
            conn.execute("UPDATE rooms SET monthly_rent=? WHERE id=?", (rent, rid))
            conn.commit()
            st.success("已保存")
            st.rerun()

        # 当前租约
        tenancy = conn.execute("""
            SELECT t.*, GROUP_CONCAT(tn.name,', ') as tenant_names
            FROM tenancies t
            LEFT JOIN tenant_links tl ON tl.tenancy_id=t.id
            LEFT JOIN tenants tn ON tn.id=tl.tenant_id
            WHERE t.room_id=? AND t.status='active'
            GROUP BY t.id""", (rid,)).fetchone()
        if tenancy:
            st.markdown("**当前租客:** " + (tenancy["tenant_names"] or "—"))
            st.caption(f"月租{fmt_money(tenancy['monthly_rent'])}元 | 押金{fmt_money(tenancy['deposit'])}元 | {tenancy['lease_type']}")
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
