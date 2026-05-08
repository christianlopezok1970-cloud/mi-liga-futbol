import streamlit as st
import sqlite3
import pandas as pd
import random
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL Y DB ---
DB_NAME = 'agencia_global_v41.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

st.set_page_config(page_title="Pro Fútbol Manager 2026", layout="wide")

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
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)

ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- PARCHE DE SEGURIDAD (Evita el OperationalError) ---
try:
    ejecutar_db("ALTER TABLE cartera ADD COLUMN titular INTEGER DEFAULT 0", commit=True)
except Exception:
    pass # Si la columna ya existe, no hace nada

# --- 2. ESTILO VISUAL "AZUL CHAMPIONS" ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); }
    h1, h2, h3, h4, h5, p, span, label { color: #f0f2f6 !important; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #003366 !important;
        border-radius: 10px;
        padding: 10px;
    }
    .stButton>button { background-color: #004494; color: white; width: 100%; border-radius: 8px; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #005bc4; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES DE CARGA Y FORMATO ---
@st.cache_data(ttl=60)
def cargar_datos_excel():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Columna D (índice 3) = Valor, Columna E (índice 4) = Puntaje
        def limpiar_v(v):
            try: return int(''.join(filter(str.isdigit, str(v).replace('.',''))))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_v)
        df['ScoreNum'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def convertir_a_estrellas(score):
    if score >= 8.5: return "⭐⭐⭐⭐⭐"
    if score >= 7.5: return "⭐⭐⭐⭐"
    if score >= 6.5: return "⭐⭐⭐"
    if score >= 5.5: return "⭐⭐"
    return "⭐"

def formatear_abreviado(monto):
    m = float(monto)
    if m >= 1_000_000: return f"{m / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
    if m >= 1_000: return f"{m / 1_000:.0f}K"
    return str(int(m))

# --- 4. ACCESO (LOGIN) ---
if 'manager_id' not in st.session_state:
    with st.sidebar:
        st.title("🛡️ ACCESO AGENTE")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR / REGISTRAR"):
            res = ejecutar_db("SELECT id, password FROM usuarios WHERE nombre = ?", (u,))
            if res:
                if res[0][1] == p:
                    st.session_state.manager_id = res[0][0]
                    st.rerun()
                else: st.error("Contraseña incorrecta")
            else:
                # Inicio con 30.000.000
                ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (u, p), commit=True)
                st.success("Cuenta creada. ¡Bienvenido!")
                st.rerun()
    st.stop()

# Cargar contexto del usuario
u_id = st.session_state.manager_id
user_data = ejecutar_db("SELECT nombre, presupuesto, prestigio FROM usuarios WHERE id = ?", (u_id,))[0]
nombre_m, presupuesto, prestigio = user_data
df_base = cargar_datos_excel()

# --- 5. SIDEBAR (MÉTRICAS Y SCOUTING) ---
with st.sidebar:
    st.subheader(f"👤 {nombre_m}")
    st.metric("Caja Global", f"€ {formatear_abreviado(presupuesto)}")
    st.metric("Reputación", f"{prestigio} pts")
    
    if st.button("Cerrar Sesión"):
        del st.session_state.manager_id
        st.rerun()

    st.divider()
    st.subheader("🛒 Mercado")
    if st.button("🔭 SCOUTING PREMIUM (2.5M)"):
        if presupuesto >= 2500000:
            jugador = df_base.sample(n=1).iloc[0]
            nom = jugador.iloc[0].strip()
            equipo = jugador.iloc[1].strip()
            val = int(jugador['ValorNum'])
            
            check = ejecutar_db("SELECT id FROM cartera WHERE usuario_id=? AND nombre_jugador=?", (u_id, nom))
            if not check:
                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club, titular) VALUES (?,?,?,?,?,0)",
                            (u_id, nom, 100, val, equipo), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - 2500000 WHERE id = ?", (u_id,), commit=True)
                st.success(f"Fichado: {nom}")
                st.rerun()
            else:
                st.error(f"{nom} ya está en tu agencia. Dinero perdido.")
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - 2500000 WHERE id = ?", (u_id,), commit=True)
                st.rerun()
        else:
            st.error("Fondos insuficientes")

