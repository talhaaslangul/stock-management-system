import streamlit as st
import database as db
import plotly.express as px

st.set_page_config(page_title="Stok Yönetim Sistemi", layout="wide")

# --- BAĞLANTI KONTROLÜ ---
st.sidebar.title("Bağlantı Durumu")
conn = db.get_connection()
if conn:
    st.sidebar.success("Veritabanı Bağlı ✅")
    conn.close()
else:
    st.sidebar.error("Bağlantı Yok ❌")
    st.stop()

# --- MENÜ ---
menu = st.sidebar.radio("Menü", ["Ana Sayfa", "Ürünler", "Depo Yönetimi", "Stok İşlemleri", "Tedarikçiler", "Raporlar"])


# ---  ANA SAYFA  ---
if menu == "Ana Sayfa":
    st.title("🚀 Yönetici Paneli")
    st.markdown("---")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    try:
        df_prod = db.run_query("SELECT COUNT(*) as ADET FROM PRODUCT")
        total_prod = df_prod.iloc[0]['ADET']
        kpi1.metric("📦 Toplam Ürün", total_prod)
        
        df_sup = db.run_query("SELECT COUNT(*) as ADET FROM SUPPLIER")
        total_sup = df_sup.iloc[0]['ADET']
        kpi2.metric("🚚 Tedarikçiler", total_sup)
        
        df_ware = db.run_query("SELECT COUNT(*) as ADET FROM WAREHOUSE")
        total_ware = df_ware.iloc[0]['ADET']
        kpi3.metric("🏭 Aktif Depolar", total_ware)
        
        df_kritik = db.run_query("SELECT COUNT(*) as ADET FROM PRODUCT WHERE min_stock_level > 0")
        riskli_sayi = df_kritik.iloc[0]['ADET']
        kpi4.metric("⚠️ Stok Takibi", riskli_sayi)
        
    except Exception as e:
        st.error(f"Veri hatası: {e}")

    st.markdown("---")

    # --- GRAFİK VE TABLO ---
    col_left, col_right = st.columns([2, 3])
    
    with col_left:
        st.subheader("Kategori Dağılımı")
        
        #(Hata önleyici)
        sql_cat = """
            SELECT NVL(category, 'Diğer') as KAT_ADI, COUNT(*) as SAYI 
            FROM PRODUCT 
            GROUP BY category
        """
        df_cat = db.run_query(sql_cat)
        
        if not df_cat.empty:
            try:
                fig = px.pie(df_cat, values='SAYI', names='KAT_ADI', hole=0.4)
                fig.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                
                st.plotly_chart(fig, use_container_width=True, key="ana_sayfa_pasta")
                
            except Exception as e:
                st.error(f"Grafik hatası: {e}")
        else:
            st.info("Veri yok.")
            
    with col_right:
        st.subheader("📋 Son Hareketler")
        sql_last = """
            SELECT p.name as URUN, m.movement_type as TIP, m.quantity as MIKTAR, m.movement_date as TARIH
            FROM STOCK_MOVEMENT m
            JOIN PRODUCT p ON m.product_id = p.product_id
            ORDER BY m.movement_date DESC
            FETCH FIRST 5 ROWS ONLY
        """
        df_last = db.run_query(sql_last)
        st.dataframe(df_last, use_container_width=True)


    st.markdown("---")
    st.info("👈 **İPUCU:** Ürün ekleme, stok güncelleme, sipariş verme veya detaylı raporları görüntülemek için **SOL MENÜYÜ** kullanabilirsiniz.")


