"""
モジュールレジストリ
サブアプリの登録・管理を一元化し、新規モジュール追加を容易にする

新しいサブアプリを追加する場合:
1. modules/<name>/ ディレクトリを作成
2. dashboard.py に show_dashboard() 関数を実装
3. 本ファイルの MODULES リストにエントリを追加
"""


MODULES = [
    {
        "id": "sentiment",
        "name": "Central Bank Sentiment",
        "icon": "🏦",
        "description": "主要中央銀行（BOJ, FED, ECB）の政策スタンス・センチメント分析",
        "import_path": "modules.sentiment.dashboard",
        "function": "show_dashboard",
    },
    {
        "id": "nowcasting",
        "name": "Nowcasting",
        "icon": "📈",
        "description": "米国主要経済指標のリアルタイム予測と実績値比較",
        "import_path": "modules.nowcasting.dashboard",
        "function": "show_dashboard",
    },
    {
        "id": "job_listings",
        "name": "Job Listings Monitor",
        "icon": "💼",
        "description": "米国求人掲載データによる雇用動向モニタリング",
        "import_path": "modules.job_listings.dashboard",
        "function": "show_dashboard",
    },
]


def get_module(module_id):
    """IDでモジュール情報を取得"""
    for m in MODULES:
        if m["id"] == module_id:
            return m
    return None


def load_dashboard(module_id):
    """モジュールのダッシュボード関数を動的にインポートして返す"""
    mod_info = get_module(module_id)
    if mod_info is None:
        raise ValueError(f"Unknown module: {module_id}")

    import importlib
    module = importlib.import_module(mod_info["import_path"])
    return getattr(module, mod_info["function"])
