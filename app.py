"""
UBS Evidence Lab - Fund Manager Data Dashboard
メインエントリポイント

新しいサブアプリの追加方法:
1. modules/<name>/ ディレクトリを作成
2. data.py (データ取得・処理) と dashboard.py (show_dashboard関数) を実装
3. modules/registry.py の MODULES リストにエントリを追加
自動的にホーム画面とナビゲーションに反映されます。

起動: streamlit run app.py
"""

import streamlit as st
from modules.registry import MODULES, load_dashboard


def show_home():
    """ホーム画面: モジュール選択"""
    st.set_page_config(
        page_title="UBS Evidence Lab - Fund Manager Dashboard",
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
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .home-subtitle {
        text-align: center;
        color: #e0e7ff;
        font-size: 1.3rem;
        margin-bottom: 3rem;
        font-weight: 500;
    }
    .module-card {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
        min-height: 180px;
    }
    .module-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0,0,0,0.25);
    }
    .module-icon {
        font-size: 3rem;
        margin-bottom: 0.8rem;
    }
    .module-name {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.5rem;
    }
    .module-desc {
        font-size: 0.9rem;
        color: #64748b;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)

    # ヘッダー
    st.markdown('<div class="home-title">UBS Evidence Lab</div>', unsafe_allow_html=True)
    st.markdown('<div class="home-subtitle">Fund Manager Data Dashboard</div>', unsafe_allow_html=True)

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    # モジュール選択ボタン (レジストリから動的生成)
    num_modules = len(MODULES)
    btn_cols = st.columns(num_modules)

    for col, mod in zip(btn_cols, MODULES):
        with col:
            st.markdown(f"""
            <div class="module-card">
                <div class="module-icon">{mod['icon']}</div>
                <div class="module-name">{mod['name']}</div>
                <div class="module-desc">{mod['description']}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                f"{mod['icon']} {mod['name']}",
                key=f"btn_{mod['id']}",
                use_container_width=True,
                type="primary"
            ):
                st.session_state['app_mode'] = mod['id']
                st.rerun()

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

    # 説明
    st.markdown("""
    ### Available Tools:
    """)
    for mod in MODULES:
        st.markdown(f"**{mod['icon']} {mod['name']}** - {mod['description']}")


def run_app():
    """アプリケーション実行"""
    if 'app_mode' not in st.session_state:
        st.session_state['app_mode'] = 'home'

    mode = st.session_state['app_mode']

    if mode == 'home':
        show_home()
    else:
        # サイドバーに戻るボタン
        with st.sidebar:
            st.markdown("---")
            if st.button("ホームに戻る", use_container_width=True, type="secondary", key="back_home"):
                st.session_state['app_mode'] = 'home'
                st.rerun()

        # モジュールのダッシュボードをロード・実行
        try:
            dashboard_fn = load_dashboard(mode)
            dashboard_fn()
        except Exception as e:
            st.error(f"モジュール読み込みエラー: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    run_app()