# --- ÜRÜN YÖNETİMİ ---
elif menu == "Ürünler":
    st.header("📦 Ürün İşlemleri")
    
    # 4 Sekmeli Yapı
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste", "➕ Ekle", "🗑️ Sil", "✏️ Düzenle"])
    
    # 1. LİSTELEME
    with tab1:
        df = db.run_query("SELECT * FROM PRODUCT ORDER BY product_id ASC")
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            fig = px.bar(df, x='NAME', y='PRICE', title="Ürün Fiyatları", color='CATEGORY')
            st.plotly_chart(fig, key="urun_fiyat_grafigi") # Key eklendi (Hata önleyici)
    
    # 2. EKLEME
    with tab2:
        st.subheader("Yeni Ürün")
        with st.form("urun_ekle"):
            ad = st.text_input("Ürün Adı")
            kat = st.text_input("Kategori")
            fiyat = st.number_input("Fiyat", min_value=0.0)
            stok = st.number_input("Min. Stok", min_value=0)
            if st.form_submit_button("Kaydet"):
                db.run_command("INSERT INTO PRODUCT (name, category, price, min_stock_level) VALUES (:1, :2, :3, :4)", (ad, kat, fiyat, stok))
                st.success("Eklendi!")
                st.rerun()

    # 3. SİLME (GÜNCELLENDİ: ARTIK HATA VERMEZ)
    with tab3:
        st.subheader("Ürün Sil")
        st.warning("⚠️ DİKKAT: Bir ürünü sildiğinizde, ona ait tüm stok geçmişi ve siparişler de silinir!")
        
        df_urunler = db.run_query("SELECT product_id, name FROM PRODUCT")
        if not df_urunler.empty:
            secenekler = [f"{row['NAME']} (ID: {row['PRODUCT_ID']})" for i, row in df_urunler.iterrows()]
            secilen = st.selectbox("Silinecek Ürün:", secenekler, key="sil_select")
            
            if st.button("Seçili Ürünü ve Geçmişini Sil", type="primary"):
                sil_id = secilen.split("ID: ")[1].replace(")", "")
                
                # ADIM 1: Önce bağlı olan 'Çocuk' kayıtları siliyoruz (Temizlik)
                db.run_command("DELETE FROM STOCK_MOVEMENT WHERE product_id = :1", (sil_id,))
                db.run_command("DELETE FROM ORDER_ITEM WHERE product_id = :1", (sil_id,))
                db.run_command("DELETE FROM SALES_RECORD WHERE product_id = :1", (sil_id,)) # Varsa
                
                # ADIM 2: Artık 'Baba' kaydı silebiliriz
                basari = db.run_command("DELETE FROM PRODUCT WHERE product_id = :1", (sil_id,))
                
                if basari:
                    st.success(f"Ürün (ID: {sil_id}) ve tüm geçmiş verileri temizlendi.")
                    st.rerun()
        else:
            st.info("Listede ürün yok.")
                
    # 4. GÜNCELLEME
    with tab4:
        st.subheader("Ürün Bilgisi Güncelle")
        df_upd = db.run_query("SELECT product_id, name, category, price, min_stock_level FROM PRODUCT")
        if not df_upd.empty:
            liste = [f"{row['NAME']} (ID: {row['PRODUCT_ID']})" for i, row in df_upd.iterrows()]
            secim = st.selectbox("Düzenlenecek Ürünü Seç:", liste, key="upd_select")
            
            secilen_id = int(secim.split("ID: ")[1].replace(")", ""))
            mevcut_veri = df_upd[df_upd['PRODUCT_ID'] == secilen_id].iloc[0]
            
            with st.form("update_form"):
                yeni_ad = st.text_input("Ürün Adı", value=mevcut_veri['NAME'])
                yeni_kat = st.text_input("Kategori", value=mevcut_veri['CATEGORY'])
                yeni_fiyat = st.number_input("Fiyat", min_value=0.0, value=float(mevcut_veri['PRICE']))
                yeni_stok = st.number_input("Min Stok", min_value=0, value=int(mevcut_veri['MIN_STOCK_LEVEL']))
                
                if st.form_submit_button("Güncelle"):
                    sql_update = """
                        UPDATE PRODUCT 
                        SET name=:1, category=:2, price=:3, min_stock_level=:4 
                        WHERE product_id=:5
                    """
                    basari = db.run_command(sql_update, (yeni_ad, yeni_kat, yeni_fiyat, yeni_stok, secilen_id))
                    if basari:
                        st.success("Ürün bilgileri güncellendi!")
                        st.rerun()
        else:
            st.info("Güncellenecek ürün yok.")

