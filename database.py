import oracledb
import pandas as pd
import streamlit as st

DB_CONFIG = {
    "user": "SYSTEM",          
    "password": "1234",    
    "dsn": "localhost:1521/XEPDB1" 
}


# --- BAĞLANTI FONKSİYONU ---
def get_connection():
    try:
        conn = oracledb.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            dsn=DB_CONFIG["dsn"]
        )
        return conn
    except oracledb.Error as e:
        st.error(f"🚨 Veritabanı Bağlantı Hatası: {e}")
        st.warning("İpucu: database.py dosyasındaki şifrenin doğru olduğundan emin olun.")
        return None

# --- SORGULARI ÇALIŞTIRAN FONKSİYON ---
def run_query(query, params=None):
    conn = get_connection()
    if conn:
        try:
            if params:
                df = pd.read_sql(query, conn, params=params)
            else:
                df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"Sorgu Hatası: {e}")
            conn.close()
            return pd.DataFrame()
    return pd.DataFrame()

# --- EKLEME/SİLME İŞLEMİ YAPAN FONKSİYON ---
def run_command(sql, params):
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit() 
            cursor.close()
            conn.close()
            return True
        except oracledb.Error as e:
            st.error(f"İşlem Hatası: {e}")
            conn.close()
            return False
    return False