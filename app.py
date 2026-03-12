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

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

# --- QUANTUM DESIGN: V214 THE SINGULARITY (BÜYÜK BİRLEŞME) ---
st.set_page_config(page_title="V214 | AUTONOMOUS FUND", layout="wide", page_icon="🧠")

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
    .match-card { background: #0c1015; border: 1px solid #1e2530; border-left: 4px solid #00ffcc; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .target-market { color: #00ffcc; font-weight: 900; font-size: 18px; background: rgba(0, 255, 204, 0.1); padding: 5px 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS VERİTABANI BAĞLANTISI ---
@st.cache_resource(ttl=600)
def init_google_sheets():
    if not GSPREAD_INSTALLED: return None
    try:
        if "gcp_service_account" in st.secrets:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            client = gspread.authorize(creds)
            return client.open("Quantum_Bilanco").sheet1
        return None
    except Exception as e:
        return None

sheet = init_google_sheets()

# --- HAFIZA KİLİDİ VE KASA MOTORU ---
if 'bekleyen_tutar' not in st.session_state: st.session_state.bekleyen_tutar = 0.0
if 'kupon_gecmisi' not in st.session_state: st.session_state.kupon_gecmisi = []
if 'raw_api_data' not in st.session_state: st.session_state.raw_api_data = []
if 'pending_slip' not in st.session_state: st.session_state.pending_slip = None 

if 'lokal_kasa' not in st.session_state:
    if sheet is not None:
        try:
            all_vals = sheet.get_all_values()
            if len(all_vals) > 0: st.session_state.lokal_kasa = float(all_vals[-1][5])
            else: st.session_state.lokal_kasa = 10000.0 
        except: st.session_state.lokal_kasa = 10000.0
    else: st.session_state.lokal_kasa = 10000.0

if 'baslangic_kasa' not in st.session_state: 
    st.session_state.baslangic_kasa = st.session_state.lokal_kasa

# --- DEV YAPAY ZEKA BEYNİ (TARİHSEL VERİTABANI) ---
LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'SP1': 'İspanya La Liga 1',
    'I1': 'İtalya Serie A', 'D1': 'Almanya Bundesliga 1', 'F1': 'Fransa Ligue 1',
    'N1': 'Hollanda Eredivisie', 'B1': 'Belçika Pro League'
}

# API'den gelen lig kodlarını bizim veritabanı kodlarına çeviren harita
API_TO_DIV = {
    "soccer_turkey_super_league": "T1", "soccer_epl": "E0",
    "soccer_spain_la_liga": "SP1", "soccer_italy_serie_a": "I1",
    "soccer_germany_bundesliga": "D1", "soccer_france_ligue_one": "F1",
    "soccer_netherlands_eredivisie": "N1", "soccer_belgium_first_div": "B1"
}

@st.cache_data(ttl=3600)
def load_quantum_data():
    # 25 Yıllık dev veri havuzu ayarı
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
        return res_df.reset_index(drop=True)
    return pd.DataFrame()

db = load_quantum_data()

# --- ARAYÜZ SEKMELERİ (TABS) ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:48px; margin-bottom:0;'>🧠 QUANTUM HEDGE FUND V214</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:16px;'>Gerçek Yapay Zeka Entegrasyonu & Otonom Broker</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🎯 SNIPER RADAR (Yapay Zeka Aktif)", "💼 FON YÖNETİMİ (Kasa & Bilanço)", "🔬 MANUEL ANALİZ (Eski Sistem)"])

