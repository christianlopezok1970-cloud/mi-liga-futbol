import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v41.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

# --- [TOQUE DE COLOR: CSS INYECTADO] ---
st.set_page_config(page_title="Pro Fútbol Manager v41", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    [data-testid="stMetricValue"] { color: #00FF41 !important; font-family: 'Courier New', monospace; }
    .stButton>button { width: 100%; border-radius: 20px; border: 1px solid #00FF41; transition: 0.3s; }
    .stButton>button:hover { background-color: #00FF41; color: black; transform: scale(1.02); }
    [data-testid="stSidebar"] { background-color: #161B22; }
    .status-abierto { color: #00FF41; font-weight: bold; }
    .status-cerrado { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

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
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# Tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password TEXT, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- 2. LÓGICA DE NEGOCIO ---
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

# --- 3. INTERFAZ E INICIO DE SESIÓN ---
st.title("💼 Pro Fútbol Manager")

with st.sidebar:
    st.header("🔐 Área de Agentes")
    manager = st.text_input("Nombre del Agente:").strip()
    password = st.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Identifícate para acceder a tu cartera.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))

if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 2000000, 10)", (manager, password), commit=True)
    st.success(f"Cuenta creada para {manager}. ¡Bienvenido!")
    st.rerun()
else:
    u_id, presupuesto, prestigio, u_pass = datos[0]
    if password != u_pass:
        st.error("❌ Contraseña incorrecta.")
        st.stop()

df_oficial = cargar_datos_completos_google()

# --- LÓGICA DE CIERRE DE MERCADO ---
mercado_bloqueado = False
if not df_oficial.empty and len(df_oficial.columns) >= 10:
    estado_j1 = str(df_oficial.iloc[0, 9]).strip().upper()
    if "CERRADO" in estado_j1:
        mercado_bloqueado = True

# --- 4. PROCESAMIENTO AUTOMÁTICO ---
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    for j_nom, j_costo in cartera_activa:
        match = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
        if not match.empty:
            pts_oficial = float(match['ScoreOficial'].values[0])
            if pts_oficial > 0:
                check_detalle = f"Auto-Jornada: {j_nom.strip()}"
                ya_cobrado = ejecutar_db("SELECT id FROM historial WHERE usuario_id = ? AND detalle = ? AND fecha LIKE ?", (u_id, check_detalle, f"{fecha_hoy}%"))
                if not ya_cobrado:
                    bal = calcular_balance_fecha(pts_oficial, j_costo)
                    pres_mod = calcular_cambio_prestigio(pts_oficial)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", (bal, pres_mod, u_id), commit=True)
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, check_detalle, bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                    st.toast(f"✅ Jornada procesada: {j_nom}")
    
    datos = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE id = ?", (u_id,))
    u_id, presupuesto, prestigio, _ = datos[0]

# --- 5. SIDEBAR (Métricas) ---
with st.sidebar:
    st.divider()
    st.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
    st.metric("Reputación", f"{prestigio} pts")
    
    with st.expander("🏦 Banco"):
        monto_p = st.number_input("Préstamo (€):", min_value=0, step=100000)
        if st.button("Solicitar"):
            if monto_p >= 100000:
                costo_rep = int(monto_p / 100000)
                if prestigio >= costo_rep:
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio - ? WHERE id = ?", (monto_p, costo_rep, u_id), commit=True)
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Préstamo (-{costo_rep} Rep)", monto_p, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                    st.rerun()

    st.divider()
    if not st.toggle("🔒 Seguridad Reset", value=True):
        if st.button("RESET TOTAL"):
            ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
            ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
            st.rerun()

# --- 6. ORGANIZACIÓN POR PESTAÑAS ---
tab_mercado, tab_cartera, tab_historial = st.tabs(["🔍 Mercado", "📋 Cartera", "📜 Historial"])

with tab_mercado:
    if mercado_bloqueado:
        st.markdown("<div class='status-cerrado'>🚨 MERCADO CERRADO POR PROCESAMIENTO</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-abierto'>🟢 MERCADO ABIERTO</div>", unsafe_allow_html=True)
        with st.expander("Panel de Scouting", expanded=True):
            if not df_oficial.empty:
                c1, c2 = st.columns(2)
                seleccion = c1.selectbox("Jugador:", options=[""] + df_oficial['Display'].tolist())
                if seleccion:
                    dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
                    nom = dj.iloc[0]
                    ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
                    
                    if ya_lo_tiene:
                        st.warning(f"Ya representas a {nom}.")
                    else:
                        v_m_t = int(dj['ValorNum'])
                        vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                        stock = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                        max_f = min(stock, int(prestigio))
                        
                        if max_f > 0:
                            pct = c2.select_slider("% a comprar:", [o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_f] or [max_f])
                            costo_f = (v_m_t * pct) / 100
                            total_f = costo_f * 1.02
                            st.write(f"Inversión total: **€ {formatear_total(total_f)}**")
                            if st.button("EFECTUAR FICHAJE"):
                                if presupuesto >= total_f:
                                    ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (total_f, u_id), commit=True)
                                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -total_f, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                                    st.rerun()
                        else: st.error("No puedes adquirir más.")

with tab_cartera:
    cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
    if not cartera:
        st.info("No tienes jugadores en cartera.")
    for j_id, j_nom, j_pct, j_costo, j_club in cartera:
        info = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
        score = info['ScoreOficial'].values[0] if not info.empty else 0
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.markdown(f"**{j_nom}**  \n{j_club}")
            col2.write(f"Participación: {int(j_pct)}%  \nValor Compra: €{formatear_total(j_costo)}")
            if col3.button("VENDER (99%)", key=f"btn_{j_id}"):
                val = j_costo * 0.99
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (val, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", val, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()

with tab_historial:
    h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
    st.dataframe(pd.DataFrame(h, columns=['Fecha', 'Evento', 'Monto']), use_container_width=True, hide_index=True)

st.divider()
with st.expander("🏆 Ranking de Prestigio"):
    res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
    st.table(pd.DataFrame(res, columns=['Agente', 'Rep', 'Caja']))
