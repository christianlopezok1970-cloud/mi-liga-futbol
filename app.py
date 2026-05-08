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

# Crear tablas si no existen (Basado en tu estructura v41)
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT, titular INTEGER DEFAULT 0)''', commit=True)

# --- 2. ESTILO VISUAL "CHAMPIONS" ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); }
    h1, h2, h3, h4, p, span, label { color: #f0f2f6 !important; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; }
    .stButton>button { background-color: #004494; color: white; width: 100%; border: none; border-radius: 8px; }
    .stButton>button:hover { background-color: #005bc4; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES DE APOYO ---
@st.cache_data(ttl=60)
def cargar_datos_excel():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Columna D (3) es Valor, Columna E (4) es Score
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

def formatear_moneda(monto):
    return f"€ {int(monto):,}".replace(",", ".")

# --- 4. ACCESO DE USUARIO ---
if 'manager_id' not in st.session_state:
    with st.sidebar:
        st.title("🛡️ AGENCIA ACCESO")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar / Registrar"):
            res = ejecutar_db("SELECT id, password FROM usuarios WHERE nombre = ?", (u,))
            if res:
                if res[0][1] == p:
                    st.session_state.manager_id = res[0][0]
                    st.rerun()
                else: st.error("Clave incorrecta")
            else:
                ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (u, p), commit=True)
                st.success("Cuenta creada exitosamente")
                st.rerun()
    st.stop()

# Cargar datos del manager logueado
u_id = st.session_state.manager_id
datos_m = ejecutar_db("SELECT nombre, presupuesto, prestigio FROM usuarios WHERE id = ?", (u_id,))[0]
nombre_m, presupuesto, prestigio = datos_m
df_base = cargar_datos_excel()

# --- 5. LÓGICA DE JUEGO (SIDEBAR) ---
with st.sidebar:
    st.subheader(f"🎮 {nombre_m}")
    st.metric("Presupuesto", formatear_moneda(presupuesto))
    st.metric("Reputación", f"{prestigio} pts")
    
    if st.button("Cerrar Sesión"):
        del st.session_state.manager_id
        st.rerun()

    st.divider()
    # RULETA DE PRESTIGIO
    if st.button("🎲 RULETA DE AGENTE"):
        cambio = random.choice([-500000, 0, 500000, 1000000, 2500000])
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (cambio, u_id), commit=True)
        st.toast(f"Resultado Ruleta: {formatear_moneda(cambio)}")
        st.rerun()

    st.divider()
    # SCOUTING (PACK)
    st.subheader("🛒 Scouting (2.5M)")
    if st.button("LANZAR SCOUTING 🔭"):
        if presupuesto >= 2500000:
            jugador = df_base.sample(n=1).iloc[0]
            nom = jugador.iloc[0].strip()
            # Evitar duplicados
            if not ejecutar_db("SELECT id FROM cartera WHERE usuario_id=? AND nombre_jugador=?", (u_id, nom)):
                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                            (u_id, nom, 100, jugador['ValorNum'], jugador.iloc[1]))
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - 2500000 WHERE id = ?", (u_id,), commit=True)
                st.success(f"¡Has fichado a {nom}!")
                st.rerun()
            else: st.warning(f"Ya tienes a {nom}, inversión perdida.")
        else: st.error("Dinero insuficiente")

# --- 6. GESTIÓN DEL ONCE Y BANCO ---
st.title("⚽ Pro Fútbol Manager 2026")

# Obtener jugadores de la DB
cartera = ejecutar_db("SELECT id, nombre_jugador, costo_compra, club, titular FROM cartera WHERE usuario_id = ?", (u_id,))
df_cartera = pd.DataFrame(cartera, columns=['id', 'Jugador', 'Valor', 'Equipo', 'titular'])

# Mezclar con datos del Excel para obtener POS y Score
if not df_cartera.empty:
    df_cartera = df_cartera.merge(df_base[['Jugador', 'POS', 'ScoreNum']], on='Jugador', how='left')
    df_cartera['Estrellas'] = df_cartera['ScoreNum'].apply(convertir_a_estrellas)

    # SECCIÓN TITULARES
    st.subheader("🔝 Once Titular")
    titulares = df_cartera[df_cartera['titular'] == 1]
    if not titulares.empty:
        # Ordenar por posición (Arquero arriba)
        titulares['orden'] = titulares['POS'].map({'ARQ':0, 'DEF':1, 'VOL':2, 'DEL':3}).fillna(9)
        st.dataframe(titulares.sort_values('orden')[['POS', 'Jugador', 'Equipo', 'Estrellas']], use_container_width=True, hide_index=True)
        
        bajar = st.selectbox("Mandar al banco:", titulares['Jugador'])
        if st.button("Bajar al banco ⬇️"):
            ejecutar_db("UPDATE cartera SET titular = 0 WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, bajar), commit=True)
            st.rerun()
    else:
        st.info("No tienes titulares seleccionados.")

    st.divider()

    # SECCIÓN BANCO
    st.subheader("⏬ Banco de Representados")
    banco = df_cartera[df_cartera['titular'] == 0]
    if not banco.empty:
        st.dataframe(banco[['Jugador', 'POS', 'Equipo', 'Estrellas']], use_container_width=True, hide_index=True)
        
        c1, c2 = st.columns(2)
        with c1:
            subir = st.selectbox("Subir al Once:", banco['Jugador'])
            if st.button("Poner de Titular ⬆️"):
                # Lógica de límites (Opcional, aquí lo pongo directo)
                ejecutar_db("UPDATE cartera SET titular = 1 WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, subir), commit=True)
                st.rerun()
        with c2:
            vender = st.selectbox("Vender Jugador:", banco['Jugador'])
            if st.button("VENDER 💰"):
                # Vende por el valor real del Excel * 0.90 (Comisión)
                val_venta = float(banco[banco['Jugador']==vender]['Valor'].values[0]) * 0.90
                ejecutar_db("DELETE FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, vender), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (val_venta, u_id), commit=True)
                st.rerun()
else:
    st.warning("Tu cartera está vacía. Usa el Scouting para obtener jugadores.")
