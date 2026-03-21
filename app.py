import streamlit as st
import requests
from openai import OpenAI
import json
import pandas as pd
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account

# ページの基本設定
st.set_page_config(page_title="自社専用 総合ダッシュボード", layout="wide")

st.title("🚀 広島パソコンサポートサービス 専用ダッシュボード")

# --- 🗝️ 見えない金庫（Secrets）からの自動読み込み ---
default_google_key = st.secrets.get("GOOGLE_API_KEY", "")
default_openai_key = st.secrets.get("OPENAI_API_KEY", "")
default_serpapi_key = st.secrets.get("SERPAPI_KEY", "")
default_ga4_id = st.secrets.get("GA4_PROPERTY_ID", "")

# サイドバー設定（金庫にキーがあれば自動入力されます）
with st.sidebar.expander("⚙️ 各種設定・APIキー（※金庫設定済みなら入力不要です！）", expanded=False):
    google_api_key = st.text_input("Google APIキー", value=default_google_key, type="password")
    openai_api_key = st.text_input("OpenAI APIキー", value=default_openai_key, type="password")
    serpapi_key = st.text_input("SerpApiキー", value=default_serpapi_key, type="password")
    
    st.divider()
    st.markdown("**📊 GA4 連携用（※金庫設定済みならアップロード不要！）**")
    uploaded_json = st.file_uploader("🗝️ 合鍵 (JSONファイル) をアップロード", type=["json"])

# --- 📱 タブ機能で画面を3つに分ける ---
tab1, tab2, tab3 = st.tabs(["💬 1. 口コミ＆AI返信", "🔍 2. 検索順位(SEO/MEO)", "📈 3. アクセス解析(GA4)"])

# ==========================================
# タブ1：口コミ＆AI返信ツール
# ==========================================
with tab1:
    st.header("🗺️×🤖 最新口コミの取得とAI自動返信")
    search_query = st.text_input("検索する店舗名", value="広島パソコンサポートサービス", key="shop_name")
    
    if st.button("✨ 口コミ取得 ＆ AI返信案を生成する", type="primary"):
        if not google_api_key or not openai_api_key:
            st.error("⚠️ サイドバーの設定から、GoogleとOpenAIのAPIキーを入力してください！")
        else:
            client = OpenAI(api_key=openai_api_key)
            with st.spinner("Googleから口コミを取得し、AIが返信を考えています...⏳"):
                try:
                    search_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={search_query}&inputtype=textquery&fields=place_id&key={google_api_key}"
                    search_res = requests.get(search_url).json()
                    
                    if search_res.get('status') == 'OK':
                        place_id = search_res['candidates'][0]['place_id']
                        detail_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,rating,user_ratings_total,reviews&language=ja&key={google_api_key}"
                        detail_res = requests.get(detail_url).json()
                        
                        if detail_res.get('status') == 'OK':
                            result = detail_res['result']
                            st.success("✅ データ取得とAIの返信案作成が完了しました！")
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric("🏢 店舗名", result.get('name', 'N/A'))
                            col2.metric("⭐ 総合評価", f"{result.get('rating', 'N/A')}")
                            col3.metric("💬 総口コミ数", f"{result.get('user_ratings_total', 'N/A')} 件")
                            
                            st.divider()
                            reviews = result.get('reviews', [])
                            if not reviews:
                                st.info("口コミがまだありません。")
                            else:
                                for review in reviews:
                                    with st.container(border=True):
                                        st.markdown(f"👤 **{review['author_name']}** さん ({review['relative_time_description']})")
                                        st.write(f"評価: {'⭐' * review['rating']}")
                                        review_text = review.get('text', '')
                                        
                                        if review_text:
                                            st.write(f"💬 「{review_text}」")
                                            response = client.chat.completions.create(
                                                model="gpt-4o-mini",
                                                messages=[
                                                    {"role": "system", "content": "あなたはパソコンサポート業の丁寧で誠実な代表です。口コミに対して、感謝とサポートへの熱意が伝わる自然な返信文を作成してください。"},
                                                    {"role": "user", "content": f"以下の口コミへの返信を書いてください。\n\n口コミ: {review_text}"}
                                                ],
                                                temperature=0.7
                                            )
                                            ai_reply = response.choices[0].message.content
                                            st.markdown("**🤖 AIの返信案（右上のマークでコピーできます）:**")
                                            st.code(ai_reply, language="text")
                                        else:
                                            st.write("（コメントなしのため返信案の生成はスキップしました）")
                        else:
                            st.error("詳細データの取得に失敗しました。")
                    else:
                        st.warning(f"店舗が見つかりませんでした。（Googleの応答: {search_res.get('status')}）")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

