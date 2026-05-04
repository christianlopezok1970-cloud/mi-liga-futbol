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

def formatear_abreviado(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
        elif monto >= 1_000: return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

@st.cache_data(ttl=30)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# --- 2. ESTILO CSS PERSONALIZADO ---
st.set_page_config(page_title="Pro Fútbol Manager v41", layout="wide")

st.markdown("""
    <style>
    /* Fondo principal y textos */
    .stApp {
        background-color: #0E1117;
    }
    h1, h2, h3, p {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif;
    }
    /* Tarjetas de jugadores */
    .stElementContainer div[data-testid="stVerticalBlock"] > div {
        border-radius: 10px;
    }
    /* Estilo para métricas */
    [data-testid="stMetricValue"] {
        color: #00FF41 !important; /* Verde Neón */
        font-weight: bold;
    }
    /* Botones personalizados */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        background-color: #1E1E1E;
        color: white;
        border: 1px solid #00FF41;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #00FF41;
        color: black;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LÓGICA DE NEGOCIO ---
def calcular_balance_fecha(pts, costo):
    pts = round(float(pts), 1)
    if pts >= 6.6: return int(costo * ((pts - 6.5) * 10 / 100))
    elif pts <= 6.3: return int(costo * ((pts - 6.4) * 10 / 100))
    return 0

def calcular_cambio_prestigio(pts):
    p = round(float(pts), 1)
    if p >= 8.0: return 2
    if p >= 7.0: return 1
    if p <= 5.9: return -2
    if p <= 6.7: return -1
    return 0

# --- LOGIN ---
with st.sidebar:
    st.title("💰 AGENCIA PRO")
    manager = st.text_input("Agente:").strip()
    password = st.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Bienvenid@. Inicia sesión para gestionar tu cartera.")
    st.stop()

# Tablas e Inicio de Sesión (simplificado para el ejemplo)
ejecutar_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)", commit=True)
ejecutar_db("CREATE TABLE IF NOT EXISTS cartera (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, porcentaje REAL, costo_compra REAL, club TEXT)", commit=True)
ejecutar_db("CREATE TABLE IF NOT EXISTS historial (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)", commit=True)

datos = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 2000000, 10)", (manager, password), commit=True)
    st.rerun()
else:
    u_id, presupuesto, prestigio, u_pass = datos[0]
    if password != u_pass:
        st.error("❌ Contraseña incorrecta.")
        st.stop()

df_oficial = cargar_datos_completos_google()

# Mercado Bloqueado (Lógica Global en fila 1)
mercado_bloqueado = False
if not df_oficial.empty:
    fila_control = " ".join(df_oficial.iloc[0].astype(str).upper())
    if "CERRADO" in fila_control: mercado_bloqueado = True

# --- 4. SIDEBAR MÉTRICAS ---
st.sidebar.divider()
st.sidebar.metric("DISPONIBLE", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("REPUTACIÓN", f"{prestigio} PTS")

# --- 5. CUERPO PRINCIPAL ---
t1, t2 = st.tabs(["📊 Gestión", "🏆 Mercado"])

with t1:
    st.markdown("### 📋 Tu Cartera de Representados")
    cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
    
    if not cartera:
        st.write("No tienes jugadores activos. ¡Busca talentos en el mercado!")
    
    for j_id, j_nom, j_pct, j_costo, j_club in cartera:
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([3, 2, 1])
            with col_a:
                st.markdown(f"**{j_nom}**")
                st.caption(f"Club: {j_club}")
            with col_b:
                st.markdown(f"Part: {int(j_pct)}% | €{formatear_total(j_costo)}")
            with col_c:
                if st.button("Vender", key=f"v_{j_id}"):
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_costo * 0.99, u_id), commit=True)
                    st.rerun()

with t2:
    if mercado_bloqueado:
        st.error("🚨 MERCADO CERRADO POR LA ADMINISTRACIÓN")
    else:
        st.markdown("### 🔍 Buscador de Talentos")
        seleccion = st.selectbox("Selecciona un jugador para analizar:", options=[""] + df_oficial['Display'].tolist())
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            v_m_t = int(dj['ValorNum'])
            st.info(f"Análisis de mercado: {dj.iloc[0]} tiene un valor base de €{formatear_total(v_m_t)}")
            
            # Lógica de compra simplificada aquí
            if st.button("SOLICITAR FICHAJE", type="primary"):
                st.toast("Procesando con la secretaría técnica...")

# --- FOOTER RANKING ---
st.divider()
with st.expander("🏆 Ranking Global de Agentes"):
    res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
    st.table(pd.DataFrame(res, columns=['Agente', 'Reputación', 'Caja']))
