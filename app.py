import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS Y EXCEL ---
DB_NAME = 'agencia_global_v41.db'
# Tu URL de Google Sheets (Formato CSV)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

def formatear_abreviado(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: 
            return f"{monto / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
        elif monto >= 1_000: 
            return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

def formatear_total(monto):
    try: return f"{int(float(monto)):,}".replace(',', '.')
    except: return "0"

@st.cache_data(ttl=60)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Limpieza de valores (Columna D - Cotización es índice 3)
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        # Score Oficial (Columna E - Puntaje es índice 4)
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: 
        st.error("Error cargando Google Sheets")
        return pd.DataFrame()

# Creación de tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- 2. ESTILO VISUAL ---
st.set_page_config(page_title="Pro Fútbol Manager v41", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #001633 0%, #000814 100%); }
    h1, h2, h3, h4, h5, p, span, label { color: #f0f2f6 !important; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #003366 !important;
        border-radius: 10px;
    }
    .stButton>button { background-color: #004494; color: white; border-radius: 5px; width: 100%; }
    .stButton>button:hover { background-color: #005bc4; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN Y SESIÓN ---
with st.sidebar:
    st.title("🔐 Acceso Agente")
    manager = st.text_input("Nombre:").strip()
    password = st.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Por favor, inicia sesión.")
    st.stop()

datos_u = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))

if not datos_u:
    # NUEVO USUARIO: 30 MILLONES
    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (manager, password), commit=True)
    st.success("Cuenta creada. ¡Bienvenido!")
    st.rerun()
else:
    u_id, presupuesto, prestigio, u_pass = datos_u[0]
    if password != u_pass:
        st.error("❌ Contraseña incorrecta.")
        st.stop()

df_oficial = cargar_datos_completos_google()

# --- 4. SIDEBAR MÉTRICAS ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("RESET TOTAL"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 30000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

# --- 5. CENTRO DE SCOUTING ---
st.subheader("🎲 Centro de Scouting")
COSTO_SCOUT = 2500000

col_inf, col_btn = st.columns([2, 1])
with col_inf:
    st.info(f"**Inversión: € {formatear_total(COSTO_SCOUT)}**. Recibirás el 100% de un jugador al azar.")

with col_btn:
    if not st.session_state.get('conf_scout', False):
        if st.button("🔭 ENVIAR OJEADORES"):
            st.session_state.conf_scout = True
            st.rerun()
    else:
        st.warning("¿Confirmar 2.5M?")
        c_si, c_no = st.columns(2)
        if c_si.button("✅ SÍ"):
            if presupuesto >= COSTO_SCOUT:
                jugador = df_oficial.sample(n=1).iloc[0]
                nom_j = jugador.iloc[0].strip()
                equipo_j = jugador.iloc[1].strip()
                valor_j = int(jugador['ValorNum'])
                
                # Check duplicados
                existe = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom_j))
                if not existe:
                    ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,100,?,?)", (u_id, nom_j, valor_j, equipo_j), commit=True)
                    st.toast(f"¡Fichado: {nom_j}!")
                else:
                    st.error(f"Ya representas a {nom_j}. Se perdió la inversión.")
                
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (COSTO_SCOUT, u_id), commit=True)
                st.session_state.conf_scout = False
                st.rerun()
        if c_no.button("❌ NO"):
            st.session_state.conf_scout = False
            st.rerun()

# --- 6. CARTERA POR POSICIONES (A:Nombre, B:Equipo, C:POS) ---
st.divider()
st.markdown("### 📋 Mi Cartera de Representados")
cartera_db = ejecutar_db("SELECT id, nombre_jugador, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera_db:
    st.info("Aún no tienes jugadores.")
else:
    # Clasificación basada en Columna C (índice 2)
    cat = {"ARQ": [], "DEF": [], "VOL": [], "DEL": [], "OTRO": []}
    for j_id, j_nom, j_valor, j_club in cartera_db:
        match = df_oficial[df_oficial.iloc[:, 0].str.strip().str.upper() == j_nom.strip().upper()]
        pos = str(match.iloc[0, 2]).strip().upper() if not match.empty else "OTRO"
        if pos in cat: cat[pos].append((j_id, j_nom, j_valor, j_club))
        else: cat["OTRO"].append((j_id, j_nom, j_valor, j_club))

    # Dibujar Columnas
    pos_list = ["ARQ", "DEF", "VOL", "DEL", "OTRO"]
    iconos = {"ARQ": "🧤 ARQUITECTOS", "DEF": "🛡️ DEFENSA", "VOL": "⚙️ VOLANTES", "DEL": "🏹 ATAQUE", "OTRO": "❓ OTROS"}
    cols = st.columns(5)

    for i, pkey in enumerate(pos_list):
        with cols[i]:
            st.markdown(f"##### {iconos[pkey]}")
            for j_id, j_nom, j_valor, j_club in cat[pkey]:
                with st.container(border=True):
                    # Ficha de jugador
                    st.markdown(f"""
                        <div style="line-height: 1.2; margin-bottom: 10px;">
                            <span style="font-size: 19px; font-weight: bold; color: #00D4FF;">{j_nom}</span><br>
                            <span style="font-size: 13px; color: #BBBBBB;">{j_club}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.write(f"Valor: **€ {formatear_abreviado(j_valor)}**")
                    
                    # Botón Venta
                    conf_v = st.checkbox("Vender", key=f"chk_{j_id}")
                    v_neto = j_valor * 0.99
                    if st.button(f"VENDER €{formatear_abreviado(v_neto)}", key=f"btn_{j_id}", disabled=not conf_v):
                        ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (v_neto, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                    (u_id, f"Venta {j_nom}", v_neto, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                        st.rerun()

# --- 7. RANKING ---
with st.expander("🏆 Ranking Global de Agentes"):
    res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
    st.table(pd.DataFrame(res, columns=['Agente', 'Reputación', 'Caja']))