# ==========================================
# タブ2：検索順位チェックツール（SEO/MEO）
# ==========================================
with tab2:
    st.header("🔍 キーワード検索順位チェック")
    st.markdown("指定したキーワードと場所で検索した際、自社が何位にいるか調べます。")
    
    location_map = {
        "📍 広島市（中心部）": "Hiroshima, Japan",
        "📍 広島市 中区": "Naka Ward, Hiroshima, Japan",
        "📍 広島市 南区": "Minami Ward, Hiroshima, Japan",
        "📍 広島市 西区": "Nishi Ward, Hiroshima, Japan",
        "📍 広島市 東区": "Higashi Ward, Hiroshima, Japan",
        "📍 広島市 安佐南区": "Asaminami Ward, Hiroshima, Japan",
        "📍 広島市 安佐北区": "Asakita Ward, Hiroshima, Japan",
        "📍 広島市 佐伯区": "Saeki Ward, Hiroshima, Japan",
        "📍 広島市 安芸区": "Aki Ward, Hiroshima, Japan",
        "📍 安芸郡 熊野町": "Kumano, Aki District, Hiroshima, Japan",
        "📍 安芸郡 府中町": "Fuchu, Aki District, Hiroshima, Japan",
        "📍 安芸郡 海田町": "Kaita, Aki District, Hiroshima, Japan",
        "📍 安芸郡 坂町": "Saka, Aki District, Hiroshima, Japan",
        "📍 呉市": "Kure, Hiroshima, Japan",
        "📍 東広島市": "Higashihiroshima, Hiroshima, Japan",
        "📍 廿日市市": "Hatsukaichi, Hiroshima, Japan",
        "🇯🇵 日本全国（指定なし）": "Japan"
    }

    selected_loc_ja = st.selectbox("🌍 検索する現在地（地域）を選んでください", list(location_map.keys()))
    
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        target_keyword = st.text_input("🔍 調べたいキーワード", value="パソコン修理")
    with col_k2:
        target_name = st.text_input("🏢 自社の店舗名（マップ用）", value="広島パソコンサポートサービス")
    with col_k3:
        target_url = st.text_input("🌐 自社サイトのURLの一部", value="nextone-pc.com")

    if st.button("📊 このエリアでの順位を調査する", type="primary", key="btn_rank"):
        if not serpapi_key:
            st.error("⚠️ サイドバーからSerpApiキーを入力してください！")
        elif not target_url:
            st.warning("⚠️ 自社サイトのURLを入力してください！")
        else:
            clean_target_url = target_url.strip("/")
            selected_loc_en = location_map[selected_loc_ja] 
            
            with st.spinner(f"{selected_loc_ja} から検索しています...🕵️‍♂️"):
                try:
                    # SEO
                    seo_params = {"engine": "google", "q": target_keyword, "hl": "ja", "gl": "jp", "google_domain": "google.co.jp", "location": selected_loc_en, "num": 100, "api_key": serpapi_key}
                    seo_res = requests.get("https://serpapi.com/search.json", params=seo_params).json()
                    
                    if "error" in seo_res:
                        st.error(f"SerpApiエラー: {seo_res['error']}")
                    else:
                        seo_rank = "圏外"
                        for res in seo_res.get("organic_results", []):
                            if clean_target_url in res.get("link", ""):
                                seo_rank = f"{res['position']} 位"
                                break

                        # MEO
                        meo_params = {"engine": "google_local", "q": target_keyword, "hl": "ja", "gl": "jp", "google_domain": "google.co.jp", "location": selected_loc_en, "api_key": serpapi_key}
                        meo_res = requests.get("https://serpapi.com/search.json", params=meo_params).json()
                        
                        meo_rank = "圏外"
                        for i, res in enumerate(meo_res.get("local_results", [])):
                            if target_name in res.get("title", ""):
                                meo_rank = f"{i + 1} 位"
                                break
                        
                        st.success("✅ 順位の調査が完了しました！")
                        res_col1, res_col2 = st.columns(2)
                        with res_col1: st.container(border=True).metric("🌐 ウェブ検索（SEO順位）", seo_rank)
                        with res_col2: st.container(border=True).metric("🗺️ Googleマップ検索（MEO順位）", meo_rank)

                except Exception as e:
                    st.error(f"順位の取得中にエラーが発生しました: {e}")

