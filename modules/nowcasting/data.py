"""
Nowcasting - データ取得・処理
"""

import re
import pandas as pd

NOWCASTING_ENDPOINT = "us-nowcasting/default/v2/data?dataAssetKey=10441"

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
}


def fetch_nowcasting_data(client, start_date_str, end_date_str):
    """Nowcasting データを取得"""
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(NOWCASTING_ENDPOINT, filters)


def process_nowcasting_data(df):
    """取得したデータを処理"""
    if df.empty:
        return None

    def convert_timestamp(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return pd.to_datetime(val, unit='ms')
        try:
            return pd.to_datetime(val)
        except Exception:
            return None

    df['periodEndDate'] = df['periodEndDate'].apply(convert_timestamp)
    df['nowcastEffectiveDate'] = df['nowcastEffectiveDate'].apply(convert_timestamp)
    df['metric_display_name'] = df['metricName'].map(METRIC_DISPLAY_MAPPING).fillna(df['metricName'])
    df['dataset_type'] = df['metricName'].apply(
        lambda x: 'UBS Nowcasting' if 'ubs_nowcast' in x.lower() else 'Official Release'
    )
    return df


def normalize_base_metric(metric_name):
    if not isinstance(metric_name, str):
        return metric_name
    base = metric_name.lower()
    if base.startswith('ubs_nowcast_'):
        base = base.replace('ubs_nowcast_', '', 1)
    base = re.sub(r'_(mm|yy|y)$', '', base)
    return base


def format_base_metric_name(base_metric):
    if not isinstance(base_metric, str):
        return base_metric
    candidate = f"ubs_nowcast_{base_metric}"
    return (METRIC_JAPANESE_NAMES.get(candidate)
            or METRIC_DISPLAY_MAPPING.get(candidate)
            or base_metric.replace('_', ' ').title())


def get_latest_nowcast_timestamps(df):
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
    summary = nowcast_df.groupby('base_metric').agg(
        latest_period=('periodEndDate', 'max'),
        latest_release=('nowcastEffectiveDate', 'max')
    ).reset_index()

    summary['指標'] = summary['base_metric'].apply(format_base_metric_name)
    summary['期間終了日'] = summary['latest_period'].dt.strftime('%Y-%m-%d').fillna('N/A')
    summary['リリース日'] = summary['latest_release'].dt.strftime('%Y-%m-%d').fillna('N/A')
    result = summary[['指標', 'リリース日', '期間終了日']].sort_values('指標').set_index('指標')
    return result


def is_percentage_metric(metric_name):
    """パーセンテージ表示すべき指標かどうか"""
    ml = metric_name.lower()
    return any(k in ml for k in ['cpi', 'rent', 'energy', 'airfare', 'lodge', 'car', 'const'])


def get_y_axis_title(metric_name):
    ml = metric_name.lower()
    if 'nfp' in ml or 'payroll' in ml:
        return "雇用者数（千人）"
    elif 'ism' in ml:
        return "ISM指数"
    elif 'auto_saar_mm' in ml:
        return "変化率 (%)"
    elif 'auto_saar' in ml or 'auto' in ml:
        return "自動車販売（百万台SAAR）"
    elif any(k in ml for k in ['const', 'housing', 'prvt_const', 'ip', 'industrial']):
        return "変化率 (%)"
    elif is_percentage_metric(metric_name):
        return "変化率 (%)"
    return "値"


def get_y_axis_tickformat(metric_name):
    ml = metric_name.lower()
    if is_percentage_metric(metric_name) or any(k in ml for k in ['ip', 'industrial', 'const', 'prvt_const', 'auto_saar_mm']):
        return ".2f%"
    return ".2f"
