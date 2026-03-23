import streamlit as st
import pandas as pd
import requests
import json
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
import re
import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
import numpy as np

# 不要な警告を抑制
warnings.simplefilter('ignore', InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Failed to patch SSL settings')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# プロキシの設定
os.environ["http_proxy"] = "http://10.7.0.165:8080"
os.environ["https_proxy"] = "http://10.7.0.165:8080"

# APIトークンの読み込み
with open("API key.txt", "r") as f:
    token = f.read().strip()

# 国コードと国名のマッピング
COUNTRY_MAPPING = {
    'JPN': '日本',
    'GBR': 'イギリス',
    'USA': 'アメリカ',
    'EUR': 'ユーロ圏'
}

# エンティティ名と国のマッピング
ENTITY_TO_COUNTRY = {
    'Bank of Japan': '日本',
    'Federal Reserve System': 'アメリカ',
    'European Central Bank': 'ユーロ圏'
}

class UBSEvidenceLab:
    def __init__(self, token):
        self.server = "https://neo.ubs.com/api/evidence-lab/api-framework"
        self.proxy = {
            "http": os.environ.get("http_proxy"),
            "https": os.environ.get("https_proxy")
        }
        self.proxy = {k: v for k, v in self.proxy.items() if v}
        self.token = token
        self.retries = 3
        self.timeout = 60

    def _http_get(self, url):
        return requests.get(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            proxies=self.proxy,
            verify=False,
            timeout=self.timeout
        )

    def _http_post(self, url, payload):
        return requests.post(
            url=url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=payload,
            proxies=self.proxy,
            verify=False,
            timeout=self.timeout
        )

    def get(self, endpoint):
        url = f"{self.server}/{endpoint}"
        for attempt in range(self.retries + 1):
            response = self._http_get(url)
            if response.status_code in [500, 503] and attempt < self.retries:
                st.warning(f"サーバーエラー: リトライ中 {attempt + 1}/{self.retries}...")
                time.sleep(5 ** (attempt + 1))
            else:
                break
        return self.handle_response(response)

    def post(self, endpoint, payload=None):
        url = f"{self.server}/{endpoint}"
        for attempt in range(self.retries + 1):
            response = self._http_post(url, payload)
            if response.status_code in [500, 503] and attempt < self.retries:
                st.warning(f"サーバーエラー: リトライ中 {attempt + 1}/{self.retries}...")
                time.sleep(5 ** (attempt + 1))
            else:
                break
        return self.handle_response(response)

    @staticmethod
    def validate_response(response):
        if response.status_code == 401:
            raise Exception("Invalid credentials")
        if response.status_code == 404:
            raise Exception("API not found")
        if response.status_code >= 400:
            data = response.json if isinstance(response.json, dict) else response.json()
            raise Exception(data.get("message", str(response.text)))
        if response.status_code == 200 and 'HTML' in response.text:
            raise Exception("Invalid credentials")

    def handle_response(self, response):
        self.validate_response(response)
        data = response.json()
        return data


def fetch_sentiment_data(client, start_date_str=None, end_date_str=None):
    """
    Central Banks Policy Sentiment Trackerのデータを取得
    """
    # 日付が指定されない場合はデフォルト値を使用
    if start_date_str is None:
        start_date_str = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    if end_date_str is None:
        end_date_str = datetime.now().strftime("%Y-%m-%d")
    
    # フィルター条件を設定
    filter_dict = {
        "filters": [
            {
                "filterType": ">=",
                "field": "periodEndDate",
                "value": start_date_str
            },
            {
                "filterType": "<=",
                "field": "periodEndDate",
                "value": end_date_str
            }
        ]
    }
    
    # 初期エンドポイント（dataAssetKey=10487をURLに含める）
    endpoint = "central-banks-policy-sentiment/default/v2/data?dataAssetKey=10487"
    
    df = pd.DataFrame()
    page_count = 0
    
    # ページネーションで全データを取得
    status_container = st.container()
    start_time = time.time()
    
    with status_container:
        status_text = st.empty()
        metric_col1, metric_col2 = st.columns(2)
        total_records_display = metric_col1.empty()
        elapsed_time_display = metric_col2.empty()
    
    while endpoint:
        page_count += 1
        
        try:
            data = client.post(endpoint=endpoint, payload=filter_dict)
            
            if 'results' in data and len(data['results']) > 0:
                df_page = pd.json_normalize(data['results'])
                df = pd.concat([df, df_page], ignore_index=True)
                elapsed = time.time() - start_time
                
                # リアルタイムで取得件数を表示
                with status_container:
                    status_text.info(f"📥 データ取得中...")
                    total_records_display.metric("📊 取得済み件数", f"{len(df):,}")
                    elapsed_time_display.metric("⏱️ 経過時間", f"{elapsed:.1f}秒")
            
            # 次のページのエンドポイントを確認
            if 'meta' in data and 'next' in data['meta']:
                next_endpoint = data['meta']['next']
                if next_endpoint:
                    endpoint = next_endpoint.replace(client.server, '')
                else:
                    break
            else:
                break
                
        except Exception as e:
            status_text.error(f"❌ 接続エラー: {str(e)}")
            raise Exception(f"データ取得中にエラーが発生しました: {str(e)}")
    
    total_elapsed = time.time() - start_time
    
    # データ取得完了後、進捗表示を非表示にする
    with status_container:
        status_text.empty()
        total_records_display.empty()
        elapsed_time_display.empty()
    
    return df


def process_sentiment_data(df):
    """
    取得したデータを処理
    """
    if df.empty:
        return None
    
    # 日付列を datetime に変換
    df['periodEndDate'] = pd.to_datetime(df['periodEndDate'])
    
    # entityNameから国名を直接マッピング
    df['country_name'] = df['entityName'].map(ENTITY_TO_COUNTRY)
    
    # 中銀名（国名）の形式で表示用列を作成
    df['bank_display'] = df['entityName'] + '（' + df['country_name'] + '）'
    
    # フィルター済みデータ（標準フィルター）
    df_processed = df[
        (df['metricType'] == 'sentiment score smoothed') &
        (df['documentType'] == 'all documents') &
        (df['setName'] == 'all speakers')
    ].copy()
    
    return df_processed


def compute_aggregates_from_raw(raw_df, start_date=None, end_date=None, countries=None, smoothing_window=40):
    """
    raw_df: DataFrame loaded from API (unprocessed)
    Returns aggregated timeseries per bank (country) with optional EWMA smoothing.
    """
    if raw_df is None or raw_df.empty:
        return None, None, None

    df = raw_df.copy()
    # ensure datetime
    df['periodEndDate'] = pd.to_datetime(df['periodEndDate'])

    # map country
    df['country_name'] = df['entityName'].map(ENTITY_TO_COUNTRY)
    df['bank_display'] = df['entityName'] + '（' + df['country_name'] + '）'

    # date-only index
    df['date'] = df['periodEndDate'].dt.normalize()

    # filter date range
    if start_date is not None:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date is not None:
        df = df[df['date'] <= pd.to_datetime(end_date)]

    if countries:
        df = df[df['country_name'].isin(countries)]

    # Count records per entity/date/topic
    grp = df.groupby(['entityName', 'country_name', 'date', 'metric', 'metricType'])
    agg = grp['metricValue'].agg(['mean', 'count']).reset_index().rename(columns={'mean': 'metric_mean', 'count': 'n'})

    # total relevant sentences per entity/date (approx by record counts)
    total_per_entity_date = agg.groupby(['entityName', 'country_name', 'date'])['n'].sum().reset_index().rename(columns={'n': 'total_n'})
    agg = agg.merge(total_per_entity_date, on=['entityName', 'country_name', 'date'], how='left')

    # topic contribution: metric_mean * (n / total_n)
    agg['topic_contribution'] = agg['metric_mean'] * (agg['n'] / agg['total_n'])

    # bank daily score: sum of topic_contribution across topics for each entity/date
    bank_score = agg.groupby(['entityName', 'country_name', 'date'])['topic_contribution'].sum().reset_index().rename(columns={'topic_contribution': 'bank_score_raw'})

    # pivot to wide format (columns per country_name)
    pivot = bank_score.pivot_table(index='date', columns='country_name', values='bank_score_raw')

    # forward-fill missing days: create full date index
    start_date = pd.to_datetime(pivot.index.min())
    end_date = pd.to_datetime(pivot.index.max())
    full_idx = pd.date_range(start=start_date, end=end_date, freq='D')
    pivot = pivot.reindex(full_idx)
    pivot = pivot.ffill()

    # apply EWMA smoothing per column
    smoothed = pivot.ewm(span=smoothing_window, adjust=False).mean()

    return pivot, smoothed, agg


def create_sentiment_chart(df_processed, selected_entity, selected_metric, selected_countries=None, date_range=None):
    """
    Sentiment スコアのチャートを作成
    """
    if df_processed is None or df_processed.empty:
        st.error("表示するデータがありません")
        return
    
    df_chart = df_processed.copy()
    
    # 国別にフィルター（country_name を使用）
    if selected_countries and len(selected_countries) > 0:
        df_chart = df_chart[df_chart['country_name'].isin(selected_countries)]
    
    # 期間でフィルター
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        df_chart = df_chart[
            (df_chart['periodEndDate'] >= start_date) & 
            (df_chart['periodEndDate'] <= end_date)
        ]
    
    # トピックでフィルター
    if selected_metric != "All Topics":
        df_chart = df_chart[df_chart['metric'] == selected_metric].copy()
    else:
        df_chart = df_chart[df_chart['metric'] == 'all topics'].copy()
    
    if df_chart.empty:
        st.error("選択した条件に該当するデータがありません")
        return
    
    # カラーパレット（はっきりした色）
    color_palette = {
        '日本': '#1f77b4',      # 濃い青
        'アメリカ': '#d62728',  # 赤
        'ユーロ圏': '#2ca02c'   # 緑
    }
    
    # チャートを作成
    fig = px.line(
        df_chart.sort_values('periodEndDate'),
        x='periodEndDate',
        y='metricValue',
        color='country_name',
        color_discrete_map=color_palette,
        title=f"Central Bank Policy Sentiment - {selected_metric}",
        labels={
            'periodEndDate': 'Date',
            'metricValue': 'Sentiment Score',
            'country_name': 'Country'
        }
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(
        hovermode='x unified',
        height=750,
        xaxis_title="Date",
        xaxis_tickformat="%Y/%m/%d",
        yaxis_title="Sentiment Score (Negative=Dovish, Positive=Hawkish)",
        font=dict(size=12),
        template="plotly_white",
        plot_bgcolor="#f8f9fa",
        paper_bgcolor="white",
        margin=dict(l=80, r=20, t=80, b=80)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # トピック寄与度分解（all topicsが選択されている場合のみ）
    if selected_metric == "All Topics" and selected_countries:
        st.markdown("---")
        st.subheader("トピック別寄与度分析")
        
        # 国別のトピック別スコアを計算
        contribution_data = []
        
        # df_processed から直接取得（df_chart ではなく全データを使用）
        for country in selected_countries:
            country_data = df_processed[df_processed['country_name'] == country]
            
            if not country_data.empty:
                # 最新日付を取得
                latest_date = country_data['periodEndDate'].max()
                latest_country_data = country_data[country_data['periodEndDate'] == latest_date]
                
                # トピック別スコアを計算
                topic_scores = latest_country_data.groupby('metric')['metricValue'].mean()
                
                for topic, score in topic_scores.items():
                    if topic != 'all topics':
                        contribution_data.append({
                            'Country': country,
                            'Topic': topic,
                            'Score': float(score)
                        })
        
        if contribution_data:
            contrib_df = pd.DataFrame(contribution_data)
            
            # トピック別寄与度グラフ
            fig_contrib = px.bar(
                contrib_df,
                x='Topic',
                y='Score',
                color='Country',
                color_discrete_map={
                    '日本': '#1f77b4',
                    'アメリカ': '#d62728',
                    'ユーロ圏': '#2ca02c'
                },
                barmode='group',
                title='各国の最新トピック別センチメントスコア',
                labels={'Score': 'Sentiment Score', 'Topic': 'Topic'},
                height=550
            )
            
            fig_contrib.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_contrib.update_layout(
                hovermode='x unified',
                template="plotly_white",
                font=dict(size=11),
                margin=dict(l=80, r=20, t=80, b=80)
            )
            st.plotly_chart(fig_contrib, use_container_width=True)
            
            # 寄与度テーブル表示
            with st.expander("トピック別スコア詳細"):
                display_contrib = contrib_df.pivot_table(
                    index='Topic',
                    columns='Country',
                    values='Score'
                ).round(4)
                st.dataframe(display_contrib, use_container_width=True)
        else:
            st.info("選択した条件のトピック別データがありません")


def get_country_palette():
    return {
        '譌･譛ｬ': '#2563eb',
        '繧｢繝｡繝ｪ繧ｫ': '#dc2626',
        '繝ｦ繝ｼ繝ｭ蝨・': '#059669'
    }


def enrich_bank_labels(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    entity_labels = {
        'Bank of Japan': 'BOJ',
        'Federal Reserve System': 'FED',
        'European Central Bank': 'ECB'
    }
    df['bank_label'] = df['entityName'].map(entity_labels).fillna(df['entityName'])
    return df


def build_overview_summary(sentiment_df):
    if sentiment_df is None or sentiment_df.empty:
        return pd.DataFrame()

    summary_rows = []
    for country, group in sentiment_df.groupby('country_name'):
        ordered = group.sort_values('periodEndDate')
        latest = ordered.iloc[-1]
        latest_score = float(latest['metricValue'])
        prev_score = float(ordered.iloc[-2]['metricValue']) if len(ordered) > 1 else np.nan
        delta = latest_score - prev_score if pd.notna(prev_score) else np.nan
        trailing_20 = ordered.tail(min(20, len(ordered)))['metricValue'].mean()
        direction = "Hawkish" if latest_score > 0 else "Dovish" if latest_score < 0 else "Neutral"
        summary_rows.append({
            "中央銀行": country,
            "最新日付": latest['periodEndDate'].strftime("%Y-%m-%d"),
            "最新スコア": latest_score,
            "前回比": delta,
            "20期平均": trailing_20,
            "期間平均": ordered['metricValue'].mean(),
            "期間高値": ordered['metricValue'].max(),
            "期間安値": ordered['metricValue'].min(),
            "観測数": len(ordered),
            "判定": direction
        })

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("最新スコア", ascending=False).reset_index(drop=True)
    return summary_df


def build_topic_summary(topic_df):
    if topic_df is None or topic_df.empty:
        return pd.DataFrame(), None

    latest_date = topic_df['periodEndDate'].max()
    latest_df = topic_df[topic_df['periodEndDate'] == latest_date].copy()
    topic_summary = latest_df.groupby(['country_name', 'metric'], as_index=False)['metricValue'].mean()
    return topic_summary, latest_date


def render_section_intro(title, subtitle):
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


def show_home_screen():
    """
    ホーム画面：メインモジュールを選択
    """
    st.set_page_config(
        page_title="UBS Evidence Lab Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    .home-title {
        text-align: center;
        color: white;
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 1rem;
        text-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    
    .home-subtitle {
        text-align: center;
        color: #e0e7ff;
        font-size: 1.3rem;
        margin-bottom: 3rem;
        font-weight: 500;
    }
    
    .home-button-container {
        display: flex;
        justify-content: center;
        gap: 3rem;
        flex-wrap: wrap;
        margin-bottom: 3rem;
    }
    
    .home-button {
        background: white;
        border: none;
        border-radius: 20px;
        padding: 3rem 4rem;
        width: 300px;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        text-decoration: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    
    .home-button:hover {
        transform: translateY(-10px);
        box-shadow: 0 15px 40px rgba(0,0,0,0.3);
    }
    
    .home-button-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    
    .home-button-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.5rem;
    }
    
    .home-button-desc {
        font-size: 0.95rem;
        color: #64748b;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # コンテナ内にコンテンツを配置
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown('<div class="home-title">📊 UBS Evidence Lab</div>', unsafe_allow_html=True)
        st.markdown('<div class="home-subtitle">Dashboard Selection</div>', unsafe_allow_html=True)
        
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        
        # ボタン1: Central Bank Sentiment
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button(
                "🏦 Central Bank\nSentiment",
                key="btn_sentiment",
                help="中央銀行のセンチメント分析ダッシュボード",
                use_container_width=True,
                type="primary"
            ):
                st.session_state['app_mode'] = 'sentiment'
                st.rerun()
        
        with col_btn2:
            if st.button(
                "📈 Nowcasting",
                key="btn_nowcasting",
                help="経済指標のNowcasting分析",
                use_container_width=True,
                type="primary"
            ):
                st.session_state['app_mode'] = 'nowcasting'
                st.rerun()
        
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        
        # 説明テキスト
        st.markdown("""
        ### Available Tools:
        
        **🏦 Central Bank Sentiment Tracker**
        - 主要中央銀行（日本銀行、米国FRB、ECB）のセンチメント分析
        - トピック別・発言者別の詳細分析
        - Historical trends and policy sentiment tracking
        
        **📈 Nowcasting**
        - 実時間経済指標の予測値と実績値の比較
        - Industrial Production、ISM製造業などの主要指標
        - Forecast accuracy and economic trend analysis
        """)


def show_sentiment_dashboard():
    # カスタムCSS - モダンで美しいデザイン
    st.markdown("""
    <style>
    /* メインコンテナ */
    .main {
        padding: 1rem 2rem;
        background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
    }
    
    /* サイドバー */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
    }
    
    /* タイトル */
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
    
    /* サブタイトル */
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
    
    /* メトリックカード */
    [data-testid="stMetricValue"] {
        color: #1e3a8a;
        font-weight: 700;
        font-size: 2rem;
    }
    
    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-weight: 600;
    }
    
    /* ボタン */
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
    
    /* プライマリボタン */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    }
    
    /* セカンダリボタン */
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    }
    
    /* タブ - サイズ大きく */
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
    
    /* データフレーム */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    
    /* インフォボックス */
    .stAlert {
        border-radius: 10px;
        border-left: 4px solid;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* プログレスバー */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    /* セレクトボックス */
    .stSelectbox {
        border-radius: 8px;
    }
    
    /* エキスパンダー */
    .streamlit-expanderHeader {
        background-color: #f8fafc;
        border-radius: 8px;
        font-weight: 600;
        color: #334155;
    }
    
    /* カード風デザイン */
    div[data-testid="stVerticalBlock"] > div:has(div.element-container) {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        margin-bottom: 1rem;
    }
    
    /* グラフコンテナ */
    .js-plotly-plot {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
    
    /* ダウンロードボタン */
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
    
    /* 入力フィールド */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        border-radius: 8px;
        border: 2px solid #e2e8f0;
        transition: border-color 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* チェックボックス */
    .stCheckbox {
        padding: 0.5rem;
        border-radius: 6px;
        transition: background-color 0.3s ease;
    }
    
    .stCheckbox:hover {
        background-color: #f1f5f9;
    }
    
    /* マルチセレクト */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #e0e7ff;
        color: #4f46e5;
        border-radius: 6px;
        font-weight: 600;
    }
    
    /* スライダー */
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 成功メッセージ */
    .stSuccess {
        background-color: #d1fae5;
        color: #065f46;
        border-left-color: #10b981;
    }
    
    /* 警告メッセージ */
    .stWarning {
        background-color: #fef3c7;
        color: #92400e;
        border-left-color: #f59e0b;
    }
    
    /* エラーメッセージ */
    .stError {
        background-color: #fee2e2;
        color: #991b1b;
        border-left-color: #ef4444;
    }
    
    /* インフォメッセージ */
    .stInfo {
        background-color: #dbeafe;
        color: #1e40af;
        border-left-color: #3b82f6;
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
    
    # メソドロジーを折りたたみ式で表示
    with st.expander("📖 中央銀行政策スタンス追跡 メソドロジー"):
        st.markdown("""
        ### 概要
        
        本研究は **UBS AI LLMs** を活用して、中央銀行スピーカーの演説やプレスカンファレンスの言語を分析し、
        金融政策に対するスタンスを追跡します。
        
        **主要機能:**
        - 各中央銀行の総合的なタカ派度/ハト派度を追跡し、時系列での推移を監視
        - 議論されているトピック（例：インフレ）を特定し、総合スタンス指数への寄与度を評価
        - 各スピーカーが銀行のスタンス指数に与える寄与度を分析
        - 異なる期間にわたるスピーカーのセンチメント推移を観察（全体および特定トピック別）
        
        ---
        
        ### メソドロジー
        
        **ステップ1: 文の分割とトピック識別**
        
        各演説は文単位に分割されます。3つのLLMが各文の主要トピックを識別します。金融政策関連のトピックのみ分析対象：
        - バランスシート（量的緩和・引き締め）
        - 通貨・為替レート
        - 雇用
        - GDP/経済成長
        - インフレ/価格
        - 金融政策/金利設定
        
        これらのトピックを含まない文は除外されます（金融安定性、規制、監督など）。
        
        **ステップ2: 関連性評価とセンチメント検出**
        
        各関連文は5段階スケールで分類されます：
        - **明確にタカ派的** (+1.0): 引き締め的金融政策スタンスを示す強い言語
        - **タカ派的** (+0.5): 中程度のタカ派センチメント
        - **混合議論** (0.0): バランスの取れた、または矛盾した記述
        - **ハト派的** (-0.5): 中程度のハト派センチメント
        - **明確にハト派的** (-1.0): 緩和的金融政策スタンスを示す強い言語
        
        **ステップ3: スコア集約**
        
        演説レベルのセンチメントスコア計算式：
        **スコア = （加重センチメントスコアの合計） / （金融政策関連トピックを含む文の総数）**
        
        加重値：明確にハト派的=-1、ハト派的=-0.5、混合=0、タカ派的=+0.5、明確にタカ派的=+1
        
        **ステップ4: 指数平滑化**
        
        センチメントスコアは指数加重移動平均（EWMA）で平滑化されます。選択可能な窓：
        - **15演説窓**: 最近の変化に敏感で、ノイズが多い
        - **30演説窓**: 感度と平滑性のバランス
        - **40演説窓**: より滑らかなトレンド、変化への反応は遅い
        
        演説間のデータ連続性のため、前の値で埋められます。
        
        **ステップ5: トピック別・スピーカー別分析**
        
        - **トピック寄与度**: 演説内のトピック頻度で加重計算
        - **スピーカー寄与度**: 各スピーカーのセンチメントスコアを演説全体で集約
        
        ---
        
        ### データソース
        
        **FED**: UBS Evidence Lab、米国連邦準備制度理事会ウェブサイトの基礎データを使用
        
        **ECB**: UBS Evidence Lab、欧州中央銀行ウェブサイトの基礎データを使用（執行役員会メンバーのみ）
        
        **BOJ**: UBS Evidence Lab、日本銀行ウェブサイトの基礎データを使用（演説のみ、プレスカンファレンスQ&Aは除外）
        
        **ニューヨーク連邦準備銀行**: UBS Evidence Lab、FRBNY ウェブサイトの基礎データを使用
        
        ---
        
        ### データに関する注記
        
        - ECB国立銀行スピーカーは除外；執行役員会メンバーのみ対象
        - BOJプレスカンファレンスQ&A: スピーカーのコメントのみ含める（質問は除外）
        - 通貨・為替レート文はBOJのみに含まれる
        - 図表・表・金融政策非関連文は除外
        - 分析対象期間：1998年～現在
        
        **免責事項**: 本分析はAIツールの支援を受けて作成され、徹底的な人間による確認を経ています。
        
        **Study ID**: 7276 | **Asset Key**: 10487
        """)
    
    # セッションステートの初期化
    if 'df_cached' not in st.session_state:
        st.session_state.df_cached = None
    if 'df_processed_cached' not in st.session_state:
        st.session_state.df_processed_cached = None
    if 'topic_selections' not in st.session_state:
        st.session_state.topic_selections = {}
    if 'speaker_selections' not in st.session_state:
        st.session_state.speaker_selections = {}
    
    # サイドバー
    st.sidebar.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem; text-align: center;'>
        <span style='color: white; font-weight: 700; font-size: 1.1rem;'>
        🏦 Central Bank Sentiment Tracker
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    st.sidebar.header("データ取得設定")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("取得期間")
    
    # 期間指定方法を選択
    date_method = st.sidebar.radio(
        "期間指定方法",
        ("過去N日", "カレンダー指定"),
        horizontal=False
    )
    
    today = datetime.now().date()
    
    if date_method == "過去N日":
        days_back_input = st.sidebar.number_input(
            "過去何日間のデータを取得するか",
                min_value=1,
                max_value=10000,
                value=365,
                step=1
        )
        start_date_load = today - timedelta(days=days_back_input)
    else:
        start_date_load = st.sidebar.date_input(
            "開始日",
            value=date(1998, 1, 1),
            min_value=date(1998, 1, 1),
            max_value=today,
            key="load_start_date"
        )
    
    st.sidebar.markdown("---")
    
    # データ取得ボタン
    if st.sidebar.button("📥 データを取得", key="load_data", use_container_width=True):
        with st.spinner("UBS APIからデータを取得中..."):
            try:
                client = UBSEvidenceLab(token)
                start_str = start_date_load.strftime("%Y-%m-%d")
                end_str = today.strftime("%Y-%m-%d")
                df = fetch_sentiment_data(client, start_date_str=start_str, end_date_str=end_str)
                
                if df.empty:
                    st.error("データの取得に失敗しました")
                    st.stop()
                
                st.session_state.df_cached = df
                
                # データを処理
                df_processed = process_sentiment_data(df)
                
                if df_processed is None or df_processed.empty:
                    st.error("処理後のデータが空です")
                    st.stop()
                
                st.session_state.df_processed_cached = df_processed
                st.sidebar.success("データ取得完了")
                
                # データ統計情報を表示
                with st.sidebar.expander("データ統計", expanded=False):
                    st.metric("総レコード数", f"{len(df):,}")
                    st.metric("処理済レコード数", f"{len(df_processed):,}")
                    st.metric("開始日", df['periodEndDate'].min().strftime('%Y-%m-%d'))
                    st.metric("終了日", df['periodEndDate'].max().strftime('%Y-%m-%d'))
                    
                    # ユニーク値の統計
                    st.markdown("**ユニーク値**")
                    st.text(f"中央銀行数: {df['entityName'].nunique()}")
                    st.text(f"発言者数: {df[df['setName'] != 'all speakers']['setName'].nunique()}")
                    st.text(f"トピック数: {df[df['metric'] != 'all topics']['metric'].nunique()}")
                    st.text(f"文書種別数: {df['documentType'].nunique()}")
                    
                    # 更新情報
                    st.markdown("**更新情報**")
                    if 'updateFlag' in df.columns:
                        update_counts = df['updateFlag'].value_counts()
                        for flag, count in update_counts.items():
                            st.text(f"{flag}: {count:,}")
            
            except Exception as e:
                st.sidebar.error(f"データ取得エラー: {str(e)}")
                st.stop()
    
    # 時間Tipsをボタンの下に表示
    st.sidebar.info(
        "⏱️ **取得時間の目安**\n\n"
        "30日分のデータ取得にはおよそ10秒かかります。\n\n"
        "期間が長いほど時間がかかる傾向があります。"
    )
    
    # キャッシュデータがない場合は停止
    if st.session_state.df_cached is None or st.session_state.df_processed_cached is None:
        st.info("サイドバーで期間を選択して「データを取得」ボタンをクリックしてください")
        st.stop()
    
    df_processed = st.session_state.df_processed_cached
    raw_df = st.session_state.df_cached.copy()
    raw_df['periodEndDate'] = pd.to_datetime(raw_df['periodEndDate'])
    raw_df['country_name'] = raw_df['entityName'].map(ENTITY_TO_COUNTRY)
    executive_df = raw_df[
        (raw_df['documentType'] == 'all documents') &
        (raw_df['setName'] == 'all speakers') &
        (raw_df['metric'] == 'all topics') &
        (raw_df['metricType'] == 'sentiment score smoothed')
    ].copy()
    
    # メインエリア
    st.markdown("---")
    
    # タブインデックスをセッション状態で管理
    if not executive_df.empty:
        summary_df = build_overview_summary(executive_df)
        latest_date = executive_df['periodEndDate'].max().strftime("%Y-%m-%d")
        render_section_intro(
            "Manager Snapshot",
            f"最新更新日 {latest_date} 時点の政策スタンスを先に把握できるよう、直近スコアと変化幅を上段にまとめています。"
        )

        top_bank = summary_df.iloc[0] if not summary_df.empty else None
        bottom_bank = summary_df.iloc[-1] if not summary_df.empty else None
        move_bank = summary_df.reindex(summary_df['前回比'].abs().sort_values(ascending=False).index).iloc[0] if not summary_df.empty else None

        snapshot_cols = st.columns(4)
        cards = [
            ("対象中央銀行", f"{executive_df['country_name'].nunique()}", f"表示中の最新日付: {latest_date}"),
            ("最もタカ派", f"{top_bank['中央銀行'] if top_bank is not None else '-'}", f"最新スコア {top_bank['最新スコア']:.3f}" if top_bank is not None else ""),
            ("最もハト派", f"{bottom_bank['中央銀行'] if bottom_bank is not None else '-'}", f"最新スコア {bottom_bank['最新スコア']:.3f}" if bottom_bank is not None else ""),
            ("最大変化", f"{move_bank['中央銀行'] if move_bank is not None else '-'}", f"前回比 {move_bank['前回比']:+.3f}" if move_bank is not None and pd.notna(move_bank['前回比']) else "前回値なし")
        ]
        for col, (label, value, text) in zip(snapshot_cols, cards):
            with col:
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

    if 'selected_tab' not in st.session_state:
        st.session_state.selected_tab = 0
    
    # タブ選択をラジオボタンで管理
    col_tabs = st.columns(4)
    with col_tabs[0]:
        if st.button("📈 Overview", use_container_width=True, key="tab_overview"):
            st.session_state.selected_tab = 0
    with col_tabs[1]:
        if st.button("📊 Topic Analysis", use_container_width=True, key="tab_topic"):
            st.session_state.selected_tab = 1
    with col_tabs[2]:
        if st.button("🎤 Speaker Analysis", use_container_width=True, key="tab_speaker"):
            st.session_state.selected_tab = 2
    with col_tabs[3]:
        if st.button("💾 Data Export", use_container_width=True, key="tab_export"):
            st.session_state.selected_tab = 3
    
    st.markdown("---")
    
    # Tab 0: Overview (旧Sentiment)
    if st.session_state.selected_tab == 0:
        st.subheader("Overview - センチメント概要")
        
        # スコア説明
        st.markdown("""
        <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
            <p style='margin: 0; font-size: 14px;'>
                <strong>📊 スコアの解釈:</strong><br>
                🔴 <strong style='color: #d62728;'>正のスコア (タカ派的)</strong> = 金融引き締め的 (金利引き上げ・流動性縮小)<br>
                🔵 <strong style='color: #1f77b4;'>負のスコア (ハト派的)</strong> = 金融緩和的 (金利引き下げ・流動性拡大)
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        主要中央銀行の政策スタンス推移を一覧比較します。
        """)
        
        # タブ内フィルター
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 期間選択
            raw_df = st.session_state.df_cached.copy()
            raw_df['periodEndDate'] = pd.to_datetime(raw_df['periodEndDate'])
            min_date = raw_df['periodEndDate'].min().date()
            max_date = raw_df['periodEndDate'].max().date()
            default_start = max(min_date, max_date - timedelta(days=365))
            
            st.markdown("**期間選択**")
            start_date = st.date_input(
                "開始日",
                    value=default_start,
                    min_value=min_date,
                    max_value=max_date,
                    key="overview_start_date"
                )
        
        with col2:
            st.markdown("**中央銀行選択**")
            raw_df['country_name'] = raw_df['entityName'].map(ENTITY_TO_COUNTRY)
            available_countries = sorted(raw_df['country_name'].unique())
            selected_countries = st.multiselect(
                "国を選択",
                available_countries,
                default=available_countries,
                key="overview_countries"
            )
        
        with col3:
            st.markdown("**表示設定**")
            sentiment_display_mode = st.selectbox(
                "データ種別",
                ["Smoothed", "Unsmoothed", "両方"],
                key="overview_mode"
            )
        
        # 終了日
        col_end = st.columns(1)[0]
        with col_end:
            end_date = st.date_input(
                "終了日",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="overview_end_date"
            )
        
        # データフィルタリング
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
        
        # 表示モードに応じてフィルター
        if sentiment_display_mode == "Smoothed":
            sentiment_df = sentiment_df[sentiment_df['metricType'] == 'sentiment score smoothed']
        elif sentiment_display_mode == "Unsmoothed":
            sentiment_df = sentiment_df[sentiment_df['metricType'] == 'sentiment score unsmoothed']
        
        if not sentiment_df.empty:
            color_palette = {
                '日本': '#1f77b4',
                'アメリカ': '#d62728',
                'ユーロ圏': '#2ca02c'
            }
            
            color_palette = get_country_palette()
            overview_summary = build_overview_summary(sentiment_df)

            render_section_intro(
                "Overview",
                "まずは各中央銀行の最新スコアと直近変化を見て、どこが相対的にタカ派・ハト派へ振れているかを確認できます。"
            )

            if not overview_summary.empty:
                latest_cols = st.columns(min(3, len(overview_summary)))
                for idx, (_, row) in enumerate(overview_summary.head(3).iterrows()):
                    with latest_cols[idx]:
                        delta_text = f"前回比 {row['前回比']:+.3f}" if pd.notna(row['前回比']) else "前回値なし"
                        st.markdown(
                            f"""
                            <div class="summary-card">
                                <div class="summary-label">{row['中央銀行']}</div>
                                <div class="summary-value">{row['最新スコア']:.3f}</div>
                                <div class="summary-text">{delta_text}<br>{row['判定']} / 20期平均 {row['20期平均']:.3f}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

            fig = px.line(
                sentiment_df.sort_values('periodEndDate'),
                x='periodEndDate',
                y='metricValue',
                color='country_name',
                line_dash='metricType' if sentiment_display_mode == "両方" else None,
                color_discrete_map=color_palette,
                title="Central Bank Policy Sentiment",
                labels={
                    'periodEndDate': 'Date',
                    'metricValue': 'Sentiment Score',
                    'country_name': 'Central Bank'
                }
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig.update_traces(line=dict(width=2.5))
            fig.update_layout(
                hovermode='x unified',
                height=750,
                template="plotly_white",
                xaxis_tickformat="%Y/%m/%d",
                font=dict(size=12),
                margin=dict(l=80, r=20, t=80, b=80)
            )
            
            st.plotly_chart(fig, use_container_width=True)

            if not overview_summary.empty:
                display_summary = overview_summary.copy()
                numeric_cols = ["最新スコア", "前回比", "20期平均", "期間平均", "期間高値", "期間安値"]
                for col in numeric_cols:
                    display_summary[col] = display_summary[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "-")
                st.markdown("### Relative Ranking")
                st.dataframe(display_summary, use_container_width=True, hide_index=True)
            
            # 国ごとの統計情報をテーブルで表示
            st.markdown("### 国別統計")
            stats_data = []
            for country in selected_countries:
                country_data = sentiment_df[sentiment_df['country_name'] == country]
                if not country_data.empty:
                    stats_data.append({
                        "国": country,
                        "平均スコア": f"{country_data['metricValue'].mean():.4f}",
                        "最高スコア": f"{country_data['metricValue'].max():.4f}",
                        "最低スコア": f"{country_data['metricValue'].min():.4f}",
                        "最新値": f"{country_data.sort_values('periodEndDate').iloc[-1]['metricValue']:.4f}",
                        "データ件数": len(country_data)
                    })
            
            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
        else:
            st.warning("選択した条件に該当するデータがありません")
    
    # Tab 1: Topic Analysis (旧Topic Contribution)
    if st.session_state.selected_tab == 1:
        st.subheader("Topic Analysis - トピック別分析")
        
        # スコア説明
        st.markdown("""
        <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
            <p style='margin: 0; font-size: 14px;'>
                <strong>📊 スコアの解釈:</strong><br>
                🔴 <strong style='color: #d62728;'>正のスコア (タカ派的)</strong> = 金融引き締め的 (金利引き上げ・流動性縮小)<br>
                🔵 <strong style='color: #1f77b4;'>負のスコア (ハト派的)</strong> = 金融緩和的 (金利引き下げ・流動性拡大)
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        各トピックがセンチメントに与える影響を分析します。
        """)
        
        # タブ内フィルター
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 期間選択
            topic_df = st.session_state.df_cached.copy()
            topic_df['periodEndDate'] = pd.to_datetime(topic_df['periodEndDate'])
            min_date = topic_df['periodEndDate'].min().date()
            max_date = topic_df['periodEndDate'].max().date()
            default_start = max(min_date, max_date - timedelta(days=180))
                
            st.markdown("**期間選択**")
            topic_start = st.date_input(
                "開始日",
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key="topic_start_date"
            )
        
        with col2:
            st.markdown("**中央銀行選択**")
            topic_df['country_name'] = topic_df['entityName'].map(ENTITY_TO_COUNTRY)
            available_countries = sorted(topic_df['country_name'].unique())
            selected_countries_topic = st.multiselect(
                "国を選択",
                available_countries,
                default=available_countries,
                key="topic_countries"
            )
        
        with col3:
            st.markdown("**スムージング**")
            smoothing_window = st.selectbox(
                "窓",
                ["15", "30", "40"],
                key="topic_smoothing"
            )
        
        # 終了日
        col_end = st.columns(1)[0]
        with col_end:
            topic_end = st.date_input(
                "終了日",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key="topic_end_date"
            )
        
        # データフィルタリング
        topic_analysis_df = topic_df[
            (topic_df['documentType'] == 'all documents') &
            (topic_df['setName'] == 'all speakers') &
            (topic_df['metricType'] == 'sentiment score smoothed') &
            (topic_df['metric'] != 'all topics')
        ].copy()
        
        if selected_countries_topic:
            topic_analysis_df = topic_analysis_df[topic_analysis_df['country_name'].isin(selected_countries_topic)]
        
        # 期間フィルター
        topic_analysis_df = topic_analysis_df[
            (topic_analysis_df['periodEndDate'] >= pd.to_datetime(topic_start)) &
            (topic_analysis_df['periodEndDate'] <= pd.to_datetime(topic_end))
        ]
        
        if not topic_analysis_df.empty:
            render_section_intro(
                "Topic Lens",
                "どのテーマが各中央銀行のセンチメントを押し上げているか、押し下げているかを最新時点ベースで比較できます。"
            )
            topic_snapshot_df, topic_snapshot_date = build_topic_summary(topic_analysis_df)
            color_palette = {
                '日本': '#1f77b4',
                'アメリカ': '#d62728',
                'ユーロ圏': '#2ca02c'
            }
            
            # トピック別時系列推移
            st.markdown("### トピック別推移")
            available_topics = sorted(topic_analysis_df['metric'].unique())
            
            # チェックボックスでトピック選択
            st.write("**表示するトピックを選択:**")
            cols = st.columns(3)
            selected_topics = []
            
            # セッション状態で選択を保存
            if 'topic_checkboxes' not in st.session_state:
                st.session_state.topic_checkboxes = {topic: idx < 3 for idx, topic in enumerate(available_topics)}
            
            for idx, topic in enumerate(available_topics):
                col = cols[idx % 3]
                current_value = st.session_state.topic_checkboxes.get(topic, idx < 3)
                is_checked = col.checkbox(topic, value=current_value, key=f"topic_checkbox_{topic}")
                st.session_state.topic_checkboxes[topic] = is_checked
                if is_checked:
                    selected_topics.append(topic)
            
            if selected_topics:
                topic_trend_df = topic_analysis_df[topic_analysis_df['metric'].isin(selected_topics)]
                
                fig_trend = px.line(
                    topic_trend_df.sort_values('periodEndDate'),
                    x='periodEndDate',
                    y='metricValue',
                    color='metric',
                    facet_col='country_name',
                    title='トピック別推移',
                    labels={'periodEndDate': 'Date', 'metricValue': 'Score', 'metric': 'Topic'},
                    height=550
                )
                fig_trend.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_trend.update_layout(template="plotly_white", xaxis_tickformat="%Y/%m/%d")
                st.plotly_chart(fig_trend, use_container_width=True)

            if topic_snapshot_date is not None and not topic_snapshot_df.empty:
                top_positive = topic_snapshot_df.sort_values('metricValue', ascending=False).head(10).copy()
                top_negative = topic_snapshot_df.sort_values('metricValue', ascending=True).head(10).copy()
                top_positive['metricValue'] = top_positive['metricValue'].map(lambda x: f"{x:.4f}")
                top_negative['metricValue'] = top_negative['metricValue'].map(lambda x: f"{x:.4f}")

                st.markdown(f"### Latest Topic Movers ({topic_snapshot_date.strftime('%Y-%m-%d')})")
                mover_col1, mover_col2 = st.columns(2)
                with mover_col1:
                    st.caption("押し上げ要因")
                    st.dataframe(
                        top_positive.rename(columns={'country_name': '中央銀行', 'metric': 'トピック', 'metricValue': 'スコア'}),
                        use_container_width=True,
                        hide_index=True
                    )
                with mover_col2:
                    st.caption("押し下げ要因")
                    st.dataframe(
                        top_negative.rename(columns={'country_name': '中央銀行', 'metric': 'トピック', 'metricValue': 'スコア'}),
                        use_container_width=True,
                        hide_index=True
                    )
            
            # 直近トピック寄与度
            st.markdown("### 国別トピック寄与度分析")
            latest_date = topic_analysis_df['periodEndDate'].max()
            
            # 各国ごとにトピック寄与度を表示
            for country in selected_countries_topic:
                country_latest = topic_analysis_df[
                    (topic_analysis_df['periodEndDate'] == latest_date) &
                    (topic_analysis_df['country_name'] == country)
                ]
                
                if not country_latest.empty:
                    st.markdown(f"#### {country}")
                    fig_bar = px.bar(
                        country_latest.sort_values('metricValue', ascending=True),
                        y='metric',
                        x='metricValue',
                        orientation='h',
                        color='metricValue',
                        color_continuous_scale='RdYlGn',
                        title=f"{country} - トピック別スコア ({latest_date.strftime('%Y-%m-%d')})",
                        labels={'metric': 'Topic', 'metricValue': 'Score'},
                        height=550
                    )
                    fig_bar.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                    fig_bar.update_layout(template="plotly_white")
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("選択した条件に該当するデータがありません")
    
    # Tab 2: Speaker Analysis (統合: 旧Tab3,4,5)
    if st.session_state.selected_tab == 2:
        st.subheader("Speaker Analysis - 発言者分析")
        
        # スコア説明
        st.markdown("""
        <div style='background-color: #f0f4ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #4f46e5;'>
            <p style='margin: 0; font-size: 14px;'>
                    <strong>📊 スコアの解釈:</strong><br>
                    🔴 <strong style='color: #d62728;'>正のスコア (タカ派的)</strong> = 金融引き締め的 (金利引き上げ・流動性縮小)<br>
                    🔵 <strong style='color: #1f77b4;'>負のスコア (ハト派的)</strong> = 金融緩和的 (金利引き下げ・流動性拡大)
                </p>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("""
        主要発言者のセンチメント分析(寄与度・時系列・トピック別)を統合表示します。
        """)
        
        # タブ内フィルター
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # 中央銀行選択
            speaker_df = st.session_state.df_cached.copy()
            speaker_df['periodEndDate'] = pd.to_datetime(speaker_df['periodEndDate'])
            speaker_df['country_name'] = speaker_df['entityName'].map(ENTITY_TO_COUNTRY)
            
            min_date = speaker_df['periodEndDate'].min().date()
            max_date = speaker_df['periodEndDate'].max().date()
            default_start = max(min_date, max_date - timedelta(days=180))
            
            # 開始日と終了日を分けて入力
            col1_from, col1_to = st.columns(2)
            with col1_from:
                speaker_start = st.date_input(
                    "開始日",
                    value=default_start,
                    min_value=min_date,
                    max_value=max_date,
                    key="speaker_start_date"
                )
            with col1_to:
                speaker_end = st.date_input(
                    "終了日",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    key="speaker_end_date"
                )
        
        with col2:
            available_countries = sorted(speaker_df['country_name'].unique())
            selected_country_speaker = st.selectbox(
                "中央銀行",
                available_countries,
                key="speaker_country"
            )
        
        # データフィルタリング
        speaker_all_df = speaker_df[
            (speaker_df['documentType'] == 'all documents') &
            (speaker_df['setName'] != 'all speakers') &
            (speaker_df['metricType'] == 'sentiment score smoothed') &
            (speaker_df['country_name'] == selected_country_speaker)
        ].copy()
        
        # 期間フィルター
        speaker_all_df = speaker_all_df[
            (speaker_all_df['periodEndDate'] >= pd.to_datetime(speaker_start)) &
            (speaker_all_df['periodEndDate'] <= pd.to_datetime(speaker_end))
        ]
        
        if not speaker_all_df.empty:
            render_section_intro(
                "Speaker Lens",
                "誰の発言がスタンス変化を主導しているかを見極めるために、発言者別の寄与度とトピック偏りをまとめています。"
            )
            # セクション1: 発言者別寄与度ランキング
            st.markdown("### 発言者別寄与度")
            
            # 全トピックでの寄与度
            speaker_contribution = speaker_all_df[speaker_all_df['metric'] == 'all topics'].copy()
            
            if not speaker_contribution.empty:
                # 期間平均スコアを計算
                speaker_avg = speaker_contribution.groupby('setName', as_index=False)['metricValue'].mean()
                speaker_avg = speaker_avg.nlargest(10, 'metricValue')

                top_speaker_name = speaker_avg.iloc[0]['setName'] if not speaker_avg.empty else "-"
                top_speaker_score = speaker_avg.iloc[0]['metricValue'] if not speaker_avg.empty else np.nan
                bottom_speaker_name = speaker_avg.iloc[-1]['setName'] if not speaker_avg.empty else "-"
                bottom_speaker_score = speaker_avg.iloc[-1]['metricValue'] if not speaker_avg.empty else np.nan
                speaker_card_cols = st.columns(3)
                speaker_cards = [
                    ("対象発言者", f"{speaker_contribution['setName'].nunique()}", f"{selected_country_speaker} の期間内発言者数"),
                    ("最もタカ派", top_speaker_name, f"平均スコア {top_speaker_score:.3f}" if pd.notna(top_speaker_score) else ""),
                    ("最もハト派", bottom_speaker_name, f"平均スコア {bottom_speaker_score:.3f}" if pd.notna(bottom_speaker_score) else "")
                ]
                for col, (label, value, text) in zip(speaker_card_cols, speaker_cards):
                    with col:
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
                
                fig_contrib = px.bar(
                    speaker_avg.sort_values('metricValue', ascending=True),
                    y='setName',
                    x='metricValue',
                    orientation='h',
                    title=f'{selected_country_speaker} - 発言者寄与度 (期間平均)',
                    labels={'setName': 'Speaker', 'metricValue': 'Avg Score'},
                    height=max(400, len(speaker_avg) * 30)
                )
                fig_contrib.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_contrib.update_layout(template="plotly_white")
                st.plotly_chart(fig_contrib, use_container_width=True)
                
                # セクション2: 発言者別時系列推移
                st.markdown("### 発言者別時系列推移")
                
                top_speakers = speaker_avg.nlargest(5, 'metricValue')['setName'].tolist()
                all_speakers = sorted(speaker_contribution['setName'].unique())
                
                # チェックボックスで発言者選択
                st.write("**表示する発言者を選択:**")
                cols = st.columns(3)
                selected_speakers = []
                
                # セッション状態で選択を保存
                if 'speaker_checkboxes' not in st.session_state:
                    st.session_state.speaker_checkboxes = {speaker: speaker in top_speakers[:3] for speaker in all_speakers}
                
                for idx, speaker in enumerate(all_speakers):
                    col = cols[idx % 3]
                    current_value = st.session_state.speaker_checkboxes.get(speaker, speaker in top_speakers[:3])
                    is_checked = col.checkbox(speaker, value=current_value, key=f"speaker_checkbox_{speaker}")
                    st.session_state.speaker_checkboxes[speaker] = is_checked
                    if is_checked:
                        selected_speakers.append(speaker)
                
                if selected_speakers:
                    speaker_ts = speaker_contribution[speaker_contribution['setName'].isin(selected_speakers)]
                    
                    fig_ts = px.line(
                        speaker_ts.sort_values('periodEndDate'),
                        x='periodEndDate',
                        y='metricValue',
                        color='setName',
                        title=f'{selected_country_speaker} - 発言者時系列推移',
                        labels={'periodEndDate': 'Date', 'metricValue': 'Score', 'setName': 'Speaker'},
                        height=600
                    )
                    fig_ts.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    fig_ts.update_layout(template="plotly_white", hovermode='x unified', xaxis_tickformat="%Y/%m/%d")
                    st.plotly_chart(fig_ts, use_container_width=True)
            
            # セクション3: 発言者×トピック分析
            st.markdown("### 発言者×トピック分析")
            
            speaker_topic_df = speaker_all_df[speaker_all_df['metric'] != 'all topics'].copy()
            
            if not speaker_topic_df.empty:
                # 期間平均でヒートマップ作成
                speaker_topic_avg = speaker_topic_df.groupby(['setName', 'metric'], as_index=False)['metricValue'].mean()
                
                # Top発言者に絞る
                top_10_speakers = speaker_avg.nlargest(10, 'metricValue')['setName'].tolist() if not speaker_contribution.empty else []
                if top_10_speakers:
                    speaker_topic_avg = speaker_topic_avg[speaker_topic_avg['setName'].isin(top_10_speakers)]
                
                pivot_data = speaker_topic_avg.pivot(index='setName', columns='metric', values='metricValue')
                
                fig_heat = px.imshow(
                    pivot_data,
                    labels=dict(x="Topic", y="Speaker", color="Score"),
                    title=f'{selected_country_speaker} - 発言者×トピック ヒートマップ',
                    color_continuous_scale='RdYlGn',
                    aspect="auto",
                    height=max(500, len(pivot_data) * 35)
                )
                fig_heat.update_xaxes(tickangle=-45)
                st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.warning("選択した条件に該当するデータがありません")
    
        # Tab 3: Data Export
    # Tab 3: Data Export
    if st.session_state.selected_tab == 3:
        st.subheader("Data Export - データエクスポート")
        
        # スタイリッシュなヘッダー
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); 
                    padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
            <h3 style='color: white; margin: 0;'>データセット選択とエクスポート</h3>
            <p style='color: #f0f0f0; margin: 5px 0 0 0;'>
                必要なデータセットを選択して、CSV/Excel/JSON形式でダウンロードできます
            </p>
            </div>
            """, unsafe_allow_html=True)
        
        # データセット選択
        col1, col2 = st.columns([2, 1])
        
        with col1:
            dataset_options = {
                "Sentiment Smoothed Data": {
                    "desc": "EWMA平滑化されたセンチメントスコア (全発言者・全トピック)",
                    "metric_type": "sentiment score smoothed",
                    "metric_filter": "all topics",
                    "speaker_filter": "all speakers",
                    "doc_filter": "all documents"
                },
                "Sentiment Unsmoothed Data": {
                    "desc": "平滑化されていない生のセンチメントスコア",
                    "metric_type": "sentiment score unsmoothed",
                    "metric_filter": "all topics",
                    "speaker_filter": "all speakers",
                    "doc_filter": "all documents"
                },
                "Topic Contribution Data": {
                    "desc": "トピック別のセンチメント寄与度データ",
                    "metric_type": "sentiment score smoothed",
                    "metric_filter": "!=all topics",
                    "speaker_filter": "all speakers",
                    "doc_filter": "all documents",
                    "icon": ""
                },
                "Speaker Contribution Data": {
                    "desc": "発言者別のセンチメント寄与度データ",
                    "metric_type": "sentiment score smoothed",
                    "metric_filter": "all topics",
                    "speaker_filter": "!=all speakers",
                    "doc_filter": "all documents",
                    "icon": ""
                },
                "Speaker Monthly Data": {
                    "desc": "発言者別の月次集計データ",
                    "metric_type": "sentiment score smoothed",
                    "metric_filter": "all topics",
                    "speaker_filter": "!=all speakers",
                    "doc_filter": "all documents",
                    "icon": ""
                },
                "Speaker × Topic Data": {
                    "desc": "発言者とトピックのクロス分析データ",
                    "metric_type": "sentiment score smoothed",
                    "metric_filter": "!=all topics",
                    "speaker_filter": "!=all speakers",
                    "doc_filter": "all documents",
                    "icon": ""
                }
            }
            
            selected_dataset = st.selectbox(
                "データセットを選択",
                options=list(dataset_options.keys()),
                label_visibility="collapsed"
            )
        
        with col2:
            st.metric("データセット数", len(dataset_options), help="利用可能なデータセット")
        
        # 選択したデータセットの説明
        st.info(f"**{selected_dataset}**: {dataset_options[selected_dataset]['desc']}")
        
        # データのフィルタリングと準備
        dataset_config = dataset_options[selected_dataset]
        export_data = st.session_state.df_cached.copy()
        export_data['periodEndDate'] = pd.to_datetime(export_data['periodEndDate'])
        export_data['country_name'] = export_data['entityName'].map(ENTITY_TO_COUNTRY)
        
        # フィルター条件を適用
        if dataset_config['metric_type']:
            export_data = export_data[export_data['metricType'] == dataset_config['metric_type']]
        
        if dataset_config['metric_filter'] == "!=all topics":
            export_data = export_data[export_data['metric'] != 'all topics']
        elif dataset_config['metric_filter'] != "all":
            export_data = export_data[export_data['metric'] == dataset_config['metric_filter']]
        
        if dataset_config['speaker_filter'] == "!=all speakers":
            export_data = export_data[export_data['setName'] != 'all speakers']
        elif dataset_config['speaker_filter'] != "all":
            export_data = export_data[export_data['setName'] == dataset_config['speaker_filter']]
        
        if dataset_config['doc_filter'] != "all":
            export_data = export_data[export_data['documentType'] == dataset_config['doc_filter']]
        
        if not export_data.empty:
            # データプレビュー
            st.markdown("---")
            st.markdown("### 📋 データプレビュー")
            
            # 統計情報カード
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("""
                <div style='background: #f0f7ff; padding: 15px; border-radius: 8px; border-left: 4px solid #2196F3;'>
                    <p style='margin: 0; color: #666; font-size: 0.9em;'>データ件数</p>
                    <h2 style='margin: 5px 0 0 0; color: #2196F3;'>{:,}</h2>
                </div>
                """.format(len(export_data)), unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div style='background: #f0fff4; padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50;'>
                    <p style='margin: 0; color: #666; font-size: 0.9em;'>平均スコア</p>
                    <h2 style='margin: 5px 0 0 0; color: #4CAF50;'>{:.4f}</h2>
                </div>
                """.format(export_data['metricValue'].mean()), unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div style='background: #fff9f0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF9800;'>
                    <p style='margin: 0; color: #666; font-size: 0.9em;'>最高スコア</p>
                    <h2 style='margin: 5px 0 0 0; color: #FF9800;'>{:.4f}</h2>
                </div>
                """.format(export_data['metricValue'].max()), unsafe_allow_html=True)
            
            with col4:
                st.markdown("""
                <div style='background: #fff0f0; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336;'>
                    <p style='margin: 0; color: #666; font-size: 0.9em;'>最低スコア</p>
                    <h2 style='margin: 5px 0 0 0; color: #f44336;'>{:.4f}</h2>
                </div>
                """.format(export_data['metricValue'].min()), unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # データテーブル表示
            display_cols = ['periodEndDate', 'entityName', 'country_name', 'metric', 'metricType', 
                            'metricValue', 'setName', 'documentType']
            available_display_cols = [col for col in display_cols if col in export_data.columns]
            
            # 表示用に列名を日本語化
            col_rename = {
                'periodEndDate': '日付',
                'entityName': '中央銀行',
                'country_name': '国',
                'metric': 'トピック',
                'metricType': 'タイプ',
                'metricValue': 'スコア',
                'setName': 'スピーカー',
                'documentType': 'ドキュメント'
            }
            
            preview_data = export_data[available_display_cols].copy()
            preview_data = preview_data.rename(columns=col_rename)
            preview_data = preview_data.sort_values('日付', ascending=False)
            
            # ページネーション付きデータ表示
            items_per_page = 50
            total_pages = (len(preview_data) - 1) // items_per_page + 1
            
            col_page1, col_page2, col_page3 = st.columns([1, 2, 1])
            with col_page2:
                page_number = st.number_input(
                    f"ページ (全{total_pages}ページ)",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1
                )
            
            start_idx = (page_number - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(preview_data))
            
            st.dataframe(
                preview_data.iloc[start_idx:end_idx],
                use_container_width=True,
                height=600
            )
            
            st.caption(f"表示中: {start_idx + 1} - {end_idx} / {len(preview_data)} 件")
            
            # ダウンロードセクション
            st.markdown("---")
            st.markdown("### 💾 ダウンロード")
            
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            
            with col_dl1:
                csv_export = export_data[available_display_cols].to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 CSV ダウンロード",
                    data=csv_export,
                    file_name=f"{selected_dataset.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )
            
            with col_dl2:
                try:
                    excel_buffer = __import__('io').BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        export_data[available_display_cols].to_excel(writer, sheet_name='Data', index=False)
                    excel_buffer.seek(0)
                    st.download_button(
                        label="📊 Excel ダウンロード",
                        data=excel_buffer.getvalue(),
                        file_name=f"{selected_dataset.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="secondary"
                    )
                except Exception as e:
                    st.button("📊 Excel ダウンロード", disabled=True, use_container_width=True, 
                            help="openpyxlが必要です: pip install openpyxl")
            
            with col_dl3:
                json_export = export_data[available_display_cols].to_json(orient='records', indent=2, force_ascii=False)
                st.download_button(
                    label="📋 JSON ダウンロード",
                    data=json_export,
                    file_name=f"{selected_dataset.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            # データ説明
            with st.expander("📖 データ項目の説明"):
                st.markdown("""
                | 項目 | 説明 |
                |------|------|
                | **日付** | periodEndDate - データの期間終了日 |
                | **中央銀行** | entityName - 対象の中央銀行名 |
                | **国** | 中央銀行の所在国 |
                | **トピック** | metric - センチメント分析のトピック |
                | **タイプ** | metricType - smoothed/unsmoothed |
                | **スコア** | metricValue - センチメントスコア値 |
                | **スピーカー** | setName - 発言者名 |
                | **ドキュメント** | documentType - 文書の種類 |
                """)
        else:
            st.warning("⚠️ 選択した条件に該当するデータがありません")


def run_app():
    """
    アプリケーション実行関数：モード選択で分岐
    """
    # session stateの初期化
    if 'app_mode' not in st.session_state:
        st.session_state['app_mode'] = 'home'
    
    # アプリモード選択
    if st.session_state['app_mode'] == 'home':
        show_home_screen()
    elif st.session_state['app_mode'] == 'sentiment':
        # サイドバーに戻るボタンを配置
        with st.sidebar:
            st.markdown("---")
            if st.button("🏠 ホームに戻る", use_container_width=True, type="secondary"):
                st.session_state['app_mode'] = 'home'
                st.rerun()
        
        # Sentiment ダッシュボード表示
        show_sentiment_dashboard()
    elif st.session_state['app_mode'] == 'nowcasting':
        # Nowcasting ダッシュボード を実装
        try:
            from nowcasting_app import show_nowcasting_dashboard
            show_nowcasting_dashboard()
        except Exception as e:
            st.error(f"❌ Nowcasting モジュールの読み込みエラー: {str(e)}")


if __name__ == "__main__":
    run_app()
