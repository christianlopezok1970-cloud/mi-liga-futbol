import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v40.db'
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

@st.cache_data(ttl=300)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['NombreLimpio'] = df.iloc[:, 0].astype(str).str.strip() # Columna clave para evitar duplicados
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# Inicialización de tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
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

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Pro Fútbol Manager v40", layout="wide")
st.subheader("Pro Fútbol Manager")

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 10)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]
df_oficial = cargar_datos_completos_google()

# --- 4. PROCESAMIENTO AUTOMÁTICO (EVITA DUPLICADOS) ---
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    cambio = False
    for j_nom, j_costo in cartera_activa:
        # Búsqueda exacta ignorando espacios
        match = df_oficial[df_oficial['NombreLimpio'] == j_nom.strip()]
        if not match.empty:
            pts_oficial = float(match['ScoreOficial'].values[0])
            if pts_oficial > 0:
                detalle_busqueda = f"Auto-Jornada: {j_nom.strip()}%"
                # Verificamos si ya existe el registro para este jugador hoy
                ya_cobrado = ejecutar_db("SELECT id FROM historial WHERE usuario_id = ? AND detalle LIKE ? AND fecha = ?", (u_id, detalle_busqueda, fecha_hoy))
                if not ya_cobrado:
                    bal = calcular_balance_fecha(pts_oficial, j_costo)
                    pres_mod = calcular_cambio_prestigio(pts_oficial)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", (bal, pres_mod, u_id), commit=True)
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                (u_id, f"Auto-Jornada: {j_nom.strip()} (Score: {pts_oficial})", int(bal), fecha_hoy), commit=True)
                    cambio = True
    if cambio: st.rerun()

# --- 5. SIDEBAR ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

with st.sidebar.expander("🏦 Préstamo Bancario"):
    monto_p = st.number_input("Monto (€):", min_value=0, step=100000)
    if st.button("Confirmar Préstamo"):
        if monto_p >= 100000:
            costo_p = int(monto_p / 100000)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = max(0, prestigio - ?) WHERE id = ?", (monto_p, costo_p, u_id), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Préstamo (-{costo_p} Rep)", int(monto_p), fecha_hoy), commit=True)
            st.rerun()

st.sidebar.divider()
if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("RESET TOTAL"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

# --- 6. SCOUTING Y MERCADO ---
with st.expander("🔍 Scouting y Mercado"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Buscar Jugador:", options=[""] + df_oficial['Display'].tolist())
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj['NombreLimpio']
            v_m_t = int(dj['ValorNum'])
            
            # Verificación de stock total
            vendido_total = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
            disp_m = 100 - (vendido_total[0][0] if vendido_total[0][0] else 0)
            max_fichable = min(disp_m, int(prestigio))
            
            if max_fichable > 0:
                opciones = sorted(list(set([o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_fichable] + [max_fichable])))
                pct = c2.select_slider("Porcentaje a comprar:", options=opciones)
                costo_f = (v_m_t * pct) / 100
                inv = costo_f + (v_m_t * 0.02)
                
                st.info(f"Disponible: {disp_m}% | Inversión: € {formatear_total(inv)}")
                if st.button("CONFIRMAR FICHAJE"):
                    if presupuesto >= inv:
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -int(inv), fecha_hoy), commit=True)
                        st.rerun()
            else: st.warning("Jugador agotado o prestigio insuficiente.")

# --- 7. MIS REPRESENTADOS ---
st.markdown("### 📋 Mis Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    info = df_oficial[df_oficial['NombreLimpio'] == j_nom.strip()]
    score = info['ScoreOficial'].values[0] if not info.empty else "N/A"
    pos = info.iloc[0, 2] if not info.empty else "N/A"

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"#### {j_nom} <small>({j_club})</small>", unsafe_allow_html=True)
            st.write(f"**{pos}** | Participación: **{int(j_pct)}%**")
            st.caption(f"Inversión: € {formatear_total(j_costo)} | Score: {score}")
        with c2:
            if st.checkbox("Vender", key=f"v_{j_id}"):
                if st.button("Confirmar Venta", key=f"btn_{j_id}"):
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_costo * 0.99, u_id), commit=True)
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", int(j_costo * 0.99), fecha_hoy), commit=True)
                    st.rerun()

# --- 8. RANKING e HISTORIAL ---
st.divider()
col1, col2 = st.columns(2)
with col1:
    with st.expander("🏆 Ranking de Agentes"):
        res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
        df_r = pd.DataFrame(res, columns=['Agente', 'Rep', 'Caja'])
        df_r['Caja'] = df_r['Caja'].apply(formatear_total)
        st.table(df_r)
with col2:
    with st.expander("📜 Últimos Movimientos"):
        h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
        df_h = pd.DataFrame(h, columns=['Fecha', 'Evento', 'Monto'])
        df_h['Monto'] = df_h['Monto'].apply(formatear_total)
        st.table(df_h)
