"""
UBS Evidence Lab 共通APIクライアント
全サブアプリで共有する統一的なAPI通信層
"""

import os
import time
import requests
import pandas as pd
import streamlit as st
from config.settings import API_BASE_URL, API_RETRIES, API_TIMEOUT, API_TOKEN


class UBSAPIClient:
    """UBS Evidence Lab API v2 汎用クライアント"""

    def __init__(self, token=None):
        self.server = API_BASE_URL
        self.proxy = {
            "http": os.environ.get("http_proxy"),
            "https": os.environ.get("https_proxy")
        }
        self.proxy = {k: v for k, v in self.proxy.items() if v}
        self.token = token or API_TOKEN
        self.retries = API_RETRIES
        self.timeout = API_TIMEOUT

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _http_get(self, url):
        return requests.get(
            url,
            headers=self._headers(),
            proxies=self.proxy,
            verify=False,
            timeout=self.timeout
        )

    def _http_post(self, url, payload):
        return requests.post(
            url=url,
            headers=self._headers(),
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
        return self._handle_response(response)

    def post(self, endpoint, payload=None):
        url = f"{self.server}/{endpoint}"
        for attempt in range(self.retries + 1):
            response = self._http_post(url, payload)
            if response.status_code in [500, 503] and attempt < self.retries:
                st.warning(f"サーバーエラー: リトライ中 {attempt + 1}/{self.retries}...")
                time.sleep(5 ** (attempt + 1))
            else:
                break
        return self._handle_response(response)

    @staticmethod
    def _validate_response(response):
        if response.status_code == 401:
            raise Exception("Invalid credentials")
        if response.status_code == 404:
            raise Exception("API not found")
        if response.status_code >= 400:
            data = response.json if isinstance(response.json, dict) else response.json()
            raise Exception(data.get("message", str(response.text)))
        if response.status_code == 200 and 'HTML' in response.text:
            raise Exception("Invalid credentials")

    def _handle_response(self, response):
        self._validate_response(response)
        return response.json()

    def fetch_paginated(self, endpoint, filters, show_progress=True):
        """
        ページネーション対応の汎用データ取得メソッド

        Parameters
        ----------
        endpoint : str
            初期エンドポイント (例: "job-listings/time-series/v3/data?dataAssetKey=10224")
        filters : dict
            フィルター条件 {"filters": [...]}
        show_progress : bool
            取得進捗を Streamlit UI に表示するか

        Returns
        -------
        pd.DataFrame
        """
        df = pd.DataFrame()
        start_time = time.time()

        status_text = None
        records_display = None
        elapsed_display = None

        if show_progress:
            container = st.container()
            with container:
                status_text = st.empty()
                c1, c2 = st.columns(2)
                records_display = c1.empty()
                elapsed_display = c2.empty()

        current_endpoint = endpoint
        while current_endpoint:
            try:
                data = self.post(endpoint=current_endpoint, payload=filters)

                if 'results' in data and len(data['results']) > 0:
                    page_df = pd.json_normalize(data['results'])
                    df = pd.concat([df, page_df], ignore_index=True)
                    elapsed = time.time() - start_time

                    if show_progress and status_text:
                        status_text.info("データ取得中...")
                        records_display.metric("取得済み件数", f"{len(df):,}")
                        elapsed_display.metric("経過時間", f"{elapsed:.1f}秒")

                # 次のページ
                if 'meta' in data and 'next' in data['meta'] and data['meta']['next']:
                    current_endpoint = data['meta']['next'].replace(self.server, '')
                else:
                    break

            except Exception as e:
                if show_progress and status_text:
                    status_text.error(f"接続エラー: {str(e)}")
                raise

        # 進捗表示をクリア
        if show_progress:
            if status_text:
                status_text.empty()
            if records_display:
                records_display.empty()
            if elapsed_display:
                elapsed_display.empty()

        return df
