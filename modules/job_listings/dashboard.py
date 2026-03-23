"""
US Job Listings Monitor - ダッシュボード

UBS Evidence Lab の求人掲載データを使用して、
米国の雇用動向をリアルタイムでモニタリングするサブアプリ。

データソース: UBS Evidence Lab, LinkUp
約50,000社の企業キャリアサイトから直接取得した求人掲載データ
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

from core.api_client import UBSAPIClient
from core.ui_components import (
    apply_common_css, render_section_intro, render_summary_card,
    render_sidebar_header, render_export_section
)
from modules.job_listings.data import (
    fetch_time_series_data, fetch_regional_data, fetch_job_family_data,
    process_job_listings_data, build_sector_summary,
    SECTOR_JAPANESE, METRIC_JAPANESE
)


def show_dashboard():
    """Job Listings Monitor ダッシュボード メイン"""
    apply_common_css()

    st.title("US Job Listings Monitor")
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;'>
        <p style='color: white; font-size: 0.95rem; margin: 0; line-height: 1.5;'>
            <strong>UBS Evidence Lab</strong> - 米国求人掲載モニター
            <br><span style='font-size: 0.85rem; opacity: 0.95;'>
            約50,000社の企業キャリアサイトから求人掲載データを追跡 | 週次更新 | 2016年〜
            </span>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # メソドロジー
    with st.expander("メソドロジー"):
        st.markdown("""
        ### US Job Listings Monitor とは？

        UBS Evidence Labは、**企業のキャリアウェブサイトから直接**求人掲載データを収集し、
        米国の雇用動向を早期に把握するための指標を提供します。

        **データの特徴:**
        - **約50,000社**の米国企業の求人掲載をカバー
        - **新規掲載、削除、アクティブ求人総数**を追跡
        - セクター別、地域別、職種別のフィルタリングが可能
        - **週次更新**で、BLS JOLTS調査よりもタイムリー

        **活用方法:**
        - セクター別の雇用トレンド変化を早期検知
        - 地域別の労働市場の強弱を比較
        - 公式雇用統計（JOLTS、NFP）の先行指標として活用

        **セクター分類:** BLS JOLTS の分類に準拠

        **データソース:** UBS Evidence Lab, LinkUp

        **Data Asset Key**: 10224
        """)

    # セッション初期化
    if 'jl_ts_cached' not in st.session_state:
        st.session_state.jl_ts_cached = None
    if 'jl_ts_processed' not in st.session_state:
        st.session_state.jl_ts_processed = None
    if 'jl_regional_cached' not in st.session_state:
        st.session_state.jl_regional_cached = None
    if 'jl_jobfamily_cached' not in st.session_state:
        st.session_state.jl_jobfamily_cached = None

    # サイドバー
    render_sidebar_header("💼", "Job Listings Monitor")
    st.sidebar.markdown("---")
    st.sidebar.header("データ取得設定")
    st.sidebar.subheader("取得期間")

    date_method = st.sidebar.radio("期間指定方法", ("過去N日", "カレンダー指定"), horizontal=False, key="jl_dm")
    today = datetime.now().date()

    if date_method == "過去N日":
        days_back = st.sidebar.number_input("過去何日間", min_value=1, max_value=5000, value=365, step=1, key="jl_days")
        start_date_load = today - timedelta(days=days_back)
    else:
        start_date_load = st.sidebar.date_input("開始日", value=today - timedelta(days=365),
                                                min_value=date(2016, 1, 1), max_value=today, key="jl_start")

    st.sidebar.markdown("---")

    # データセット選択
    st.sidebar.subheader("データセット")
    fetch_ts = st.sidebar.checkbox("時系列データ (Time Series)", value=True, key="jl_fetch_ts")
    fetch_regional = st.sidebar.checkbox("地域別データ (Regional)", value=False, key="jl_fetch_reg")
    fetch_jf = st.sidebar.checkbox("職種別データ (Job Family)", value=False, key="jl_fetch_jf")

    st.sidebar.markdown("---")

    if st.sidebar.button("データを取得", type="primary", use_container_width=True, key="jl_fetch"):
        client = UBSAPIClient()
        start_str = start_date_load.strftime("%Y-%m-%d")
        end_str = today.strftime("%Y-%m-%d")

        try:
            with st.spinner("Job Listings データを取得中..."):
                if fetch_ts:
                    df_ts = fetch_time_series_data(client, start_str, end_str)
                    if not df_ts.empty:
                        st.session_state.jl_ts_cached = df_ts
                        st.session_state.jl_ts_processed = process_job_listings_data(df_ts)

                if fetch_regional:
                    df_reg = fetch_regional_data(client, start_str, end_str)
                    if not df_reg.empty:
                        st.session_state.jl_regional_cached = process_job_listings_data(df_reg)

                if fetch_jf:
                    df_jf = fetch_job_family_data(client, start_str, end_str)
                    if not df_jf.empty:
                        st.session_state.jl_jobfamily_cached = process_job_listings_data(df_jf)

                st.success("データ取得完了")
        except Exception as e:
            st.error(f"データ取得エラー: {str(e)}")

    # サイドバー統計
    if st.session_state.jl_ts_processed is not None:
        with st.sidebar.expander("データ統計", expanded=False):
            df = st.session_state.jl_ts_processed
            st.metric("レコード数", f"{len(df):,}")
            if 'periodEndDate' in df.columns:
                st.metric("開始日", df['periodEndDate'].min().strftime('%Y-%m-%d'))
                st.metric("終了日", df['periodEndDate'].max().strftime('%Y-%m-%d'))
            if 'sectorName' in df.columns:
                st.metric("セクター数", df['sectorName'].nunique())

    # メインエリア
    if st.session_state.jl_ts_processed is None:
        st.info("サイドバーで期間を選択して「データを取得」ボタンをクリックしてください")
        st.stop()

    df_ts = st.session_state.jl_ts_processed

    st.markdown("---")

    # タブナビゲーション
    if 'jl_tab' not in st.session_state:
        st.session_state.jl_tab = 0

    tab_cols = st.columns(4)
    tab_labels = [("セクター概要", 0), ("時系列分析", 1), ("地域・職種", 2), ("データ出力", 3)]
    for col, (label, idx) in zip(tab_cols, tab_labels):
        with col:
            if st.button(label, use_container_width=True,
                        type="primary" if st.session_state.jl_tab == idx else "secondary",
                        key=f"jl_tab_{idx}"):
                st.session_state.jl_tab = idx
                st.rerun()

    st.markdown("---")

    if st.session_state.jl_tab == 0:
        _render_sector_overview(df_ts)
    elif st.session_state.jl_tab == 1:
        _render_time_series_analysis(df_ts)
    elif st.session_state.jl_tab == 2:
        _render_regional_job_family()
    elif st.session_state.jl_tab == 3:
        _render_export(df_ts)


def _render_sector_overview(df):
    """セクター別概要タブ"""
    st.subheader("セクター別概要")

    render_section_intro("Sector Snapshot", "セクター別の求人掲載動向を概観し、雇用市場の強弱を把握")

    # 利用可能なカラムを確認して適応
    has_sector = 'sectorName' in df.columns
    has_metric_name = 'metricName' in df.columns
    has_metric_value = 'metricValue' in df.columns

    if not has_metric_value:
        st.warning("metricValue カラムが見つかりません。データ構造をご確認ください。")
        st.dataframe(df.head(20), use_container_width=True)
        return

    latest_date = df['periodEndDate'].max()
    latest_df = df[df['periodEndDate'] == latest_date].copy()

    # サマリーカード
    cols = st.columns(4)
    total_records = len(df)
    unique_dates = df['periodEndDate'].nunique()

    with cols[0]:
        render_summary_card("最新データ日", latest_date.strftime('%Y-%m-%d'), f"全{unique_dates}期間")
    with cols[1]:
        render_summary_card("総レコード数", f"{total_records:,}", "取得期間内")

    if has_sector:
        with cols[2]:
            render_summary_card("セクター数", f"{df['sectorName'].nunique()}", "")
    if has_metric_name:
        with cols[3]:
            render_summary_card("指標数", f"{df['metricName'].nunique()}", "")

    # セクター別最新値
    if has_sector and has_metric_name:
        st.markdown("### セクター別最新値")

        available_metrics = sorted(df['metricName'].unique())
        selected_metric = st.selectbox("表示する指標", available_metrics, key="jl_sector_metric",
                                       format_func=lambda x: METRIC_JAPANESE.get(x, x))

        sector_data = latest_df[latest_df['metricName'] == selected_metric].copy()

        if not sector_data.empty:
            # セクター別棒グラフ
            sector_data['sector_display'] = sector_data['sectorName'].map(
                lambda x: f"{SECTOR_JAPANESE.get(x, x)}"
            )
            sector_data = sector_data.sort_values('metricValue', ascending=True)

            fig = px.bar(sector_data, y='sector_display', x='metricValue', orientation='h',
                        title=f"セクター別 {METRIC_JAPANESE.get(selected_metric, selected_metric)} ({latest_date.strftime('%Y-%m-%d')})",
                        labels={'sector_display': 'セクター', 'metricValue': '値'},
                        color='metricValue', color_continuous_scale='Blues',
                        height=max(500, len(sector_data) * 28))
            fig.update_layout(template="plotly_white", margin=dict(l=200))
            st.plotly_chart(fig, use_container_width=True)

            # テーブル
            with st.expander("セクター別詳細テーブル"):
                display = sector_data[['sectorName', 'sector_display', 'metricValue']].copy()
                display.columns = ['セクター（英語）', 'セクター', '値']
                display = display.sort_values('値', ascending=False)
                st.dataframe(display, use_container_width=True, hide_index=True)
    elif has_metric_value:
        st.markdown("### 最新データプレビュー")
        st.dataframe(latest_df.head(50), use_container_width=True, hide_index=True)


def _render_time_series_analysis(df):
    """時系列分析タブ"""
    st.subheader("時系列分析")

    render_section_intro("Time Series Analysis", "求人掲載数の推移を時系列で分析")

    has_sector = 'sectorName' in df.columns
    has_metric_name = 'metricName' in df.columns

    if has_metric_name:
        available_metrics = sorted(df['metricName'].unique())
        selected_metric = st.selectbox("指標を選択", available_metrics, key="jl_ts_metric",
                                       format_func=lambda x: METRIC_JAPANESE.get(x, x))
        ts_df = df[df['metricName'] == selected_metric].copy()
    else:
        ts_df = df.copy()

    if has_sector:
        available_sectors = sorted(df['sectorName'].unique())
        default_sectors = [s for s in ['Total Private', 'Total Nonfarm', 'Manufacturing', 'Information',
                                       'Financial Activities', 'Health Care and Social Assistance']
                          if s in available_sectors][:5]

        selected_sectors = st.multiselect(
            "セクターを選択",
            available_sectors,
            default=default_sectors,
            key="jl_ts_sectors",
            format_func=lambda x: SECTOR_JAPANESE.get(x, x)
        )

        if selected_sectors:
            ts_df = ts_df[ts_df['sectorName'].isin(selected_sectors)]

    if ts_df.empty:
        st.warning("選択した条件に該当するデータがありません")
        return

    ts_df = ts_df.sort_values('periodEndDate')

    if has_sector and 'sectorName' in ts_df.columns:
        ts_df['display_name'] = ts_df['sectorName'].map(lambda x: SECTOR_JAPANESE.get(x, x))

        fig = px.line(ts_df, x='periodEndDate', y='metricValue', color='display_name',
                     title=f"{METRIC_JAPANESE.get(selected_metric, selected_metric) if has_metric_name else '値'} - 時系列推移",
                     labels={'periodEndDate': '日付', 'metricValue': '値', 'display_name': 'セクター'},
                     height=650)
    else:
        fig = px.line(ts_df, x='periodEndDate', y='metricValue',
                     title="時系列推移", labels={'periodEndDate': '日付', 'metricValue': '値'},
                     height=650)

    fig.update_layout(template="plotly_white", hovermode='x unified',
                     xaxis_tickformat="%Y/%m/%d", font=dict(size=12),
                     margin=dict(l=80, r=20, t=80, b=80))
    st.plotly_chart(fig, use_container_width=True)

    # 統計テーブル
    st.markdown("### 統計情報")
    if has_sector and 'sectorName' in ts_df.columns:
        stats_rows = []
        for sector in ts_df['sectorName'].unique():
            s_data = ts_df[ts_df['sectorName'] == sector]['metricValue'].dropna()
            if len(s_data) > 0:
                stats_rows.append({
                    'セクター': SECTOR_JAPANESE.get(sector, sector),
                    '最新値': f"{s_data.iloc[-1]:,.0f}",
                    '平均': f"{s_data.mean():,.0f}",
                    '最大': f"{s_data.max():,.0f}",
                    '最小': f"{s_data.min():,.0f}",
                    'データ件数': len(s_data)
                })
        if stats_rows:
            st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)
    else:
        vals = ts_df['metricValue'].dropna()
        if len(vals) > 0:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("最新値", f"{vals.iloc[-1]:,.0f}")
            with c2:
                st.metric("平均", f"{vals.mean():,.0f}")
            with c3:
                st.metric("最大", f"{vals.max():,.0f}")
            with c4:
                st.metric("データ件数", len(vals))


def _render_regional_job_family():
    """地域別・職種別タブ"""
    st.subheader("地域別・職種別分析")

    df_reg = st.session_state.jl_regional_cached
    df_jf = st.session_state.jl_jobfamily_cached

    if df_reg is None and df_jf is None:
        st.info("サイドバーで「地域別データ」または「職種別データ」にチェックを入れてデータを取得してください")
        return

    if df_reg is not None and not df_reg.empty:
        st.markdown("### 地域別データ")
        render_section_intro("Regional Analysis", "地域ごとの求人掲載動向を比較")

        latest_date = df_reg['periodEndDate'].max()
        latest_reg = df_reg[df_reg['periodEndDate'] == latest_date].copy()

        if 'regionName' in latest_reg.columns or 'stateName' in latest_reg.columns:
            geo_col = 'regionName' if 'regionName' in latest_reg.columns else 'stateName'

            if 'metricName' in latest_reg.columns:
                reg_metrics = sorted(latest_reg['metricName'].unique())
                sel_metric = st.selectbox("指標", reg_metrics, key="jl_reg_metric",
                                          format_func=lambda x: METRIC_JAPANESE.get(x, x))
                latest_reg = latest_reg[latest_reg['metricName'] == sel_metric]

            if 'metricValue' in latest_reg.columns and not latest_reg.empty:
                reg_sorted = latest_reg.sort_values('metricValue', ascending=True)
                fig = px.bar(reg_sorted, y=geo_col, x='metricValue', orientation='h',
                            title=f"地域別データ ({latest_date.strftime('%Y-%m-%d')})",
                            labels={geo_col: '地域', 'metricValue': '値'},
                            color='metricValue', color_continuous_scale='Viridis',
                            height=max(500, len(reg_sorted) * 22))
                fig.update_layout(template="plotly_white", margin=dict(l=200))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(latest_reg.head(50), use_container_width=True)

    if df_jf is not None and not df_jf.empty:
        st.markdown("### 職種別データ")
        render_section_intro("Job Family Analysis", "職種カテゴリ別の求人掲載動向")

        latest_date = df_jf['periodEndDate'].max()
        latest_jf = df_jf[df_jf['periodEndDate'] == latest_date].copy()

        jf_col = None
        for candidate in ['jobFamilyName', 'jobFamily', 'occupationName']:
            if candidate in latest_jf.columns:
                jf_col = candidate
                break

        if jf_col and 'metricValue' in latest_jf.columns:
            if 'metricName' in latest_jf.columns:
                jf_metrics = sorted(latest_jf['metricName'].unique())
                sel_jf_metric = st.selectbox("指標", jf_metrics, key="jl_jf_metric",
                                             format_func=lambda x: METRIC_JAPANESE.get(x, x))
                latest_jf = latest_jf[latest_jf['metricName'] == sel_jf_metric]

            if not latest_jf.empty:
                jf_sorted = latest_jf.sort_values('metricValue', ascending=True).tail(30)
                fig = px.bar(jf_sorted, y=jf_col, x='metricValue', orientation='h',
                            title=f"職種別データ Top 30 ({latest_date.strftime('%Y-%m-%d')})",
                            labels={jf_col: '職種', 'metricValue': '値'},
                            color='metricValue', color_continuous_scale='Plasma',
                            height=max(500, len(jf_sorted) * 22))
                fig.update_layout(template="plotly_white", margin=dict(l=200))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(latest_jf.head(50), use_container_width=True)


def _render_export(df):
    """データエクスポートタブ"""
    st.subheader("データエクスポート")

    st.markdown("""
    <div style='background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
        <h3 style='color: white; margin: 0;'>Job Listings データエクスポート</h3>
        <p style='color: #f0f0f0; margin: 5px 0 0 0;'>CSV/Excel/JSON形式でダウンロードできます</p>
    </div>
    """, unsafe_allow_html=True)

    # データソース選択
    sources = {"時系列データ": st.session_state.jl_ts_processed}
    if st.session_state.jl_regional_cached is not None:
        sources["地域別データ"] = st.session_state.jl_regional_cached
    if st.session_state.jl_jobfamily_cached is not None:
        sources["職種別データ"] = st.session_state.jl_jobfamily_cached

    selected_source = st.selectbox("データソース", list(sources.keys()), key="jl_export_src")
    export_df = sources[selected_source]

    if export_df is None or export_df.empty:
        st.warning("エクスポートするデータがありません")
        return

    sort_by = st.selectbox("ソート順", ["日付（新→旧）", "日付（旧→新）"], key="jl_sort")
    if sort_by == "日付（新→旧）":
        export_df = export_df.sort_values('periodEndDate', ascending=False)
    else:
        export_df = export_df.sort_values('periodEndDate', ascending=True)

    st.markdown(f"**データ件数: {len(export_df):,}**")

    with st.expander("データプレビュー（最初の100件）", expanded=True):
        st.dataframe(export_df.head(100), use_container_width=True, height=500)

    st.markdown("---")
    render_export_section(export_df, prefix=f"job_listings_{selected_source.replace(' ', '_').lower()}")

    # 統計
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("総データ件数", f"{len(export_df):,}")
    with c2:
        if 'periodEndDate' in export_df.columns:
            st.metric("期間", f"{export_df['periodEndDate'].min().strftime('%Y-%m-%d')} 〜 {export_df['periodEndDate'].max().strftime('%Y-%m-%d')}")
