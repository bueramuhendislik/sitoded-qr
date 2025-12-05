import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO
import time
from datetime import datetime
import uuid

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="SİTODED QR Sistemi", page_icon="📝", layout="centered")

# --- ORTAK HAFIZA (GLOBAL STATE) ---
# Bu kısım, Tablet ve Telefonların birbiriyle haberleşmesini sağlar.
# Flask'taki global değişkenlerin Streamlit karşılığıdır.
@st.cache_resource
class TokenManager:
    def __init__(self):
        self.active_gate_tokens = {}  # {token: expire_time}

    def create_token(self, lifespan_seconds=15):
        # Eski tokenları temizle
        now = time.time()
        self.active_gate_tokens = {k: v for k, v in self.active_gate_tokens.items() if v > now}
        
        # Yeni token oluştur
        token = str(uuid.uuid4())
        self.active_gate_tokens[token] = now + lifespan_seconds
        return token

    def is_valid(self, token):
        # Token var mı ve süresi dolmamış mı?
        now = time.time()
        if token in self.active_gate_tokens:
            if self.active_gate_tokens[token] > now:
                return True
        return False

# Hafızayı başlat
manager = TokenManager()

# --- VERİTABANI İŞLEMLERİ ---
def init_db():
    conn = sqlite3.connect('katilimcilar.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS katilimcilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isim TEXT NOT NULL,
            soyisim TEXT NOT NULL,
            telefon TEXT,
            mail TEXT,
            gonullu TEXT,
            kayit_zamani TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(isim, soyisim, telefon, mail, gonullu):
    conn = sqlite3.connect('katilimcilar.db')
    c = conn.cursor()
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO katilimcilar (isim, soyisim, telefon, mail, gonullu, kayit_zamani) VALUES (?,?,?,?,?,?)',
              (isim, soyisim, telefon, mail, gonullu, zaman))
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect('katilimcilar.db')
    df = pd.read_sql_query("SELECT * FROM katilimcilar ORDER BY id DESC", conn)
    conn.close()
    return df

# Veritabanını başlat
init_db()

# --- MOD SEÇİMİ ---
query_params = st.query_params
mod = query_params.get("mod", "admin")

# --- 1. MOD: KAYIT FORMU (TELEFON) ---
if mod == "kayit":
    st.title("📝 Kayıt Formu")
    
    # URL'den gelen token'ı al
    token = query_params.get("token", None)
    
    # Eğer kullanıcı daha önce onaylandıysa (session state) veya token geçerliyse
    if st.session_state.get("form_unlocked", False) or (token and manager.is_valid(token)):
        
        # Formu kilitle (Böylece QR değişse bile kullanıcı formda kalır)
        st.session_state["form_unlocked"] = True
        
        with st.form("kayit_formu", clear_on_submit=True):
            isim = st.text_input("İsim*")
            soyisim = st.text_input("Soyisim*")
            telefon = st.text_input("Telefon Numarası (İsteğe Bağlı)")
            mail = st.text_input("E-posta Adresi (İsteğe Bağlı)")
            gonullu = st.radio("SİTODED Gönüllüsü müsünüz?", ["Evet", "Hayır"], index=1)
            
            submitted = st.form_submit_button("Kaydı Tamamla")
            
            if submitted:
                if isim and soyisim:
                    add_user(isim, soyisim, telefon, mail, gonullu)
                    st.success(f"Teşekkürler {isim}, kaydınız alındı! 🎉")
                    st.balloons()
                    # Kayıt bitince kilidi kaldırabiliriz veya bırakabiliriz
                else:
                    st.error("Lütfen İsim ve Soyisim alanlarını doldurun.")
    else:
        st.error("⚠️ Bu QR kodun süresi dolmuş veya geçersiz.")
        st.info("Lütfen kapıdaki ekrandan güncel kodu tekrar okutun.")

# --- 2. MOD: QR EKRANI (TABLET - OTOMATİK YENİLENEN) ---
elif mod == "ekran":
    # Ekran modunda sidebar'ı gizle
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            .block-container {padding-top: 1rem;}
        </style>
        """, unsafe_allow_html=True)

    st.header("Etkinliğimize Hoş Geldiniz! 👋")
    
    # URL'i al (Admin panelinden girilen veya otomatik)
    base_url = query_params.get("url", "https://sitoded-qr.streamlit.app")
    
    # Yer tutucular (Placeholder): İçerikleri sonradan güncelleyeceğiz
    qr_placeholder = st.empty()
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # 15 Saniyelik Döngü
    LIFESPAN = 15
    
    # Token Oluştur
    current_token = manager.create_token(LIFESPAN)
    link = f"{base_url}/?mod=kayit&token={current_token}"
    
    # QR Kodu Oluştur
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    
    # QR'ı Ekrana Bas
    qr_placeholder.image(buf, width=400)
    
    # Geri sayım sayacı (Progress Bar)
    for i in range(LIFESPAN):
        # Kalan süreyi göster
        kalan = LIFESPAN - i
        status_text.caption(f"QR Kod **{kalan}** saniye sonra yenilenecek...")
        progress_bar.progress((i + 1) / LIFESPAN)
        time.sleep(1) # 1 saniye bekle
        
    # Süre dolunca sayfayı yenile (Rerun)
    st.rerun()

# --- 3. MOD: ADMİN PANELİ ---
else:
    st.title("Admin Paneli 🔒")
    st.sidebar.header("⚙️ Ayarlar")
    
    # Link Ayarı
    if "base_link" not in st.session_state:
        st.session_state["base_link"] = "https://sitoded-qr.streamlit.app"
        
    deployed_url = st.sidebar.text_input("Canlı Site Linkiniz:", value=st.session_state["base_link"])
    st.session_state["base_link"] = deployed_url
    
    st.sidebar.divider()
    
    # Hızlı Linkler
    st.sidebar.markdown(f"**Kapı Ekranı Linki:**")
    st.sidebar.code(f"{deployed_url}/?mod=ekran&url={deployed_url}")
    st.sidebar.link_button("Kapı Ekranını Aç 🖥️", f"{deployed_url}/?mod=ekran&url={deployed_url}")
    
    st.divider()
    
    # Tablo
    st.subheader("📊 Canlı Liste")
    if st.button("Yenile 🔄"):
        st.rerun()
        
    df = get_data()
    st.metric("Toplam Katılımcı", len(df))
    st.dataframe(df, use_container_width=True)
    
    # Excel İndir
    if not df.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Excel İndir", data=output.getvalue(), file_name="sitoded_liste.xlsx")
        
    # Silme
    with st.expander("⚠️ Veritabanını Sıfırla"):
        if st.button("TÜMÜNÜ SİL"):
            conn = sqlite3.connect('katilimcilar.db')
            conn.execute("DELETE FROM katilimcilar")
            conn.commit()
            conn.close()
            st.success("Silindi!")
            time.sleep(1)
            st.rerun()