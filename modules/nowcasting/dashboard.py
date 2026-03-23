"""
UBS Nowcasting Dashboard - ダッシュボード
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, date

from core.api_client import UBSAPIClient
from core.ui_components import (
    apply_common_css, render_sidebar_header, render_export_section
)
from modules.nowcasting.data import (
    fetch_nowcasting_data, process_nowcasting_data,
    get_latest_nowcast_timestamps, METRIC_JAPANESE_NAMES,
    is_percentage_metric, get_y_axis_title, get_y_axis_tickformat
)


def show_dashboard():
    """Nowcasting ダッシュボード メイン"""
    apply_common_css()
    st.title("UBS Nowcasting Dashboard")

    render_sidebar_header("📈", "Nowcasting Dashboard")

    try:
        client = UBSAPIClient()

        if 'nowcast_df_cached' not in st.session_state:
            st.session_state.nowcast_df_cached = None
        if 'nowcast_df_processed' not in st.session_state:
            st.session_state.nowcast_df_processed = None

        st.sidebar.markdown("---")
        st.sidebar.header("データ取得設定")
        st.sidebar.subheader("取得期間")

        date_method = st.sidebar.radio("期間指定方法", ("過去N日", "カレンダー指定"), horizontal=False, key="nc_dm")
        today = datetime.now().date()

        if date_method == "過去N日":
            days_back = st.sidebar.number_input("過去何日間", min_value=1, max_value=10000, value=365, step=1, key="nc_days")
            start_date_load = today - timedelta(days=days_back)
        else:
            start_date_load = st.sidebar.date_input("開始日", value=today - timedelta(days=180),
                                                    min_value=date(2020, 1, 1), max_value=today, key="nc_start")

        start_str = start_date_load.strftime("%Y-%m-%d")
        end_str = (today + timedelta(days=40)).strftime("%Y-%m-%d")

        st.sidebar.markdown("---")

        if st.sidebar.button("データを取得", type="primary", use_container_width=True, key="nc_fetch"):
            try:
                with st.spinner("Nowcasting データを取得中..."):
                    df = fetch_nowcasting_data(client, start_str, end_str)
                    if not df.empty:
                        st.session_state.nowcast_df_cached = df
                        st.session_state.nowcast_df_processed = process_nowcasting_data(df)
                        st.success("データ取得完了")
                    else:
                        st.warning("取得するデータがありません")
            except Exception as e:
                st.error(f"エラー: {str(e)}")

        st.sidebar.markdown("---")

        if st.session_state.nowcast_df_processed is not None and not st.session_state.nowcast_df_processed.empty:
            latest_table = get_latest_nowcast_timestamps(st.session_state.nowcast_df_processed)
            if not latest_table.empty:
                st.sidebar.markdown("### 最新Nowcasting更新時刻")
                st.sidebar.table(latest_table)
                st.sidebar.markdown("---")

        # メインエリア
        if st.session_state.nowcast_df_processed is None or st.session_state.nowcast_df_processed.empty:
            st.info("左のサイドバーからデータを取得してください")
            with st.expander("メソドロジー"):
                st.markdown("""
                ### Nowcasting とは？
                マクロ経済指標について、**非伝統的ビッグデータ**を活用し、
                政府の公式発表サイクルに先んじて暫定推計を提供します。

                **対象指標 (7種):** ISM Manufacturing, Auto SAAR, Retail Sales, Nonfarm Payrolls,
                Private Construction Spending, CPI, Core CPI

                **更新:** 毎月おおむね25日ごろに当月の暫定Nowcastを作成

                **データソース:** UBS独自データ基盤、政府データ、第三者業界データ
                """)
        else:
            df_processed = st.session_state.nowcast_df_processed

            st.markdown("---")
            if 'nc_tab' not in st.session_state:
                st.session_state.nc_tab = 0

            tab_cols = st.columns(4)
            tab_labels = [("チャート分析", 0), ("統計情報", 1), ("CPI寄与度", 2), ("データ出力", 3)]
            for col, (label, idx) in zip(tab_cols, tab_labels):
                with col:
                    if st.button(label, use_container_width=True,
                                type="primary" if st.session_state.nc_tab == idx else "secondary",
                                key=f"nc_tab_{idx}"):
                        st.session_state.nc_tab = idx
                        st.rerun()

            st.markdown("---")

            if st.session_state.nc_tab == 0:
                _render_chart_tab(df_processed)
            elif st.session_state.nc_tab == 1:
                _render_stats_tab(df_processed)
            elif st.session_state.nc_tab == 2:
                _render_cpi_tab(df_processed)
            elif st.session_state.nc_tab == 3:
                _render_export_tab(df_processed)

    except Exception as e:
        st.error(f"エラー: {str(e)}")


def _render_chart_tab(df_processed):
    st.subheader("Nowcasting vs 実績値")

    col1, col2 = st.columns(2)
    with col1:
        show_nowcast = st.checkbox("UBS Nowcasting（予測値）", value=True, key="nc_cb_now")
    with col2:
        show_actual = st.checkbox("Official Release（実績値）", value=True, key="nc_cb_act")

    st.markdown("---")

    available_metrics = sorted(df_processed['metricName'].unique())
    base_metrics = sorted(set(
        m.replace('ubs_nowcast_', '').replace('_mm', '').replace('_yy', '')
        for m in available_metrics if 'ubs_nowcast_' in m
    ))

    selected_base = st.selectbox("分析する指標を選択", base_metrics, key="nc_base_metric",
                                  format_func=lambda x: METRIC_JAPANESE_NAMES.get(f'ubs_nowcast_{x}', x))

    st.markdown("---")

    df_chart = df_processed[
        df_processed['metricName'].str.contains(selected_base, case=False, na=False)
    ].copy()

    if show_nowcast and not show_actual:
        df_chart = df_chart[df_chart['dataset_type'] == 'UBS Nowcasting']
    elif show_actual and not show_nowcast:
        df_chart = df_chart[df_chart['dataset_type'] == 'Official Release']

    if df_chart.empty:
        st.error("選択した指標のデータがありません")
        return

    metric_groups = {}
    for mn in sorted(df_chart['metricName'].unique()):
        vt = 'Month-over-Month' if '_mm' in mn else ('Year-over-Year' if '_yy' in mn or '_y' in mn else 'Base')
        metric_groups.setdefault(vt, []).append(mn)

    colors = {'UBS Nowcasting': '#1f77b4', 'Official Release': '#a0503f'}

    for var_type in sorted(metric_groups.keys()):
        metrics_in_group = metric_groups[var_type]
        group_data = df_chart[df_chart['metricName'].isin(metrics_in_group)].copy()

        if group_data['metricValue'].notna().sum() == 0:
            continue

        fig = go.Figure()
        group_metric = metrics_in_group[0] if metrics_in_group else selected_base

        for mn in sorted(metrics_in_group):
            md = group_data[group_data['metricName'] == mn].sort_values('periodEndDate')
            if md['metricValue'].notna().sum() == 0:
                continue

            ds_type = md['dataset_type'].iloc[0]
            display = md['metric_display_name'].iloc[0]
            is_pct = is_percentage_metric(mn)
            y_vals = md['metricValue'] * 100 if is_pct else md['metricValue']

            fig.add_trace(go.Scatter(
                x=md['periodEndDate'], y=y_vals, mode='lines', name=display,
                line=dict(width=2, color=colors.get(ds_type, '#1f77b4')),
                hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%b %Y}<br>Value: ' +
                              ('%{y:.2f}%' if is_pct else '%{y:.2f}') + '<extra></extra>'
            ))

        base_name = group_metric.replace('ubs_nowcast_', '').replace('first_official_report_', '')
        fig.update_layout(
            title=dict(text=METRIC_JAPANESE_NAMES.get(f'ubs_nowcast_{selected_base}', selected_base),
                      x=0.0, xanchor='left', font=dict(size=14, color='#1a1a1a')),
            hovermode='x unified',
            xaxis=dict(title="", tickformat="%y/%m/%d", showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)'),
            yaxis=dict(title=get_y_axis_title(base_name), tickformat=get_y_axis_tickformat(base_name),
                      showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.05)',
                      zeroline=True, zerolinecolor='rgba(0,0,0,0.2)'),
            font=dict(size=11), template="plotly_white",
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=70, r=60, t=60, b=60),
            legend=dict(x=0.0, y=0.98, bgcolor='rgba(255,255,255,0.8)',
                       bordercolor='rgba(0,0,0,0.2)', borderwidth=1),
            height=600, showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)

    # 統計
    st.markdown("---")
    st.subheader("統計情報")
    c1, c2, c3 = st.columns(3)
    valid = df_chart['metricValue'].dropna()
    if len(valid) > 0:
        with c1:
            st.metric("最新値", f"{valid.iloc[-1]:.4f}")
        with c2:
            st.metric("平均値", f"{valid.mean():.4f}")
        with c3:
            st.metric("データ件数", len(valid))


def _render_stats_tab(df_processed):
    st.subheader("統計情報")
    rows = []
    for mn in sorted(df_processed['metricName'].unique()):
        dm = df_processed[df_processed['metricName'] == mn]
        if dm.empty:
            continue
        vals = dm['metricValue'].dropna()
        if len(vals) == 0:
            continue
        rows.append({
            '指標': dm['metric_display_name'].iloc[0],
            'データセット': dm['dataset_type'].iloc[0],
            '最新値': vals.iloc[-1], '平均': vals.mean(),
            '最大': vals.max(), '最小': vals.min(),
            '標準偏差': vals.std(), 'データ件数': len(vals)
        })
    if rows:
        stats_df = pd.DataFrame(rows)
        st.dataframe(stats_df, use_container_width=True, height=500)
        csv = stats_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("統計情報をCSVで保存", data=csv,
                          file_name=f"nowcasting_stats_{datetime.now().strftime('%Y%m%d')}.csv",
                          mime="text/csv", key="nc_dl_stats")


def _render_cpi_tab(df_processed):
    st.subheader("CPI寄与度分解（時系列）")
    cpi_data = df_processed[df_processed['metricName'].str.contains('cpi', case=False, na=False)].copy()

    if cpi_data.empty:
        st.warning("CPIデータがありません")
        return

    c1, c2 = st.columns(2)
    with c1:
        show_nc = st.checkbox("UBS Nowcasting", value=True, key="cpi_nc")
    with c2:
        show_act = st.checkbox("Official Release", value=True, key="cpi_act")

    st.markdown("---")

    nowcast_components = [
        'ubs_nowcast_cpi_rent', 'ubs_nowcast_cpi_new_car', 'ubs_nowcast_cpi_used_car',
        'ubs_nowcast_cpi_lodging', 'ubs_nowcast_cpi_lodge', 'ubs_nowcast_cpi_airfare',
        'ubs_nowcast_cpi_energy'
    ]
    actual_components = [
        'first_official_report_cpi_rent', 'first_official_report_cpi_new_car',
        'first_official_report_cpi_used_car', 'first_official_report_cpi_lodge',
        'first_official_report_cpi_airfare', 'first_official_report_cpi_energy'
    ]
    colors_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']

    for label, ds_type, comp_list, overall_list, core_list in [
        ("UBS Nowcasting（予測値）", "UBS Nowcasting", nowcast_components,
         ['ubs_nowcast_cpi', 'ubs_nowcast_cpi_overall'], ['ubs_nowcast_cpi_core', 'ubs_nowcast_core_cpi']),
        ("Official Release（実績値）", "Official Release", actual_components,
         ['first_official_report_cpi'], ['first_official_report_cpi_core', 'first_official_report_core_cpi']),
    ]:
        show = show_nc if ds_type == "UBS Nowcasting" else show_act
        if not show:
            continue

        subset = cpi_data[cpi_data['dataset_type'] == ds_type].copy()
        if subset.empty:
            continue

        st.subheader(label)
        overall = subset[subset['metricName'].isin(overall_list)].copy()
        core = subset[subset['metricName'].isin(core_list)].copy()
        components = subset[subset['metricName'].isin(comp_list)].copy()

        if components.empty:
            continue

        pivot = components.pivot_table(index='periodEndDate', columns='metric_display_name',
                                       values='metricValue', aggfunc='first') * 100
        pivot = pivot.sort_index()

        fig = go.Figure()
        for idx, column in enumerate(pivot.columns):
            fig.add_trace(go.Bar(x=pivot.index, y=pivot[column], name=column,
                                marker=dict(color=colors_palette[idx % len(colors_palette)]),
                                hovertemplate='<b>%{fullData.name}</b><br>%{x|%y/%m/%d}<br>%{y:.2f}%<extra></extra>'))

        if not overall.empty:
            s = overall.sort_values('periodEndDate')
            fig.add_trace(go.Scatter(x=s['periodEndDate'], y=s['metricValue'] * 100, name='総合CPI',
                                    mode='lines', line=dict(color='#1a1a1a', width=3)))
        if not core.empty:
            s = core.sort_values('periodEndDate')
            fig.add_trace(go.Scatter(x=s['periodEndDate'], y=s['metricValue'] * 100, name='コアCPI',
                                    mode='lines', line=dict(color='#d62728', width=2.5, dash='dash')))

        fig.update_layout(
            title=f"CPI寄与度分解 - {label}", barmode='stack', height=600,
            template="plotly_white", hovermode='x unified',
            xaxis=dict(tickformat="%y/%m/%d"), yaxis_title="寄与度（%）",
            legend=dict(orientation='v', x=1.02, y=1),
            margin=dict(l=70, r=200, t=80, b=60)
        )
        st.plotly_chart(fig, use_container_width=True)

        # テーブル
        if not components.empty:
            table = components[['periodEndDate', 'metric_display_name', 'metricValue']].copy()
            table['metricValue'] = table['metricValue'] * 100
            latest = table['periodEndDate'].max()
            lt = table[table['periodEndDate'] == latest][['metric_display_name', 'metricValue']].sort_values('metricValue', ascending=False)
            lt.columns = ['要素', '寄与度（%）']
            lt['寄与度（%）'] = lt['寄与度（%）'].astype(float).apply(lambda x: f"{x:.3f}")
            st.dataframe(lt, use_container_width=True, hide_index=True)


def _render_export_tab(df_processed):
    st.subheader("データ一括出力")

    c1, c2 = st.columns(2)
    with c1:
        sort_by = st.selectbox("ソート順", ["日付（新→旧）", "日付（旧→新）", "指標名"], key="nc_sort")

    df_export = df_processed.copy()
    if sort_by == "日付（新→旧）":
        df_export = df_export.sort_values('periodEndDate', ascending=False)
    elif sort_by == "日付（旧→新）":
        df_export = df_export.sort_values('periodEndDate', ascending=True)
    else:
        df_export = df_export.sort_values('metric_display_name')

    st.markdown(f"**データ件数: {len(df_export):,} | 指標数: {df_export['metricName'].nunique()}種**")

    display_cols = ['periodEndDate', 'nowcastEffectiveDate', 'metric_display_name', 'dataset_type', 'metricValue']
    available_cols = [c for c in display_cols if c in df_export.columns]

    with st.expander("データプレビュー（最初の100件）", expanded=True):
        preview = df_export[available_cols].head(100).copy()
        preview.columns = ['期間終了日', 'リリース日', '指標', 'データセット', '値']
        st.dataframe(preview, use_container_width=True, height=500)

    st.markdown("---")
    render_export_section(df_export, prefix="nowcasting", display_cols=available_cols)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("総データ件数", f"{len(df_export):,}")
    with c2:
        st.metric("指標種別数", df_export['metricName'].nunique())
    with c3:
        st.metric("開始日", df_export['periodEndDate'].min().strftime("%Y-%m-%d"))
    with c4:
        st.metric("終了日", df_export['periodEndDate'].max().strftime("%Y-%m-%d"))
