"""
UBS Nowcasting Dashboard Module
経済指標の予測値と実績値を比較分析するモジュール
"""

import streamlit as st
import pandas as pd
import requests
import json
import time
import plotly.graph_objects as go
import plotly.express as px
import re
from datetime import datetime, timedelta, date
import os
import warnings
from urllib3.exceptions import InsecureRequestWarning
import numpy as np

# 不要な警告を抑制
warnings.simplefilter('ignore', InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Failed to patch SSL settings')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# プロキシの設定
os.environ["http_proxy"] = "http://10.7.0.165:8080"
os.environ["https_proxy"] = "http://10.7.0.165:8080"

# APIトークンの読み込み
with open("API key.txt", "r") as f:
    token = f.read().strip()

# Nowcasting指標のマッピング
NOWCASTING_METRICS = {
    'ubs_nowcast_auto_saar': 'Auto SAAR（自動車売上）',
    'ubs_nowcast_ism_manufacturing': 'ISM Manufacturing（製造業）',
    'ubs_nowcast_industrial_production': 'Industrial Production（鉱工業生産）',
    'ubs_nowcast_payrolls': 'Payrolls（雇用統計）',
    'ubs_nowcast_cpi': 'CPI（消費者物価指数）',
    'ubs_nowcast_pce': 'PCE（個人消費支出）',
    'ubs_nowcast_consumer_spending': 'Consumer Spending（消費支出）',
    'ubs_nowcast_initial_jobless_claims': 'Initial Jobless Claims（失業保険申請）',
}

# データセットラベル
DATASET_LABELS = {
    'UBS Evidence Lab Nowcasting': 'UBS Nowcasting（予測値）',
    'Actual: Official Release': '実績値（公式発表）'
}

# メトリック表示名マッピング（詳細）
METRIC_DISPLAY_MAPPING = {
    'ubs_nowcast_auto_saar': 'Auto SAAR',
    'ubs_nowcast_auto_saar_mm': 'Auto SAAR (M/M)',
    'ubs_nowcast_ism': 'ISM Manufacturing',
    'ubs_nowcast_ism_manufacturing': 'ISM Manufacturing',
    'ubs_nowcast_payrolls': 'Payrolls',
    'ubs_nowcast_industrial_production': 'Industrial Production (Y/Y)',
    'ubs_nowcast_cpi_overall': 'Overall CPI',
    'ubs_nowcast_cpi_core': 'Core CPI',
    'ubs_nowcast_cpi_rent': 'Primary Rent CPI',
    'ubs_nowcast_cpi_new_car': 'New Car CPI',
    'ubs_nowcast_cpi_used_car': 'Used Car CPI',
    'ubs_nowcast_cpi_lodging': 'Lodging CPI',
    'ubs_nowcast_cpi_airfare': 'Airfares CPI',
    'ubs_nowcast_cpi_energy': 'Energy CPI',
    'ubs_nowcast_private_construction': 'Private Construction (M/M)',
    'first_official_report_auto_saar_mm': 'Auto SAAR (M/M) - Official',
    'first_official_report_cpi_energy': 'Energy CPI - Official',
    'first_official_report_cpi_airfare': 'Airfares CPI - Official',
    'first_official_report_cpi_lodge': 'Lodging CPI - Official',
    'first_official_report_cpi_used_car': 'Used Car CPI - Official',
    'first_official_report_cpi_new_car': 'New Car CPI - Official',
    'first_official_report_cpi_rent': 'Primary Rent CPI - Official',
    'first_official_report_cpi_core': 'Core CPI - Official',
    'first_official_report_cpi': 'Overall CPI - Official',
    'first_official_report_payrolls': 'Payrolls - Official',
    'first_official_report_industrial_production': 'Industrial Production (Y/Y) - Official',
}

# 日本語表示名マッピング（プルダウン用）
METRIC_JAPANESE_NAMES = {
    'ubs_nowcast_auto_saar': '自動車売上（年率換算）',
    'ubs_nowcast_auto_saar_mm': '自動車売上（月比）',
    'ubs_nowcast_ism': 'ISM製造業指数',
    'ubs_nowcast_ism_manufacturing': 'ISM製造業指数',
    'ubs_nowcast_payrolls': '非農業部門雇用者数',
    'ubs_nowcast_nfp': '非農業部門雇用者数',
    'ubs_nowcast_industrial_production': '鉱工業生産（前年比）',
    'ubs_nowcast_cpi_overall': '総合CPI',
    'ubs_nowcast_cpi': '総合CPI',
    'ubs_nowcast_cpi_core': 'コアCPI',
    'ubs_nowcast_core_cpi': 'コアCPI',
    'ubs_nowcast_cpi_rent': 'プライマリレント',
    'ubs_nowcast_cpi_new_car': '新車CPI',
    'ubs_nowcast_cpi_used_car': '中古車CPI',
    'ubs_nowcast_cpi_lodging': '宿泊料金CPI',
    'ubs_nowcast_cpi_lodge': '宿泊料金CPI',
    'ubs_nowcast_cpi_airfare': '航空運賃CPI',
    'ubs_nowcast_cpi_energy': 'エネルギーCPI',
    'ubs_nowcast_private_construction': '民間建設支出（月比）',
    'ubs_nowcast_prvt_const': '民間建設支出（月比）',
    'first_official_report_auto_saar_mm': '自動車売上（月比）- 実績',
    'first_official_report_auto_saar': '自動車売上（年率換算）- 実績',
    'first_official_report_cpi_energy': 'エネルギーCPI - 実績',
    'first_official_report_cpi_airfare': '航空運賃CPI - 実績',
    'first_official_report_cpi_lodge': '宿泊料金CPI - 実績',
    'first_official_report_cpi_used_car': '中古車CPI - 実績',
    'first_official_report_cpi_new_car': '新車CPI - 実績',
    'first_official_report_cpi_rent': 'プライマリレント - 実績',
    'first_official_report_cpi_core': 'コアCPI - 実績',
    'first_official_report_core_cpi': 'コアCPI - 実績',
    'first_official_report_cpi': '総合CPI - 実績',
    'first_official_report_payrolls': '非農業部門雇用者数 - 実績',
    'first_official_report_nfp': '非農業部門雇用者数 - 実績',
    'first_official_report_prvt_const': '民間建設支出 - 実績',
    'first_official_report_ism': 'ISM製造業指数 - 実績',
    'first_official_report_industrial_production': '鉱工業生産（前年比）- 実績',
}


class NowcastingClient:
    """UBS Nowcasting API クライアント"""
    
    def __init__(self, token):
        self.server = "https://neo.ubs.com/api/evidence-lab/api-framework"
        self.proxy = {
            "http": os.environ.get("http_proxy"),
            "https": os.environ.get("https_proxy")
        }
        self.proxy = {k: v for k, v in self.proxy.items() if v}
        self.token = token
    
    def get_headers(self):
        """リクエストヘッダーを取得"""
        return {
            "authorization": f"Bearer {self.token}",
            "content-type": "application/json",
            "Accept": "application/json"
        }
    
    def post(self, endpoint, payload=None):
        """POST リクエストを実行"""
        url = f"{self.server}/{endpoint}"
        headers = self.get_headers()
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                proxies=self.proxy if self.proxy else None,
                timeout=30,
                verify=False
            )
            return self.handle_response(response)
        except Exception as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def validate_response(self, response):
        """レスポンスを検証"""
        if response.status_code == 401:
            raise Exception("Authentication failed - Invalid API key")
        if response.status_code == 403:
            raise Exception("API not found")
        if response.status_code >= 400:
            try:
                data = response.json()
                error_msg = data.get("message", str(response.text))
            except:
                error_msg = response.text
            raise Exception(f"HTTP {response.status_code}: {error_msg}")
        if response.status_code == 200 and 'HTML' in response.text:
            raise Exception("Invalid credentials")
    
    def handle_response(self, response):
        """レスポンスを処理"""
        self.validate_response(response)
        data = response.json()
        return data


