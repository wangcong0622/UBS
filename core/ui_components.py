"""
共通UIコンポーネント
全サブアプリで使用するCSS、カード、セクションヘッダーなど
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime


def apply_common_css():
    """アプリ共通のCSSスタイルを適用"""
    st.markdown("""
    <style>
    .main {
        padding: 1rem 2rem;
        background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
    }

    h1 {
        color: #1e3a8a;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    h2 {
        color: #3b82f6;
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #e0e7ff;
    }

    h3 {
        color: #4f46e5;
        font-size: 1.3rem;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #1e3a8a;
        font-weight: 700;
        font-size: 2rem;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-weight: 600;
    }

    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
        background-color: #f1f5f9;
        padding: 16px;
        border-radius: 12px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 110px;
        background-color: white;
        border-radius: 10px;
        color: #475569;
        font-weight: 700;
        font-size: 28px;
        padding: 28px 50px;
        border: 2px solid transparent;
        transition: all 0.3s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e0e7ff;
        color: #4f46e5;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border-color: #6366f1;
        box-shadow: 0 4px 6px rgba(99, 102, 241, 0.2);
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        border: none;
        transition: all 0.3s ease;
    }

    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(16, 185, 129, 0.3);
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: #e0e7ff;
        color: #4f46e5;
        border-radius: 6px;
        font-weight: 600;
    }

    .summary-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        min-height: 132px;
    }

    .summary-label {
        color: #64748b;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }

    .summary-value {
        color: #0f172a;
        font-size: 1.8rem;
        font-weight: 800;
        margin-top: 0.35rem;
        margin-bottom: 0.35rem;
    }

    .summary-text {
        color: #475569;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)


def render_section_intro(title, subtitle):
    """グラデーション背景のセクションヘッダーを描画"""
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
                    padding: 1rem 1.2rem; border-radius: 14px; margin-bottom: 1rem; color: white;'>
            <div style='font-size: 1.15rem; font-weight: 700; margin-bottom: 0.35rem;'>{title}</div>
            <div style='font-size: 0.92rem; opacity: 0.92; line-height: 1.5;'>{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_summary_card(label, value, text=""):
    """サマリーカードを描画"""
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
            <div class="summary-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_stat_card(label, value, color="#2196F3", bg_color="#f0f7ff"):
    """統計カード（色付きボーダー）を描画"""
    st.markdown(f"""
    <div style='background: {bg_color}; padding: 15px; border-radius: 8px; border-left: 4px solid {color};'>
        <p style='margin: 0; color: #666; font-size: 0.9em;'>{label}</p>
        <h2 style='margin: 5px 0 0 0; color: {color};'>{value}</h2>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_header(icon, title):
    """サイドバーヘッダーを描画"""
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem; text-align: center;'>
        <span style='color: white; font-weight: 700; font-size: 1.1rem;'>
        {icon} {title}
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_export_section(df, prefix="data", display_cols=None, col_rename=None):
    """
    汎用データエクスポートセクション
    CSV/Excel/JSON ダウンロードボタンを表示
    """
    if df is None or df.empty:
        st.warning("エクスポートするデータがありません")
        return

    export_df = df[display_cols].copy() if display_cols else df.copy()

    st.markdown("### データダウンロード")
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    with col_dl1:
        csv_data = export_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="CSV ダウンロード",
            data=csv_data,
            file_name=f"{prefix}_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary",
            key=f"dl_csv_{prefix}"
        )

    with col_dl2:
        try:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                export_df.to_excel(writer, sheet_name='Data', index=False)
            buf.seek(0)
            st.download_button(
                label="Excel ダウンロード",
                data=buf.getvalue(),
                file_name=f"{prefix}_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="secondary",
                key=f"dl_xlsx_{prefix}"
            )
        except Exception:
            st.button("Excel ダウンロード", disabled=True, use_container_width=True,
                      help="openpyxlが必要です", key=f"dl_xlsx_disabled_{prefix}")

    with col_dl3:
        json_data = export_df.to_json(orient='records', indent=2, force_ascii=False, default_handler=str)
        st.download_button(
            label="JSON ダウンロード",
            data=json_data,
            file_name=f"{prefix}_{timestamp}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{prefix}"
        )
