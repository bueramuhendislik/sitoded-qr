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

# --- URL PARAMETRELERİNİ AL ---
# Streamlit'in yeni versiyonunda query params alma yöntemi:
query_params = st.query_params
mod = query_params.get("mod", "admin") # Varsayılan mod: admin

# --- 1. MOD: KAYIT FORMU (TELEFONDA GÖRÜNEN) ---
if mod == "kayit":
    st.title("📝 Kayıt Formu")
    
    with st.form("kayit_formu", clear_on_submit=True):
        isim = st.text_input("İsim*")
        soyisim = st.text_input("Soyisim*")
        
        # Admin panelinden gelen ayarlara göre alanları göster/gizle
        # (Not: Basitlik için burada URL parametresi ile de ayar taşınabilir ama
        # şimdilik opsiyonel alanları her zaman gösterelim veya boş bırakılabilir yapalım)
        telefon = st.text_input("Telefon Numarası (İsteğe Bağlı)")
        mail = st.text_input("E-posta Adresi (İsteğe Bağlı)")
        gonullu = st.radio("SİTODED Gönüllüsü müsünüz?", ["Evet", "Hayır"], index=1)
        
        submitted = st.form_submit_button("Kaydı Tamamla")
        
        if submitted:
            if isim and soyisim:
                add_user(isim, soyisim, telefon, mail, gonullu)
                st.success(f"Teşekkürler {isim}, kaydınız alındı! 🎉")
                st.balloons()
            else:
                st.error("Lütfen İsim ve Soyisim alanlarını doldurun.")

# --- 2. MOD: QR EKRANI (KAPIDAKİ TABLET) ---
elif mod == "ekran":
    # Yan menüyü ve gereksiz öğeleri gizle
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .block-container {padding-top: 2rem;}
        </style>
        """, unsafe_allow_html=True)

    st.header("Etkinliğimize Hoş Geldiniz! 👋")
    st.write("Lütfen kayıt olmak için QR kodu okutun.")
    
    # QR Kodun yönlendireceği adres
    # Not: Buraya canlıya aldığınızda size verilen adresi yazmalısınız!
    # Şimdilik URL'den base_url'i çekmeye çalışalım, olmazsa manuel girilir.
    
    # Kullanıcıdan veya URL'den ana adresi al
    base_url = query_params.get("url", "https://LUTFEN-ADMIN-PANELINDEN-LINKI-GUNCELLEYIN.com")
    link = f"{base_url}/?mod=kayit"
    
    # QR Kod Oluşturma
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Görüntüyü Streamlit'e uygun hale getir
    buf = BytesIO()
    img.save(buf, format="PNG")
    st.image(buf, width=350)
    
    st.info("Formu doldurmak için kameranızı açın.")
    
    # Sayfayı periyodik olarak yenilemeye gerek yok çünkü link sabit.
    # Ancak "Dinamik his" vermek veya bağlantıyı taze tutmak için:
    time.sleep(1) # CPU yormamak için minik bekleme

# --- 3. MOD: ADMİN PANELİ (SİZİN EKRANINIZ) ---
else:
    st.title("Admin Paneli 🔒")
    
    st.sidebar.header("⚙️ Ayarlar")
    
    # Canlı URL Ayarı
    deployed_url = st.sidebar.text_input(
        "Canlı Site Linkiniz:", 
        value="https://sitoded-kayit.streamlit.app",
        help="Render veya Streamlit Cloud'dan aldığınız linki buraya yapıştırın."
    )
    
    st.sidebar.divider()
    
    st.sidebar.markdown("### 🔗 Hızlı Linkler")
    st.sidebar.markdown(f"**Kapı Ekranı Linki:**\n`{deployed_url}/?mod=ekran&url={deployed_url}`")
    st.sidebar.link_button("Kapı Ekranını Aç 🖥️", f"{deployed_url}/?mod=ekran&url={deployed_url}")
    
    st.sidebar.markdown(f"**Kayıt Formu Linki:**\n`{deployed_url}/?mod=kayit`")
    
    st.divider()
    
    # Verileri Göster
    st.subheader("📊 Canlı Katılımcı Listesi")
    
    # Yenileme butonu
    if st.button("Listeyi Yenile 🔄"):
        st.rerun()
        
    df = get_data()
    
    # İstatistikler
    col1, col2 = st.columns(2)
    col1.metric("Toplam Katılımcı", len(df))
    col2.metric("Son Kayıt", df.iloc[0]['kayit_zamani'] if not df.empty else "-")
    
    # Tabloyu göster
    st.dataframe(df, use_container_width=True)
    
    # Excel İndirme Butonu
    if not df.empty:
        # Excel dosyasını bellekte oluştur
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Katilimcilar')
            
        st.download_button(
            label="📥 Listeyi Excel Olarak İndir",
            data=output.getvalue(),
            file_name=f"sitoded_katilimcilar_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Veritabanı Temizleme (Tehlikeli Bölge)
    with st.expander("⚠️ Tehlikeli Bölge (Sıfırlama)"):
        st.write("Bu işlem tüm kayıtları siler. Geri alınamaz!")
        if st.button("Tüm Veritabanını Sil"):
            conn = sqlite3.connect('katilimcilar.db')
            c = conn.cursor()
            c.execute("DELETE FROM katilimcilar")
            conn.commit()
            conn.close()
            st.warning("Veritabanı sıfırlandı!")
            time.sleep(1)
            st.rerun()