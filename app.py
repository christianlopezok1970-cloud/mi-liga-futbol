import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v39.db'
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
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        
        # AJUSTE AQUÍ: Se añade el club al final de la cadena de texto[cite: 2]
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 2] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 1] + "]"
        
        return df
    except: return pd.DataFrame()

# Tablas[cite: 2]
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- 2. LÓGICA ---
def calcular_balance_fecha(pts, costo):
    pts = round(float(pts), 1)
    if pts >= 6.6: return int(costo * ((pts - 6.5) * 10 / 100))
    elif pts <= 6.3: return int(costo * ((pts - 6.4) * 10 / 100))
    return 0

def calcular_cambio_prestigio(pts):
    p = round(float(pts), 1)
    if p >= 7.5: return 2      # Excelente: Ganas 2 pts
    if p >= 6.6: return 1      # Bueno: Ganas 1 pt[cite: 2]
    if p <= 5.9: return -2     # Malo: Pierdes 2 pts[cite: 2]
    if p <= 6.5: return -1     # Regular: Pierdes 1 pt[cite: 2]
    return 0

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market", layout="wide")
if 'version' not in st.session_state: st.session_state.version = 0

st.subheader("Transfer Market")

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 10)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

st.sidebar.divider()
if prestigio >= 1:
    with st.sidebar.popover("💰 Crédito"):
        if st.button("Confirmar (€ 150.000 x -1 Reputación)"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 150000, prestigio = prestigio - 1 WHERE id = ?", (u_id,), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                        (u_id, "Crédito Bancario", 150000, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
            st.session_state.version += 1
            st.rerun()

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    with st.sidebar.expander("⚠️ RESET"):
        if st.text_input("Escribe la clave:").upper() == "BORRAR":
            if st.button("EJECUTAR RESET"):
                ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
                ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
                st.session_state.version += 1
                st.rerun()

# --- 4. SCOUTING ---
df_oficial = cargar_datos_completos_google()
with st.expander("🔍 Scouting y Co-propiedad"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Jugador:", options=[""] + df_oficial['Display'].tolist(), key=f"sel_{st.session_state.version}")
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj.iloc[0]
            existe = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
            if existe:
                st.warning(f"⚠️ Ya tienes a {nom} en tu cartera.")
            else:
                vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                disp = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                if disp > 0:
                    st.info(f"📊 Disponible: {int(disp)}%")
                    opciones = [p for p in [25, 50, 75, 100] if p <= disp]
                    if opciones:
                        pct = c2.select_slider("Porcentaje:", opciones, key=f"pct_{st.session_state.version}")
                        costo = (int(dj['ValorNum']) * pct) / 100
                        st.write(f"Inversión: **€ {formatear_total(costo)}**")
                        if st.button("CERRAR TRATO", type="primary") and presupuesto >= costo:
                            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                                        (u_id, nom, pct, costo, dj.iloc[1]), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo, u_id), commit=True)
                            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                        (u_id, f"Compra {int(pct)}% {nom}", -costo, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                            st.session_state.version += 1
                            st.rerun()

# --- 5. PANEL DE ACTIVOS ---
st.markdown("##### 📋 Mis Jugadores Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    v_key = f"v{st.session_state.version}_{j_id}"
    with st.container(border=True):
        col_info, col_input, col_ops = st.columns([2, 2, 2])
        col_info.subheader(j_nom)
        col_info.write(f"🌍 {j_club}")
        col_info.markdown(f'<div style="font-size:16px; color:#FFD700; font-weight:bold;">{int(j_pct)}% | Inversión: € {formatear_total(j_costo)}</div>', unsafe_allow_html=True)
        
        pts = col_input.number_input(f"Score", 1.0, 10.0, 6.4, 0.1, key=f"score_{v_key}")
        bal = calcular_balance_fecha(pts, j_costo)
        col_input.markdown(f"Resultado: :{'green' if pts>=6.6 else 'red' if pts<=6.3 else 'gray'}[€ {formatear_total(bal)}]")
        
        with col_ops:
            conf = st.checkbox("Confirmar", key=f"check_{v_key}", value=False)
            c_c1, c_c2 = st.columns(2)
            if c_c1.button("CARGAR", key=f"btn_r_{v_key}", type="primary", disabled=not conf, use_container_width=True):
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                            (bal, calcular_cambio_prestigio(pts), u_id), commit=True)
                if bal != 0:
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                (u_id, f"Rendimiento {j_nom}", bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.session_state.version += 1
                st.rerun()
            if c_c2.button("VENDER", key=f"btn_v_{v_key}", disabled=not conf, use_container_width=True):
                monto_venta = j_costo * 0.99
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                            (u_id, f"Venta {int(j_pct)}% {j_nom}", monto_venta, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (monto_venta, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()

# --- 6. RANKING Y HISTORIAL ---
st.divider()
c_rank, c_hist = st.columns(2)

with c_rank:
    with st.expander("🏆 Ranking"):
        usuarios_raw = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios")
        df_ranking = pd.DataFrame(usuarios_raw, columns=['Agente', 'Reputación (pts)', 'Presupuesto'])
        df_ranking = df_ranking.sort_values(by='Reputación (pts)', ascending=False).reset_index(drop=True)
        df_ranking.index += 1
        df_ranking['Presupuesto'] = df_ranking['Presupuesto'].apply(lambda x: f"€ {formatear_total(x)}")
        st.table(df_ranking)

with c_hist:
    with st.expander("📜 Historial de Operaciones"):
        historial_raw = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 20", (u_id,))
        if historial_raw:
            df_hist = pd.DataFrame(historial_raw, columns=['Fecha', 'Detalle', 'Monto'])
            df_hist['Monto'] = df_hist['Monto'].apply(lambda x: f"{'🟢' if x>0 else '🔴'} € {formatear_total(x)}")
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.write("No hay operaciones registradas.")