# --- 6. CUERPO PRINCIPAL (ONCE Y BANCO) ---
st.title("⚽ Pro Fútbol Manager 2026")

cartera = ejecutar_db("SELECT id, nombre_jugador, costo_compra, club, titular FROM cartera WHERE usuario_id = ?", (u_id,))
df_cartera = pd.DataFrame(cartera, columns=['id', 'Jugador', 'Valor', 'Equipo', 'titular'])

if not df_cartera.empty:
    # Unir con datos del Excel (Posición está en columna C - índice 2)
    df_cartera = df_cartera.merge(df_base.iloc[:, [0, 2, 4, 5]], left_on='Jugador', right_on=df_base.columns[0], how='left')
    df_cartera['Estrellas'] = df_cartera['ScoreNum'].apply(convertir_a_estrellas)
    df_cartera['POS'] = df_cartera.iloc[:, 5] # Tomamos la columna C del merge

    # SECCIÓN ONCE TITULAR
    st.subheader("🔝 Once Titular")
    titulares = df_cartera[df_cartera['titular'] == 1]
    if not titulares.empty:
        titulares['orden'] = titulares['POS'].map({'ARQ':0, 'DEF':1, 'VOL':2, 'DEL':3}).fillna(9)
        st.dataframe(titulares.sort_values('orden')[['POS', 'Jugador', 'Equipo', 'Estrellas']], use_container_width=True, hide_index=True)
        
        bajar = st.selectbox("Mandar al banco:", titulares['Jugador'], key="sel_bajar")
        if st.button("Bajar al banco ⬇️"):
            ejecutar_db("UPDATE cartera SET titular = 0 WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, bajar), commit=True)
            st.rerun()
    else:
        st.info("Selecciona jugadores del banco para armar tu Once.")

    st.divider()

    # SECCIÓN BANCO (ORGANIZADO POR POSICIÓN)
    st.subheader("⏬ Banco de Representados")
    banco = df_cartera[df_cartera['titular'] == 0]
    if not banco.empty:
        # Mostramos el banco en columnas
        pos_list = ["ARQ", "DEF", "VOL", "DEL", "OTRO"]
        cols = st.columns(5)
        for i, pkey in enumerate(pos_list):
            with cols[i]:
                st.markdown(f"**{pkey}**")
                jugs_pos = banco[banco['POS'].str.upper() == pkey] if pkey != "OTRO" else banco[~banco['POS'].isin(["ARQ", "DEF", "VOL", "DEL"])]
                for _, jug in jugs_pos.iterrows():
                    with st.container(border=True):
                        st.markdown(f"<span style='font-size:18px; color:#00D4FF; font-weight:bold;'>{jug['Jugador']}</span>", unsafe_allow_html=True)
                        st.caption(f"{jug['Equipo']} | {jug['Estrellas']}")
                        st.write(f"Valor: €{formatear_abreviado(jug['Valor'])}")
                        
                        if st.button("TITULAR ⬆️", key=f"sub_{jug['id']}"):
                            ejecutar_db("UPDATE cartera SET titular = 1 WHERE id = ?", (jug['id'],), commit=True)
                            st.rerun()
                        
                        if st.checkbox("Vender", key=f"vchk_{jug['id']}"):
                            if st.button("VENDER 💰", key=f"vbtn_{jug['id']}"):
                                pago = jug['Valor'] * 0.99
                                ejecutar_db("DELETE FROM cartera WHERE id = ?", (jug['id'],), commit=True)
                                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (pago, u_id), commit=True)
                                st.rerun()
    else:
        st.write("Banco vacío.")
else:
    st.warning("No tienes jugadores en tu agencia.")
