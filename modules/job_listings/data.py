"""
US Job Listings Monitor - データ取得・処理

UBS Evidence Lab Job Listings API
Framework: job-listings
Views: time-series (v3), regional-analysis (v2), job-family (v2)
Data Asset Key: 10224
Data: 2016-01〜 週次更新、約50,000社の求人掲載データ
"""

import pandas as pd

# エンドポイント定義
ENDPOINTS = {
    "time_series": "job-listings/time-series/v3/data?dataAssetKey=10224",
    "regional": "job-listings/regional-analysis/v2/data?dataAssetKey=10224",
    "job_family": "job-listings/job-family/v2/data?dataAssetKey=10224",
}

# セクター日本語マッピング
SECTOR_JAPANESE = {
    'Total Private': '民間全体',
    'Total Nonfarm': '非農業全体',
    'Mining and Logging': '鉱業・伐採業',
    'Construction': '建設業',
    'Manufacturing': '製造業',
    'Durable Goods': '耐久財',
    'Nondurable Goods': '非耐久財',
    'Trade, Transportation, and Utilities': '貿易・運輸・公益事業',
    'Wholesale Trade': '卸売業',
    'Retail Trade': '小売業',
    'Transportation and Warehousing': '運輸・倉庫業',
    'Utilities': '公益事業',
    'Information': '情報通信',
    'Financial Activities': '金融活動',
    'Finance and Insurance': '金融・保険',
    'Real Estate and Rental and Leasing': '不動産・賃貸',
    'Professional and Business Services': '専門・ビジネスサービス',
    'Education and Health Services': '教育・医療サービス',
    'Health Care and Social Assistance': '医療・社会福祉',
    'Leisure and Hospitality': 'レジャー・ホスピタリティ',
    'Accommodation and Food Services': '宿泊・飲食',
    'Other Services': 'その他サービス',
    'Government': '政府',
}

# メトリクス日本語マッピング
METRIC_JAPANESE = {
    'new_listings': '新規求人掲載数',
    'removed_listings': '削除求人数',
    'total_active_listings': 'アクティブ求人総数',
    'net_change': '純変化',
    'active_listings': 'アクティブ求人数',
    'new': '新規',
    'removed': '削除',
    'total': '合計',
    'change': '変化',
    'listings_count': '求人掲載数',
    'yoy_change': '前年比変化',
    'wow_change': '前週比変化',
    'mom_change': '前月比変化',
}


def fetch_time_series_data(client, start_date_str, end_date_str):
    """時系列データを取得"""
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(ENDPOINTS["time_series"], filters)


def fetch_regional_data(client, start_date_str, end_date_str):
    """地域別データを取得"""
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(ENDPOINTS["regional"], filters)


def fetch_job_family_data(client, start_date_str, end_date_str):
    """職種別データを取得"""
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(ENDPOINTS["job_family"], filters)


def process_job_listings_data(df):
    """
    求人掲載データを処理
    """
    if df is None or df.empty:
        return None

    # 日付変換
    for col in ['periodEndDate', 'releaseDate']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # metricValue を数値変換
    if 'metricValue' in df.columns:
        df['metricValue'] = pd.to_numeric(df['metricValue'], errors='coerce')

    # セクター日本語名を追加
    if 'sectorName' in df.columns:
        df['sector_jp'] = df['sectorName'].map(SECTOR_JAPANESE).fillna(df['sectorName'])

    # メトリクス日本語名を追加
    if 'metricName' in df.columns:
        df['metric_jp'] = df['metricName'].map(METRIC_JAPANESE).fillna(df['metricName'])

    return df


def build_sector_summary(df):
    """セクター別サマリーを構築"""
    if df is None or df.empty:
        return pd.DataFrame()

    if 'sectorName' not in df.columns or 'metricValue' not in df.columns:
        return pd.DataFrame()

    latest_date = df['periodEndDate'].max()
    latest = df[df['periodEndDate'] == latest_date].copy()

    if latest.empty:
        return pd.DataFrame()

    summary = latest.groupby('sectorName').agg(
        latest_value=('metricValue', 'sum'),
        record_count=('metricValue', 'count')
    ).reset_index()

    summary['sector_jp'] = summary['sectorName'].map(SECTOR_JAPANESE).fillna(summary['sectorName'])
    summary = summary.sort_values('latest_value', ascending=False)
    return summary
