"""
Central Bank Sentiment - データ取得・処理
"""

import pandas as pd
import numpy as np
from config.settings import ENTITY_TO_COUNTRY

SENTIMENT_ENDPOINT = "central-banks-policy-sentiment/default/v2/data?dataAssetKey=10487"


def fetch_sentiment_data(client, start_date_str, end_date_str):
    """センチメントデータを取得"""
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(SENTIMENT_ENDPOINT, filters)


def process_sentiment_data(df):
    """取得したデータを処理"""
    if df.empty:
        return None

    df['periodEndDate'] = pd.to_datetime(df['periodEndDate'])
    df['country_name'] = df['entityName'].map(ENTITY_TO_COUNTRY)
    df['bank_display'] = df['entityName'] + '（' + df['country_name'] + '）'

    df_processed = df[
        (df['metricType'] == 'sentiment score smoothed') &
        (df['documentType'] == 'all documents') &
        (df['setName'] == 'all speakers')
    ].copy()

    return df_processed


def build_overview_summary(sentiment_df):
    """概要テーブルを構築"""
    if sentiment_df is None or sentiment_df.empty:
        return pd.DataFrame()

    rows = []
    for country, group in sentiment_df.groupby('country_name'):
        ordered = group.sort_values('periodEndDate')
        latest = ordered.iloc[-1]
        latest_score = float(latest['metricValue'])
        prev_score = float(ordered.iloc[-2]['metricValue']) if len(ordered) > 1 else np.nan
        delta = latest_score - prev_score if pd.notna(prev_score) else np.nan
        trailing_20 = ordered.tail(min(20, len(ordered)))['metricValue'].mean()
        direction = "Hawkish" if latest_score > 0 else "Dovish" if latest_score < 0 else "Neutral"
        rows.append({
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

    summary_df = pd.DataFrame(rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values("最新スコア", ascending=False).reset_index(drop=True)
    return summary_df


def build_topic_summary(topic_df):
    """トピック別サマリーを構築"""
    if topic_df is None or topic_df.empty:
        return pd.DataFrame(), None

    latest_date = topic_df['periodEndDate'].max()
    latest_df = topic_df[topic_df['periodEndDate'] == latest_date].copy()
    topic_summary = latest_df.groupby(['country_name', 'metric'], as_index=False)['metricValue'].mean()
    return topic_summary, latest_date