def fetch_nowcasting_data(client, metrics=None, start_date_str=None, end_date_str=None):
    """
    Nowcasting データを取得
    
    Parameters:
    -----------
    client : NowcastingClient
        APIクライアント
    metrics : list
        取得する指標のリスト
    start_date_str : str
        開始日（YYYY-MM-DD形式）
    end_date_str : str
        終了日（YYYY-MM-DD形式）
    
    Returns:
    --------
    pd.DataFrame
        取得したNowcastingデータ
    """
    # 日付が指定されない場合はデフォルト値を使用
    if start_date_str is None:
        start_date_str = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
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
    
    # エンドポイント（dataAssetKey=10441を含める）
    endpoint = "us-nowcasting/default/v2/data?dataAssetKey=10441"
    
    df = pd.DataFrame()
    
    # ページネーションで全データを取得
    status_container = st.container()
    start_time = time.time()
    
    with status_container:
        status_text = st.empty()
        metric_col1, metric_col2 = st.columns(2)
        total_records_display = metric_col1.empty()
        elapsed_time_display = metric_col2.empty()
    
    try:
        # 最初のリクエスト
        data = client.post(endpoint=endpoint, payload=filter_dict)
        
        if 'results' in data and len(data['results']) > 0:
            df = pd.json_normalize(data['results'])
            elapsed = time.time() - start_time
            
            # リアルタイムで取得件数を表示
            with status_container:
                status_text.info(f"📥 データ取得中...")
                total_records_display.metric("📊 取得済み件数", f"{len(df):,}")
                elapsed_time_display.metric("⏱️ 経過時間", f"{elapsed:.1f}秒")
        
        # ページネーション：nextエンドポイントがあれば続行
        while 'meta' in data and 'next' in data['meta'] and data['meta']['next']:
            next_endpoint = data['meta']['next'].replace(client.server, '')
            data = client.post(endpoint=next_endpoint, payload=filter_dict)
            
            if 'results' in data and len(data['results']) > 0:
                df_page = pd.json_normalize(data['results'])
                df = pd.concat([df, df_page], ignore_index=True)
                elapsed = time.time() - start_time
                
                # リアルタイムで取得件数を表示
                with status_container:
                    status_text.info(f"📥 データ取得中...")
                    total_records_display.metric("📊 取得済み件数", f"{len(df):,}")
                    elapsed_time_display.metric("⏱️ 経過時間", f"{elapsed:.1f}秒")
                
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


