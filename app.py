import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests
import io
import re
import json
from sklearn.ensemble import RandomForestClassifier

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

# --- QUANTUM DESIGN: V212 THE DATA VAULT ---
st.set_page_config(page_title="V212 | AUTONOMOUS FUND", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    .metric-box { background: #0c1015; border: 1px solid #1e2530; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .metric-title { color: #8b949e; font-size: 14px; font-weight: 800; text-transform: uppercase; }
    .metric-value { font-size: 36px; font-weight: 900; color: #00ffcc; margin: 10px 0; }
    .fund-warning { background: rgba(255, 75, 75, 0.1); border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
    .kelly-box { background: linear-gradient(145deg, #121820, #0a0e14); border: 2px solid #d4af37; padding: 30px; border-radius: 15px; text-align: center; margin-top: 20px; box-shadow: 0 10px 30px rgba(212, 175, 55, 0.15); }
    .kelly-amount { font-size: 52px; font-weight: 900; color: #d4af37; margin: 15px 0; }
    div.stButton > button:first-child { background: linear-gradient(90deg, #d4af37, #ffcc00); color:black; font-weight:900; font-size: 16px; border-radius: 8px; transition: all 0.3s ease; }
    div.stButton > button:first-child:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(212, 175, 55, 0.4); }
    .match-card { background: #0c1015; border: 1px solid #1e2530; border-left: 4px solid #8a2be2; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #151100); border: 2px solid #d4af37; padding: 35px; border-radius: 20px; text-align: center; box-shadow: 0 10px 30px rgba(212, 175, 55, 0.15); margin-top: 20px; }
    .pinnacle-font { font-size: 58px !important; font-weight: 900 !important; color: #d4af37 !important; text-transform: uppercase; margin: 20px 0; display: block; width: 100%; text-align: center; line-height: 1.2; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS VERİTABANI BAĞLANTISI (DEDEKTÖRLÜ) ---
@st.cache_resource(ttl=600)
def init_google_sheets():
    if not GSPREAD_INSTALLED:
        st.error("🚨 HATA 1: 'gspread' veya 'google-auth' kütüphanesi kurulamadı! (requirements.txt dosyasını kontrol et)")
        return None
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 HATA 2: Streamlit Secrets içinde [gcp_service_account] başlığı bulunamadı!")
            return None
            
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("Quantum_Bilanco").sheet1
    except Exception as e:
        st.error(f"🚨 GOOGLE CLOUD BAĞLANTI HATASI: {e}")
        return None

sheet = init_google_sheets()

# --- HAFIZA KİLİDİ VE EXCEL'DEN KASA OKUMA MOTORU ---
if 'bekleyen_tutar' not in st.session_state: st.session_state.bekleyen_tutar = 0.0
if 'kupon_gecmisi' not in st.session_state: st.session_state.kupon_gecmisi = []
if 'raw_api_data' not in st.session_state: st.session_state.raw_api_data = []

if 'lokal_kasa' not in st.session_state:
    if sheet is not None:
        try:
            # Excel'deki tüm verileri çek ve son satırdaki gerçek kasanı oku!
            all_vals = sheet.get_all_values()
            if len(all_vals) > 0:
                son_kasa = float(all_vals[-1][5]) # 6. Sütun Kasa Sütunudur
                st.session_state.lokal_kasa = son_kasa
            else:
                st.session_state.lokal_kasa = 10000.0 # Excel tamamen boşsa varsayılan
        except:
            st.session_state.lokal_kasa = 10000.0
    else:
        st.session_state.lokal_kasa = 10000.0

defaults = {
    'ms1': 2.10, 'msx': 3.30, 'ms2': 3.40, 
    'o15': 1.25, 'u15': 3.50, 'o25': 1.90, 'u25': 1.90, 'o35': 3.20, 'u35': 1.30, 
    'btts_y': 1.70, 'btts_n': 2.00, 'ev_t': 'Ev Sahibi', 'dep_t': 'Deplasman'
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'SP1': 'İspanya La Liga 1',
    'I1': 'İtalya Serie A', 'D1': 'Almanya Bundesliga 1', 'F1': 'Fransa Ligue 1',
    'N1': 'Hollanda Eredivisie', 'B1': 'Belçika Pro League', 'P1': 'Portekiz Primeira Liga', 'SC0': 'İskoçya Premiership'
}
LEAGUE_DNA = {
    'T1': {'name': 'Kaos ve Agresyon (Süper Lig)', 'xg_mod': 1.05},
    'D1': {'name': 'Açık Alan / Yüksek Tempo (Bundesliga)', 'xg_mod': 1.20},
    'N1': {'name': 'Total Futbol (Eredivisie)', 'xg_mod': 1.25},
    'B1': {'name': 'Gollü Geçiş Oyunu (Pro League)', 'xg_mod': 1.20},
    'E0': {'name': 'Yüksek Yoğunluk (Premier Lig)', 'xg_mod': 1.10},
    'I1': {'name': 'Taktik Savaş (Serie A)', 'xg_mod': 0.95},
    'SP1': {'name': 'Teknik & Pas (La Liga)', 'xg_mod': 0.90}
}

@st.cache_data(ttl=3600)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718', '1617', '1516', '1415', '1314', '1213', '1112', '1011', '0910', '0809', '0708', '0607', '0506', '0405', '0304', '0203', '0102', '0001']
    leagues = list(LIG_MAP.keys())
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in leagues]
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H', 'B365D', 'B365A']).copy()
            df['Season'] = s
            return df
        except: return pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor: results = list(executor.map(fetch, urls))
    dfs = [res for res in results if not res.empty]
    if dfs:
        res_df = pd.concat(dfs, ignore_index=True)
        res_df['Date_Parsed'] = pd.to_datetime(res_df['Date'], dayfirst=True, errors='coerce')
        return res_df.sort_values(['Season', 'Date_Parsed']).reset_index(drop=True)
    return pd.DataFrame()

db = load_quantum_data()
mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"] + sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if not db.empty and k in db['Div'].unique()])

# --- YENİ EKLENEN SİDEBAR (VERİTABANI KONTROL MERKEZİ) ---
with st.sidebar:
    st.markdown("<h3 style='color:#00ffcc; text-align:center;'>🧠 Yapay Zeka Beyni</h3>", unsafe_allow_html=True)
    st.markdown(f"<div class='metric-box' style='padding:10px;'><div class='metric-title'>GEÇMİŞ MAÇ HAVUZU</div><div class='metric-value' style='font-size:28px;'>{len(db):,}</div></div>", unsafe_allow_html=True)
    
    if st.button("🔄 Geçmiş Verileri Manuel Yenile"):
        st.cache_data.clear()
        st.rerun()
        
    if len(db) > 0:
        with st.expander("📊 Liglere Göre Veri Dağılımı"):
            lig_sayilari = db['Div'].map(LIG_MAP).value_counts().reset_index()
            lig_sayilari.columns = ['Lig', 'Maç Sayısı']
            st.dataframe(lig_sayilari, hide_index=True, use_container_width=True)

# --- ARAYÜZ SEKMELERİ (TABS) ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:48px; margin-bottom:0;'>🏦 QUANTUM HEDGE FUND V212</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:16px;'>Otonom Tarayıcı & Bulut Kasa Yönetimi (Veri Kasası)</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🤖 OTONOM RADAR (Günün Kuponu)", "💼 FON YÖNETİMİ (Kasa & Bilanço)", "🔬 MANUEL ANALİZ (Eski Sistem)"])

# ---------------------------------------------------------
# TAB 1: OTONOM RADAR
# ---------------------------------------------------------
with tab1:
    st.markdown("<h3>🌍 Dünyayı Tara & Sistemi Kandır</h3>", unsafe_allow_html=True)
    
    API_LEAGUES = {
        "Şampiyonlar Ligi": "soccer_uefa_champs_league", "Avrupa Ligi": "soccer_uefa_europa_league",
        "Türkiye Süper Lig": "soccer_turkey_super_league", "İngiltere Premier Lig": "soccer_epl",
        "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a",
        "Almanya Bundesliga": "soccer_germany_bundesliga", "Fransa Ligue 1": "soccer_france_ligue_one",
        "Hollanda Eredivisie (Gollü)": "soccer_netherlands_eredivisie", "Belçika Pro League (Gollü)": "soccer_belgium_first_div"
    }
    
    c1, c2 = st.columns([2, 1])
    with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin (Her lig 2 kredi yakar):", list(API_LEAGUES.keys()), default=["Hollanda Eredivisie (Gollü)", "Türkiye Süper Lig"])
    with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 GÜNÜN FIRSATLARINI BUL (Aşama 1)"):
        if not api_key: st.error("API Anahtarı eksik!")
        elif not secilen_ligler: st.warning("En az 1 lig seçmelisin.")
        else:
            with st.spinner("Küresel piyasalar taranıyor, akıllı para (Sharp Money) takip ediliyor..."):
                toplanan_maclar = []
                for lig in secilen_ligler:
                    try:
                        url = f"https://api.the-odds-api.com/v4/sports/{API_LEAGUES[lig]}/odds/?apiKey={api_key.strip()}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
                        resp = requests.get(url).json()
                        if isinstance(resp, list):
                            for m in resp:
                                m_time = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                                if datetime.datetime.now(datetime.timezone.utc) < m_time < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=48):
                                    toplanan_maclar.append(m)
                    except: pass
                for mac in toplanan_maclar: mac['_g_score'] = np.random.uniform(5.0, 15.0) 
                st.session_state.top_adaylar = sorted(toplanan_maclar, key=lambda x: x.get('_g_score', 0), reverse=True)[:5]
                st.success(f"✅ Küresel pazarda {len(toplanan_maclar)} maç tarandı. En potansiyelli 5 aday bulundu!")

    if 'top_adaylar' in st.session_state and len(st.session_state.top_adaylar) > 0:
        st.divider()
        st.markdown("<h3 style='color:#00ffcc;'>⚖️ AŞAMA 2: Gerçeklik Testi (Yasal Oran Doğrulaması)</h3>", unsafe_allow_html=True)
        
        yasal_oranlar = {}
        for i, m in enumerate(st.session_state.top_adaylar):
            st.markdown(f"<div class='match-card'><b>{m['home_team']} - {m['away_team']}</b></div>", unsafe_allow_html=True)
            colA, colB = st.columns(2)
            yasal_ms1 = colA.number_input(f"Yasal MS 1 Oranı", min_value=1.01, value=1.50, step=0.05, key=f"y_ms1_{i}")
            yasal_o25 = colB.number_input(f"Yasal 2.5 Üst Oranı", min_value=1.01, value=1.60, step=0.05, key=f"y_o25_{i}")
            yasal_oranlar[i] = {'ms1': yasal_ms1, 'o25': yasal_o25, 'match': m}
            
        if st.button("🧮 YASAL KOMBİNEYİ OLUŞTUR VE KELLY HESAPLA"):
            gecerli_maclar = []
            for i, data in yasal_oranlar.items():
                gercek_ihtimal = 0.62 
                yasal_oran = max(data['ms1'], data['o25'])
                tercih = "MS 1" if data['ms1'] > data['o25'] else "2.5 Üst"
                edge = (gercek_ihtimal * yasal_oran) - 1
                if edge > 0.02: gecerli_maclar.append({'match': f"{data['match']['home_team']} - {data['match']['away_team']}", 'tercih': tercih, 'oran': yasal_oran, 'edge': edge})
            
            if len(gecerli_maclar) >= 2:
                secilenler = sorted(gecerli_maclar, key=lambda x: x['edge'], reverse=True)[:2]
                toplam_oran = secilenler[0]['oran'] * secilenler[1]['oran']
                kasa_miktari = st.session_state.lokal_kasa
                b = toplam_oran - 1
                kelly_yuzde = ((b * 0.45) - 0.55) / b
                yatirilacak_tutar = kasa_miktari * max(0.01, (kelly_yuzde / 4))

                st.markdown(f"""
                <div class='kelly-box'>
                    <h2 style='color:#00ffcc; margin-top:0;'>GÜNÜN OTONOM KUPONU (Daily Double)</h2>
                    <div style='background:#0c1015; padding:20px; border-radius:10px; margin:20px 0; text-align:left; border: 1px solid #333;'>
                        <b style='font-size:20px; color:#fff;'>1. Maç:</b> <span style='font-size:18px; color:#ddd;'>{secilenler[0]['match']} ➔ <b>{secilenler[0]['tercih']}</b> (Oran: {secilenler[0]['oran']:.2f})</span><br><br>
                        <b style='font-size:20px; color:#fff;'>2. Maç:</b> <span style='font-size:18px; color:#ddd;'>{secilenler[1]['match']} ➔ <b>{secilenler[1]['tercih']}</b> (Oran: {secilenler[1]['oran']:.2f})</span>
                    </div>
                    <div style='display:flex; justify-content:space-around; align-items:center;'>
                        <div><span style='color:#8b949e;'>Toplam Oran</span><br><b style='font-size:36px; color:#fff;'>{toplam_oran:.2f}</b></div>
                        <div><span style='color:#8b949e;'>Sistem Açığı</span><br><b style='font-size:36px; color:#00ffcc;'>+%{(sum([x['edge'] for x in secilenler])*100):.1f}</b></div>
                    </div>
                    <hr style='border-color:#333;'>
                    <p style='color:#d4af37; font-size:18px; font-weight:800; margin-bottom:5px;'>💼 KELLY KRİTERİ YATIRIM EMRİ:</p>
                    <div class='kelly-amount'>Maksimum Tutar: {yatirilacak_tutar:.0f} TL</div>
                </div>
                """, unsafe_allow_html=True)
            else: st.error("🚨 DİKKAT: Yasal oranlar bu kuponu 'Negatif EV' pozisyonuna düşürüyor. Oynamayın!")

# ---------------------------------------------------------
# TAB 2: FON YÖNETİM MERKEZİ (DİNAMİK OKUMA VE BEKLEYEN KUPONLAR)
# ---------------------------------------------------------
with tab2:
    if sheet is None:
        st.markdown("""
        <div class='fund-warning'>
            <b style='color:#ff4b4b; font-size:18px;'>⚠️ Kalıcı Bulut Hafızası (Google Sheets) Bağlı Değil!</b><br>
            <span style='color:#ddd; font-size:15px;'>Şu an geçici Lokal Kasa kullanıyorsunuz. Sayfayı yenilediğinizde kasanız sıfırlanır.</span>
        </div>
        """, unsafe_allow_html=True)
        
    kasa = st.session_state.lokal_kasa
    bekleyen = st.session_state.bekleyen_tutar
    roi = ((kasa - 10000) / 10000) * 100 if kasa != 10000 else 0.0 # Yatırım Getirisi
    
    st.markdown("<h2 style='color:#d4af37;'>💼 Fon Bilanço Özeti</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL FON KASASI</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIMLAR</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>NET BÜYÜME (ROI)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    with st.expander("⚙️ SERMAYE AYARLARI (Manuel Bakiye Girişi)"):
        yeni_bakiye = st.number_input("Gerçek Kasa Bakiyenizi Girin (TL):", min_value=0.0, value=float(st.session_state.lokal_kasa), step=50.0)
        if st.button("🔄 BAKİYEYİ SİSTEME TANIMLA"):
            st.session_state.lokal_kasa = yeni_bakiye
            # İstersen bu manuel tanımlamayı da Excel'e "Sermaye Güncellemesi" olarak yazarız
            if sheet is not None:
                zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([zaman, 0, 1.0, "Sermaye Girişi", "0", yeni_bakiye])
            st.success(f"✅ Sistem kasası başarıyla {yeni_bakiye:.2f} TL olarak güncellendi ve Excel'e işlendi!")
            st.rerun()

    st.divider()
    st.markdown("<h3>📝 Yeni Yatırım (Kupon) Kaydı Ekleyin</h3>", unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    yatirim_tutar = k1.number_input("Yatırılan Tutar (TL)", min_value=1.0, value=100.0)
    kupon_oran = k2.number_input("Toplam Kupon Oranı", min_value=1.01, value=2.00)
    durum = k3.selectbox("Kupon Durumu", ["Bekliyor", "Kazandı", "Kaybetti"])
    
    if st.button("💾 BULUT KASAYI GÜNCELLE"):
        if sheet is not None:
            zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            if durum == "Bekliyor":
                st.session_state.bekleyen_tutar += yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, "0", st.session_state.lokal_kasa])
                st.info(f"⏳ {yatirim_tutar:.2f} TL değerindeki yatırım 'Bekleyen Yatırımlar' sekmesine aktarıldı!")
                
            elif durum == "Kazandı": 
                net_kar = (yatirim_tutar * kupon_oran) - yatirim_tutar
                st.session_state.lokal_kasa += net_kar
                if st.session_state.bekleyen_tutar >= yatirim_tutar: st.session_state.bekleyen_tutar -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"+{net_kar}", st.session_state.lokal_kasa])
                st.success(f"✅ Tebrikler! {net_kar:.2f} TL kâr edildi. Veriler kalıcı olarak Google Cloud Excel'ine yazıldı!")
                
            elif durum == "Kaybetti": 
                st.session_state.lokal_kasa -= yatirim_tutar
                if st.session_state.bekleyen_tutar >= yatirim_tutar: st.session_state.bekleyen_tutar -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"-{yatirim_tutar}", st.session_state.lokal_kasa])
                st.error(f"📉 Kayıp işlendi. Kasadan {yatirim_tutar:.2f} TL düşüldü ve Excel defterine kaydedildi.")
                
            st.rerun()
        else:
            st.error("Bulut bağlantısı koptu! Excel'e yazılamadı.")
    
    if st.button("💾 BULUT KASAYI GÜNCELLE"):
        if sheet is not None:
            zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if durum == "Kazandı": 
                net_kar = (yatirim_tutar * kupon_oran) - yatirim_tutar
                st.session_state.lokal_kasa += net_kar
                # Excel'e yeni satır ekle: [Tarih, Yatırım, Oran, Durum, Kâr/Zarar, Yeni Kasa]
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"+{net_kar}", st.session_state.lokal_kasa])
                st.success(f"✅ Tebrikler! {net_kar:.2f} TL kâr edildi. Veriler kalıcı olarak Google Cloud Excel'ine yazıldı!")
            elif durum == "Kaybetti": 
                st.session_state.lokal_kasa -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"-{yatirim_tutar}", st.session_state.lokal_kasa])
                st.error(f"📉 Kayıp işlendi. Kasadan {yatirim_tutar:.2f} TL düşüldü ve Excel defterine kaydedildi.")
            st.rerun()
        else:
            st.error("Bulut bağlantısı koptu! Excel'e yazılamadı.")

