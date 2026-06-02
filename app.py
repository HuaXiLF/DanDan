"""
数据科分析面板 — 通用数据分析平台
支持：自定义数据集创建 → 数据录入 → 数据浏览 → 数据分析与可视化
"""

import sqlite3
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import streamlit as st

# ── 页面配置 ─────────────────────────────────────────────
st.set_page_config(
    page_title="数据科分析面板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 数据库路径 ───────────────────────────────────────────
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "app.db")


# ══════════════════════════════════════════════════════════
#  数据库工具函数
# ══════════════════════════════════════════════════════════

def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            col_name TEXT NOT NULL,
            col_type TEXT NOT NULL DEFAULT 'text',
            col_order INTEGER DEFAULT 0,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
            UNIQUE(dataset_id, col_name)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def get_datasets():
    """获取所有数据集"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT d.*, (SELECT COUNT(*) FROM records WHERE dataset_id = d.id) as record_count "
        "FROM datasets d ORDER BY d.created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def create_dataset(name, description="", columns=None):
    """创建数据集"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO datasets (name, description) VALUES (?, ?)", (name, description))
        ds_id = cursor.lastrowid
        if columns:
            for i, col in enumerate(columns):
                cursor.execute(
                    "INSERT INTO columns (dataset_id, col_name, col_type, col_order) VALUES (?, ?, ?, ?)",
                    (ds_id, col["name"], col["type"], i),
                )
        conn.commit()
        return ds_id, None
    except sqlite3.IntegrityError:
        return None, f"数据集名称「{name}」已存在"
    finally:
        conn.close()


def delete_dataset(ds_id):
    """删除数据集"""
    conn = get_conn()
    conn.execute("DELETE FROM datasets WHERE id = ?", (ds_id,))
    conn.commit()
    conn.close()