def process_nowcasting_data(df):
    """
    取得したNowcastingデータを処理
    """
    if df.empty:
        return None
    
    # 日付列を datetime に変換
    # 数値（ミリ秒）または文字列（ISO形式）の両方に対応
    def convert_timestamp(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            # ミリ秒単位の整数の場合
            return pd.to_datetime(val, unit='ms')
        else:
            # 文字列の場合
            try:
                return pd.to_datetime(val)
            except:
                return None
    
    df['periodEndDate'] = df['periodEndDate'].apply(convert_timestamp)
    df['nowcastEffectiveDate'] = df['nowcastEffectiveDate'].apply(convert_timestamp)
    
    # モジュールレベルの METRIC_DISPLAY_MAPPING を使用
    df['metric_display_name'] = df['metricName'].map(METRIC_DISPLAY_MAPPING).fillna(df['metricName'])
    
    # データセット分類（metricName から判定）
    df['dataset_type'] = df['metricName'].apply(
        lambda x: 'UBS Nowcasting' if 'ubs_nowcast' in x.lower() else 'Official Release'
    )
    
    return df


def normalize_base_metric(metric_name):
    """Base metricを抽出"""
    if not isinstance(metric_name, str):
        return metric_name

    base = metric_name.lower()
    if base.startswith('ubs_nowcast_'):
        base = base.replace('ubs_nowcast_', '', 1)
    base = re.sub(r'_(mm|yy|y)$', '', base)
    return base


def format_base_metric_name(base_metric):
    """表示名のフォーマット"""
    if not isinstance(base_metric, str):
        return base_metric

    candidate = f"ubs_nowcast_{base_metric}"
    return (
        METRIC_JAPANESE_NAMES.get(candidate)
        or METRIC_DISPLAY_MAPPING.get(candidate)
        or NOWCASTING_METRICS.get(candidate)
        or base_metric.replace('_', ' ').title()
    )


def get_latest_nowcast_timestamps(df):
    """各Nowcasting指標の最新periodEndDateを抽出"""
    if df is None or df.empty:
        return pd.DataFrame()

    nowcast_df = df[df['metricName'].str.contains('ubs_nowcast_', case=False, na=False)].copy()
    if nowcast_df.empty:
        return pd.DataFrame()

    nowcast_df['periodEndDate'] = pd.to_datetime(nowcast_df['periodEndDate'], errors='coerce')
    nowcast_df['nowcastEffectiveDate'] = pd.to_datetime(nowcast_df.get('nowcastEffectiveDate'), errors='coerce')
    nowcast_df = nowcast_df.dropna(subset=['periodEndDate'])
    if nowcast_df.empty:
        return pd.DataFrame()

    nowcast_df['base_metric'] = nowcast_df['metricName'].apply(normalize_base_metric)
    summary = (
        nowcast_df.groupby('base_metric').agg(
            latest_period=('periodEndDate', 'max'),
            latest_release=('nowcastEffectiveDate', 'max')
        )
        .reset_index()
    )

    summary['指標'] = summary['base_metric'].apply(format_base_metric_name)
    summary['期間終了日'] = summary['latest_period'].dt.strftime('%Y-%m-%d').fillna('N/A')
    summary['リリース日'] = summary['latest_release'].dt.strftime('%Y-%m-%d').fillna('N/A')
    result = summary[['指標', 'リリース日', '期間終了日']].sort_values('指標')
    result = result.set_index('指標')
    return result


def get_format_function(metric_name):
    """
    指標に応じた値のフォーマット関数を返す
    """
    metric_lower = metric_name.lower()
    
    # CPI関連は小数点第2位のパーセンテージで表示
    if 'cpi' in metric_lower or 'rent' in metric_lower or 'energy' in metric_lower or \
       'airfare' in metric_lower or 'lodge' in metric_lower or 'car' in metric_lower or \
       'const' in metric_lower:
        return lambda x: f"{x*100:.2f}%" if not pd.isna(x) else "N/A"
    
    # ISM、NFP、Auto SAARは通常の小数点表示
    else:
        return lambda x: f"{x:.2f}" if not pd.isna(x) else "N/A"


def get_hover_format(metric_name, value):
    """
    ホバー表示用のフォーマット
    """
    metric_lower = metric_name.lower()
    
    if 'cpi' in metric_lower or 'rent' in metric_lower or 'energy' in metric_lower or \
       'airfare' in metric_lower or 'lodge' in metric_lower or 'car' in metric_lower or \
       'const' in metric_lower:
        return f"{value*100:.2f}%"
    else:
        return f"{value:.2f}"


def get_y_axis_title(metric_name):
    """
    メトリクスに応じたY軸タイトルを取得
    
    Parameters:
    -----------
    metric_name : str
        メトリクス名（ベース名）
        
    Returns:
    --------
    str
        Y軸に表示するタイトル
    """
    metric_lower = metric_name.lower()
    
    # NFP・雇用者数
    if 'nfp' in metric_lower or 'payroll' in metric_lower:
        return "雇用者数（千人）"
    # ISM指数
    elif 'ism' in metric_lower:
        return "ISM指数"
    # 自動車販売（M/M変化率）
    elif 'auto_saar_mm' in metric_lower:
        return "変化率 (%)"
    # 自動車販売（年率換算）
    elif 'auto_saar' in metric_lower or 'auto' in metric_lower:
        return "自動車販売（百万台SAAR）"
    # 民間建設支出（変化率）
    elif 'const' in metric_lower or 'housing' in metric_lower or 'prvt_const' in metric_lower:
        return "変化率 (%)"
    # 鉱工業生産
    elif 'ip' in metric_lower or 'industrial' in metric_lower:
        return "変化率 (%)"
    # CPI関連
    elif 'cpi' in metric_lower or 'rent' in metric_lower or 'energy' in metric_lower or \
         'airfare' in metric_lower or 'lodge' in metric_lower or 'car' in metric_lower:
        return "変化率 (%)"
    else:
        return "値"


def get_y_axis_tickformat(metric_name):
    """
    メトリクスに応じたY軸目盛りフォーマットを取得
    
    Parameters:
    -----------
    metric_name : str
        メトリクス名（ベース名）
        
    Returns:
    --------
    str
        Plotlyのtickformat文字列
    """
    metric_lower = metric_name.lower()
    
    # パーセンテージフォーマット
    if 'cpi' in metric_lower or 'rent' in metric_lower or 'energy' in metric_lower or \
       'airfare' in metric_lower or 'lodge' in metric_lower or 'car' in metric_lower or \
       'ip' in metric_lower or 'industrial' in metric_lower or 'const' in metric_lower or \
       'prvt_const' in metric_lower or 'auto_saar_mm' in metric_lower:
        return ".2f%"
    else:
        # 通常の数値フォーマット
        return ".2f"


def create_comparison_chart(df_processed, selected_metric, selected_datasets):
    """
    Nowcasting vs 実績値の比較チャートを作成
    
    Parameters:
    -----------
    df_processed : pd.DataFrame
        処理済みデータ
    selected_metric : str
        選択された指標
    selected_datasets : list
        選択されたデータセット
    """
    if df_processed is None or df_processed.empty:
        st.error("表示するデータがありません")
        return
    
    # 指標でフィルター
    df_chart = df_processed[df_processed['metricName'] == selected_metric].copy()
    
    if df_chart.empty:
        st.error("選択した指標のデータがありません")
        return
    
    # dataAssetKey を確認
    available_keys = df_chart['dataAssetKey'].unique()
    
    # データセットでフィルター
    filtered_datasets = []
    for dataset_key in selected_datasets:
        if int(dataset_key) in available_keys:
            filtered_datasets.append(int(dataset_key))
    
    if not filtered_datasets:
        st.error("選択したデータセットが利用できません")
        return
    
    df_chart = df_chart[df_chart['dataAssetKey'].isin(filtered_datasets)]
    
    if df_chart.empty:
        st.error("選択した条件に該当するデータがありません")
        return
    
    # dataAssetKey の値でラベルを作成
    # 実際のdataAssetKeyの値を確認して適切なマッピングを設定
    dataset_mapping = {}
    for key in df_chart['dataAssetKey'].unique():
        # clientStudyNameがある場合はそれを使用
        if 'clientStudyName' in df_chart.columns:
            study_names = df_chart[df_chart['dataAssetKey'] == key]['clientStudyName'].unique()
            if len(study_names) > 0:
                dataset_mapping[key] = study_names[0]
            else:
                dataset_mapping[key] = f"Dataset {key}"
        else:
            if key == 10488 or str(key).endswith('88'):
                dataset_mapping[key] = 'UBS Nowcasting（予測値）'
            elif key == 10489 or str(key).endswith('89'):
                dataset_mapping[key] = '実績値（公式発表）'
            else:
                dataset_mapping[key] = f"Dataset {key}"
    
    df_chart['dataset_label'] = df_chart['dataAssetKey'].map(dataset_mapping)
    
    # 日付でソート
    df_chart = df_chart.sort_values('periodEndDate')
    
    # チャートを作成
    fig = px.line(
        df_chart,
        x='periodEndDate',
        y='metricValue',
        color='dataset_label',
        color_discrete_map={
            'UBS Nowcasting（予測値）': '#1f77b4',
            '実績値（公式発表）': '#a0503f'
        },
        title=f"{NOWCASTING_METRICS.get(selected_metric, selected_metric)}",
        labels={
            'periodEndDate': 'Date',
            'metricValue': 'Value',
            'dataset_label': 'Dataset'
        },
        markers=False,
        height=600
    )
    
    # ラインスタイルを設定
    for i, trace in enumerate(fig.data):
        if 'Nowcasting' in trace.name:
            trace.line.width = 2
            trace.line.color = '#1f77b4'
        else:
            trace.line.width = 2
            trace.line.color = '#a0503f'
    
    fig.update_layout(
        hovermode='x unified',
        xaxis=dict(
            title="",
            tickformat="%b '%y",
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 0, 0, 0.05)',
            zeroline=False
        ),
        yaxis=dict(
            title="",
            tickformat=".1%",
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 0, 0, 0.05)',
            zeroline=True,
            zerolinecolor='rgba(0, 0, 0, 0.2)',
            zerolinewidth=1
        ),
        font=dict(size=11, family="Arial, sans-serif"),
        template="plotly_white",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=70, r=60, t=60, b=60),
        legend=dict(
            x=0.0,
            y=0.98,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='rgba(0, 0, 0, 0.2)',
            borderwidth=1,
            xanchor='left',
            yanchor='top'
        ),
        title=dict(
            text=f"{NOWCASTING_METRICS.get(selected_metric, selected_metric)}",
            x=0.0,
            xanchor='left',
            font=dict(size=14, color='#1a1a1a')
        ),
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 統計情報
    st.markdown("---")
    st.subheader("📊 統計情報")
    
    col1, col2, col3 = st.columns(3)
    
    # データセット別の統計
    dataset_names = sorted(df_chart['dataset_label'].unique())
    
    for idx, dataset_label in enumerate(dataset_names):
        dataset_data = df_chart[df_chart['dataset_label'] == dataset_label]['metricValue']
        
        if not dataset_data.empty:
            latest_value = dataset_data.iloc[-1]
            change = latest_value - dataset_data.iloc[-2] if len(dataset_data) > 1 else None
            
            if idx == 0:
                with col1:
                    st.metric(
                        dataset_label,
                        f"{latest_value:.2f}",
                        f"{change:.2f}" if change else None
                    )
            elif idx == 1:
                with col2:
                    st.metric(
                        dataset_label,
                        f"{latest_value:.2f}",
                        f"{change:.2f}" if change else None
                    )
    
    # 精度（最新値の差）
    if len(dataset_names) >= 2:
        nowcast_data = df_chart[df_chart['dataset_label'].str.contains('予測値|Nowcasting', na=False)]['metricValue']
        actual_data = df_chart[df_chart['dataset_label'].str.contains('実績値|Actual', na=False)]['metricValue']
        
        if len(nowcast_data) > 0 and len(actual_data) > 0:
            latest_diff = abs(nowcast_data.iloc[-1] - actual_data.iloc[-1])
            with col3:
                st.metric("予測誤差（最新）", f"{latest_diff:.2f}")