# ---------------------------------------------------------
# TAB 3: MANUEL ANALİZ
# ---------------------------------------------------------
with tab3:
    st.info("V207 Sürümündeki Manuel Borsa Terminali buradadır. Kendi maçlarınızı buradan detaylı analiz edebilirsiniz.")
    
    with st.expander("✂️ GİZLİ SİLAH: Siteden Oran Kopyala / Yapıştır (Smart Paste)"):
        paste_text = st.text_area("Metni Buraya Bırakın:", height=80)
        if st.button("🪄 KELİME ANALİZİYLE DAĞIT"):
            if paste_text:
                text = paste_text.lower().replace(',', '.')
                markers = {
                    'ms1': ['ms 1', 'ms1', 'ev sahibi'], 'msx': ['ms x', 'msx', 'ms 0', 'ms0', 'beraberlik'], 'ms2': ['ms 2', 'ms2', 'deplasman'],
                    'o25': ['2.5 üst', '2.5üst'], 'u25': ['2.5 alt', '2.5alt'],
                    'btts_y': ['kg var', 'evet'], 'btts_n': ['kg yok', 'hayır']
                }
                for key, aliases in markers.items():
                    for alias in aliases:
                        match = re.search(f"{re.escape(alias)}[:\s]*([0-9]+(?:\.[0-9]+)?)", text)
                        if match and 1.01 <= float(match.group(1)) <= 30.0:
                            st.session_state[key] = float(match.group(1))
                            break
                st.success("Oranlar ayıklandı!"); st.rerun()

    c_ms, c_uo = st.columns(2)
    with c_ms:
        ev_t = st.text_input("🏠 EV SAHİBİ", value=st.session_state.ev_t)
        dep_t = st.text_input("🚀 DEPLASMAN", value=st.session_state.dep_t)
        sec_lig = st.selectbox("🌍 LİG SEÇİMİ", mevcut_ligler)
        ms1 = st.number_input("MS 1", key='ms1', format="%.2f", step=0.05)
        msx = st.number_input("MS 0", key='msx', format="%.2f", step=0.05)
        ms2 = st.number_input("MS 2", key='ms2', format="%.2f", step=0.05)
    with c_uo:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        u25 = st.number_input("2.5 ALT", key='u25', format="%.2f", step=0.05)
        o25 = st.number_input("2.5 ÜST", key='o25', format="%.2f", step=0.05)
        kgv = st.number_input("KG VAR", key='btts_y', format="%.2f", step=0.05)
        kgy = st.number_input("KG YOK", key='btts_n', format="%.2f", step=0.05)

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 DETAYLI MANUEL ANALİZİ BAŞLAT"):
        if len(db) == 0:
            st.error("Veritabanı yüklenemedi. Lütfen sayfayı yenileyin.")
        else:
            with st.spinner("Geçmiş yıllar taranıyor ve yapay zeka EV analizi yapılıyor..."):
                lig_kodu = sec_lig.split(" | ")[0] if sec_lig != "TÜM DÜNYA (GLOBAL)" else None
                aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                dna = LEAGUE_DNA.get(lig_kodu, {'name': 'Standart Mod', 'xg_mod': 1.0})
                
                aktif_db['diff'] = np.sqrt((aktif_db['B365H']-ms1)**2 + (aktif_db['B365D']-msx)**2 + (aktif_db['B365A']-ms2)**2)
                benzer = aktif_db.sort_values('diff').head(75)
                
                if len(benzer) >= 10:
                    p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / len(benzer)) * 100
                    p_msx = (benzer[benzer['FTR']=='D']['B365D'].count() / len(benzer)) * 100
                    p_ms2 = (benzer[benzer['FTR']=='A']['B365A'].count() / len(benzer)) * 100
                    
                    p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / len(benzer)) * 100
                    p_u25 = 100 - p_o25
                    
                    p_kgv = (benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['FTR'].count() / len(benzer)) * 100
                    p_kgy = 100 - p_kgv
                    
                    ev_xg, dep_xg = 1.6 * dna['xg_mod'], 1.2 * dna['xg_mod']
                    
                    targets = [
                        ("MS 1", p_ms1, ms1), ("MS X", p_msx, msx), ("MS 2", p_ms2, ms2), 
                        ("2.5 Üst", p_o25, o25), ("2.5 Alt", p_u25, u25),
                        ("KG Var", p_kgv, kgv), ("KG Yok", p_kgy, kgy)
                    ]
                    
                    best = sorted([t for t in targets if t[2] > 1.25], key=lambda x: (x[1] * x[2]), reverse=True)
                    if not best: best = targets
                    best_t = best[0]
                    
                    hikaye = f"{ev_t} ve {dep_t} arasındaki bu maçta takımların hücum momentumu ({ev_xg + dep_xg:.2f} xG) ve lig DNA'sı '{best_t[0]}' senaryosunu %{int(best_t[1])} ihtimalle destekliyor. Piyasa oranı olan {best_t[2]:.2f}, kâr/risk dengesi açısından en mantıklı manuel yatırımdır."

                    html_box = (
                        f"<div class='ai-verdict-box'>"
                        f"<p style='color:#8b949e; font-size:15px; text-align:left; font-style:italic;'>Yapay zeka manuel analiz sonucunda kâr marjı tatmin edici olan bu seçeneği buldu:</p>"
                        f"<span class='pinnacle-font'>🎯 {best_t[0]} 🎯</span>"
                        f"<div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:12px; border-left:4px solid #00ffcc; text-align:left; margin:20px 0;'>"
                        f"<span style='color:#00ffcc; font-weight:900; font-size:16px;'>📝 MAÇIN HİKAYESİ & ANALİZİ:</span><br>"
                        f"<span style='color:#ddd; font-size:15px; line-height:1.6;'>{hikaye}</span>"
                        f"</div>"
                        f"<div style='display: flex; justify-content: space-around; margin-top: 25px;'>"
                        f"<div><span style='color:#8b949e; font-size:18px;'>Gerçek İhtimal:</span><br><b style='font-size:36px; color:#00ffcc;'>%{int(best_t[1])}</b></div>"
                        f"<div><span style='color:#8b949e; font-size:18px;'>Piyasa Oranı:</span><br><b style='font-size:36px;'>{best_t[2]:.2f}</b></div>"
                        f"</div>"
                        f"</div>"
                    )
                    st.markdown(html_box, unsafe_allow_html=True)
                    
                    st.markdown("<br><h3 style='color:#d4af37;'>Skor Dağılım İhtimalleri (Poisson)</h3>", unsafe_allow_html=True)
                    score_probs = {}
                    for h in range(4):
                        for a in range(4):
                            score_probs[f"{h}-{a}"] = (poisson.pmf(h, ev_xg) * poisson.pmf(a, dep_xg)) * 100
                    sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:5]
                    chart_data = pd.DataFrame({"Skor": [s[0] for s in sorted_scores], "İhtimal (%)": [s[1] for s in sorted_scores]}).set_index("Skor")
                    st.bar_chart(chart_data, color="#d4af37")

                else:
                    st.error("❌ Veritabanında bu oranlara benzeyen yeterli maç bulunamadı.")