# --- DEPO YÖNETİMİ ---
elif menu == "Depo Yönetimi":
    st.header("🏭 Depo ve Şube Yönetimi")
    
    tab1, tab2 = st.tabs(["📋 Depo Listesi", "➕ Yeni Depo Ekle"])
    
    # Depoları Listele
    with tab1:
        df = db.run_query("SELECT * FROM WAREHOUSE")
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            st.write("---")
            st.subheader("🗑️ Depo Sil")
            depo_list = [f"{row['NAME']} (ID: {row['WAREHOUSE_ID']})" for i, row in df.iterrows()]
            silinecek = st.selectbox("Silinecek Depoyu Seçin", depo_list)
            
            if st.button("Seçili Depoyu Sil", type="primary"):
                sil_id = silinecek.split("ID: ")[1].replace(")", "")
                kontrol = db.run_query(f"SELECT COUNT(*) as ADET FROM STOCK_MOVEMENT WHERE warehouse_id = {sil_id}")
                hareket_sayisi = kontrol.iloc[0]['ADET']
                
                if hareket_sayisi > 0:
                    st.error(f"Bu depoda {hareket_sayisi} adet işlem kaydı var! Önce kayıtları silmelisiniz.")
                else:
                    db.run_command("DELETE FROM WAREHOUSE WHERE warehouse_id = :1", (sil_id,))
                    st.success("Depo başarıyla silindi.")
                    st.rerun()

    # Yeni Depo Ekle
    with tab2:
        st.subheader("Yeni Depo Bilgileri")
        with st.form("depo_ekle_form"):
            ad = st.text_input("Depo Adı (Örn: İzmir Şube)")
            konum = st.text_input("Konum / Adres (Örn: Bornova, İzmir)")
            
            submit = st.form_submit_button("Kaydet")
            
            if submit:
                sql = "INSERT INTO WAREHOUSE (name, location) VALUES (:1, :2)"
                if db.run_command(sql, (ad, konum)):
                    st.success(f"✅ {ad} sisteme eklendi!")
                    st.rerun()

