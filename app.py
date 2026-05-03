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
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
        elif monto >= 1_000: return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

def formatear_total(monto):
    try: return f"{int(monto):,}".replace(',', '.')
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
        # 0:Nombre, 1:Equipo, 2:POS, 3:Cotización[cite: 1]
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

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

# --- 4. PROCESAMIENTO AUTOMÁTICO ---
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    for j_nom, j_costo in cartera_activa:
        match = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
        if not match.empty:
            pts_oficial = float(match['ScoreOficial'].values[0])
            if pts_oficial > 0:
                check_detalle = f"Auto-Jornada: {j_nom.strip()}%"
                ya_cobrado = ejecutar_db(
                    "SELECT id FROM historial WHERE usuario_id = ? AND detalle LIKE ? AND fecha LIKE ?", 
                    (u_id, check_detalle, f"{fecha_hoy}%")
                )
                if not ya_cobrado:
                    bal = calcular_balance_fecha(pts_oficial, j_costo)
                    pres_mod = calcular_cambio_prestigio(pts_oficial)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", (bal, pres_mod, u_id), commit=True)
                    detalle = f"Auto-Jornada: {j_nom.strip()} (Score: {pts_oficial}) | € {formatear_total(bal)}"
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, detalle, bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                    st.toast(f"✅ Jornada procesada: {j_nom}")
    
    datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
    u_id, presupuesto, prestigio = datos[0]

# --- 5. SIDEBAR ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    with st.sidebar.expander("⚠️ ZONA DE RESET"):
        if st.text_input("Escribe BORRAR:").upper() == "BORRAR":
            if st.button("EJECUTAR RESET"):
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
            nom = dj.iloc[0]
            
            ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
            
            if ya_lo_tiene:
                st.warning(f"⚠️ Ya representas a {nom}.")
            else:
                v_m_t = int(dj['ValorNum'])
                vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                disp_m = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                max_posible = min(disp_m, int(prestigio))
                
                if max_posible > 0:
                    opciones_validas = [o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_posible]
                    if not opciones_validas: opciones_validas = [max_posible]
                    
                    pct = c2.select_slider("Porcentaje a adquirir:", opciones_validas)
                    costo_f = (v_m_t * pct) / 100
                    inv = costo_f + (v_m_t * 0.02)
                    
                    st.info(f"Ficha: € {formatear_total(costo_f)} | Gastos Admin (2%): € {formatear_total(v_m_t * 0.02)}")
                    if st.button("FICHAR JUGADOR", type="primary"):
                        if presupuesto >= inv:
                            # Guardamos el club/equipo (Índice 1)[cite: 1]
                            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv, u_id), commit=True)
                            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -inv, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                            st.rerun()

# --- 7. MIS REPRESENTADOS (VISUALIZACIÓN LIMPIA) ---
st.markdown("### 📋 Mis Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
if not cartera: st.write("No tienes jugadores representados.")

for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    posicion = ""
    score_e = 0
    if not df_oficial.empty:
        match_info = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
        if not match_info.empty:
            score_e = match_info['ScoreOficial'].values[0]
            posicion = match_info.iloc[0, 2] # Columna POS[cite: 1]

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            # Formato solicitado: Nombre / Posición | Porcentaje[cite: 1]
            st.markdown(f"#### {j_nom}")
            st.markdown(f"{posicion} | {int(j_pct)}%")
            # Texto limpio: Inversión | Último Score[cite: 1]
            st.write(f"Inversión: € {formatear_total(j_costo)} | Último Score: {score_e}")
        with col2:
            confirmar = st.checkbox("Confirmar Venta", key=f"check_{j_id}")
            v_venta = j_costo * 0.99
            if st.button(f"VENDER (€{formatear_total(v_venta)})", key=f"v_{j_id}", disabled=not confirmar):
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (v_venta, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", v_venta, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()

# --- 8. RANKING E HISTORIAL ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    with st.expander("🏆 Ranking"):
        usuarios = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
        st.table(pd.DataFrame(usuarios, columns=['Agente', 'Rep', 'Caja']))
with c2:
    with st.expander("📜 Historial"):
        hist = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
        st.dataframe(pd.DataFrame(hist, columns=['Fecha', 'Detalle', 'Monto']), hide_index=True)