# ==========================================
# タブ3：アクセス解析（GA4連携）
# ==========================================
with tab3:
    st.header("📈 自社サイト アクセスランキング (過去30日間)")
    st.markdown("Googleアナリティクス(GA4)から、どのページがよく見られているかを取得します。")

    ga4_property_id = st.text_input("📊 GA4 プロパティID（数字のみ）", value=default_ga4_id)
    st.caption("※自動読み込み設定済みの場合はそのままボタンを押してください。")
    
    if st.button("🚀 アクセスデータを取得する", type="primary"):
        credentials = None
        
        # 1. 見えない金庫（Secrets）に合鍵があればそれを使う
        if "GOOGLE_CREDENTIALS" in st.secrets:
            try:
                key_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
                credentials = service_account.Credentials.from_service_account_info(key_dict)
            except Exception as e:
                st.error("⚠️ 金庫の中の合鍵（JSON）の形式にエラーがあります。コピペミスがないか確認してください。")
        
        # 2. 金庫になければ、手動アップロードされた合鍵を使う
        elif uploaded_json is not None:
            uploaded_json.seek(0)
            key_dict = json.load(uploaded_json)
            credentials = service_account.Credentials.from_service_account_info(key_dict)

        if not ga4_property_id:
            st.warning("⚠️ プロパティIDを入力してください！")
        elif credentials is None:
            st.error("⚠️ 合鍵（JSONデータ）が見つかりません。Secrets（金庫）に設定するか、サイドバーからファイルをアップロードしてください。")
        else:
            with st.spinner("ロボットがGA4からアクセスデータを取得しています...⏳"):
                try:
                    client = BetaAnalyticsDataClient(credentials=credentials)

                    # GA4に「過去30日のページ別PV数を教えて！」とお願いする
                    request = RunReportRequest(
                        property=f"properties/{ga4_property_id.strip()}",
                        dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
                        metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
                        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
                    )
                    
                    response = client.run_report(request)
                    
                    data = []
                    total_pv = 0
                    total_users = 0
                    
                    for row in response.rows:
                        pv = int(row.metric_values[0].value)
                        users = int(row.metric_values[1].value)
                        data.append({
                            "ページタイトル": row.dimension_values[0].value,
                            "URLパス": row.dimension_values[1].value,
                            "PV数 (見られた回数)": pv,
                            "ユーザー数 (見た人数)": users
                        })
                        total_pv += pv
                        total_users += users
                        
                    if data:
                        st.success("✅ データの取得に大成功しました！")
                        
                        col1, col2 = st.columns(2)
                        col1.metric("👁️ 過去30日の 総PV数", f"{total_pv:,} 回")
                        col2.metric("👥 過去30日の 総ユーザー数", f"{total_users:,} 人")
                        
                        st.divider()
                        st.subheader("🏆 ページ別 アクセスランキング (トップ10)")
                        
                        df = pd.DataFrame(data)
                        df_sorted = df.sort_values("PV数 (見られた回数)", ascending=False).head(10)
                        df_sorted.index = range(1, len(df_sorted) + 1)
                        st.dataframe(df_sorted, use_container_width=True)
                    else:
                        st.info("データがありません（過去30日間にアクセスがないか、設定直後のためデータが反映されていない可能性があります）。")

                except Exception as e:
                    st.error(f"GA4データの取得中にエラーが発生しました: {e}")