# STOK İŞLEMLERİ
elif menu == "Stok İşlemleri":
    st.header("🔄 Stok Giriş / Çıkış")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Yeni İşlem Kaydı")
        
        # Ürün Seçimi
        df_urn = db.run_query("SELECT product_id, name FROM PRODUCT")
        if df_urn.empty:
            st.error("Önce ürün eklemelisiniz!")
            st.stop()
        
        urn_list = [f"{row['NAME']} (ID: {row['PRODUCT_ID']})" for i, row in df_urn.iterrows()]
        secilen_urun = st.selectbox("Ürün Seçiniz", urn_list)
        
        # Depo Seçimi
        df_depo = db.run_query("SELECT warehouse_id, name FROM WAREHOUSE")
        if df_depo.empty:
            st.error("Sistemde depo yok! Lütfen veritabanına depo ekleyin.")
            # Otomatik depo ekleme butonu (Kolaylık olsun diye)
            if st.button("Otomatik 'Merkez Depo' Oluştur"):
                db.run_command("INSERT INTO WAREHOUSE (name, location) VALUES ('Merkez Depo', 'Ankara')")
                st.rerun()
            st.stop()
            
        depo_list = [f"{row['NAME']} (ID: {row['WAREHOUSE_ID']})" for i, row in df_depo.iterrows()]
        secilen_depo = st.selectbox("Depo Seçiniz", depo_list)
        
        # İşlem Tipi ve Miktar
        islem_tipi = st.radio("Hareket Tipi", ["GİRİŞ (Stok Ekle)", "ÇIKIŞ (Stok Düş)"])
        miktar = st.number_input("Miktar", min_value=1, value=10)
        
        if st.button("İşlemi Onayla"):
            p_id = secilen_urun.split("ID: ")[1].replace(")", "")
            w_id = secilen_depo.split("ID: ")[1].replace(")", "")
            
            db_tip = 'IN' if "GİRİŞ" in islem_tipi else 'OUT'
            
            sql = """
                INSERT INTO STOCK_MOVEMENT (product_id, warehouse_id, movement_type, quantity, movement_date)
                VALUES (:1, :2, :3, :4, SYSDATE)
            """
            basari = db.run_command(sql, (p_id, w_id, db_tip, miktar))
            
            if basari:
                st.success(f"{miktar} adet işlem başarıyla kaydedildi!")
                st.rerun()
                
    with col2:
        st.subheader("📋 Son Hareketler")
        sql_gecmis = """
            SELECT p.name as URUN, w.name as DEPO, m.movement_type as TIP, m.quantity as MIKTAR, m.movement_date as TARIH
            FROM STOCK_MOVEMENT m
            JOIN PRODUCT p ON m.product_id = p.product_id
            JOIN WAREHOUSE w ON m.warehouse_id = w.warehouse_id
            ORDER BY m.movement_date DESC
            FETCH FIRST 10 ROWS ONLY
        """
        df_gecmis = db.run_query(sql_gecmis)
        st.dataframe(df_gecmis, use_container_width=True)