# ---------------------------------------------------------
# TAB 1: SNIPER RADAR (GERÇEK YAPAY ZEKA BAĞLANTISI)
# ---------------------------------------------------------
with tab1:
    st.markdown("<h3>🌍 Dünyayı Tara & İddaa'yı Avla</h3>", unsafe_allow_html=True)
    
    API_LEAGUES = {
        "Şampiyonlar Ligi": "soccer_uefa_champs_league", "Avrupa Ligi": "soccer_uefa_europa_league",
        "Türkiye Süper Lig": "soccer_turkey_super_league", "İngiltere Premier Lig": "soccer_epl",
        "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a",
        "Almanya Bundesliga": "soccer_germany_bundesliga", "Fransa Ligue 1": "soccer_france_ligue_one",
        "Hollanda Eredivisie (Gollü)": "soccer_netherlands_eredivisie", "Belçika Pro League (Gollü)": "soccer_belgium_first_div"
    }
    
    c1, c2 = st.columns([2, 1])
    with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["Hollanda Eredivisie (Gollü)", "Almanya Bundesliga", "Türkiye Süper Lig"])
    with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password")
    
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("📡 CANLI ORANLARI MANUEL ÇEK", key="btn_cek"):
            if not api_key: st.error("API Anahtarı eksik!")
            elif not secilen_ligler: st.warning("En az 1 lig seçmelisin.")
            else:
                with st.spinner("Küresel piyasalar anlık olarak çekiliyor..."):
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
                    st.session_state.raw_api_data = toplanan_maclar
                    st.success(f"✅ Sistem güncellendi! {len(toplanan_maclar)} maç havuzda.")

    st.divider()

    # AŞAMA 1 (GERÇEK YAPAY ZEKA ANALİZİ)
    if st.button("🧠 GÜNÜN FIRSATLARINI BUL (Yapay Zeka Analizi)", key="btn_firsat"):
        if len(st.session_state.raw_api_data) == 0:
            st.warning("Önce yukarıdaki 'CANLI ORANLARI MANUEL ÇEK' butonuna basarak havuzu doldurun!")
        elif len(db) == 0:
            st.error("Tarihsel veritabanı yüklenemedi. Lütfen sayfayı yenileyin.")
        else:
            with st.spinner("Yapay Zeka devrede... Canlı maçlar on binlerce geçmiş maç ile matematiksel olarak çarpıştırılıyor. Lütfen bekleyin..."):
                analiz_edilenler = []
                
                for mac in st.session_state.raw_api_data:
                    # 1. Maçın Ligini Bul ve Veritabanını Filtrele
                    lig_kodu = API_TO_DIV.get(mac.get('sport_key'))
                    aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                    
                    if len(aktif_db) > 100:
                        # 2. Canlı Oranları API'nin Karmaşık JSON'ından Çek (Defansif Kodlama)
                        h_odd, d_odd, a_odd = 2.50, 3.20, 2.80 # Varsayılanlar
                        try:
                            for bkm in mac.get('bookmakers', []):
                                for mkt in bkm.get('markets', []):
                                    if mkt['key'] == 'h2h':
                                        for out in mkt['outcomes']:
                                            if out['name'] == mac['home_team']: h_odd = out['price']
                                            elif out['name'] == mac['away_team']: a_odd = out['price']
                                            elif out['name'] == 'Draw': d_odd = out['price']
                        except: pass
                        
                        # 3. Matematiksel Mesafe (Öklid) ile Tarihte Eşi Benzeri Olan Maçları Bul
                        aktif_db['diff'] = np.sqrt((aktif_db['B365H']-h_odd)**2 + (aktif_db['B365D']-d_odd)**2 + (aktif_db['B365A']-a_odd)**2)
                        benzer = aktif_db.sort_values('diff').head(80) # En çok benzeyen 80 geçmiş maç
                        
                        # 4. İhtimal Hesaplamaları (Gerçek Tarihsel Yüzdeler)
                        p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / len(benzer))
                        p_msx = (benzer[benzer['FTR']=='D']['B365D'].count() / len(benzer))
                        p_ms2 = (benzer[benzer['FTR']=='A']['B365A'].count() / len(benzer))
                        p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / len(benzer))
                        p_u25 = 1.0 - p_o25
                        p_kgv = (benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['FTR'].count() / len(benzer))
                        p_kgy = 1.0 - p_kgv
                        
                        targets = [
                            ("MS 1", p_ms1), ("MS 0 (Beraberlik)", p_msx), ("MS 2", p_ms2), 
                            ("2.5 Üst", p_o25), ("2.5 Alt", p_u25), ("KG Var", p_kgv), ("KG Yok", p_kgy)
                        ]
                        
                        # 5. En Yüksek İhtimali Olan Pazarı (Sniper Hedefini) Seç (Sadece %55 üzeri olanlar)
                        gecerli_hedefler = [t for t in targets if t[1] > 0.55]
                        if gecerli_hedefler:
                            best_t = sorted(gecerli_hedefler, key=lambda x: x[1], reverse=True)[0]
                            mac['hedef_pazar'] = best_t[0]
                            mac['gercek_ihtimal'] = best_t[1]
                            mac['_g_score'] = best_t[1] # Yapay zekanın güven skoru
                            analiz_edilenler.append(mac)

                # En güvenilir 5 maçı vitrine çıkar
                st.session_state.top_adaylar = sorted(analiz_edilenler, key=lambda x: x.get('_g_score', 0), reverse=True)[:5]
                st.session_state.pending_slip = None 
                
                if len(st.session_state.top_adaylar) > 0:
                    st.success(f"🧠 Yapay Zeka On Binlerce veriyi işledi! En kârlı 5 özel Sniper Pazarı tespit edildi.")
                else:
                    st.warning("Bugün bültende geçmiş istatistiklerle örtüşen güvenilir bir maç bulunamadı. Paranı koru!")

    # AŞAMA 2 (NOKTA ATIŞI YASAL ORAN GİRİŞİ)
    if 'top_adaylar' in st.session_state and len(st.session_state.top_adaylar) > 0 and st.session_state.pending_slip is None:
        st.divider()
        st.markdown("<h3 style='color:#00ffcc;'>🎯 AŞAMA 2: Sniper Doğrulaması (Yasal Oran)</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8b949e;'>Yapay Zeka bu maçların geçmiş 25 yıllık DNA'sını çözdü. Sistem senden sadece belirttiği <b>Kusursuz Pazar'ın</b> yasal oranını istiyor.</p>", unsafe_allow_html=True)
        
        yasal_oranlar = {}
        for i, m in enumerate(st.session_state.top_adaylar):
            st.markdown(f"<div class='match-card'><b>{m['home_team']} - {m['away_team']}</b><br><span style='color:#8b949e;'>Geçmiş İhtimal: %{int(m['gercek_ihtimal']*100)} | Hedef Pazar: </span><span class='target-market'>{m['hedef_pazar']}</span></div>", unsafe_allow_html=True)
            yasal_oran = st.number_input(f"Yasal [{m['hedef_pazar']}] Oranını Girin:", min_value=1.01, value=1.50, step=0.05, key=f"y_oran_{i}")
            yasal_oranlar[i] = {'oran': yasal_oran, 'match': m}
            
        if st.button("🧮 YASAL KOMBİNEYİ OLUŞTUR VE KELLY HESAPLA", key="btn_kombine"):
            gecerli_maclar = []
            for i, data in yasal_oranlar.items():
                oran = data['oran']
                ihtimal = data['match']['gercek_ihtimal']
                edge = (ihtimal * oran) - 1
                if edge > 0.05: # Matematiksel olarak yasal sitede %2 avantajımız varsa oyna!
                    gecerli_maclar.append({'match': f"{data['match']['home_team']} - {data['match']['away_team']}", 'tercih': data['match']['hedef_pazar'], 'oran': oran, 'edge': edge, 'prob': ihtimal})
            
            if len(gecerli_maclar) >= 2:
                secilenler = sorted(gecerli_maclar, key=lambda x: x['edge'], reverse=True)[:2]
                toplam_oran = secilenler[0]['oran'] * secilenler[1]['oran']
                kasa_miktari = st.session_state.lokal_kasa
                b = toplam_oran - 1
                p = secilenler[0]['prob'] * secilenler[1]['prob'] # Yapay zekanın 2 maçı birden bilme ihtimali
                q = 1 - p
                kelly_yuzde = ((b * p) - q) / b
                hesaplanan_tutar = kasa_miktari * max(0.01, (kelly_yuzde / 4)) # Saf Matematik
