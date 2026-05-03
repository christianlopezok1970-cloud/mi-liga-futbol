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

def formatear_total(monto):
    try: return f"{int(monto):,}".replace(',', '.')
    except: return "0"

def formatear_abreviado(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
        elif monto >= 1_000: return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

@st.cache_data(ttl=60) # Bajamos el TTL a 1 minuto para que refresque rápido el Excel
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Limpieza de nombres de jugadores (Quita espacios invisibles)
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()
        
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
            
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 2] + ") - € " + df['ValorNum'].apply(formatear_abreviado)
        
        if 'Puntaje' in df.columns:
            df['ScoreOficial'] = pd.to_numeric(df['Puntaje'], errors='coerce').fillna(0)
        else:
            df['ScoreOficial'] = 0
            
        return df
    except: return pd.DataFrame()

# Tablas
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
manager = st.sidebar.text_input("Nombre del Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 10)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]
df_oficial = cargar_datos_completos_google()

# --- 4. PROCESAMIENTO AUTOMÁTICO (BLINDADO) ---
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    col_jornada = 'Jornada' if 'Jornada' in df_oficial.columns else None

    if col_jornada:
        for j_nom, j_costo in cartera_activa:
            # Buscamos ignorando espacios y mayúsculas
            match = df_oficial[df_oficial.iloc[:, 0].str.lower() == j_nom.strip().lower()]
            
            if not match.empty:
                pts_oficial = float(match['ScoreOficial'].values[0])
                id_jornada = str(match[col_jornada].values[0]).strip()
                
                if pts_oficial > 0 and id_jornada not in ["0", "nan", "", "None"]:
                    # EL CANDADO: Buscamos el nombre exacto + ID de jornada en el historial
                    # Usamos una estructura fija: "Auto-Jornada: [Nombre] ([Jornada])"
                    check_key = f"Auto-Jornada: {j_nom.strip()} ({id_jornada})"
                    
                    ya_cobrado = ejecutar_db(
                        "SELECT id FROM historial WHERE usuario_id = ? AND detalle LIKE ?", 
                        (u_id, f"%{check_key}%")
                    )
                    
                    if not ya_cobrado:
                        bal = calcular_balance_fecha(pts_oficial, j_costo)
                        pres_mod = calcular_cambio_prestigio(pts_oficial)
                        
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                                    (bal, pres_mod, u_id), commit=True)
                        
                        detalle_historial = f"{check_key} | Score: {pts_oficial} | € {formatear_total(bal)}"
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                    (u_id, detalle_historial, bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                        st.toast(f"✅ Cobrado: {j_nom} ({id_jornada})")
        
        # Refrescar datos después de procesar todo
        datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
        u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

with st.sidebar.popover("💰 Crédito"):
    if st.button("Confirmar € 100K"):
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 100000, prestigio = prestigio - 1 WHERE id = ?", (u_id,), commit=True)
        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?, 'Crédito', 100000, datetime.now().strftime('%Y-%m-%d %H:%M'))", (u_id,), commit=True)
        st.rerun()

# --- 5. MERCADO ---
with st.expander("🔍 Mercado"):
    if not df_oficial.empty:
        seleccion = st.selectbox("Elegir Jugador:", [""] + df_oficial['Display'].tolist())
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj.iloc[0].strip()
            v_m_t = int(dj['ValorNum'])
            
            vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
            disp_m = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
            max_f = min(disp_m, int(prestigio))
            
            if max_f > 0:
                pct = st.select_slider("Porcentaje:", [o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_f])
                costo_f = (v_m_t * pct) / 100
                inv = costo_f + (v_m_t * 0.02)
                st.write(f"Inversión Total: € {formatear_total(inv)} (Inc. 2% Admin)")
                if st.button("FICHAR"):
                    if presupuesto >= inv:
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[2]), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?, ?, ?, ?)", (u_id, f"Compra {pct}% {nom}", -inv, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                        st.rerun()
            else: st.error("Sin capacidad.")

# --- 6. REPRESENTADOS ---
st.write("### 📋 Mis Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.write(f"**{j_nom}** | 🏛️ {j_club} | {int(j_pct)}%")
            st.caption(f"Inversión: € {formatear_total(j_costo)}")
        with c2:
            conf = st.checkbox("Confirmar", key=f"c_{j_id}")
            if st.button("VENDER", key=f"v_{j_id}", disabled=not conf):
                v_v = j_costo * 0.99
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (v_v, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?, ?, ?, ?)", (u_id, f"Venta {j_nom}", v_v, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()

# --- 7. EXPANSORES ---
st.divider()
with st.expander("🏆 Ranking"):
    r = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
    st.table(pd.DataFrame(r, columns=['Agente', 'Rep', 'Caja']))
with st.expander("📜 Historial"):
    h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
    st.table(pd.DataFrame(h, columns=['Fecha', 'Detalle', 'Monto']))