# --- TEDARİKÇİ VE SİPARİŞ YÖNETİMİ ---
elif menu == "Tedarikçiler":
    st.header("🚚 Tedarikçi ve Sipariş Yönetimi")
    
    tab1, tab2, tab3 = st.tabs(["🏢 Tedarikçi Listesi", "➕ Yeni Tedarikçi", "📝 Sipariş Oluştur"])
    
    # --- TEDARİKÇİ LİSTESİ VE SİLME ---
    with tab1:
        st.subheader("Kayıtlı Tedarikçiler")
        df_ted = db.run_query("SELECT * FROM SUPPLIER")
        st.dataframe(df_ted, use_container_width=True)
        
        if not df_ted.empty:
            st.divider()
            st.write("🗑️ **Tedarikçi Sil**")
            liste = [f"{row['NAME']} (ID: {row['SUPPLIER_ID']})" for i, row in df_ted.iterrows()]
            silinecek = st.selectbox("Silinecek Firmayı Seçin", liste)
            
            if st.button("Firmayı Sil", type="primary"):
                sil_id = silinecek.split("ID: ")[1].replace(")", "")
                chk = db.run_query(f"SELECT COUNT(*) as ADET FROM ORDERS WHERE supplier_id={sil_id}")
                if chk.iloc[0]['ADET'] > 0:
                    st.error("Bu tedarikçiye ait siparişler var! Önce siparişleri silmelisiniz.")
                else:
                    db.run_command("DELETE FROM SUPPLIER WHERE supplier_id=:1", (sil_id,))
                    st.success("Tedarikçi silindi.")
                    st.rerun()

    # --- YENİ TEDARİKÇİ EKLEME ---
    with tab2:
        st.subheader("Yeni Firma Kaydı")
        with st.form("tedarikci_ekle"):
            ad = st.text_input("Firma Adı")
            tel = st.text_input("Telefon")
            adres = st.text_area("Adres")
            mail = st.text_input("E-posta")
            
            if st.form_submit_button("Kaydet"):
                sql = "INSERT INTO SUPPLIER (name, phone, address, email) VALUES (:1, :2, :3, :4)"
                if db.run_command(sql, (ad, tel, adres, mail)):
                    st.success(f"{ad} sisteme eklendi!")
                    st.rerun()

    # --- SİPARİŞ OLUŞTURMA  ---
    with tab3:
        st.subheader("Yeni Sipariş Ver")
        
        col1, col2 = st.columns(2)
        
        with col1: 
            # 1. Tedarikçi Seç
            df_sup = db.run_query("SELECT supplier_id, name FROM SUPPLIER")
            if df_sup.empty:
                st.warning("Önce tedarikçi eklemelisiniz.")
                st.stop()
            sup_list = [f"{row['NAME']} (ID: {row['SUPPLIER_ID']})" for i, row in df_sup.iterrows()]
            secilen_sup = st.selectbox("Tedarikçi Seç:", sup_list)
            
            # 2. Ürün Seç 
            df_prod = db.run_query("SELECT product_id, name FROM PRODUCT")
            if df_prod.empty:
                st.warning("Ürün listesi boş.")
                st.stop()
            prod_list = [f"{row['NAME']} (ID: {row['PRODUCT_ID']})" for i, row in df_prod.iterrows()]
            secilen_prod = st.selectbox("Sipariş Edilecek Ürün:", prod_list)
            
            # 3. Miktar ve Durum
            miktar = st.number_input("Adet", min_value=1, value=100)
            durum = st.selectbox("Sipariş Durumu", ["Onay Bekliyor", "Teslim Edildi", "İptal Edildi"])
            
            if st.button("Siparişi Oluştur"):
                sup_id = secilen_sup.split("ID: ")[1].replace(")", "")
                prod_id = secilen_prod.split("ID: ")[1].replace(")", "")
                
                # ORDERS tablosuna ekle
                sql_order = "INSERT INTO ORDERS (supplier_id, order_date, status) VALUES (:1, SYSDATE, :2)"
                db.run_command(sql_order, (sup_id, durum))
                
                # Son eklenen Order ID'yi bul
                df_last = db.run_query("SELECT MAX(order_id) as SON_ID FROM ORDERS")
                son_id = int(df_last.iloc[0]['SON_ID'])
                
                # ORDER_ITEM tablosuna detay ekle
                sql_item = "INSERT INTO ORDER_ITEM (order_id, product_id, quantity) VALUES (:1, :2, :3)"
                basari = db.run_command(sql_item, (son_id, prod_id, miktar))
                
                if basari:
                    st.success(f"Sipariş (No: {son_id}) başarıyla oluşturuldu!")
                    st.rerun()

        with col2:
            st.write("📋 **Son Siparişler**")
            sql_list = """
            SELECT o.order_id, s.name as FIRMA, p.name as URUN, i.quantity as ADET, o.status as DURUM, o.order_date
            FROM ORDERS o
            JOIN SUPPLIER s ON o.supplier_id = s.supplier_id
            JOIN ORDER_ITEM i ON o.order_id = i.order_id
            JOIN PRODUCT p ON i.product_id = p.product_id
            ORDER BY o.order_id DESC
            """
            df_orders = db.run_query(sql_list)
            st.dataframe(df_orders, use_container_width=True)