def show_nowcasting_dashboard():
    """
    Nowcasting ダッシュボード（メイン関数）
    """
    # カスタムCSS
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
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📈 UBS Nowcasting Dashboard")
    
    # サイドバーのヘッダー
    st.sidebar.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem; text-align: center;'>
        <span style='color: white; font-weight: 700; font-size: 1.1rem;'>
        📈 Nowcasting Dashboard
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("🏠 ホームに戻る", use_container_width=True, type="secondary", key="back_to_home_nowcast"):
        st.session_state['app_mode'] = 'home'
        st.rerun()
    
    st.sidebar.markdown("---")
    
    try:
        # APIクライアント初期化
        client = NowcastingClient(token)
        
        # キャッシュの初期化
        if 'df_nowcast_cached' not in st.session_state:
            st.session_state.df_nowcast_cached = None
        if 'df_nowcast_processed' not in st.session_state:
            st.session_state.df_nowcast_processed = None
        
        # サイドバー：データ取得設定
        st.sidebar.header("📥 データ取得設定")
        
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
                value=today - timedelta(days=180),
                min_value=date(2020, 1, 1),
                max_value=today,
                key="nowcast_load_start_date"
            )
        
        start_date_str = start_date_load.strftime("%Y-%m-%d")
        inclusive_end_date = today + timedelta(days=40)
        end_date_str = inclusive_end_date.strftime("%Y-%m-%d")
        
        st.sidebar.markdown("---")
        
        # データ取得ボタン
        if st.sidebar.button("📥 データを取得", type="primary", use_container_width=True, key="fetch_nowcast"):
            try:
                with st.spinner("📥 Nowcasting データを取得中..."):
                    df_nowcast = fetch_nowcasting_data(
                        client,
                        start_date_str=start_date_str,
                        end_date_str=end_date_str
                    )
                    
                    if not df_nowcast.empty:
                        st.session_state.df_nowcast_cached = df_nowcast
                        st.session_state.df_nowcast_processed = process_nowcasting_data(df_nowcast)
                        st.success("✅ データ取得完了")
                    else:
                        st.warning("⚠️ 取得するデータがありません")
            
            except Exception as e:
                st.error(f"❌ エラーが発生しました: {str(e)}")
        
        st.sidebar.markdown("---")

        if st.session_state.df_nowcast_processed is not None and not st.session_state.df_nowcast_processed.empty:
            latest_table = get_latest_nowcast_timestamps(st.session_state.df_nowcast_processed)
            if not latest_table.empty:
                st.sidebar.markdown("### 最新Nowcasting更新時刻")
                st.sidebar.table(latest_table)
                st.sidebar.markdown("---")

        # メインエリア
        if st.session_state.df_nowcast_processed is None or st.session_state.df_nowcast_processed.empty:
            st.info("📊 左のサイドバーからデータを取得してください")
            
            # メソドロジーセクション
            
            with st.expander("📖 Nowcasting メソドロジー"):
                st.markdown("""
                    ### Nowcasting（ナウキャスティング）とは？
                    マクロ経済学者は、GDPのような経済指標について、定期的に公表される各種データの発表に応じて予測するモデルを開発してきました。  
                    アトランタ連銀はこの手法を用いて、**公式GDPが発表される前にGDPのNowcast（予測）**を提示しています。これは、**当該四半期に利用可能なデータに基づく実質GDP成長率の「逐次更新される推定値」**として捉えるのが適切です。

                    UBS Evidence Labも同様のアプローチを採用していますが、**非伝統的（従来型ではない）データセット**を取り入れることで、政府の公式発表サイクルに必ずしも連動しない複数の主要指標について暫定推計を行い、**足元の経済状況をよりタイムリーに把握できる示唆**を提供します。

                    ---

                    ### UBS Evidence Lab Nowcastingとは？
                    **非伝統的なビッグデータ**を取り入れ、政府の公式統計の発表サイクルに縛られず（多くの場合、公式発表より数週間早く）、米国の主要経済指標のNowcast（推定値）を作成します。  
                    Evidence Labは、次の**7つの主要経済指標**について暫定推計を提供します。

                    - **1) ISM Manufacturing**（ISM製造業景況指数）
                    - **2) Auto SAAR**（自動車SAAR：年率換算販売台数）
                    - **3) Retail Sales (ex-gas, ex-auto)**（小売売上高：ガソリン除く・自動車除く）
                    - **4) Nonfarm payrolls**（非農業部門雇用者数）
                    - **5) Private Construction Spending**（民間建設支出）
                    - **6) CPI**（消費者物価指数）
                    - **7) Core CPI**（コアCPI）

                    ---

                    ### 推計値のタイミング（いつ作る？）
                    当月の経済指標についての**暫定Nowcast**は、**毎月おおむね25日ごろ**に作成されます。  
                    この推計は、**当月前半に観測された経済活動**に基づいています。

                    ---

                    ### どのような「非伝統的ビッグデータ」を使う？
                    各指標に対応する経済状況を表現するために、次のデータを活用します。

                    - **UBS独自（プロプライエタリ）のデータ基盤**
                    - **迅速に入手できる政府データ**
                    - **第三者による業界データ**  
                    例：消費支出、各種サーベイ、トラック輸送関連データ等

                    """)       
        else:
            df_processed = st.session_state.df_nowcast_processed
            
            # タブナビゲーション
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            if 'nowcast_tab' not in st.session_state:
                st.session_state.nowcast_tab = 0
            
            with col1:
                if st.button("📈 チャート分析", use_container_width=True, 
                           type="primary" if st.session_state.nowcast_tab == 0 else "secondary",
                           key="tab_chart"):
                    st.session_state.nowcast_tab = 0
                    st.rerun()
            
            with col2:
                if st.button("📊 統計情報", use_container_width=True,
                           type="primary" if st.session_state.nowcast_tab == 1 else "secondary",
                           key="tab_stats"):
                    st.session_state.nowcast_tab = 1
                    st.rerun()
            
            with col3:
                if st.button("🥧 CPI寄与度", use_container_width=True,
                           type="primary" if st.session_state.nowcast_tab == 2 else "secondary",
                           key="tab_cpi_contrib"):
                    st.session_state.nowcast_tab = 2
                    st.rerun()
            
            with col4:
                if st.button("📥 データ一括出力", use_container_width=True,
                           type="primary" if st.session_state.nowcast_tab == 3 else "secondary",
                           key="tab_export"):
                    st.session_state.nowcast_tab = 3
                    st.rerun()
            
            st.markdown("---")
            
            # タブ 0: チャート分析
            if st.session_state.nowcast_tab == 0:
                # データセット選択
                st.subheader("📋 データセット選択")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    show_nowcast = st.checkbox(
                        "UBS Evidence Lab Nowcasting（予測値）",
                        value=True,
                        key="cb_nowcast"
                    )
                
                with col2:
                    show_actual = st.checkbox(
                        "Official Release（実績値）",
                        value=True,
                        key="cb_actual"
                    )
                
                st.markdown("---")
                
                # チャート表示
                st.subheader("📈 Nowcasting vs 実績値")
                
                # 利用可能な指標を取得（base metricNameのリスト）
                available_metrics = sorted(df_processed['metricName'].unique())
                
                # Base metricNameを抽出
                base_metrics = set()
                for metric in available_metrics:
                    if 'ubs_nowcast_' in metric:
                        base = metric.replace('ubs_nowcast_', '').replace('_mm', '').replace('_yy', '')
                        base_metrics.add(base)
                
                base_metrics = sorted(base_metrics)
                
                # メトリック選択
                st.subheader("📊 指標選択")
                
                # Base metricのリスト表示（日本語）
                selected_base_metric = st.selectbox(
                    "分析する指標を選択",
                    base_metrics,
                    key="select_base_metric",
                    format_func=lambda x: METRIC_JAPANESE_NAMES.get(f'ubs_nowcast_{x}', x)
                )
                
                st.markdown("---")
                
                # フィルター適用：選択したbase metricに関連するすべてのメトリックを取得
                df_chart = df_processed[
                    df_processed['metricName'].str.contains(selected_base_metric, case=False, na=False)
                ].copy()
                
                # データセットフィルター適用
                if show_nowcast and not show_actual:
                    df_chart = df_chart[df_chart['dataset_type'] == 'UBS Nowcasting']
                elif show_actual and not show_nowcast:
                    df_chart = df_chart[df_chart['dataset_type'] == 'Official Release']
                
                if df_chart.empty:
                    st.error("選択した指標のデータがありません")
                else:
                    # 同じbase metricに複数のメトリック変数がある場合、それぞれのグラフを作成
                    metric_groups = {}
                    for metric_name in sorted(df_chart['metricName'].unique()):
                        # 変数型を判定（_mm, _yy など）
                        var_type = 'Base'
                        if '_mm' in metric_name:
                            var_type = 'Month-over-Month'
                        elif '_yy' in metric_name or '_y' in metric_name:
                            var_type = 'Year-over-Year'
                        
                        if var_type not in metric_groups:
                            metric_groups[var_type] = []
                        metric_groups[var_type].append(metric_name)
                    
                    # 各グラフを作成
                    for var_type in sorted(metric_groups.keys()):
                        metrics_in_group = metric_groups[var_type]
                        
                        # このグループのデータを取得
                        group_data = df_chart[df_chart['metricName'].isin(metrics_in_group)].copy()
                        
                        if group_data['metricValue'].notna().sum() > 0:
                            # 総合CPI (cpi) の場合は特別処理
                            is_overall_cpi = selected_base_metric == 'cpi' and var_type == 'Base'
                            
                            # グラフを作成
                            fig = go.Figure()
                            
                            # メトリック別に色を設定
                            colors = {'UBS Nowcasting': '#1f77b4', 'Official Release': '#a0503f'}
                            
                            # グループの代表メトリクス名を取得（Y軸タイトル決定用）
                            group_metric_name = metrics_in_group[0] if metrics_in_group else selected_base_metric
                            
                            if is_overall_cpi:
                                # 総合CPI: 折れ線グラフのみ
                                overall_metrics = [m for m in metrics_in_group if 'overall' in m or (m == 'ubs_nowcast_cpi' or m == 'first_official_report_cpi')]
                                
                                for metric_name in overall_metrics:
                                    metric_data = group_data[group_data['metricName'] == metric_name].sort_values('periodEndDate')
                                    
                                    if metric_data['metricValue'].notna().sum() > 0:
                                        dataset_type = metric_data['dataset_type'].iloc[0]
                                        metric_display = metric_data['metric_display_name'].iloc[0]
                                        
                                        # Y軸フォーマット（CPI系はパーセンテージ）
                                        y_values = metric_data['metricValue'] * 100
                                        
                                        fig.add_trace(go.Scatter(
                                            x=metric_data['periodEndDate'],
                                            y=y_values,
                                            mode='lines',
                                            name=metric_display,
                                            line=dict(
                                                width=3,
                                                color=colors.get(dataset_type, '#1f77b4')
                                            ),
                                            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%b %Y}<br>Value: %{y:.2f}%<extra></extra>'
                                        ))
                                
                                # グラフスタイルを設定
                                fig.update_layout(
                                    title=dict(
                                        text=f"{METRIC_JAPANESE_NAMES.get(f'ubs_nowcast_{selected_base_metric}', selected_base_metric)}",
                                        x=0.0,
                                        xanchor='left',
                                        font=dict(size=14, color='#1a1a1a')
                                    ),
                                    hovermode='x unified',
                                    xaxis=dict(
                                        title="",
                                        tickformat="%y/%m/%d",
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=False
                                    ),
                                    yaxis=dict(
                                        title="変化率 (%)",
                                        tickformat=".2f%",
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=True,
                                        zerolinecolor='rgba(0, 0, 0, 0.2)',
                                        zerolinewidth=1
                                    ),
                                    font=dict(size=11, family="Arial, sans-serif"),
                                    template="plotly_white",
                                    plot_bgcolor="white",
                                    paper_bgcolor="white",
                                    margin=dict(l=70, r=60, t=60, b=60),
                                    legend=dict(
                                        x=0.0,
                                        y=0.98,
                                        bgcolor='rgba(255, 255, 255, 0.8)',
                                        bordercolor='rgba(0, 0, 0, 0.2)',
                                        borderwidth=1,
                                        xanchor='left',
                                        yanchor='top'
                                    ),
                                    height=600,
                                    showlegend=True
                                )
                            else:
                                # その他の指標: 通常の折れ線グラフ
                                for metric_name in sorted(metrics_in_group):
                                    metric_data = group_data[group_data['metricName'] == metric_name].sort_values('periodEndDate')
                                    
                                    if metric_data['metricValue'].notna().sum() > 0:
                                        dataset_type = metric_data['dataset_type'].iloc[0]
                                        metric_display = metric_data['metric_display_name'].iloc[0]
                                        
                                        # Y軸フォーマット（CPI系はパーセンテージ）
                                        is_percentage = 'cpi' in metric_name.lower() or 'rent' in metric_name.lower() or \
                                                       'energy' in metric_name.lower() or 'airfare' in metric_name.lower() or \
                                                       'lodge' in metric_name.lower() or 'car' in metric_name.lower() or \
                                                       'const' in metric_name.lower()
                                        y_values = metric_data['metricValue'] * 100 if is_percentage else metric_data['metricValue']
                                        
                                        fig.add_trace(go.Scatter(
                                            x=metric_data['periodEndDate'],
                                            y=y_values,
                                            mode='lines',
                                            name=metric_display,
                                            line=dict(
                                                width=2,
                                                color=colors.get(dataset_type, '#1f77b4')
                                            ),
                                            hovertemplate='<b>%{fullData.name}</b><br>Date: %{x|%b %Y}<br>Value: ' + 
                                                        ('%{y:.2f}%' if is_percentage else '%{y:.2f}') + '<extra></extra>'
                                        ))
                                
                                # グラフスタイルを設定
                                fig.update_layout(
                                    title=dict(
                                        text=f"{METRIC_JAPANESE_NAMES.get(f'ubs_nowcast_{selected_base_metric}', selected_base_metric)}",
                                        x=0.0,
                                        xanchor='left',
                                        font=dict(size=14, color='#1a1a1a')
                                    ),
                                    hovermode='x unified',
                                    xaxis=dict(
                                        title="",
                                        tickformat="%y/%m/%d",
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=False
                                    ),
                                    yaxis=dict(
                                        title=get_y_axis_title(group_metric_name.replace('ubs_nowcast_', '').replace('first_official_report_', '')),
                                        tickformat=get_y_axis_tickformat(group_metric_name.replace('ubs_nowcast_', '').replace('first_official_report_', '')),
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=True,
                                        zerolinecolor='rgba(0, 0, 0, 0.2)',
                                        zerolinewidth=1
                                    ),
                                    font=dict(size=11, family="Arial, sans-serif"),
                                    template="plotly_white",
                                    plot_bgcolor="white",
                                    paper_bgcolor="white",
                                    margin=dict(l=70, r=60, t=60, b=60),
                                    legend=dict(
                                        x=0.0,
                                        y=0.98,
                                        bgcolor='rgba(255, 255, 255, 0.8)',
                                        bordercolor='rgba(0, 0, 0, 0.2)',
                                        borderwidth=1,
                                        xanchor='left',
                                        yanchor='top'
                                    ),
                                    height=600,
                                    showlegend=True
                                )
                            
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # 統計情報
                    st.markdown("---")
                    st.subheader("📊 統計情報")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    if not df_chart.empty:
                        valid_values = df_chart['metricValue'].dropna()
                        if len(valid_values) > 0:
                            with col1:
                                st.metric("最新値", f"{valid_values.iloc[-1]:.4f}")
                            with col2:
                                st.metric("平均値", f"{valid_values.mean():.4f}")
                            with col3:
                                st.metric("データ件数", len(valid_values))
            
            # タブ 1: 統計情報
            elif st.session_state.nowcast_tab == 1:
                st.subheader("📊 統計情報")
                
                # 統計指標の計算
                summary_stats = []
                
                for metric_name in sorted(df_processed['metricName'].unique()):
                    df_metric = df_processed[df_processed['metricName'] == metric_name]
                    
                    if not df_metric.empty:
                        values = df_metric['metricValue'].dropna()
                        
                        if len(values) > 0:
                            metric_display = df_metric['metric_display_name'].iloc[0]
                            dataset_type = df_metric['dataset_type'].iloc[0]
                            
                            summary_stats.append({
                                '指標': metric_display,
                                'データセット': dataset_type,
                                '最新値': values.iloc[-1],
                                '平均': values.mean(),
                                '最大': values.max(),
                                '最小': values.min(),
                                '標準偏差': values.std(),
                                'データ件数': len(values)
                            })
                
                if summary_stats:
                    stats_df = pd.DataFrame(summary_stats)
                    st.dataframe(stats_df, use_container_width=True, height=500)
                    
                    # ダウンロード
                    csv = stats_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 統計情報をCSVで保存",
                        data=csv,
                        file_name=f"nowcasting_statistics_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="download_stats_csv"
                    )
            
            # タブ 2: CPI寄与度分解
            elif st.session_state.nowcast_tab == 2:
                st.subheader("🥧 CPI寄与度分解（時系列）")
                
                # CPIデータを抽出
                cpi_data = df_processed[df_processed['metricName'].str.contains('cpi', case=False, na=False)].copy()
                
                if cpi_data.empty:
                    st.warning("CPIデータがありません")
                else:
                    # データセット選択
                    col1, col2 = st.columns(2)
                    with col1:
                        show_nowcast_cpi = st.checkbox("UBS Nowcasting", value=True, key="cpi_nowcast")
                    with col2:
                        show_actual_cpi = st.checkbox("Official Release", value=True, key="cpi_actual")
                    
                    st.markdown("---")
                    
                    # データセット別に処理
                    if show_nowcast_cpi:
                        nowcast_cpi = cpi_data[cpi_data['dataset_type'] == 'UBS Nowcasting'].copy()
                        
                        if not nowcast_cpi.empty:
                            st.subheader("UBS Nowcasting（予測値）")
                            
                            # 総合CPIとコアCPIを抽出（折れ線用）
                            overall_cpi = nowcast_cpi[nowcast_cpi['metricName'].isin(['ubs_nowcast_cpi', 'ubs_nowcast_cpi_overall'])].copy()
                            core_cpi = nowcast_cpi[nowcast_cpi['metricName'].isin(['ubs_nowcast_cpi_core', 'ubs_nowcast_core_cpi'])].copy()
                            
                            # 要素を分離（積み上げ棒グラフ用）- CPI関連メトリックのみ抽出
                            cpi_component_metrics = [
                                'ubs_nowcast_cpi_rent', 'ubs_nowcast_cpi_new_car', 'ubs_nowcast_cpi_used_car',
                                'ubs_nowcast_cpi_lodging', 'ubs_nowcast_cpi_lodge', 'ubs_nowcast_cpi_airfare', 
                                'ubs_nowcast_cpi_energy'
                            ]
                            components = nowcast_cpi[nowcast_cpi['metricName'].isin(cpi_component_metrics)].copy()
                            
                            if not components.empty:
                                # ピボットテーブルを作成（日付 x コンポーネント）
                                pivot_data = components.pivot_table(
                                    index='periodEndDate',
                                    columns='metric_display_name',
                                    values='metricValue',
                                    aggfunc='first'
                                ) * 100  # パーセンテージに変換
                                
                                pivot_data = pivot_data.sort_index()
                                
                                # 複合グラフを作成（積み上げ棒グラフ + 折れ線）
                                fig_contrib = go.Figure()
                                
                                # カラーパレット（要素用）
                                colors_palette = [
                                    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                                    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                                    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
                                ]
                                
                                # 各コンポーネントを積み上げ棒グラフとして追加
                                for idx, column in enumerate(pivot_data.columns):
                                    color = colors_palette[idx % len(colors_palette)]
                                    fig_contrib.add_trace(go.Bar(
                                        x=pivot_data.index,
                                        y=pivot_data[column],
                                        name=column,
                                        marker=dict(color=color),
                                        hovertemplate='<b>%{fullData.name}</b><br>日付: %{x|%y/%m/%d}<br>寄与度: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                # 総合CPIを折れ線として追加
                                if not overall_cpi.empty:
                                    overall_sorted = overall_cpi.sort_values('periodEndDate')
                                    overall_values = overall_sorted['metricValue'] * 100
                                    fig_contrib.add_trace(go.Scatter(
                                        x=overall_sorted['periodEndDate'],
                                        y=overall_values,
                                        name='総合CPI',
                                        mode='lines',
                                        line=dict(color='#1a1a1a', width=3, dash='solid'),
                                        hovertemplate='<b>総合CPI</b><br>日付: %{x|%y/%m/%d}<br>値: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                # コアCPIを折れ線として追加
                                if not core_cpi.empty:
                                    core_sorted = core_cpi.sort_values('periodEndDate')
                                    core_values = core_sorted['metricValue'] * 100
                                    fig_contrib.add_trace(go.Scatter(
                                        x=core_sorted['periodEndDate'],
                                        y=core_values,
                                        name='コアCPI',
                                        mode='lines',
                                        line=dict(color='#d62728', width=2.5, dash='dash'),
                                        hovertemplate='<b>コアCPI</b><br>日付: %{x|%y/%m/%d}<br>値: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                fig_contrib.update_layout(
                                    title="CPI寄与度分解（時系列）- 積み上げ棒グラフ + 総合CPI/コアCPI折れ線",
                                    xaxis_title="",
                                    yaxis_title="寄与度（%）",
                                    barmode='stack',
                                    height=600,
                                    template="plotly_white",
                                    hovermode='x unified',
                                    xaxis=dict(
                                        tickformat="%y/%m/%d",
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)'
                                    ),
                                    yaxis=dict(
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=True,
                                        zerolinecolor='rgba(0, 0, 0, 0.2)',
                                        zerolinewidth=1
                                    ),
                                    legend=dict(
                                        orientation='v',
                                        x=1.02,
                                        y=1,
                                        bgcolor='rgba(255, 255, 255, 0.8)',
                                        bordercolor='rgba(0, 0, 0, 0.2)',
                                        borderwidth=1
                                    ),
                                    margin=dict(l=70, r=200, t=80, b=60)
                                )
                                
                                st.plotly_chart(fig_contrib, use_container_width=True)
                                
                                # 分解テーブルを表示
                                st.markdown("**CPI寄与度分解テーブル**")
                                
                                # テーブル用データ整形
                                if not components.empty:
                                    st.markdown("**CPI寄与度分解テーブル**")
                                    table_data = components[['periodEndDate', 'metric_display_name', 'metricValue']].copy()
                                    table_data['metricValue'] = table_data['metricValue'] * 100
                                    
                                    # 最新データのテーブル
                                    latest_date = table_data['periodEndDate'].max()
                                    latest_table = table_data[table_data['periodEndDate'] == latest_date][['metric_display_name', 'metricValue']].sort_values('metricValue', ascending=False)
                                    latest_table = latest_table.copy()
                                    latest_table.columns = ['要素', '寄与度（%）']
                                    latest_table['寄与度（%）'] = latest_table['寄与度（%）'].astype(float).apply(lambda x: f"{x:.3f}")
                                    
                                    st.dataframe(latest_table, use_container_width=True, hide_index=True)
                    
                    if show_actual_cpi:
                        actual_cpi = cpi_data[cpi_data['dataset_type'] == 'Official Release'].copy()
                        
                        if not actual_cpi.empty:
                            st.subheader("Official Release（実績値）")
                            
                            # 総合CPIとコアCPIを抽出（折れ線用）
                            overall_cpi_actual = actual_cpi[actual_cpi['metricName'].isin(['first_official_report_cpi'])].copy()
                            core_cpi_actual = actual_cpi[actual_cpi['metricName'].isin(['first_official_report_cpi_core', 'first_official_report_core_cpi'])].copy()
                            
                            # 要素を分離（積み上げ棒グラフ用）- CPI要素メトリックのみ抽出
                            cpi_component_metrics_actual = [
                                'first_official_report_cpi_rent', 'first_official_report_cpi_new_car', 'first_official_report_cpi_used_car',
                                'first_official_report_cpi_lodge', 'first_official_report_cpi_airfare', 
                                'first_official_report_cpi_energy'
                            ]
                            components_actual = actual_cpi[actual_cpi['metricName'].isin(cpi_component_metrics_actual)].copy()
                            
                            if not components_actual.empty:
                                # ピボットテーブルを作成（日付 x コンポーネント）
                                pivot_data_actual = components_actual.pivot_table(
                                    index='periodEndDate',
                                    columns='metric_display_name',
                                    values='metricValue',
                                    aggfunc='first'
                                ) * 100  # パーセンテージに変換
                                
                                pivot_data_actual = pivot_data_actual.sort_index()
                                
                                # 複合グラフを作成（積み上げ棒グラフ + 折れ線）
                                fig_contrib_actual = go.Figure()
                                
                                # カラーパレット（要素用）
                                colors_palette_actual = [
                                    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                                    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                                    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
                                ]
                                
                                # 各コンポーネントを積み上げ棒グラフとして追加
                                for idx, column in enumerate(pivot_data_actual.columns):
                                    color = colors_palette_actual[idx % len(colors_palette_actual)]
                                    fig_contrib_actual.add_trace(go.Bar(
                                        x=pivot_data_actual.index,
                                        y=pivot_data_actual[column],
                                        name=column,
                                        marker=dict(color=color),
                                        hovertemplate='<b>%{fullData.name}</b><br>日付: %{x|%y/%m/%d}<br>寄与度: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                # 総合CPIを折れ線として追加
                                if not overall_cpi_actual.empty:
                                    overall_sorted_actual = overall_cpi_actual.sort_values('periodEndDate')
                                    overall_values_actual = overall_sorted_actual['metricValue'] * 100
                                    fig_contrib_actual.add_trace(go.Scatter(
                                        x=overall_sorted_actual['periodEndDate'],
                                        y=overall_values_actual,
                                        name='総合CPI',
                                        mode='lines',
                                        line=dict(color='#1a1a1a', width=3, dash='solid'),
                                        hovertemplate='<b>総合CPI</b><br>日付: %{x|%y/%m/%d}<br>値: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                # コアCPIを折れ線として追加
                                if not core_cpi_actual.empty:
                                    core_sorted_actual = core_cpi_actual.sort_values('periodEndDate')
                                    core_values_actual = core_sorted_actual['metricValue'] * 100
                                    fig_contrib_actual.add_trace(go.Scatter(
                                        x=core_sorted_actual['periodEndDate'],
                                        y=core_values_actual,
                                        name='コアCPI',
                                        mode='lines',
                                        line=dict(color='#d62728', width=2.5, dash='dash'),
                                        hovertemplate='<b>コアCPI</b><br>日付: %{x|%y/%m/%d}<br>値: %{y:.2f}%<extra></extra>',
                                        yaxis='y'
                                    ))
                                
                                fig_contrib_actual.update_layout(
                                    title="CPI寄与度分解（時系列）- 積み上げ棒グラフ + 総合CPI/コアCPI折れ線 - Official Release",
                                    xaxis_title="",
                                    yaxis_title="寄与度（%）",
                                    barmode='stack',
                                    height=600,
                                    template="plotly_white",
                                    hovermode='x unified',
                                    xaxis=dict(
                                        tickformat="%y/%m/%d",
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)'
                                    ),
                                    yaxis=dict(
                                        showgrid=True,
                                        gridwidth=1,
                                        gridcolor='rgba(0, 0, 0, 0.05)',
                                        zeroline=True,
                                        zerolinecolor='rgba(0, 0, 0, 0.2)',
                                        zerolinewidth=1
                                    ),
                                    legend=dict(
                                        orientation='v',
                                        x=1.02,
                                        y=1,
                                        bgcolor='rgba(255, 255, 255, 0.8)',
                                        bordercolor='rgba(0, 0, 0, 0.2)',
                                        borderwidth=1
                                    ),
                                    margin=dict(l=70, r=200, t=80, b=60)
                                )
                                
                                st.plotly_chart(fig_contrib_actual, use_container_width=True)
                                
                                # 分解テーブルを表示
                                if not components_actual.empty:
                                    st.markdown("**CPI寄与度分解テーブル**")
                                    
                                    # テーブル用データ整形
                                    table_data_actual = components_actual[['periodEndDate', 'metric_display_name', 'metricValue']].copy()
                                    table_data_actual['metricValue'] = table_data_actual['metricValue'] * 100
                                    
                                    # 最新データのテーブル
                                    latest_date_actual = table_data_actual['periodEndDate'].max()
                                    latest_table_actual = table_data_actual[table_data_actual['periodEndDate'] == latest_date_actual][['metric_display_name', 'metricValue']].sort_values('metricValue', ascending=False)
                                    latest_table_actual = latest_table_actual.copy()
                                    latest_table_actual.columns = ['要素', '寄与度（%）']
                                    latest_table_actual['寄与度（%）'] = latest_table_actual['寄与度（%）'].astype(float).apply(lambda x: f"{x:.3f}")
                                    
                                    st.dataframe(latest_table_actual, use_container_width=True, hide_index=True)
            
            # タブ 3: データ一括出力
            elif st.session_state.nowcast_tab == 3:
                st.subheader("📥 データ一括出力")
                
                # 出力オプション
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    export_format = st.selectbox(
                        "出力形式",
                        ["CSV", "Excel", "JSON"],
                        key="export_format"
                    )
                
                with col2:
                    include_processed = st.checkbox(
                        "処理済みデータのみ",
                        value=True,
                        key="include_processed"
                    )
                
                with col3:
                    sort_by = st.selectbox(
                        "ソート順",
                        ["日付（新→旧）", "日付（旧→新）", "指標名"],
                        key="sort_by"
                    )
                
                st.markdown("---")
                
                # データテーブル表示
                df_export = df_processed.copy()
                
                # ソート適用
                if sort_by == "日付（新→旧）":
                    df_export = df_export.sort_values('periodEndDate', ascending=False)
                elif sort_by == "日付（旧→新）":
                    df_export = df_export.sort_values('periodEndDate', ascending=True)
                else:
                    df_export = df_export.sort_values('metric_display_name')
                
                st.markdown(f"**取得データ件数: {len(df_export):,}件**")
                st.markdown(f"**指標数: {df_export['metricName'].nunique()}種**")
                
                # データプレビュー
                with st.expander("📋 データプレビュー（最初の100件）", expanded=True):
                    display_columns = [
                        'periodEndDate', 'nowcastEffectiveDate', 'metric_display_name', 
                        'dataset_type', 'metricValue'
                    ]
                    
                    available_columns = [col for col in display_columns if col in df_export.columns]
                    
                    # 表示用にカラム名を日本語化
                    df_display = df_export[available_columns].head(100).copy()
                    df_display.columns = ['期間終了日', 'リリース日', '指標', 'データセット', '値']
                    
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        height=500
                    )
                
                st.markdown("---")
                
                # ダウンロード機能
                st.subheader("💾 データダウンロード")
                
                if export_format == "CSV":
                    csv_data = df_export.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 CSVで全データをダウンロード",
                        data=csv_data,
                        file_name=f"nowcasting_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="download_csv",
                        use_container_width=True
                    )
                
                elif export_format == "Excel":
                    import io
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df_export.to_excel(writer, sheet_name='Nowcasting Data', index=False)
                    
                    excel_buffer.seek(0)
                    st.download_button(
                        label="📥 Excelで全データをダウンロード",
                        data=excel_buffer,
                        file_name=f"nowcasting_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_excel",
                        use_container_width=True
                    )
                
                elif export_format == "JSON":
                    json_data = df_export.to_json(orient='records', indent=2, default_handler=str)
                    st.download_button(
                        label="📥 JSONで全データをダウンロード",
                        data=json_data,
                        file_name=f"nowcasting_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="download_json",
                        use_container_width=True
                    )
                
                st.markdown("---")
                
                # データ項目の説明
                with st.expander("📖 データ項目の説明"):
                    st.markdown("""
                    | 項目 | 説明 |
                    |------|------|
                    | **periodEndDate** | 対象期間の終了日 |
                    | **nowcastEffectiveDate** | 予測値の発表日（リリース日） |
                    | **metric_display_name** | 見やすい指標名（例：Auto SAAR、ISM Manufacturing） |
                    | **dataset_type** | データセットタイプ（UBS Nowcasting または Official Release） |
                    | **metricValue** | 指標の値 |
                    | **metricName** | API内部的な指標名（例：ubs_nowcast_auto_saar） |
                    """)
                
                st.markdown("---")
                
                # 統計サマリー
                st.subheader("📊 データ統計")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("総データ件数", f"{len(df_export):,}")
                
                with col2:
                    st.metric("指標種別数", df_export['metricName'].nunique())
                
                with col3:
                    st.metric("日付範囲（開始）", df_export['periodEndDate'].min().strftime("%Y-%m-%d"))
                
                with col4:
                    st.metric("日付範囲（終了）", df_export['periodEndDate'].max().strftime("%Y-%m-%d"))
    
    except Exception as e:
        st.error(f"❌ エラーが発生しました: {str(e)}")
        st.warning("""
        ### トラブルシューティング:
        1. **ネットワーク接続を確認** - インターネット接続が安定しているか確認
        2. **UBS APIサーバーのステータス確認** - サーバーが利用可能か確認
        3. **APIキーの確認** - `API key.txt`に有効なAPIキーが保存されているか確認
        """)
