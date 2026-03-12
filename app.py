import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests
import io

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

# --- QUANTUM DESIGN: V217 THE CALIBRATED QUANT ---
st.set_page_config(page_title="V217 | AUTONOMOUS FUND", layout="wide", page_icon="🧠")

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
    .ml-badge { background: #d4af37; color: #000; font-size: 12px; padding: 3px 8px; border-radius: 4px; font-weight: 900; margin-left: 10px; }
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
all_vals = sheet.get_all_values() if sheet else []

# --- ÖLÜMSÜZ HAFIZA & MAKİNE ÖĞRENİMİ (ML) MOTORU ---
if 'lokal_kasa' not in st.session_state:
    if len(all_vals) > 0:
        last_row = all_vals[-1]
        st.session_state.lokal_kasa = float(last_row[5]) if len(last_row) > 5 else 10000.0
        st.session_state.bekleyen_tutar = float(last_row[6]) if len(last_row) > 6 else 0.0
        st.session_state.baslangic_kasa = float(last_row[7]) if len(last_row) > 7 else st.session_state.lokal_kasa
    else:
        st.session_state.lokal_kasa = 10000.0
        st.session_state.bekleyen_tutar = 0.0
        st.session_state.baslangic_kasa = 10000.0

if 'raw_api_data' not in st.session_state: st.session_state.raw_api_data = []
if 'pending_slip' not in st.session_state: st.session_state.pending_slip = None 

# 🧠 YAPAY ZEKA DERİN ÖĞRENME DOSYASINI OKUMA (Excel'den DNA Çıkarma)
ml_stats = {} # Format: "Lig|Pazar" -> {'w': kazanilan, 'l': kaybedilen, 'ai_probs': [], 'oranlar': []}
for r in all_vals:
    if len(r) >= 12: # V217 Genişletilmiş Öğrenme Verisi: Lig, Pazar, AI_Prob, Oran
        durum = r[3]
        if durum in ["Kazandı_Sonuc", "Kaybetti_Sonuc"]:
            ligler = r[8].split('#')
            pazarlar = r[9].split('#')
            ai_probs = r[10].split('#')
            oranlar = r[11].split('#')
            
            for l, p, a_p, o in zip(ligler, pazarlar, ai_probs, oranlar):
                key = f"{l}|{p}"
                if key not in ml_stats: ml_stats[key] = {'w': 0, 'l': 0, 'ai_probs': [], 'oranlar': []}
                
                try:
                    ml_stats[key]['ai_probs'].append(float(a_p))
                    ml_stats[key]['oranlar'].append(float(o))
                except: pass
                
                if durum == "Kazandı_Sonuc": ml_stats[key]['w'] += 1
                else: ml_stats[key]['l'] += 1
st.session_state.ml_stats = ml_stats

# --- DEV YAPAY ZEKA BEYNİ (TARİHSEL VERİTABANI) ---
LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'SP1': 'İspanya La Liga 1',
    'I1': 'İtalya Serie A', 'D1': 'Almanya Bundesliga 1', 'F1': 'Fransa Ligue 1',
    'N1': 'Hollanda Eredivisie', 'B1': 'Belçika Pro League'
}

API_TO_DIV = {
    "soccer_turkey_super_league": "T1", "soccer_epl": "E0",
    "soccer_spain_la_liga": "SP1", "soccer_italy_serie_a": "I1",
    "soccer_germany_bundesliga": "D1", "soccer_france_ligue_one": "F1",
    "soccer_netherlands_eredivisie": "N1", "soccer_belgium_first_div": "B1"
}

@st.cache_data(ttl=3600, show_spinner=False)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718', '1617', '1516', '1415', '1314', '1213', '1112', '1011', '0910', '0809', '0708', '0607', '0506', '0405', '0304', '0203', '0102', '0001']
    leagues = list(LIG_MAP.keys())
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in leagues]
    
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H', 'B365D', 'B365A']).copy()
            df['Season'] = s
            return df
        except: return pd.DataFrame()
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: 
        results = list(executor.map(fetch, urls))
        
    dfs = [res for res in results if not res.empty]
    if dfs:
        res_df = pd.concat(dfs, ignore_index=True)
        return res_df.reset_index(drop=True)
    return pd.DataFrame()