# --- RAPORLAR  ---
elif menu == "Raporlar":
    st.header("📈 Raporlar ve Analiz")
    
    tab1, tab2, tab3 = st.tabs(["⚠️ Kritik Stok", "🏭 Depo Analizi", "🏆 En Çok Satanlar"])
    
    # --- KRİTİK STOK ---
    with tab1:
        st.subheader("Stok Seviyesi Uyarısı")
        st.info("Giren (IN) ve Çıkan (OUT) ürün farkına göre güncel stok hesaplanır.")
        
        sql_stok = """
        SELECT 
            p.name as URUN, 
            p.category as KATEGORI,
            p.min_stock_level as MIN_SEVIYE,
            NVL((SELECT SUM(quantity) FROM STOCK_MOVEMENT WHERE product_id = p.product_id AND movement_type = 'IN'), 0) - 
            NVL((SELECT SUM(quantity) FROM STOCK_MOVEMENT WHERE product_id = p.product_id AND movement_type = 'OUT'), 0) as GUNCEL_STOK
        FROM PRODUCT p
        """
        df_stok = db.run_query(sql_stok)
        
        if not df_stok.empty:
            df_kritik = df_stok[df_stok['GUNCEL_STOK'] <= df_stok['MIN_SEVIYE']]
            
            if not df_kritik.empty:
                st.error(f"Dikkat! Toplam {len(df_kritik)} ürün kritik seviyenin altında!")
                st.dataframe(df_kritik, use_container_width=True)
            else:
                st.success("Harika! Tüm ürünlerin stok seviyesi güvenli.")
            
            with st.expander("Tüm Ürünlerin Stok Durumunu İncele"):
                st.dataframe(df_stok, use_container_width=True)
        else:
            st.warning("Veritabanında henüz ürün veya stok hareketi yok.")

    # --- DEPO ANALİZİ ---
    with tab2:
        st.subheader("Depo İşlem Hacimleri")
        
        sql_depo = """
        SELECT w.name as DEPO_ADI, w.location as KONUM, SUM(sm.quantity) as ISLEM_HACMI
        FROM STOCK_MOVEMENT sm
        JOIN WAREHOUSE w ON sm.warehouse_id = w.warehouse_id
        GROUP BY w.name, w.location
        ORDER BY ISLEM_HACMI DESC
        """
        df_depo = db.run_query(sql_depo)
        
        if not df_depo.empty:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.write("Depo Bazlı Toplam Hareket:")
                st.dataframe(df_depo, use_container_width=True)
            
            with col2:
                fig = px.pie(df_depo, values='ISLEM_HACMI', names='DEPO_ADI', 
                             title='Depolardaki Yoğunluk Dağılımı', hole=0.4)
                st.plotly_chart(fig)
        else:
            st.info("Depolarda henüz işlem kaydı bulunmamaktadır.")

    # --- EN ÇOK SATANLAR ---
    with tab3:
        st.subheader("🏆 En Çok Tercih Edilen Ürünler")
        st.markdown("Depodan çıkışı (**Satış**) en çok yapılan ürünlerin sıralamasıdır.")
        
        sql_best = """
        SELECT p.name as URUN_ADI, p.category as KATEGORI, SUM(sm.quantity) as TOPLAM_SATIS
        FROM STOCK_MOVEMENT sm
        JOIN PRODUCT p ON sm.product_id = p.product_id
        WHERE sm.movement_type = 'OUT'
        GROUP BY p.name, p.category
        ORDER BY TOPLAM_SATIS DESC
        """
        df_best = db.run_query(sql_best)
        
        if not df_best.empty:
            c1, c2, c3 = st.columns(3)
            
            if len(df_best) > 0:
                c1.metric("🥇 Şampiyon", df_best.iloc[0]['URUN_ADI'], f"{df_best.iloc[0]['TOPLAM_SATIS']} Adet")
            if len(df_best) > 1:
                c2.metric("🥈 İkinci", df_best.iloc[1]['URUN_ADI'], f"{df_best.iloc[1]['TOPLAM_SATIS']} Adet")
            if len(df_best) > 2:
                c3.metric("🥉 Üçüncü", df_best.iloc[2]['URUN_ADI'], f"{df_best.iloc[2]['TOPLAM_SATIS']} Adet")
            
            st.divider()
            
            col_tablo, col_grafik = st.columns([1, 2])
            
            with col_tablo:
                st.dataframe(df_best, use_container_width=True)
                
            with col_grafik:
                fig_best = px.bar(df_best, x='URUN_ADI', y='TOPLAM_SATIS', 
                                  color='TOPLAM_SATIS', title="Satış Performans Grafiği")
                st.plotly_chart(fig_best)
        else:
            st.warning("Henüz hiç 'ÇIKIŞ' (Satış) işlemi yapılmadığı için veri yok.")