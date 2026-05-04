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

@st.cache_data(ttl=60) # Reducido a 60 para detectar el cierre más rápido
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

# --- ESTILO AZUL CHAMPIONS ---
st.markdown("""
    <style>
    /* Fondo principal */
    .stApp {
        background: linear-gradient(180deg, #001633 0%, #000814 100%);
    }
    
    /* Color de los textos para que resalten */
    h1, h2, h3, h4, p, span, label {
        color: #f0f2f6 !important;
    }

    /* Estilo para las tarjetas de los jugadores */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #003366 !important;
        border-radius: 10px;
    }

    /* Sidebar con un azul un poco más oscuro */
    section[data-testid="stSidebar"] {
        background-color: #000b1a;
    }
    
    /* Botones estilo premium */
    .stButton>button {
        background-color: #004494;
        color: white;
        border-radius: 5px;
        border: none;
    }
    
    .stButton>button:hover {
        background-color: #005bc4;
        border: none;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. INTERFAZ E INICIO DE SESIÓN ---
st.set_page_config(page_title="Pro Fútbol Manager v40", layout="wide")
st.subheader("Pro Fútbol Manager")

with st.sidebar:
    st.title("🔐 Acceso Agente")
    manager = st.text_input("Nombre del Agente:").strip()
    password = st.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Por favor, introduce tu nombre y contraseña.")
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

# --- LÓGICA DE CIERRE DE MERCADO (SIMPLE Y SEGURA) ---
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

# --- 5. SIDEBAR (Métricas + Préstamo) ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

with st.sidebar.expander("🏦 Préstamo Bancario"):
    st.caption("€ 100.000 = -1 de Reputación")
    monto_p = st.number_input("Monto (€):", min_value=0, step=100000)
    if st.button("Confirmar Préstamo"):
        if monto_p >= 100000:
            costo_rep = int(monto_p / 100000)
            if prestigio >= costo_rep:
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio - ? WHERE id = ?", (monto_p, costo_rep, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Préstamo (-{costo_rep} Rep)", monto_p, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()
            else:
                st.error("Reputación insuficiente.")

st.sidebar.divider()
if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("RESET TOTAL"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

# --- 6. SCOUTING Y MERCADO ---
if mercado_bloqueado:
    st.error("🚨 EL MERCADO ESTÁ ACTUALMENTE CERRADO. No se permiten nuevas contrataciones.")
else:
    with st.expander("🔍 Scouting y Mercado"):
        if not df_oficial.empty:
            c1, c2 = st.columns(2)
            seleccion = c1.selectbox("Buscar Jugador:", options=[""] + df_oficial['Display'].tolist())
            if seleccion:
                dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
                nom = dj.iloc[0]
                
                ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
                if ya_lo_tiene:
                    st.warning(f"⚠️ Ya representas a {nom}.")
                else:
                    v_m_t = int(dj['ValorNum'])
                    vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                    stock_disponible = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                    
                    max_fichaje = min(stock_disponible, int(prestigio))
                    
                    if max_fichaje > 0:
                        opciones_fichaje = [o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_fichaje]
                        if not opciones_fichaje or max_fichaje not in opciones_fichaje:
                            opciones_fichaje.append(max_fichaje)
                        opciones_fichaje = sorted(list(set(opciones_fichaje)))

                        pct = c2.select_slider("Porcentaje a adquirir:", opciones_fichaje)
                        costo_f = (v_m_t * pct) / 100
                        inv_total = costo_f + (v_m_t * 0.02)
                        
                        st.info(f"Ficha: € {formatear_total(costo_f)} | Gastos Admin (2%): € {formatear_total(v_m_t * 0.02)}")
                        if st.button("FICHAR JUGADOR", type="primary"):
                            if presupuesto >= inv_total:
                                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv_total, u_id), commit=True)
                                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -inv_total, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                                st.rerun()
                    else:
                        st.error("Reputación insuficiente.")

# --- 7. MIS REPRESENTADOS ---
st.markdown("### 📋 Mis Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    info = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
    score = info['ScoreOficial'].values[0] if not info.empty else 0
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"#### {j_nom} <small>({j_club})</small>", unsafe_allow_html=True)
            st.markdown(f"**Participación:** {int(j_pct)}%")
            st.write(f"Inversión: € {formatear_total(j_costo)} | Score: {score}")
        with c2:
            confirmar_v = st.checkbox("Confirmar Venta", key=f"chk_{j_id}")
            valor_salida = j_costo * 0.99
            if st.button(f"VENDER €{formatear_total(valor_salida)}", key=f"btn_{j_id}", disabled=not confirmar_v):
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (valor_salida, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", valor_salida, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()

# --- 8. RANKING E HISTORIAL ---
st.divider()
c_rank, c_hist = st.columns(2)
with c_rank:
    with st.expander("🏆 Ranking"):
        res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
        st.table(pd.DataFrame(res, columns=['Agente', 'Rep', 'Caja']))
with c_hist:
    with st.expander("📜 Historial"):
        h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
        st.dataframe(pd.DataFrame(h, columns=['Fecha', 'Evento', 'Monto']), hide_index=True)
