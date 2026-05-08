import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS Y EXCEL ---
DB_NAME = 'agencia_global_v41.db'
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
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        # Columna D (Índice 3) es el Valor/Cotización
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        # Columna E (Índice 4) es el Score/Puntaje
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: 
        st.error("Error conectando con la base de datos de Google Sheets.")
        return pd.DataFrame()

# Inicialización de tablas
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
    [data-testid="stMetricValue"] { color: #00D4FF !important; }
    .stButton>button { background-color: #004494; color: white; border-radius: 5px; width: 100%; }
    .stButton>button:hover { background-color: #005bc4; }
    div[data-testid="stExpander"] { background-color: rgba(255, 255, 255, 0.03); border: 1px solid #1a3a5a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN Y SESIÓN ---
with st.sidebar:
    st.title("🔐 Acceso Agente")
    manager = st.text_input("Nombre de Agente:").strip()
    password = st.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Inicia sesión para gestionar tu agencia.")
    st.stop()

datos_u = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))

if not datos_u:
    if st.sidebar.button("REGISTRAR NUEVA AGENCIA"):
        ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 30000000, 10)", (manager, password), commit=True)
        st.success("Agencia registrada. ¡Bienvenido!")
        st.rerun()
    st.stop()
else:
    u_id, presupuesto, prestigio, u_pass = datos_u[0]
    if password != u_pass:
        st.error("❌ Contraseña incorrecta.")
        st.stop()

df_oficial = cargar_datos_completos_google()

# --- 4. SIDEBAR MÉTRICAS ---
st.sidebar.divider()
st.sidebar.metric("Presupuesto Transferencias", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación de Agencia", f"{prestigio} pts")

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("BORRAR TODO EL PROGRESO"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 30000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

# --- 5. CENTRO DE SCOUTING ---
st.subheader("🎲 Operaciones de Scouting")
COSTO_SCOUT = 2500000

with st.container(border=True):
    col_inf, col_btn = st.columns([2, 1])
    with col_inf:
        st.markdown(f"### Inversión de Búsqueda: **€ {formatear_total(COSTO_SCOUT)}**")
        st.write("Envía ojeadores para obtener el 100% de los derechos de un jugador aleatorio.")
    with col_btn:
        if not st.session_state.get('conf_scout', False):
            if st.button("🔭 EJECUTAR SCOUTING"):
                st.session_state.conf_scout = True
                st.rerun()
        else:
            st.warning("¿Confirmar desembolso de 2.5M?")
            c_si, c_no = st.columns(2)
            if c_si.button("✅ CONFIRMAR"):
                if presupuesto >= COSTO_SCOUT:
                    jugador = df_oficial.sample(n=1).iloc[0]
                    nom_j = str(jugador.iloc[0]).strip()
                    equipo_j = str(jugador.iloc[1]).strip()
                    valor_j = int(jugador['ValorNum'])
                    
                    existe = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom_j))
                    if not existe:
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,100,?,?)", (u_id, nom_j, valor_j, equipo_j), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (COSTO_SCOUT, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                    (u_id, f"Fichaje: {nom_j}", -COSTO_SCOUT, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                        st.toast(f"¡Nuevo representado: {nom_j}!")
                    else:
                        st.error(f"Ya tienes a {nom_j}. El club canceló la operación.")
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (COSTO_SCOUT, u_id), commit=True)
                    
                    st.session_state.conf_scout = False
                    st.rerun()
                else:
                    st.error("No tienes suficiente presupuesto.")
            if c_no.button("❌ CANCELAR"):
                st.session_state.conf_scout = False
                st.rerun()

# --- 6. CARTERA (TITULARES Y SUPLENTES) ---
st.divider()
st.markdown("### 📋 Gestión de Cartera de Representados")
cartera_db = ejecutar_db("SELECT id, nombre_jugador, costo_compra, club FROM cartera WHERE usuario_id = ? ORDER BY id ASC", (u_id,))

if not cartera_db:
    st.info("Aún no tienes jugadores. Realiza un scouting para comenzar.")
else:
    # Agrupar y obtener datos del Excel
    cat = {"ARQ": [], "DEF": [], "VOL": [], "DEL": [], "OTRO": []}
    for j_id, j_nom, j_valor, j_club in cartera_db:
        match = df_oficial[df_oficial.iloc[:, 0].str.strip().str.upper() == j_nom.strip().upper()]
        
        if not match.empty:
            pos = str(match.iloc[0, 2]).strip().upper()
            score = match.iloc[0, 4]
        else:
            pos = "OTRO"
            score = 0
            
        jugador_data = {"id": j_id, "nom": j_nom, "valor": j_valor, "club": j_club, "score": score}
        if pos in cat: cat[pos].append(jugador_data)
        else: cat["OTRO"].append(jugador_data)

    # Configuración de formación titular
    CUPOS = {"ARQ": 1, "DEF": 4, "VOL": 4, "DEL": 2, "OTRO": 0}
    iconos = {"ARQ": "🧤 ARQUITECTOS", "DEF": "🛡️ DEFENSA", "VOL": "⚙️ VOLANTES", "DEL": "🏹 ATAQUE", "OTRO": "❓ OTROS"}
    
    cols = st.columns(5)
    for i, pkey in enumerate(["ARQ", "DEF", "VOL", "DEL", "OTRO"]):
        with cols[i]:
            st.markdown(f"#### {iconos[pkey]}")
            for idx, j in enumerate(cat[pkey]):
                es_titular = idx < CUPOS.get(pkey, 0)
                status = "⭐ TITULAR" if es_titular else "🪑 Suplente"
                
                with st.expander(f"{status}: {j['nom']}"):
                    if es_titular:
                        st.markdown(f"""
                            <div style="background-color: rgba(0, 212, 255, 0.15); padding: 8px; border-radius: 5px; border: 1px solid #00D4FF; margin-bottom: 10px;">
                                <h2 style="margin:0; color: #00D4FF; text-align: center;">{j['score']}</h2>
                                <p style="margin:0; text-align: center; font-size: 0.8em; color: #AAA;">SCORE OFICIAL</p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.write(f"Posición: {pkey} (Reserva)")
                    
                    st.write(f"Club actual: **{j['club']}**")
                    st.write(f"Valor: **€ {formatear_abreviado(j['valor'])}**")
                    
                    # Sistema de Venta
                    v_neto = j['valor'] * 0.99
                    conf_v = st.checkbox("Confirmar traspaso", key=f"v_{j['id']}")
                    if st.button(f"VENDER (€{formatear_abreviado(v_neto)})", key=f"b_{j['id']}", disabled=not conf_v):
                        ejecutar_db("DELETE FROM cartera WHERE id = ?", (j['id'],), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (v_neto, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                    (u_id, f"Venta: {j['nom']}", v_neto, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                        st.rerun()

# --- 7. RANKING E HISTORIAL ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    with st.expander("🏆 Ranking de Agentes"):
        ranking = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
        st.dataframe(pd.DataFrame(ranking, columns=['Agente', 'Reputación', 'Caja']), use_container_width=True)

with c2:
    with st.expander("📑 Últimos Movimientos"):
        logs = ejecutar_db("SELECT detalle, monto, fecha FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 5", (u_id,))
        if logs:
            st.table(pd.DataFrame(logs, columns=['Acción', 'Monto', 'Fecha']))
        else:
            st.write("No hay actividad reciente.")