db = load_quantum_data()

# --- ARAYÜZ SEKMELERİ (TABS) ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:48px; margin-bottom:0;'>🧠 QUANTUM V217</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:16px;'>İstatistiksel Kalibrasyon & Kendi Kendini Eğiten Zeka</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🎯 SNIPER RADAR (Kalibre Zeka)", "💼 FON YÖNETİMİ (Kasa & Bilanço)", "🔬 MANUEL ANALİZ"])

# ---------------------------------------------------------
# TAB 1: SNIPER RADAR (KALİBRE EDİLMİŞ EV MATEMATİĞİ)
# ---------------------------------------------------------
with tab1:
    st.markdown("<h3>🌍 Dünyayı Tara & Kendi İstatistiklerinden Öğren</h3>", unsafe_allow_html=True)
    API_LEAGUES = {
        "Şampiyonlar Ligi": "soccer_uefa_champs_league", "Avrupa Ligi": "soccer_uefa_europa_league",
        "Türkiye Süper Lig": "soccer_turkey_super_league", "İngiltere Premier Lig": "soccer_epl",
        "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a",
        "Almanya Bundesliga": "soccer_germany_bundesliga", "Fransa Ligue 1": "soccer_france_ligue_one",
        "Hollanda Eredivisie": "soccer_netherlands_eredivisie", "Belçika Pro League": "soccer_belgium_first_div"
    }
    
    c1, c2 = st.columns([2, 1])
    with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["Hollanda Eredivisie", "Almanya Bundesliga", "Türkiye Süper Lig"])
    with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password")
    
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
                                m['kendi_ligi'] = lig
                                m_time = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                                if datetime.datetime.now(datetime.timezone.utc) < m_time < datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=48):
                                    toplanan_maclar.append(m)
                    except: pass
                st.session_state.raw_api_data = toplanan_maclar
                st.success(f"✅ Sistem güncellendi! {len(toplanan_maclar)} maç havuzda.")

    st.divider()

    # AŞAMA 1 (KALİBRE EDİLMİŞ ÖĞRENEN ZEKA)
    if st.button("🧠 GÜNÜN FIRSATLARINI BUL (Kişisel Kalibrasyon)", key="btn_firsat"):
        if len(st.session_state.raw_api_data) == 0: st.warning("Önce 'CANLI ORANLARI ÇEK' butonuna basın!")
        else:
            with st.spinner("Oynanmış kuponlardaki başarı yüzdeleri (Hit Rate) hesaplanıyor. Teorik ihtimaller, gerçek dünya istatistikleriyle kalibre ediliyor..."):
                analiz_edilenler = []
                
                for mac in st.session_state.raw_api_data:
                    lig_kodu = API_TO_DIV.get(mac.get('sport_key'))
                    aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                    gercek_lig_adi = mac.get('kendi_ligi', 'Bilinmeyen Lig')
                    
                    if len(aktif_db) > 100:
                        h_odd, d_odd, a_odd, o25_odd, u25_odd = 2.50, 3.20, 2.80, 1.90, 1.90
                        try:
                            for bkm in mac.get('bookmakers', []):
                                for mkt in bkm.get('markets', []):
                                    if mkt['key'] == 'h2h':
                                        for out in mkt['outcomes']:
                                            if out['name'] == mac['home_team']: h_odd = out['price']
                                            elif out['name'] == mac['away_team']: a_odd = out['price']
                                            elif out['name'] == 'Draw': d_odd = out['price']
                                    elif mkt['key'] == 'totals':
                                        for out in mkt['outcomes']:
                                            if out['name'] == 'Over' and out.get('point') == 2.5: o25_odd = out['price']
                                            elif out['name'] == 'Under' and out.get('point') == 2.5: u25_odd = out['price']
                        except: pass
                        
                        aktif_db['diff'] = np.sqrt((aktif_db['B365H']-h_odd)**2 + (aktif_db['B365D']-d_odd)**2 + (aktif_db['B365A']-a_odd)**2)
                        benzer = aktif_db.sort_values('diff').head(80) 
                        
                        p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / len(benzer))
                        p_msx = (benzer[benzer['FTR']=='D']['B365D'].count() / len(benzer))
                        p_ms2 = (benzer[benzer['FTR']=='A']['B365A'].count() / len(benzer))
                        p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / len(benzer))
                        p_u25 = 1.0 - p_o25
                        
                        ev_targets = [("MS 1", p_ms1, h_odd), ("MS 0 (Beraberlik)", p_msx, d_odd), ("MS 2", p_ms2, a_odd), ("2.5 Üst", p_o25, o25_odd), ("2.5 Alt", p_u25, u25_odd)]
                        
                        en_iyi_ev = -999.0
                        en_iyi_pazar = None
                        ogrenilmis_ihtimal_son = 0.0
                        ml_kullanildi_mi = False
                        
                        for pazar_adi, raw_ihtimal, k_oran in ev_targets:
                            # 🧠 KALİBRASYON MOTORU: Teorik İhtimal vs Fonun Gerçek Kazanma Oranı
                            ml_key = f"{gercek_lig_adi}|{pazar_adi}"
                            stats = st.session_state.ml_stats.get(ml_key, {'w':0, 'l':0})
                            total_bets = stats['w'] + stats['l']
                            
                            kalibre_ihtimal = raw_ihtimal
                            is_ml_active = False
                            
                            # Eğer sistem o ligde o pazara en az 3 kere oynamışsa, yüzdeleri öğrenir!
                            if total_bets >= 3:
                                real_hit_rate = stats['w'] / total_bets
                                # %70 Tarihsel İstatistik + %30 Senin Gerçek Dünyadaki Başarı Oranın (Ağırlıklı Ortalama)
                                kalibre_ihtimal = (raw_ihtimal * 0.70) + (real_hit_rate * 0.30)
                                is_ml_active = True
                            
                            hesaplanan_ev = (kalibre_ihtimal * k_oran) - 1
                            
                            if hesaplanan_ev > en_iyi_ev:
                                en_iyi_ev = hesaplanan_ev
                                en_iyi_pazar = (pazar_adi, raw_ihtimal, hesaplanan_ev)
                                ogrenilmis_ihtimal_son = kalibre_ihtimal
                                ml_kullanildi_mi = is_ml_active
                                
                        # Gerçekçi olmayan veya %40'ın altındaki sürprizleri ele
                        if en_iyi_pazar and ogrenilmis_ihtimal_son > 0.40:
                            mac['hedef_pazar'] = en_iyi_pazar[0]
                            mac['raw_ihtimal'] = en_iyi_pazar[1]
                            mac['kalibre_ihtimal'] = ogrenilmis_ihtimal_son
                            mac['_g_score'] = en_iyi_pazar[2] 
                            mac['ml_kullanildi'] = ml_kullanildi_mi
                            analiz_edilenler.append(mac)

                st.session_state.top_adaylar = sorted(analiz_edilenler, key=lambda x: x.get('_g_score', -999), reverse=True)[:5]
                st.session_state.pending_slip = None 
                if len(st.session_state.top_adaylar) > 0: st.success("🧠 Fonun gerçek yatırım geçmişi analiz edildi. Oranlar başarı yüzdelerine göre kalibre edildi!")

    if 'top_adaylar' in st.session_state and len(st.session_state.top_adaylar) > 0 and st.session_state.pending_slip is None:
        st.divider()
        st.markdown("<h3 style='color:#00ffcc;'>🎯 AŞAMA 2: Yasal Oran Doğrulaması</h3>", unsafe_allow_html=True)
        
        yasal_oranlar = {}
        for i, m in enumerate(st.session_state.top_adaylar):
            badge = "<span class='ml-badge'>🧠 İstatistiksel Olarak Kalibre Edildi</span>" if m['ml_kullanildi'] else ""
            st.markdown(f"<div class='match-card'><b>{m['home_team']} - {m['away_team']}</b> {badge}<br><span style='color:#8b949e;'>Teorik İhtimal: %{int(m['raw_ihtimal']*100)} ➔ Kalibre Edilmiş Gerçek İhtimal: <b>%{int(m['kalibre_ihtimal']*100)}</b><br>Hedef Pazar: </span><span class='target-market'>{m['hedef_pazar']}</span></div>", unsafe_allow_html=True)
            yasal_oran = st.number_input(f"Yasal [{m['hedef_pazar']}] Oranını Girin:", min_value=1.01, value=1.50, step=0.05, key=f"y_oran_{i}")
            yasal_oranlar[i] = {'oran': yasal_oran, 'match': m}
            
        if st.button("🧮 YASAL KOMBİNEYİ OLUŞTUR VE KELLY HESAPLA"):
            gecerli_maclar = []
            for i, data in yasal_oranlar.items():
                oran = data['oran']
                # Kelly hesaplamasında artık RAW (Teorik) ihtimal değil, geçmişimizden öğrendiğimiz KALİBRE ihtimal kullanılıyor
                kalibre_edilen = data['match']['kalibre_ihtimal']
                edge = (kalibre_edilen * oran) - 1
                
                if edge > -0.05: 
                    gecerli_maclar.append({'match': f"{data['match']['home_team']} - {data['match']['away_team']}", 'tercih': data['match']['hedef_pazar'], 'oran': oran, 'edge': edge, 'prob': kalibre_edilen, 'lig': data['match']['kendi_ligi']})
            
            if len(gecerli_maclar) >= 2:
                secilenler = sorted(gecerli_maclar, key=lambda x: x['edge'], reverse=True)[:2]
                toplam_oran = secilenler[0]['oran'] * secilenler[1]['oran']
                b = toplam_oran - 1
                p = secilenler[0]['prob'] * secilenler[1]['prob'] 
                q = 1 - p
                kelly_yuzde = ((b * p) - q) / b
                
                hesaplanan_tutar = st.session_state.lokal_kasa * max(0.01, (kelly_yuzde / 4)) 
                yatirilacak_tutar = max(50.0, hesaplanan_tutar)

                st.session_state.pending_slip = {'maclar': secilenler, 'toplam_oran': toplam_oran, 'tutar': yatirilacak_tutar, 'edge': sum([x['edge'] for x in secilenler])}
                st.rerun()
            else: st.error("🚨 DİKKAT: Kalibre edilmiş istatistiklerimize göre bu maçlar uzun vadede riskli. Yatırım iptal edildi!")

    if st.session_state.pending_slip is not None:
        slip = st.session_state.pending_slip
        st.markdown(f"""
        <div class='kelly-box'>
            <h2 style='color:#00ffcc; margin-top:0;'>🎯 OTONOM HEDGE KUPONU</h2>
            <div style='background:#0c1015; padding:20px; border-radius:10px; margin:20px 0; text-align:left; border: 1px solid #333;'>
                <b style='font-size:20px; color:#fff;'>1. Maç:</b> <span style='font-size:18px; color:#ddd;'>{slip['maclar'][0]['match']} ➔ <span style='color:#00ffcc;'><b>{slip['maclar'][0]['tercih']}</b></span> (Oran: {slip['maclar'][0]['oran']:.2f})</span><br><br>
                <b style='font-size:20px; color:#fff;'>2. Maç:</b> <span style='font-size:18px; color:#ddd;'>{slip['maclar'][1]['match']} ➔ <span style='color:#00ffcc;'><b>{slip['maclar'][1]['tercih']}</b></span> (Oran: {slip['maclar'][1]['oran']:.2f})</span>
            </div>
            <div class='kelly-amount'>Tutar: {slip['tutar']:.0f} TL</div>
        </div>
        """, unsafe_allow_html=True)
        
        c_yes, c_no = st.columns(2)
        if c_yes.button("✅ KUPONU OYNADIM (Kasaya & Yapay Zekaya İşle)", use_container_width=True):
            tutar = slip['tutar']
            st.session_state.lokal_kasa -= tutar
            st.session_state.bekleyen_tutar += tutar
            
            # 🧠 YAPAY ZEKA DERİN ÖĞRENME VERİLERİNİ EXCEL'E YAZIYORUZ (Lig, Pazar, İhtimal, Oran)
            ml_ligler = f"{slip['maclar'][0]['lig']}#{slip['maclar'][1]['lig']}"
            ml_pazarlar = f"{slip['maclar'][0]['tercih']}#{slip['maclar'][1]['tercih']}"
            ml_probs = f"{slip['maclar'][0]['prob']:.3f}#{slip['maclar'][1]['prob']:.3f}"
            ml_oranlar = f"{slip['maclar'][0]['oran']:.2f}#{slip['maclar'][1]['oran']:.2f}"
            
            if sheet is not None:
                zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([zaman, tutar, slip['toplam_oran'], "Bekliyor", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, ml_ligler, ml_pazarlar, ml_probs, ml_oranlar])
            st.session_state.pending_slip = None
            st.session_state.top_adaylar = []
            st.success("✅ İstatistiksel veriler başarıyla buluta işlendi. Sonucu Tab 2'den işaretleyebilirsiniz.")
            
        if c_no.button("❌ OYNAMADIM (İptal Et)", use_container_width=True):
            st.session_state.pending_slip = None
            st.session_state.top_adaylar = []
            st.rerun()

