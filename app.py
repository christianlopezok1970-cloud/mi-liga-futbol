import streamlit as st
import sqlite3
import pandas as pd
import random
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL Y DB ---
DB_NAME = 'agencia_global_v41.db'
# Convertimos el link HTML a CSV para que Pandas lo entienda
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

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

# Parche por si la columna titular no existe en tu .db actual
try:
    ejecutar_db("ALTER TABLE cartera ADD COLUMN titular INTEGER DEFAULT 0", commit=True)
except:
    pass

# --- 2. ESTILO VISUAL AZUL PROFUNDO ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); }
    h1, h2, h3, h4, h5, p, span, label { color: #f0f2f6 !important; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #003366 !important;
        border-radius: 12px;
        padding: 15px;
    }
    .stButton>button { background-color: #004494; color: white; border-radius: 8px; font-weight: bold; width: 100%; border: none; height: 3em; }
    .stButton>button:hover { background-color: #005bc4; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. PROCESAMIENTO DE DATOS ---
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Limpieza de Cotización (Columna D - Índice 3)
        def limpiar_v(v):
            try: return int(''.join(filter(str.isdigit, str(v).replace('.',''))))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_v)
        # Puntaje (Columna E - Índice 4)
        df['ScoreNum'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return pd.DataFrame()

def obtener_estrellas(score):
    try:
        s = float(score)
        if s >= 9: return "⭐⭐⭐⭐⭐"
        if s >= 7.5: return "⭐⭐⭐⭐"
        if s >= 6: return "⭐⭐⭐"
        if s >= 4.5: return "⭐⭐"
        return "⭐"
    except: return "⭐"

def formato_dinero(monto):
    m = float(monto)
    if m >= 1_000_000: return f"{m / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
    if m >= 1_000: return f"{m / 1_000:.0f}K"
    return str(int(m))

# --- 4. SISTEMA DE LOGIN ---
if 'manager_id' not in st.session_state:
    with st.sidebar:
        st.title("🛡️ AGENCIA ACCESO")
        u = st.text_input("Agente").strip()
        p = st.text_input("Password", type="password").strip()
        if st.button("INGRESAR"):
            if u and p:
                res = ejecutar_db("SELECT id, password FROM usuarios WHERE nombre = ?", (u,))
                if res:
                    if res[0][1] == p:
                        st.session_state.manager_id = res[0][0]
                        st.rerun()
                    else: st.error("Password incorrecto")
                else:
                    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (u, p), commit=True)
                    st.success("Cuenta de Agente creada")
                    st.rerun()
    st.stop()

# Cargar Info Manager
u_id = st.session_state.manager_id
u_nombre, u_presu, u_pres = ejecutar_db("SELECT nombre, presupuesto, prestigio FROM usuarios WHERE id = ?", (u_id,))[0]
df_base = cargar_datos()

# --- 5. PANEL LATERAL ---
with st.sidebar:
    st.subheader(f"💼 Agente: {u_nombre}")
    st.metric("Caja Global", f"€ {formato_dinero(u_presu)}")
    st.metric("Reputación", f"{u_pres} pts")
    
    if st.button("Cerrar Sesión"):
        del st.session_state.manager_id
        st.rerun()

    st.divider()
    st.subheader("🔭 Scouting Premium")
    costo_scout = 2500000
    if st.button(f"BUSCAR JUGADOR ({formato_dinero(costo_scout)})"):
        if u_presu >= costo_scout:
            j_azar = df_base.sample(n=1).iloc[0]
            nom = j_azar.iloc[0]
            club = j_azar.iloc[1]
            valor = j_azar['ValorNum']
            
            # Check duplicados
            if not ejecutar_db("SELECT id FROM cartera WHERE usuario_id=? AND nombre_jugador=?", (u_id, nom)):
                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, costo_compra, club) VALUES (?, ?, ?, ?)",
                            (u_id, nom, valor, club), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_scout, u_id), commit=True)
                st.success(f"¡Fichado: {nom}!")
                st.rerun()
            else:
                st.warning(f"{nom} ya está en tu agencia. Dinero perdido.")
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_scout, u_id), commit=True)
                st.rerun()
        else:
            st.error("Fondos insuficientes")

# --- 6. GESTIÓN DE PLANTILLA ---
st.title("⚽ AFA Manager Pro 2026")

raw_cartera = ejecutar_db("SELECT id, nombre_jugador, club, titular FROM cartera WHERE usuario_id = ?", (u_id,))
df_cartera = pd.DataFrame(raw_cartera, columns=['id', 'Jugador', 'Club_DB', 'titular'])

if not df_cartera.empty:
    # Unir con datos del Sheet para POS y Score
    df_cartera = df_cartera.merge(df_base.iloc[:, [0, 2, 4]], left_on='Jugador', right_on=df_base.columns[0], how='left')
    df_cartera['Estrellas'] = df_cartera.iloc[:, 5].apply(obtener_estrellas) # Columna Score
    df_cartera['POS'] = df_cartera.iloc[:, 4] # Columna POS

    # --- SECCIÓN TITULARES ---
    st.subheader("🔝 El Once de Gala")
    tits = df_cartera[df_cartera['titular'] == 1]
    if not tits.empty:
        # Orden táctico
        tits['orden'] = tits['POS'].map({'ARQ':0, 'DEF':1, 'VOL':2, 'DEL':3}).fillna(9)
        st.dataframe(tits.sort_values('orden')[['POS', 'Jugador', 'Estrellas', 'Club_DB']], use_container_width=True, hide_index=True)
        
        b_col1, b_col2 = st.columns([1,3])
        with b_col1:
            bajar = st.selectbox("Mandar al banco:", tits['Jugador'])
            if st.button("BAJAR ⬇️"):
                ejecutar_db("UPDATE cartera SET titular = 0 WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, bajar), commit=True)
                st.rerun()
    else:
        st.info("No hay jugadores en el Once Titular.")

    st.divider()

    # --- SECCIÓN BANCO ---
    st.subheader("⏬ Cartera de Representados")
    banco = df_cartera[df_cartera['titular'] == 0]
    
    pos_keys = ["ARQ", "DEF", "VOL", "DEL"]
    cols = st.columns(4)
    
    for i, pk in enumerate(pos_keys):
        with cols[i]:
            st.markdown(f"#### {pk}")
            j_pos = banco[banco['POS'] == pk]
            for _, j in j_pos.iterrows():
                with st.container(border=True):
                    st.markdown(f"<div style='font-size:20px; font-weight:bold; color:#00D4FF;'>{j['Jugador']}</div>", unsafe_allow_html=True)
                    st.caption(f"{j['Club_DB']}")
                    st.write(j['Estrellas'])
                    
                    if st.button("TITULAR ⬆️", key=f"up_{j['id']}"):
                        ejecutar_db("UPDATE cartera SET titular = 1 WHERE id = ?", (j['id'],), commit=True)
                        st.rerun()
                    
                    if st.button("VENDER 💰", key=f"sel_{j['id']}"):
                        # Venta al 90% del valor inicial
                        pago = 1500000 # Valor base de venta
                        ejecutar_db("DELETE FROM cartera WHERE id = ?", (j['id'],), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (pago, u_id), commit=True)
                        st.rerun()
else:
    st.info("Tu agencia no tiene jugadores aún. ¡Empieza el Scouting!")
    
