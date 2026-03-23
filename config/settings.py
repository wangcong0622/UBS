"""
共通設定モジュール
プロキシ、APIトークン、環境設定を一元管理
"""

import os
import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning
from pathlib import Path

# 不要な警告を抑制
warnings.simplefilter('ignore', InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Failed to patch SSL settings')
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# プロジェクトルートディレクトリ
PROJECT_ROOT = Path(__file__).parent.parent

# プロキシの設定
PROXY_HTTP = "http://10.7.0.165:8080"
PROXY_HTTPS = "http://10.7.0.165:8080"
os.environ["http_proxy"] = PROXY_HTTP
os.environ["https_proxy"] = PROXY_HTTPS

# UBS Evidence Lab API 基本設定
API_BASE_URL = "https://neo.ubs.com/api/evidence-lab/api-framework"
API_RETRIES = 3
API_TIMEOUT = 60

# APIトークンの読み込み
_token_path = PROJECT_ROOT / "API key.txt"
if _token_path.exists():
    API_TOKEN = _token_path.read_text().strip()
else:
    API_TOKEN = ""


# エンティティ名と国のマッピング（センチメント用）
ENTITY_TO_COUNTRY = {
    'Bank of Japan': '日本',
    'Federal Reserve System': 'アメリカ',
    'European Central Bank': 'ユーロ圏'
}

COUNTRY_PALETTE = {
    '日本': '#2563eb',
    'アメリカ': '#dc2626',
    'ユーロ圏': '#059669'
}
