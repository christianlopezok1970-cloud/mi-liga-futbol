import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v41.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

def formatear_total(monto):
    try: return f"{int(float(monto)):,}".replace(',', '.')
    except: return "0"

@st.cache_data(ttl=60)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Limpieza de valores numéricos de la columna D (índice 3)
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        # Puntaje oficial está en la columna E (índice 4)
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# Tablas iniciales
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- ESTILO ---
st.markdown("<style>.stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); } h1,h2,h3,h4,p,span,label { color: #f0f2f6 !important; } div[data-testid='stVerticalBlock'] > div[style*='border'] { background-color: rgba(255, 255, 255, 0.05); border: 1px solid #003366 !important; border-radius: 10px; } .stButton>button { background-color: #004494; color: white; width: 100%; }</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Pro Fútbol Manager v41", layout="wide")
st.subheader("Pro Fútbol Manager")

# --- LOGIN ---
with st.sidebar:
    st.title("🔐 Acceso")
    manager = st.text_input("Agente:").strip()
    password = st.text_input("Password:", type="password").strip()

if not manager or not password:
    st.info("Introduce tus credenciales.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))

if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (manager, password), commit=True)
    st.rerun()
else:
    u_id, presupuesto, prestigio, u_pass = datos[0]
    if password != u_pass:
        st.error("❌ Error"); st.stop()

df_oficial = cargar_datos_completos_google()

# --- SIDEBAR MÉTRICAS ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

# --- 6. SCOUTING (2.5M) ---
st.markdown("### 🎲 Scouting Premium")
COSTO_OP = 2500000
if st.button(f"🔭 LANZAR BÚSQUEDA (2.5M)"):
    if presupuesto >= COSTO_OP:
        jugador_azar = df_oficial.sample(n=1).iloc[0]
        nom = jugador_azar.iloc[0].strip()
        valor_real = int(jugador_azar['ValorNum'])
        club_j = jugador_azar.iloc[1]
        
        ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
        if not ya_lo_tiene:
            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?, ?, 100, ?, ?)", (u_id, nom, valor_real, club_j), commit=True)
            st.success(f"¡Fichado: {nom}!")
        else:
            st.error(f"Duplicado: {nom}. Dinero perdido.")
        
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (COSTO_OP, u_id), commit=True)
        st.rerun()
    else:
        st.error("No tienes dinero.")

# --- 7. MIS REPRESENTADOS (ORGANIZADOS POR TUS COLUMNAS) ---
st.divider()
st.markdown("### 📋 Mis Jugadores")
cartera_db = ejecutar_db("SELECT id, nombre_jugador, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera_db:
    st.info("Tu cartera está vacía.")
else:
    # Clasificación exacta por columna C (Posición)
    cat = {"ARQ": [], "DEF": [], "VOL": [], "DEL": [], "OTRO": []}
    
    for j_id, j_nom, j_valor, j_club in cartera_db:
        # Buscamos en el excel
        m = df_oficial[df_oficial.iloc[:, 0].str.strip().str.upper() == j_nom.strip().upper()]
        if not m.empty:
            p_excel = str(m.iloc[0, 2]).strip().upper() # Columna C es índice 2
            if p_excel in cat: cat[p_excel].append((j_id, j_nom, j_valor, j_club))
            else: cat["OTRO"].append((j_id, j_nom, j_valor, j_club))
        else:
            cat["OTRO"].append((j_id, j_nom, j_valor, j_club))

    cols = st.columns(5)
    titulos = ["ARQ", "DEF", "VOL", "DEL", "OTRO"]
    iconos = ["🧤 ARQ", "🛡️ DEF", "⚙️ VOL", "🏹 DEL", "❓ OTRO"]

    for i, t in enumerate(titulos):
        with cols[i]:
            st.markdown(f"**{iconos[i]}**")
            for j_id, j_nom, j_valor, j_club in cat[t]:
                with st.container(border=True):
                    st.markdown(f"**{j_nom}**")
                    st.write(f"Valor: €{formatear_total(j_valor)}")
                    if st.checkbox("Vender", key=f"c_{j_id}"):
                        if st.button("CONFIRMAR", key=f"b_{j_id}"):
                            ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_valor * 0.99, u_id), commit=True)
                            st.rerun()