yatirilacak_tutar = max(50.0, hesaplanan_tutar) # Yasal Site Minimum Limiti (50 TL Koruması)

                st.session_state.pending_slip = {
                    'maclar': secilenler,
                    'toplam_oran': toplam_oran,
                    'tutar': yatirilacak_tutar,
                    'edge': sum([x['edge'] for x in secilenler])
                }
                st.rerun()
            else: 
                st.error("🚨 DİKKAT: Girdiğiniz yasal oranlar bu maçları 'Negatif EV' pozisyonuna düşürüyor. Yasal site komisyonu çok yüksek. Yatırım iptal edildi!")

    # AŞAMA 3 (EMİR ÇALIŞTIRMA: OYNADIM / OYNAMADIM)
    if st.session_state.pending_slip is not None:
        slip = st.session_state.pending_slip
        st.markdown(f"""
        <div class='kelly-box'>
            <h2 style='color:#00ffcc; margin-top:0;'>🎯 OTONOM HEDGE KUPONU</h2>
            <div style='background:#0c1015; padding:20px; border-radius:10px; margin:20px 0; text-align:left; border: 1px solid #333;'>
                <b style='font-size:20px; color:#fff;'>1. Maç:</b> <span style='font-size:18px; color:#ddd;'>{slip['maclar'][0]['match']} ➔ <span style='color:#00ffcc;'><b>{slip['maclar'][0]['tercih']}</b></span> (Oran: {slip['maclar'][0]['oran']:.2f})</span><br><br>
                <b style='font-size:20px; color:#fff;'>2. Maç:</b> <span style='font-size:18px; color:#ddd;'>{slip['maclar'][1]['match']} ➔ <span style='color:#00ffcc;'><b>{slip['maclar'][1]['tercih']}</b></span> (Oran: {slip['maclar'][1]['oran']:.2f})</span>
            </div>
            <div style='display:flex; justify-content:space-around; align-items:center;'>
                <div><span style='color:#8b949e;'>Toplam Oran</span><br><b style='font-size:36px; color:#fff;'>{slip['toplam_oran']:.2f}</b></div>
                <div><span style='color:#8b949e;'>Sistem Açığı</span><br><b style='font-size:36px; color:#00ffcc;'>+%{(slip['edge']*100):.1f}</b></div>
            </div>
            <hr style='border-color:#333;'>
            <p style='color:#d4af37; font-size:18px; font-weight:800; margin-bottom:5px;'>💼 KELLY KRİTERİ YATIRIM EMRİ:</p>
            <div class='kelly-amount'>Tutar: {slip['tutar']:.0f} TL</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br><h3 style='text-align:center;'>Bu emri yasal sitenizde uyguladınız mı?</h3>", unsafe_allow_html=True)
        b1, b2, b3 = st.columns([1,2,1])
        with b2:
            c_yes, c_no = st.columns(2)
            if c_yes.button("✅ KUPONU OYNADIM (Kasaya İşle)", use_container_width=True, key="btn_oynadim"):
                tutar = slip['tutar']
                st.session_state.lokal_kasa -= tutar
                st.session_state.bekleyen_tutar += tutar
                if sheet is not None:
                    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    sheet.append_row([zaman, tutar, slip['toplam_oran'], "Bekliyor", "0", st.session_state.lokal_kasa])
                st.session_state.pending_slip = None
                st.session_state.top_adaylar = []
                st.success("✅ Yatırım onaylandı! Kasanızdan düşüldü ve buluta işlendi. Sonucu Tab 2'den takip edebilirsiniz.")
                
            if c_no.button("❌ OYNAMADIM (İptal Et)", use_container_width=True, key="btn_oynamadim"):
                st.session_state.pending_slip = None
                st.session_state.top_adaylar = []
                st.warning("Yatırım emri iptal edildi.")
                st.rerun()

# ---------------------------------------------------------
# TAB 2: FON YÖNETİM MERKEZİ
# ---------------------------------------------------------
with tab2:
    kasa = st.session_state.lokal_kasa
    bekleyen = st.session_state.bekleyen_tutar
    baslangic = st.session_state.baslangic_kasa
    roi = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    
    st.markdown("<h2 style='color:#d4af37;'>💼 Fon Bilanço Özeti</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL FON KASASI</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIMLAR</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>NET BÜYÜME (ROI)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    with st.expander("⚙️ SERMAYE AYARLARI (Manuel Bakiye Girişi)"):
        yeni_bakiye = st.number_input("Gerçek Kasa Bakiyenizi Girin (TL):", min_value=0.0, value=float(st.session_state.lokal_kasa), step=50.0, key="ayar_bakiye")
        if st.button("🔄 BAKİYEYİ SİSTEME TANIMLA", key="btn_bakiye_tanimla"):
            st.session_state.lokal_kasa = yeni_bakiye
            st.session_state.baslangic_kasa = yeni_bakiye
            if sheet is not None:
                zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([zaman, 0, 1.0, "Sermaye Girişi", "0", yeni_bakiye])
            st.success(f"✅ Sistem kasası {yeni_bakiye:.2f} TL olarak güncellendi ve ROI sıfırlandı!")
            st.rerun()

    st.divider()
    st.markdown("<h3>📝 Bekleyen Kuponu Sonuçlandır veya Yeni Kayıt Ekle</h3>", unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    yatirim_tutar = k1.number_input("Yatırılan Tutar (TL)", min_value=1.0, value=100.0, key="kayit_tutar")
    kupon_oran = k2.number_input("Toplam Kupon Oranı", min_value=1.01, value=2.00, key="kayit_oran")
    durum = k3.selectbox("Kupon Durumu", ["Kazandı", "Kaybetti", "Manuel Bekliyor Ekle"], key="kayit_durum")
    
    if st.button("💾 BULUT KASAYI GÜNCELLE", key="btn_bulut_guncelle"):
        if sheet is not None:
            zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
            if durum == "Manuel Bekliyor Ekle":
                st.session_state.bekleyen_tutar += yatirim_tutar
                st.session_state.lokal_kasa -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, "Bekliyor", "0", st.session_state.lokal_kasa])
                st.info(f"⏳ Yatırım manuel olarak 'Bekleyen Yatırımlar' sekmesine aktarıldı!")
                
            elif durum == "Kazandı": 
                net_kar = (yatirim_tutar * kupon_oran) - yatirim_tutar
                st.session_state.lokal_kasa += (yatirim_tutar * kupon_oran) 
                if st.session_state.bekleyen_tutar >= yatirim_tutar: st.session_state.bekleyen_tutar -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"+{net_kar}", st.session_state.lokal_kasa])
                st.success(f"✅ Tebrikler! {net_kar:.2f} TL kâr edildi.")
                
            elif durum == "Kaybetti": 
                if st.session_state.bekleyen_tutar >= yatirim_tutar: st.session_state.bekleyen_tutar -= yatirim_tutar
                sheet.append_row([zaman, yatirim_tutar, kupon_oran, durum, f"-{yatirim_tutar}", st.session_state.lokal_kasa])
                st.error(f"📉 Kayıp işlendi ve Excel defterine kaydedildi.")
                
            st.rerun()
        else:
            st.error("Bulut bağlantısı koptu! Excel'e yazılamadı.")

# ---------------------------------------------------------
# TAB 3: MANUEL ANALİZ (ESKİ SİSTEM)
# ---------------------------------------------------------
with tab3:
    st.info("Eski Manuel Borsa Terminali buradadır. Kendi maçlarınızı buradan detaylı manuel oran girerek analiz edebilirsiniz.")


