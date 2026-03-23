"""
Central Bank Policy Sentiment Tracker - ダッシュボード
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, date

from config.settings import ENTITY_TO_COUNTRY, COUNTRY_PALETTE
from core.api_client import UBSAPIClient
from core.ui_components import (
    apply_common_css, render_section_intro, render_summary_card,
    render_sidebar_header, render_export_section
)
from modules.sentiment.data import (
    fetch_sentiment_data, process_sentiment_data,
    build_overview_summary, build_topic_summary
)


def show_dashboard():
    """センチメント ダッシュボード メイン"""
    apply_common_css()

    st.title("Central Banks Policy Sentiment Tracker")
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem;'>
        <p style='color: white; font-size: 0.95rem; margin: 0; line-height: 1.5;'>
            <strong>UBS Evidence Lab API</strong> - 中央銀行政策スタンス分析
            <br><span style='font-size: 0.85rem; opacity: 0.95;'>
            負のスコア=ハト派的 | 正のスコア=タカ派的
            </span>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # メソドロジー
    with st.expander("メソドロジー"):
        st.markdown("""
        ### 概要
        本研究は **UBS AI LLMs** を活用して中央銀行スピーカーの演説やプレスカンファレンスの言語を分析し、
        金融政策に対するスタンスを追跡します。

        **センチメント分類 (5段階):**
        - 明確にタカ派的 (+1.0) / タカ派的 (+0.5) / 混合 (0.0) / ハト派的 (-0.5) / 明確にハト派的 (-1.0)

        **スコア計算:** 加重センチメントスコアの合計 / 金融政策関連トピックを含む文の総数

        **平滑化:** EWMA (15/30/40演説窓) で指数平滑化。演説間は前の値で埋め。

        **対象トピック:** インフレ/価格、雇用、GDP/成長、金融政策/金利、バランスシート、通貨/為替(BOJのみ)

        **データソース:** FED (連邦準備制度理事会), ECB (執行役員会のみ), BOJ (演説のみ)

        **Study ID**: 7276 | **Asset Key**: 10487
        """)

    # セッション初期化
    if 'sentiment_df_cached' not in st.session_state:
        st.session_state.sentiment_df_cached = None
    if 'sentiment_df_processed' not in st.session_state:
        st.session_state.sentiment_df_processed = None

    # サイドバー
    render_sidebar_header("🏦", "Sentiment Tracker")

    st.sidebar.markdown("---")
    st.sidebar.header("データ取得設定")
    st.sidebar.subheader("取得期間")

    date_method = st.sidebar.radio("期間指定方法", ("過去N日", "カレンダー指定"), horizontal=False, key="sent_date_method")
    today = datetime.now().date()

    if date_method == "過去N日":
        days_back = st.sidebar.number_input("過去何日間", min_value=1, max_value=10000, value=365, step=1, key="sent_days")
        start_date_load = today - timedelta(days=days_back)
    else:
        start_date_load = st.sidebar.date_input("開始日", value=date(1998, 1, 1), min_value=date(1998, 1, 1), max_value=today, key="sent_start")

    st.sidebar.markdown("---")

    if st.sidebar.button("データを取得", key="sent_fetch", use_container_width=True):
        with st.spinner("UBS APIからデータを取得中..."):
            try:
                client = UBSAPIClient()
                start_str = start_date_load.strftime("%Y-%m-%d")
                end_str = today.strftime("%Y-%m-%d")
                df = fetch_sentiment_data(client, start_str, end_str)

                if df.empty:
                    st.error("データの取得に失敗しました")
                    st.stop()

                st.session_state.sentiment_df_cached = df
                df_processed = process_sentiment_data(df)

                if df_processed is None or df_processed.empty:
                    st.error("処理後のデータが空です")
                    st.stop()

                st.session_state.sentiment_df_processed = df_processed
                st.sidebar.success("データ取得完了")

                with st.sidebar.expander("データ統計", expanded=False):
                    st.metric("総レコード数", f"{len(df):,}")
                    st.metric("処理済レコード数", f"{len(df_processed):,}")
            except Exception as e:
                st.sidebar.error(f"データ取得エラー: {str(e)}")
                st.stop()

    st.sidebar.info("30日分のデータ取得にはおよそ10秒かかります。")

    if st.session_state.sentiment_df_cached is None:
        st.info("サイドバーで期間を選択して「データを取得」ボタンをクリックしてください")
        st.stop()

    df_processed = st.session_state.sentiment_df_processed
    raw_df = st.session_state.sentiment_df_cached.copy()
    raw_df['periodEndDate'] = pd.to_datetime(raw_df['periodEndDate'])
    raw_df['country_name'] = raw_df['entityName'].map(ENTITY_TO_COUNTRY)

    executive_df = raw_df[
        (raw_df['documentType'] == 'all documents') &
        (raw_df['setName'] == 'all speakers') &
        (raw_df['metric'] == 'all topics') &
        (raw_df['metricType'] == 'sentiment score smoothed')
    ].copy()

    st.markdown("---")

    # Manager Snapshot
    if not executive_df.empty:
        summary_df = build_overview_summary(executive_df)
        latest_date = executive_df['periodEndDate'].max().strftime("%Y-%m-%d")
        render_section_intro("Manager Snapshot", f"最新更新日 {latest_date} 時点の政策スタンスサマリー")

        top_bank = summary_df.iloc[0] if not summary_df.empty else None
        bottom_bank = summary_df.iloc[-1] if not summary_df.empty else None
        move_bank = summary_df.reindex(summary_df['前回比'].abs().sort_values(ascending=False).index).iloc[0] if not summary_df.empty else None

        cols = st.columns(4)
        cards = [
            ("対象中央銀行", f"{executive_df['country_name'].nunique()}", f"最新日付: {latest_date}"),
            ("最もタカ派", f"{top_bank['中央銀行'] if top_bank is not None else '-'}", f"スコア {top_bank['最新スコア']:.3f}" if top_bank is not None else ""),
            ("最もハト派", f"{bottom_bank['中央銀行'] if bottom_bank is not None else '-'}", f"スコア {bottom_bank['最新スコア']:.3f}" if bottom_bank is not None else ""),
            ("最大変化", f"{move_bank['中央銀行'] if move_bank is not None else '-'}", f"前回比 {move_bank['前回比']:+.3f}" if move_bank is not None and pd.notna(move_bank['前回比']) else "前回値なし")
        ]
        for col, (label, value, text) in zip(cols, cards):
            with col:
                render_summary_card(label, value, text)

    # タブ選択
    if 'sent_tab' not in st.session_state:
        st.session_state.sent_tab = 0

    col_tabs = st.columns(4)
    tab_labels = [("Overview", 0), ("Topic Analysis", 1), ("Speaker Analysis", 2), ("Data Export", 3)]
    for col, (label, idx) in zip(col_tabs, tab_labels):
        with col:
            if st.button(label, use_container_width=True, key=f"sent_tab_{idx}"):
                st.session_state.sent_tab = idx

    st.markdown("---")

    # ==================== Tab 0: Overview ====================
    if st.session_state.sent_tab == 0:
        _render_overview_tab(raw_df)

    # ==================== Tab 1: Topic Analysis ====================
    elif st.session_state.sent_tab == 1:
        _render_topic_tab(raw_df)

    # ==================== Tab 2: Speaker Analysis ====================
    elif st.session_state.sent_tab == 2:
        _render_speaker_tab(raw_df)

    # ==================== Tab 3: Data Export ====================
    elif st.session_state.sent_tab == 3:
        _render_export_tab()


def _render_overview_tab(raw_df):
    st.subheader("Overview - センチメント概要")

    st.markdown("""
    <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
        <p style='margin: 0; font-size: 14px;'>
            <strong>スコアの解釈:</strong><br>
            <strong style='color: #d62728;'>正のスコア (タカ派的)</strong> = 金融引き締め的<br>
            <strong style='color: #1f77b4;'>負のスコア (ハト派的)</strong> = 金融緩和的
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    raw_df['periodEndDate'] = pd.to_datetime(raw_df['periodEndDate'])
    raw_df['country_name'] = raw_df['entityName'].map(ENTITY_TO_COUNTRY)
    min_date = raw_df['periodEndDate'].min().date()
    max_date = raw_df['periodEndDate'].max().date()
    default_start = max(min_date, max_date - timedelta(days=365))

    with col1:
        start_date = st.date_input("開始日", value=default_start, min_value=min_date, max_value=max_date, key="ov_start")
    with col2:
        available_countries = sorted(raw_df['country_name'].unique())
        selected_countries = st.multiselect("中央銀行", available_countries, default=available_countries, key="ov_countries")
    with col3:
        mode = st.selectbox("データ種別", ["Smoothed", "Unsmoothed", "両方"], key="ov_mode")

    end_date = st.date_input("終了日", value=max_date, min_value=min_date, max_value=max_date, key="ov_end")

    sentiment_df = raw_df[
        (raw_df['documentType'] == 'all documents') &
        (raw_df['setName'] == 'all speakers') &
        (raw_df['metric'] == 'all topics')
    ].copy()

    if selected_countries:
        sentiment_df = sentiment_df[sentiment_df['country_name'].isin(selected_countries)]

    sentiment_df = sentiment_df[
        (sentiment_df['periodEndDate'] >= pd.to_datetime(start_date)) &
        (sentiment_df['periodEndDate'] <= pd.to_datetime(end_date))
    ]

    if mode == "Smoothed":
        sentiment_df = sentiment_df[sentiment_df['metricType'] == 'sentiment score smoothed']
    elif mode == "Unsmoothed":
        sentiment_df = sentiment_df[sentiment_df['metricType'] == 'sentiment score unsmoothed']

    if not sentiment_df.empty:
        overview_summary = build_overview_summary(sentiment_df)
        render_section_intro("Overview", "各中央銀行の最新スコアと直近変化を確認")

        if not overview_summary.empty:
            latest_cols = st.columns(min(3, len(overview_summary)))
            for idx, (_, row) in enumerate(overview_summary.head(3).iterrows()):
                with latest_cols[idx]:
                    delta_text = f"前回比 {row['前回比']:+.3f}" if pd.notna(row['前回比']) else "前回値なし"
                    render_summary_card(row['中央銀行'], f"{row['最新スコア']:.3f}",
                                       f"{delta_text}<br>{row['判定']} / 20期平均 {row['20期平均']:.3f}")

        fig = px.line(
            sentiment_df.sort_values('periodEndDate'),
            x='periodEndDate', y='metricValue', color='country_name',
            line_dash='metricType' if mode == "両方" else None,
            color_discrete_map=COUNTRY_PALETTE,
            title="Central Bank Policy Sentiment",
            labels={'periodEndDate': 'Date', 'metricValue': 'Sentiment Score', 'country_name': 'Central Bank'}
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.update_traces(line=dict(width=2.5))
        fig.update_layout(hovermode='x unified', height=750, template="plotly_white",
                         xaxis_tickformat="%Y/%m/%d", font=dict(size=12), margin=dict(l=80, r=20, t=80, b=80))
        st.plotly_chart(fig, use_container_width=True)

        if not overview_summary.empty:
            display_summary = overview_summary.copy()
            for c in ["最新スコア", "前回比", "20期平均", "期間平均", "期間高値", "期間安値"]:
                display_summary[c] = display_summary[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
            st.markdown("### Relative Ranking")
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
    else:
        st.warning("選択した条件に該当するデータがありません")


def _render_topic_tab(raw_df):
    st.subheader("Topic Analysis - トピック別分析")

    st.markdown("""
    <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
        <p style='margin: 0; font-size: 14px;'>
            <strong>スコアの解釈:</strong>
            <strong style='color: #d62728;'>正=タカ派的</strong> |
            <strong style='color: #1f77b4;'>負=ハト派的</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    topic_df = raw_df.copy()
    topic_df['periodEndDate'] = pd.to_datetime(topic_df['periodEndDate'])
    topic_df['country_name'] = topic_df['entityName'].map(ENTITY_TO_COUNTRY)
    min_date = topic_df['periodEndDate'].min().date()
    max_date = topic_df['periodEndDate'].max().date()
    default_start = max(min_date, max_date - timedelta(days=180))

    col1, col2, col3 = st.columns(3)
    with col1:
        topic_start = st.date_input("開始日", value=default_start, min_value=min_date, max_value=max_date, key="tp_start")
    with col2:
        available_countries = sorted(topic_df['country_name'].unique())
        selected_countries = st.multiselect("中央銀行", available_countries, default=available_countries, key="tp_countries")
    with col3:
        smoothing_window = st.selectbox("スムージング窓", ["15", "30", "40"], key="tp_smooth")

    topic_end = st.date_input("終了日", value=max_date, min_value=min_date, max_value=max_date, key="tp_end")

    topic_analysis_df = topic_df[
        (topic_df['documentType'] == 'all documents') &
        (topic_df['setName'] == 'all speakers') &
        (topic_df['metricType'] == 'sentiment score smoothed') &
        (topic_df['metric'] != 'all topics')
    ].copy()

    if selected_countries:
        topic_analysis_df = topic_analysis_df[topic_analysis_df['country_name'].isin(selected_countries)]

    topic_analysis_df = topic_analysis_df[
        (topic_analysis_df['periodEndDate'] >= pd.to_datetime(topic_start)) &
        (topic_analysis_df['periodEndDate'] <= pd.to_datetime(topic_end))
    ]

    if not topic_analysis_df.empty:
        render_section_intro("Topic Lens", "どのテーマがセンチメントを押し上げ/押し下げているかを確認")
        topic_snapshot_df, topic_snapshot_date = build_topic_summary(topic_analysis_df)

        # トピック選択チェックボックス
        st.markdown("### トピック別推移")
        available_topics = sorted(topic_analysis_df['metric'].unique())
        st.write("**表示するトピックを選択:**")
        tcols = st.columns(3)
        selected_topics = []

        if 'topic_checkboxes' not in st.session_state:
            st.session_state.topic_checkboxes = {t: i < 3 for i, t in enumerate(available_topics)}

        for idx, topic in enumerate(available_topics):
            col = tcols[idx % 3]
            checked = col.checkbox(topic, value=st.session_state.topic_checkboxes.get(topic, idx < 3), key=f"tp_cb_{topic}")
            st.session_state.topic_checkboxes[topic] = checked
            if checked:
                selected_topics.append(topic)

        if selected_topics:
            trend_df = topic_analysis_df[topic_analysis_df['metric'].isin(selected_topics)]
            fig_trend = px.line(trend_df.sort_values('periodEndDate'),
                               x='periodEndDate', y='metricValue', color='metric', facet_col='country_name',
                               title='トピック別推移', labels={'periodEndDate': 'Date', 'metricValue': 'Score', 'metric': 'Topic'},
                               height=550)
            fig_trend.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_trend.update_layout(template="plotly_white", xaxis_tickformat="%Y/%m/%d")
            st.plotly_chart(fig_trend, use_container_width=True)

        if topic_snapshot_date is not None and not topic_snapshot_df.empty:
            top_pos = topic_snapshot_df.sort_values('metricValue', ascending=False).head(10).copy()
            top_neg = topic_snapshot_df.sort_values('metricValue', ascending=True).head(10).copy()
            top_pos['metricValue'] = top_pos['metricValue'].map(lambda x: f"{x:.4f}")
            top_neg['metricValue'] = top_neg['metricValue'].map(lambda x: f"{x:.4f}")

            st.markdown(f"### Latest Topic Movers ({topic_snapshot_date.strftime('%Y-%m-%d')})")
            mc1, mc2 = st.columns(2)
            with mc1:
                st.caption("押し上げ要因")
                st.dataframe(top_pos.rename(columns={'country_name': '中央銀行', 'metric': 'トピック', 'metricValue': 'スコア'}),
                            use_container_width=True, hide_index=True)
            with mc2:
                st.caption("押し下げ要因")
                st.dataframe(top_neg.rename(columns={'country_name': '中央銀行', 'metric': 'トピック', 'metricValue': 'スコア'}),
                            use_container_width=True, hide_index=True)

        # 国別トピック寄与度
        st.markdown("### 国別トピック寄与度分析")
        latest_date = topic_analysis_df['periodEndDate'].max()
        for country in selected_countries:
            country_latest = topic_analysis_df[
                (topic_analysis_df['periodEndDate'] == latest_date) &
                (topic_analysis_df['country_name'] == country)
            ]
            if not country_latest.empty:
                st.markdown(f"#### {country}")
                fig_bar = px.bar(country_latest.sort_values('metricValue', ascending=True),
                                y='metric', x='metricValue', orientation='h',
                                color='metricValue', color_continuous_scale='RdYlGn',
                                title=f"{country} - トピック別スコア ({latest_date.strftime('%Y-%m-%d')})",
                                labels={'metric': 'Topic', 'metricValue': 'Score'}, height=550)
                fig_bar.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_bar.update_layout(template="plotly_white")
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("選択した条件に該当するデータがありません")


def _render_speaker_tab(raw_df):
    st.subheader("Speaker Analysis - 発言者分析")

    st.markdown("""
    <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
        <p style='margin: 0; font-size: 14px;'>
            <strong>スコアの解釈:</strong>
            <strong style='color: #d62728;'>正=タカ派的</strong> |
            <strong style='color: #1f77b4;'>負=ハト派的</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    speaker_df = raw_df.copy()
    speaker_df['periodEndDate'] = pd.to_datetime(speaker_df['periodEndDate'])
    speaker_df['country_name'] = speaker_df['entityName'].map(ENTITY_TO_COUNTRY)
    min_date = speaker_df['periodEndDate'].min().date()
    max_date = speaker_df['periodEndDate'].max().date()
    default_start = max(min_date, max_date - timedelta(days=180))

    col1, col2 = st.columns([3, 2])
    with col1:
        c1, c2 = st.columns(2)
        with c1:
            speaker_start = st.date_input("開始日", value=default_start, min_value=min_date, max_value=max_date, key="sp_start")
        with c2:
            speaker_end = st.date_input("終了日", value=max_date, min_value=min_date, max_value=max_date, key="sp_end")
    with col2:
        available_countries = sorted(speaker_df['country_name'].unique())
        selected_country = st.selectbox("中央銀行", available_countries, key="sp_country")

    speaker_all_df = speaker_df[
        (speaker_df['documentType'] == 'all documents') &
        (speaker_df['setName'] != 'all speakers') &
        (speaker_df['metricType'] == 'sentiment score smoothed') &
        (speaker_df['country_name'] == selected_country)
    ].copy()

    speaker_all_df = speaker_all_df[
        (speaker_all_df['periodEndDate'] >= pd.to_datetime(speaker_start)) &
        (speaker_all_df['periodEndDate'] <= pd.to_datetime(speaker_end))
    ]

    if not speaker_all_df.empty:
        render_section_intro("Speaker Lens", "誰の発言がスタンス変化を主導しているかを確認")

        speaker_contribution = speaker_all_df[speaker_all_df['metric'] == 'all topics'].copy()

        if not speaker_contribution.empty:
            speaker_avg = speaker_contribution.groupby('setName', as_index=False)['metricValue'].mean()
            speaker_avg = speaker_avg.nlargest(10, 'metricValue')

            top_name = speaker_avg.iloc[0]['setName'] if not speaker_avg.empty else "-"
            top_score = speaker_avg.iloc[0]['metricValue'] if not speaker_avg.empty else np.nan
            bot_name = speaker_avg.iloc[-1]['setName'] if not speaker_avg.empty else "-"
            bot_score = speaker_avg.iloc[-1]['metricValue'] if not speaker_avg.empty else np.nan

            sc = st.columns(3)
            speaker_cards = [
                ("対象発言者", f"{speaker_contribution['setName'].nunique()}", f"{selected_country} の発言者数"),
                ("最もタカ派", top_name, f"平均スコア {top_score:.3f}" if pd.notna(top_score) else ""),
                ("最もハト派", bot_name, f"平均スコア {bot_score:.3f}" if pd.notna(bot_score) else "")
            ]
            for col, (label, value, text) in zip(sc, speaker_cards):
                with col:
                    render_summary_card(label, value, text)

            fig_c = px.bar(speaker_avg.sort_values('metricValue', ascending=True),
                          y='setName', x='metricValue', orientation='h',
                          title=f'{selected_country} - 発言者寄与度 (期間平均)',
                          labels={'setName': 'Speaker', 'metricValue': 'Avg Score'},
                          height=max(400, len(speaker_avg) * 30))
            fig_c.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_c.update_layout(template="plotly_white")
            st.plotly_chart(fig_c, use_container_width=True)

            # 時系列
            st.markdown("### 発言者別時系列推移")
            top_speakers = speaker_avg.nlargest(5, 'metricValue')['setName'].tolist()
            all_speakers = sorted(speaker_contribution['setName'].unique())

            st.write("**表示する発言者を選択:**")
            scols = st.columns(3)
            selected_speakers = []

            if 'speaker_checkboxes' not in st.session_state:
                st.session_state.speaker_checkboxes = {s: s in top_speakers[:3] for s in all_speakers}

            for idx, speaker in enumerate(all_speakers):
                col = scols[idx % 3]
                checked = col.checkbox(speaker, value=st.session_state.speaker_checkboxes.get(speaker, speaker in top_speakers[:3]),
                                      key=f"sp_cb_{speaker}")
                st.session_state.speaker_checkboxes[speaker] = checked
                if checked:
                    selected_speakers.append(speaker)

            if selected_speakers:
                ts_df = speaker_contribution[speaker_contribution['setName'].isin(selected_speakers)]
                fig_ts = px.line(ts_df.sort_values('periodEndDate'),
                                x='periodEndDate', y='metricValue', color='setName',
                                title=f'{selected_country} - 発言者時系列推移',
                                labels={'periodEndDate': 'Date', 'metricValue': 'Score', 'setName': 'Speaker'},
                                height=600)
                fig_ts.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_ts.update_layout(template="plotly_white", hovermode='x unified', xaxis_tickformat="%Y/%m/%d")
                st.plotly_chart(fig_ts, use_container_width=True)

        # ヒートマップ
        st.markdown("### 発言者×トピック分析")
        speaker_topic_df = speaker_all_df[speaker_all_df['metric'] != 'all topics'].copy()

        if not speaker_topic_df.empty:
            sta = speaker_topic_df.groupby(['setName', 'metric'], as_index=False)['metricValue'].mean()
            if not speaker_contribution.empty:
                top10 = speaker_avg.nlargest(10, 'metricValue')['setName'].tolist()
                sta = sta[sta['setName'].isin(top10)]

            pivot = sta.pivot(index='setName', columns='metric', values='metricValue')
            fig_heat = px.imshow(pivot, labels=dict(x="Topic", y="Speaker", color="Score"),
                                title=f'{selected_country} - 発言者×トピック ヒートマップ',
                                color_continuous_scale='RdYlGn', aspect="auto",
                                height=max(500, len(pivot) * 35))
            fig_heat.update_xaxes(tickangle=-45)
            st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("選択した条件に該当するデータがありません")


def _render_export_tab():
    st.subheader("Data Export - データエクスポート")

    st.markdown("""
    <div style='background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
                padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
        <h3 style='color: white; margin: 0;'>データセット選択とエクスポート</h3>
        <p style='color: #f0f0f0; margin: 5px 0 0 0;'>CSV/Excel/JSON形式でダウンロードできます</p>
    </div>
    """, unsafe_allow_html=True)

    dataset_options = {
        "Sentiment Smoothed": {"mt": "sentiment score smoothed", "mf": "all topics", "sf": "all speakers"},
        "Sentiment Unsmoothed": {"mt": "sentiment score unsmoothed", "mf": "all topics", "sf": "all speakers"},
        "Topic Contribution": {"mt": "sentiment score smoothed", "mf": "!=all topics", "sf": "all speakers"},
        "Speaker Contribution": {"mt": "sentiment score smoothed", "mf": "all topics", "sf": "!=all speakers"},
        "Speaker × Topic": {"mt": "sentiment score smoothed", "mf": "!=all topics", "sf": "!=all speakers"},
    }

    selected = st.selectbox("データセットを選択", list(dataset_options.keys()), key="sent_export_ds")
    config = dataset_options[selected]

    export_data = st.session_state.sentiment_df_cached.copy()
    export_data['periodEndDate'] = pd.to_datetime(export_data['periodEndDate'])
    export_data['country_name'] = export_data['entityName'].map(ENTITY_TO_COUNTRY)

    export_data = export_data[export_data['metricType'] == config['mt']]
    export_data = export_data[export_data['documentType'] == 'all documents']

    if config['mf'] == "!=all topics":
        export_data = export_data[export_data['metric'] != 'all topics']
    else:
        export_data = export_data[export_data['metric'] == config['mf']]

    if config['sf'] == "!=all speakers":
        export_data = export_data[export_data['setName'] != 'all speakers']
    else:
        export_data = export_data[export_data['setName'] == config['sf']]

    if not export_data.empty:
        display_cols = ['periodEndDate', 'entityName', 'country_name', 'metric', 'metricType', 'metricValue', 'setName', 'documentType']
        available_cols = [c for c in display_cols if c in export_data.columns]

        st.markdown(f"**データ件数: {len(export_data):,}**")

        preview = export_data[available_cols].sort_values('periodEndDate', ascending=False)
        items = 50
        total_pages = max(1, (len(preview) - 1) // items + 1)
        page = st.number_input(f"ページ (全{total_pages}ページ)", min_value=1, max_value=total_pages, value=1, key="sent_page")
        start_i = (page - 1) * items
        end_i = min(start_i + items, len(preview))
        st.dataframe(preview.iloc[start_i:end_i], use_container_width=True, height=600)
        st.caption(f"表示中: {start_i + 1} - {end_i} / {len(preview)} 件")

        st.markdown("---")
        render_export_section(export_data, prefix=f"sentiment_{selected.lower().replace(' ', '_')}", display_cols=available_cols)
    else:
        st.warning("選択した条件に該当するデータがありません")
