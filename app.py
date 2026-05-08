import streamlit as st
import sqlite3
import pandas as pd
import random
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL Y DB ---
DB_NAME = 'agencia_global_v41.db'
# NUEVO SHEET PROPORCIONADO
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ2VmykJ-6g-KVHVS3doLPVdxGA09KgOByjy67lnJW-VlJxLWgukpKAUM1PmeTOKbPtH1fNDSUyCBTO/pub?output=csv"

st.set_page_config(page_title="AFA Manager Pro 2026", layout="wide")

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

# --- INICIALIZACIÓN DE TABLAS ---
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)''', commit=True)

ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT, titular INTEGER DEFAULT 0)''', commit=True)

# Parche de seguridad por si la tabla ya existía sin la columna titular
try:
    ejecutar_db("ALTER TABLE cartera ADD COLUMN titular INTEGER DEFAULT 0", commit=True)
except:
    pass

# --- 2. ESTILO VISUAL ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); }
    h1, h2, h3, h4, h5, p, span, label { color: #f0f2f6 !important; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #003366 !important;
        border-radius: 10px;
        padding: 15px;
    }
    .stButton>button { background-color: #004494; color: white; border-radius: 8px; font-weight: bold; width: 100%; border: none; }
    .stButton>button:hover { background-color: #005bc4; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES DE CARGA Y ESTRELLAS ---
@st.cache_data(ttl=60)
def cargar_datos_excel():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # En este sheet: Nivel es la columna 2, Score es la columna 4
        df['NivelNum'] = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(1)
        df['ScoreNum'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def formato_estrellas(nivel):
    n = int(nivel)
    if n >= 5: return "⭐⭐⭐⭐⭐"
    if n == 4: return "⭐⭐⭐⭐"
    if n == 3: return "⭐⭐⭐"
    if n == 2: return "⭐⭐"
    return "⭐"

def formatear_abreviado(monto):
    m = float(monto)
    if m >= 1_000_000: return f"{m / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
    if m >= 1_000: return f"{m / 1_000:.0f}K"
    return str(int(m))

# --- 4. LOGIN ---
if 'manager_id' not in st.session_state:
    with st.sidebar:
        st.title("🛡️ ACCESO")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR / REGISTRAR"):
            res = ejecutar_db("SELECT id, password FROM usuarios WHERE nombre = ?", (u,))
            if res:
                if res[0][1] == p:
                    st.session_state.manager_id = res[0][0]
                    st.rerun()
                else: st.error("Clave incorrecta")
            else:
                ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (u, p), commit=True)
                st.success("Cuenta creada")
                st.rerun()
    st.stop()

u_id = st.session_state.manager_id
user_info = ejecutar_db("SELECT nombre, presupuesto, prestigio FROM usuarios WHERE id = ?", (u_id,))[0]
df_base = cargar_datos_excel()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.subheader(f"👤 {user_info[0]}")
    st.metric("Presupuesto", f"€ {formatear_abreviado(user_info[1])}")
    
    if st.button("Cerrar Sesión"):
        del st.session_state.manager_id
        st.rerun()

    st.divider()
    st.subheader("🛒 Mercado")
    if st.button("🔭 COMPRAR PACK SCOUTING (100c)"):
        # Adaptado a 100 créditos como tu ejemplo original si prefieres, 
        # o puedes cambiarlo a 2.5M. Usaremos 2.500.000 para consistencia con tu v41.
        costo = 2500000 
        if user_info[1] >= costo:
            jugador = df_base.sample(n=1).iloc[0]
            nom = jugador.iloc[0] # Columna Jugador
            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, costo_compra, club) VALUES (?, ?, ?, ?)",
                        (u_id, nom, 1000000, jugador.iloc[3]), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo, u_id), commit=True)
            st.success(f"¡Salió {nom}!")
            st.rerun()
        else:
            st.error("Dinero insuficiente")

# --- 6. INTERFAZ PRINCIPAL ---
st.title("⚽ AFA Manager Pro 2026")

cartera = ejecutar_db("SELECT id, nombre_jugador, club, titular FROM cartera WHERE usuario_id = ?", (u_id,))
df_cartera = pd.DataFrame(cartera, columns=['id', 'Jugador', 'Equipo', 'titular'])

if not df_cartera.empty:
    # Unir con datos del Sheet (Jugador, POS, Nivel, Score)
    df_cartera = df_cartera.merge(df_base[['Jugador', 'POS', 'NivelNum', 'ScoreNum']], on='Jugador', how='left')
    df_cartera['Estrellas'] = df_cartera['NivelNum'].apply(formato_estrellas)

    # TITULARES
    st.subheader("🔝 Once Titular")
    tits = df_cartera[df_cartera['titular'] == 1]
    if not tits.empty:
        st.dataframe(tits[['POS', 'Jugador', 'Equipo', 'Estrellas', 'ScoreNum']], use_container_width=True, hide_index=True)
        bajar = st.selectbox("Quitar del once:", tits['Jugador'])
        if st.button("Mandar al banco ⬇️"):
            ejecutar_db("UPDATE cartera SET titular = 0 WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, bajar), commit=True)
            st.rerun()
    else:
        st.info("No hay titulares.")

    st.divider()

    # BANCO (POR COLUMNAS)
    st.subheader("⏬ Banco de Suplentes")
    banco = df_cartera[df_cartera['titular'] == 0]
    
    posiciones = ["ARQ", "DEF", "VOL", "DEL"]
    cols = st.columns(4)
    
    for i, p in enumerate(posiciones):
        with cols[i]:
            st.markdown(f"#### {p}")
            jugs = banco[banco['POS'] == p]
            for _, j in jugs.iterrows():
                with st.container(border=True):
                    st.markdown(f"<span style='font-size:20px; font-weight:bold; color:#00D4FF;'>{j['Jugador']}</span>", unsafe_allow_html=True)
                    st.write(f"{j['Equipo']}")
                    st.write(j['Estrellas'])
                    
                    if st.button("TITULAR ⬆️", key=f"t_{j['id']}"):
                        ejecutar_db("UPDATE cartera SET titular = 1 WHERE id = ?", (j['id'],), commit=True)
                        st.rerun()
                    
                    if st.button("VENDER 💰", key=f"v_{j['id']}"):
                        pago = 500000 # Valor fijo o basado en nivel
                        ejecutar_db("DELETE FROM cartera WHERE id = ?", (j['id'],), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (pago, u_id), commit=True)
                        st.rerun()
else:
    st.warning("Compra jugadores en el mercado lateral.")