def get_columns(ds_id):
    """获取数据集的列定义"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM columns WHERE dataset_id = ? ORDER BY col_order", (ds_id,)
    ).fetchall()
    conn.close()
    return rows


def add_column(ds_id, col_name, col_type):
    """添加列"""
    conn = get_conn()
    try:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(col_order), -1) as m FROM columns WHERE dataset_id = ?", (ds_id,)
        ).fetchone()["m"]
        conn.execute(
            "INSERT INTO columns (dataset_id, col_name, col_type, col_order) VALUES (?, ?, ?, ?)",
            (ds_id, col_name, col_type, max_order + 1),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, f"列名「{col_name}」已存在"
    finally:
        conn.close()


def delete_column(col_id):
    """删除列"""
    conn = get_conn()
    conn.execute("DELETE FROM columns WHERE id = ?", (col_id,))
    conn.commit()
    conn.close()


def add_record(ds_id, data_dict):
    """添加记录"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO records (dataset_id, data) VALUES (?, ?)",
        (ds_id, json.dumps(data_dict, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def update_record(record_id, data_dict):
    """更新记录"""
    conn = get_conn()
    conn.execute(
        "UPDATE records SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(data_dict, ensure_ascii=False), record_id),
    )
    conn.commit()
    conn.close()


def delete_record(record_id):
    """删除记录"""
    conn = get_conn()
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_records(ds_id):
    """获取数据集的所有记录"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM records WHERE dataset_id = ? ORDER BY created_at DESC", (ds_id,)
    ).fetchall()
    conn.close()
    return rows


def records_to_dataframe(ds_id):
    """将记录转换为 pandas DataFrame"""
    columns = get_columns(ds_id)
    records = get_records(ds_id)
    if not records:
        return pd.DataFrame()
    col_names = [c["col_name"] for c in columns]
    col_types = {c["col_name"]: c["col_type"] for c in columns}
    data_rows = []
    for r in records:
        row_data = json.loads(r["data"])
        row_data["_id"] = r["id"]
        row_data["_created_at"] = r["created_at"]
        data_rows.append(row_data)
    df = pd.DataFrame(data_rows)
    # 类型转换
    for col in col_names:
        if col in df.columns and col_types.get(col) == "number":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── 初始化数据库 ────────────────────────────────────────
init_db()

# ── 侧边栏导航 ──────────────────────────────────────────
st.sidebar.title("📊 数据科分析面板")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "导航",
    ["📂 数据集管理", "📝 数据录入", "👁️ 数据浏览", "📈 数据分析", "⚙️ 数据集设置"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption(f"数据库路径: `{DB_PATH}`")


# ══════════════════════════════════════════════════════════
#  页面 1: 数据集管理
# ══════════════════════════════════════════════════════════

if page == "📂 数据集管理":
    st.title("📂 数据集管理")

    # 创建新数据集
    with st.expander("➕ 创建新数据集", expanded=True):
        col1, col2 = st.columns([2, 3])
        with col1:
            new_name = st.text_input("数据集名称", placeholder="例如：同程旅行财务数据")
        with col2:
            new_desc = st.text_input("描述（可选）", placeholder="数据集的简要说明")

        st.markdown("**定义字段列**")
        col_defs_container = st.container()

        if "new_cols" not in st.session_state:
            st.session_state.new_cols = [{"name": "", "type": "text"}]

        def add_col_input():
            st.session_state.new_cols.append({"name": "", "type": "text"})

        def remove_col_input():
            if len(st.session_state.new_cols) > 1:
                st.session_state.new_cols.pop()

        # 显示列定义输入
        for i, col_def in enumerate(st.session_state.new_cols):
            cols = st.columns([3, 2, 1])
            with cols[0]:
                st.session_state.new_cols[i]["name"] = st.text_input(
                    f"列名 #{i+1}", value=col_def["name"], key=f"new_col_name_{i}", label_visibility="collapsed",
                    placeholder="列名"
                )
            with cols[1]:
                st.session_state.new_cols[i]["type"] = st.selectbox(
                    f"类型 #{i+1}",
                    ["text", "number", "date"],
                    index=["text", "number", "date"].index(col_def["type"]),
                    key=f"new_col_type_{i}",
                    label_visibility="collapsed",
                )
            with cols[2]:
                if i > 0:
                    st.button("✕", key=f"remove_col_{i}", on_click=remove_col_input, use_container_width=True)

        st.button("➕ 添加列", on_click=add_col_input, use_container_width=True)

        if st.button("✅ 创建数据集", type="primary", use_container_width=True):
            if not new_name.strip():
                st.error("请输入数据集名称")
            else:
                valid_cols = [c for c in st.session_state.new_cols if c["name"].strip()]
                if not valid_cols:
                    st.error("请至少定义一个字段列")
                else:
                    ds_id, err = create_dataset(new_name.strip(), new_desc, valid_cols)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"数据集「{new_name}」创建成功！")
                        st.session_state.new_cols = [{"name": "", "type": "text"}]
                        st.rerun()

    # 已有数据集列表
    st.markdown("---")
    st.subheader("已有数据集")
    datasets = get_datasets()
    if not datasets:
        st.info("还没有数据集，请先创建一个。")
    else:
        for ds in datasets:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.markdown(f"**{ds['name']}**")
                    if ds["description"]:
                        st.caption(ds["description"])
                with cols[1]:
                    st.caption(f"📄 {ds['record_count']} 条记录")
                with cols[2]:
                    st.caption(f"🆔 #{ds['id']}")

                # 选择进入该数据集
                if st.button(f"进入「{ds['name']}」", key=f"enter_{ds['id']}", use_container_width=True):
                    st.session_state["active_dataset"] = ds["id"]
                    st.session_state["active_dataset_name"] = ds["name"]
                    st.rerun()

    # 快捷切换
    if "active_dataset" in st.session_state:
        st.sidebar.markdown("---")
        st.sidebar.success(f"当前数据集: **{st.session_state.get('active_dataset_name', '')}**")


# ══════════════════════════════════════════════════════════
#  页面 2: 数据录入
# ══════════════════════════════════════════════════════════

elif page == "📝 数据录入":
    st.title("📝 数据录入")

    # 选择数据集
    datasets = get_datasets()
    if not datasets:
        st.warning("暂无数据集，请先在「数据集管理」页面创建。")
        st.stop()

    ds_options = {ds["name"]: ds["id"] for ds in datasets}
    default_name = st.session_state.get("active_dataset_name", list(ds_options.keys())[0])
    default_idx = list(ds_options.keys()).index(default_name) if default_name in ds_options else 0

    selected_name = st.selectbox("选择数据集", list(ds_options.keys()), index=default_idx)
    ds_id = ds_options[selected_name]
    st.session_state["active_dataset"] = ds_id
    st.session_state["active_dataset_name"] = selected_name

    columns = get_columns(ds_id)
    if not columns:
        st.warning("该数据集尚未定义字段列，请在「数据集设置」中添加。")
        st.stop()

    # 录入表单
    st.markdown("---")
    st.subheader("录入新记录")

    input_data = {}
    col_meta = {}
    for col in columns:
        col_meta[col["col_name"]] = col["col_type"]

    with st.form("entry_form", clear_on_submit=True):
        form_cols = st.columns(2)
        for i, col in enumerate(columns):
            with form_cols[i % 2]:
                label = f"{col['col_name']} ({col['col_type']})"
                if col["col_type"] == "number":
                    input_data[col["col_name"]] = st.number_input(
                        label, value=None, step=0.01, format="%f", key=f"inp_{col['id']}"
                    )
                elif col["col_type"] == "date":
                    input_data[col["col_name"]] = st.date_input(label, key=f"inp_{col['id']}")
                else:
                    input_data[col["col_name"]] = st.text_input(label, key=f"inp_{col['id']}")

        submitted = st.form_submit_button("📥 提交记录", type="primary", use_container_width=True)

    if submitted:
        # 清理空值
        clean_data = {}
        for k, v in input_data.items():
            if v is not None and v != "":
                if col_meta.get(k) == "date" and hasattr(v, "isoformat"):
                    clean_data[k] = v.isoformat()
                else:
                    clean_data[k] = v
        if not clean_data:
            st.warning("请至少填写一个字段")
        else:
            add_record(ds_id, clean_data)
            st.success("记录已保存！")
            st.rerun()

    # 最近录入的记录快速预览
    st.markdown("---")
    st.subheader("最近录入")
    records = get_records(ds_id)
    if records:
        preview = records[:5]
        for r in preview:
            data = json.loads(r["data"])
            with st.container(border=True):
                st.caption(f"#{r['id']} — {r['created_at']}")
                for k, v in data.items():
                    st.write(f"**{k}**: {v}")
    else:
        st.info("暂无记录")


# ══════════════════════════════════════════════════════════
#  页面 3: 数据浏览
# ══════════════════════════════════════════════════════════

elif page == "👁️ 数据浏览":
    st.title("👁️ 数据浏览")

    datasets = get_datasets()
    if not datasets:
        st.warning("暂无数据集")
        st.stop()

    ds_options = {ds["name"]: ds["id"] for ds in datasets}
    default_name = st.session_state.get("active_dataset_name", list(ds_options.keys())[0])
    default_idx = list(ds_options.keys()).index(default_name) if default_name in ds_options else 0

    selected_name = st.selectbox("选择数据集", list(ds_options.keys()), index=default_idx,
                                 key="browse_dataset_select")
    ds_id = ds_options[selected_name]
    st.session_state["active_dataset"] = ds_id
    st.session_state["active_dataset_name"] = selected_name

    df = records_to_dataframe(ds_id)
    columns = get_columns(ds_id)
    col_names = [c["col_name"] for c in columns]

    if df.empty:
        st.info("该数据集暂无记录")
        st.stop()

    # 筛选器
    with st.expander("🔍 筛选条件", expanded=False):
        filters = {}
        for col in columns:
            if col["col_type"] == "number":
                vals = pd.to_numeric(df[col["col_name"]], errors="coerce").dropna()
                if not vals.empty:
                    min_v, max_v = float(vals.min()), float(vals.max())
                    if min_v < max_v:
                        f_range = st.slider(
                            f"{col['col_name']} 范围",
                            min_value=min_v, max_value=max_v,
                            value=(min_v, max_v), key=f"filter_{col['id']}"
                        )
                        filters[col["col_name"]] = f_range
            elif col["col_type"] == "text":
                uniq = df[col["col_name"]].dropna().unique().tolist()
                if uniq:
                    selected = st.multiselect(
                        f"{col['col_name']} 筛选",
                        options=sorted(uniq), key=f"filter_{col['id']}"
                    )
                    if selected:
                        filters[col["col_name"]] = selected

        # 应用筛选
        filtered_df = df.copy()
        for col_name, condition in filters.items():
            if isinstance(condition, tuple):
                filtered_df = filtered_df[
                    pd.to_numeric(filtered_df[col_name], errors="coerce").between(condition[0], condition[1])
                ]
            elif isinstance(condition, list):
                filtered_df = filtered_df[filtered_df[col_name].isin(condition)]

    # 显示表格
    display_cols = col_names + ["_created_at"]
    available_cols = [c for c in display_cols if c in filtered_df.columns]

    st.caption(f"共 {len(filtered_df)} 条记录（筛选后）")
    st.dataframe(
        filtered_df[available_cols].rename(columns={"_created_at": "创建时间"}),
        use_container_width=True,
        height=400,
        hide_index=True,
    )

    # 导出
    with st.expander("📥 导出数据"):
        export_format = st.radio("导出格式", ["CSV", "Excel"], horizontal=True)
        if st.button("导出"):
            export_df = filtered_df[available_cols].rename(columns={"_created_at": "创建时间"})
            if export_format == "CSV":
                csv_data = export_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇ 下载 CSV",
                    csv_data,
                    file_name=f"{selected_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
            else:
                output_path = os.path.join(DB_DIR, f"{selected_name}_export.xlsx")
                export_df.to_excel(output_path, index=False)
                with open(output_path, "rb") as f:
                    st.download_button(
                        "⬇ 下载 Excel",
                        f,
                        file_name=f"{selected_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # 批量删除
    with st.expander("🗑️ 删除记录"):
        st.warning("此操作不可撤销！")
        record_ids = filtered_df["_id"].tolist()
        if record_ids:
            ids_to_delete = st.multiselect(
                "选择要删除的记录 (ID)",
                options=record_ids,
                format_func=lambda x: f"记录 #{x}",
            )
            if ids_to_delete and st.button("删除选中记录", type="primary"):
                for rid in ids_to_delete:
                    delete_record(int(rid))
                st.success(f"已删除 {len(ids_to_delete)} 条记录")
                st.rerun()


# ══════════════════════════════════════════════════════════
#  页面 4: 数据分析
# ══════════════════════════════════════════════════════════

elif page == "📈 数据分析":
    st.title("📈 数据分析与可视化")

    datasets = get_datasets()
    if not datasets:
        st.warning("暂无数据集")
        st.stop()

    ds_options = {ds["name"]: ds["id"] for ds in datasets}
    default_name = st.session_state.get("active_dataset_name", list(ds_options.keys())[0])
    default_idx = list(ds_options.keys()).index(default_name) if default_name in ds_options else 0

    selected_name = st.selectbox("选择数据集", list(ds_options.keys()), index=default_idx,
                                 key="analysis_dataset_select")
    ds_id = ds_options[selected_name]
    st.session_state["active_dataset"] = ds_id
    st.session_state["active_dataset_name"] = selected_name

    df = records_to_dataframe(ds_id)
    columns = get_columns(ds_id)
    num_cols = [c["col_name"] for c in columns if c["col_type"] == "number"]
    text_cols = [c["col_name"] for c in columns if c["col_type"] == "text"]
    date_cols = [c["col_name"] for c in columns if c["col_type"] == "date"]

    if df.empty:
        st.info("该数据集暂无数据，请先录入一些记录")
        st.stop()

    # ── 统计摘要 ──
    tab_summary, tab_chart, tab_corr = st.tabs(["📋 统计摘要", "📊 图表分析", "🔗 相关性分析"])

    with tab_summary:
        st.subheader("描述性统计")
        if num_cols:
            numeric_df = df[num_cols].select_dtypes(include="number")
            if not numeric_df.empty:
                stats = numeric_df.describe().T
                stats["count"] = stats["count"].astype(int)
                stats["缺失值"] = len(numeric_df) - stats["count"]
                st.dataframe(stats, use_container_width=True)
            else:
                st.info("暂无数值型列可统计")
        else:
            st.info("该数据集未定义数值型字段")

        # 数据概览
        st.subheader("数据概览")
        overview = pd.DataFrame({
            "指标": ["总记录数", "数值列数", "文本列数", "日期列数"],
            "值": [len(df), len(num_cols), len(text_cols), len(date_cols)],
        })
        st.dataframe(overview, use_container_width=True, hide_index=True)

    with tab_chart:
        st.subheader("图表生成")

        if not num_cols:
            st.warning("需要至少一个数值型字段才能生成图表。请在「数据集设置」中添加数值型字段。")
        else:
            chart_type = st.selectbox("图表类型", ["折线图", "柱状图", "散点图", "箱线图", "直方图"])

            x_col = st.selectbox("X 轴", [""] + list(df.columns), index=0)
            y_col = st.selectbox("Y 轴（数值）", [""] + num_cols, index=0)
            color_col = st.selectbox("颜色分组（可选）", ["无"] + text_cols, index=0)

            if x_col and y_col and x_col != y_col:
                try:
                    if chart_type == "折线图":
                        fig = px.line(df, x=x_col, y=y_col, color=None if color_col == "无" else color_col,
                                      title=f"{y_col} 按 {x_col} 变化")
                    elif chart_type == "柱状图":
                        fig = px.bar(df, x=x_col, y=y_col, color=None if color_col == "无" else color_col,
                                     title=f"{y_col} 按 {x_col} 分布", barmode="group")
                    elif chart_type == "散点图":
                        fig = px.scatter(df, x=x_col, y=y_col, color=None if color_col == "无" else color_col,
                                         title=f"{y_col} vs {x_col}", trendline="ols")
                    elif chart_type == "箱线图":
                        fig = px.box(df, x=x_col if color_col == "无" else None,
                                     y=y_col, color=None if color_col == "无" else color_col,
                                     title=f"{y_col} 箱线图")
                    else:  # 直方图
                        fig = px.histogram(df, x=y_col, color=None if color_col == "无" else color_col,
                                           title=f"{y_col} 分布", nbins=20)

                    fig.update_layout(height=500, margin=dict(l=40, r=40, t=40, b=40))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"生成图表时出错: {e}")
            else:
                st.info("请选择 X 轴和 Y 轴（数值）来生成图表")

        # 饼图（基于文本列）
        if text_cols:
            st.markdown("---")
            st.subheader("类别分布（饼图）")
            pie_col = st.selectbox("选择分类字段", text_cols, key="pie_col")
            if pie_col:
                value_counts = df[pie_col].value_counts()
                fig = px.pie(
                    values=value_counts.values,
                    names=value_counts.index,
                    title=f"{pie_col} 分布",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    with tab_corr:
        st.subheader("相关性分析")
        if len(num_cols) >= 2:
            numeric_df = df[num_cols].select_dtypes(include="number")
            if numeric_df.shape[1] >= 2 and numeric_df.shape[0] >= 3:
                corr = numeric_df.corr()
                fig = px.imshow(
                    corr,
                    text_auto=".3f",
                    color_continuous_scale="RdBu_r",
                    title="相关系数矩阵",
                    aspect="auto",
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("详细相关系数")
                # 展开上三角矩阵
                pairs = []
                for i in range(len(corr.columns)):
                    for j in range(i + 1, len(corr.columns)):
                        pairs.append({
                            "变量1": corr.columns[i],
                            "变量2": corr.columns[j],
                            "相关系数": f"{corr.iloc[i, j]:.4f}",
                            "相关强度": (
                                "强" if abs(corr.iloc[i, j]) > 0.7
                                else "中" if abs(corr.iloc[i, j]) > 0.4
                                else "弱"
                            ),
                        })
                st.dataframe(pd.DataFrame(pairs), use_container_width=True, hide_index=True)
            else:
                st.info("需要至少 2 个数值列和 3 条记录才能计算相关性")
        else:
            st.info("需要至少 2 个数值型字段")


# ══════════════════════════════════════════════════════════
#  页面 5: 数据集设置
# ══════════════════════════════════════════════════════════

elif page == "⚙️ 数据集设置":
    st.title("⚙️ 数据集设置")

    datasets = get_datasets()
    if not datasets:
        st.warning("暂无数据集")
        st.stop()

    ds_options = {ds["name"]: f"{ds['id']}" for ds in datasets}
    default_name = st.session_state.get("active_dataset_name", list(ds_options.keys())[0])
    default_idx = list(ds_options.keys()).index(default_name) if default_name in ds_options else 0

    selected_name = st.selectbox("选择数据集", list(ds_options.keys()), index=default_idx,
                                 key="settings_dataset_select")
    ds_id = ds_options[selected_name]

    columns = get_columns(ds_id)
    records = get_records(ds_id)

    # 数据集信息
    with st.container(border=True):
        st.markdown(f"**数据集**: {selected_name}  |  字段数: {len(columns)}  |  记录数: {len(records)}")

    # 管理字段列
    st.subheader("字段列管理")
    for col in columns:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.write(f"**{col['col_name']}**")
            with c2:
                st.caption(f"类型: {col['col_type']}")
            with c3:
                if st.button("删除", key=f"del_col_{col['id']}"):
                    delete_column(col["id"])
                    st.rerun()

    # 添加新列
    with st.expander("➕ 添加新字段"):
        new_col_name = st.text_input("字段名", key="new_setting_col_name")
        new_col_type = st.selectbox("字段类型", ["text", "number", "date"], key="new_setting_col_type")
        if st.button("添加字段", use_container_width=True):
            if new_col_name.strip():
                success, err = add_column(ds_id, new_col_name.strip(), new_col_type)
                if success:
                    st.success(f"字段「{new_col_name}」已添加")
                    st.rerun()
                else:
                    st.error(err)
            else:
                st.error("请输入字段名")

    # 删除数据集
    st.markdown("---")
    with st.expander("⚠️ 危险操作"):
        st.warning("删除数据集将同时删除所有数据和字段定义，此操作不可撤销！")
        confirm = st.text_input("请输入数据集名称确认删除", placeholder=selected_name)
        if confirm == selected_name:
            if st.button("🗑️ 确认删除数据集", type="primary", use_container_width=True):
                delete_dataset(ds_id)
                st.success("数据集已删除")
                if "active_dataset" in st.session_state:
                    del st.session_state["active_dataset"]
                    del st.session_state["active_dataset_name"]
                st.rerun()
        elif confirm:
            st.error("名称不匹配，请输入完整的数据集名称")


# ── 页脚 ────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.caption("数据科分析面板 v1.0 | 基于 Streamlit")