# ---------------------------------------------------------
# TAB 2: FON YÖNETİM MERKEZİ (TAM OTOMATİK)
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
        yeni_bakiye = st.number_input("Gerçek Kasa Bakiyenizi Girin (TL):", min_value=0.0, value=float(st.session_state.lokal_kasa), step=50.0)
        if st.button("🔄 BAKİYEYİ SİSTEME TANIMLA"):
            st.session_state.lokal_kasa = yeni_bakiye
            st.session_state.baslangic_kasa = yeni_bakiye
            if sheet is not None:
                zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([zaman, 0, 1.0, "Sermaye Girişi", "0", yeni_bakiye, st.session_state.bekleyen_tutar, yeni_bakiye, "Yok", "Yok", "0", "0"])
            st.success("✅ Sistem güncellendi!")
            st.rerun()

    st.divider()
    st.markdown("<h3>📝 Bekleyen Otonom Kuponlar (Yapay Zeka Eğitimi)</h3>", unsafe_allow_html=True)
    
    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] == "Bekliyor"]
    
    if not bekleyenler:
        st.info("Şu an sistemde bekleyen akıllı yatırımınız bulunmamaktadır.")
    else:
        for row_idx, r in bekleyenler:
            b_tutar = float(r[1])
            b_oran = float(r[2])
            b_lig = r[8] if len(r) > 8 else "Bilinmiyor"
            
            st.markdown(f"<div style='background:#1e2530; padding:15px; border-radius:8px; margin-bottom:10px;'><b>Yatırım:</b> {b_tutar:.0f} TL | <b>Oran:</b> {b_oran:.2f} | <b>Ligler:</b> {b_lig.replace('#', ' - ')}</div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            
            if col1.button(f"✅ KAZANDI (İstatistiği Eğit)", key=f"win_{row_idx}"):
                net_kar = (b_tutar * b_oran) - b_tutar
                st.session_state.lokal_kasa += (b_tutar * b_oran)
                st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                
                if sheet:
                    sheet.update_cell(row_idx, 4, "Bekliyor_Kapandı")
                    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    ml_l, ml_p = r[8] if len(r)>8 else "Yok", r[9] if len(r)>9 else "Yok"
                    ml_probs, ml_oranlar = r[10] if len(r)>10 else "0", r[11] if len(r)>11 else "0"
                    sheet.append_row([zaman, b_tutar, b_oran, "Kazandı_Sonuc", f"+{net_kar}", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, ml_l, ml_p, ml_probs, ml_oranlar])
                st.rerun()
                
            if col2.button(f"❌ KAYBETTİ (İstatistiği Kalibre Et)", key=f"lose_{row_idx}"):
                st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                
                if sheet:
                    sheet.update_cell(row_idx, 4, "Bekliyor_Kapandı")
                    zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    ml_l, ml_p = r[8] if len(r)>8 else "Yok", r[9] if len(r)>9 else "Yok"
                    ml_probs, ml_oranlar = r[10] if len(r)>10 else "0", r[11] if len(r)>11 else "0"
                    sheet.append_row([zaman, b_tutar, b_oran, "Kaybetti_Sonuc", f"-{b_tutar}", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, ml_l, ml_p, ml_probs, ml_oranlar])
                st.rerun()

with tab3:
    st.info("Eski Manuel Borsa Terminali buradadır.")
