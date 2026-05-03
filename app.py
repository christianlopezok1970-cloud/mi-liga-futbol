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
    try: return f"{int(float(monto)):,}".replace(',', '.')
    except: return "0"

def formatear_abreviado(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
        elif monto >= 1_000: return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
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
        df['NombreLimpio'] = df.iloc[:, 0].astype(str).str.strip()
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# Tablas
ejecutar_db('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)', commit=True)
ejecutar_db('CREATE TABLE IF NOT EXISTS cartera (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, porcentaje REAL, costo_compra REAL, club TEXT)', commit=True)
ejecutar_db('CREATE TABLE IF NOT EXISTS historial (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)', commit=True)

# --- 2. INTERFAZ ---
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

# --- 3. PROCESAMIENTO JORNADA (CORRECCIÓN DE DUPLICADOS) ---
fecha_hoy = datetime.now().strftime("%Y-%m-%d")

if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    cambio = False
    for j_nom, j_costo in cartera_activa:
        j_nom = j_nom.strip()
        match = df_oficial[df_oficial['NombreLimpio'] == j_nom]
        
        if not match.empty:
            pts = float(match['ScoreOficial'].values[0])
            if pts > 0:
                # CLAVE ÚNICA: Evita que el mismo jugador cobre dos veces el mismo día
                id_unico_pago = f"JORNADA_{j_nom}_{fecha_hoy}"
                ya_existe = ejecutar_db("SELECT id FROM historial WHERE usuario_id = ? AND detalle = ?", (u_id, id_unico_pago))
                
                if not ya_existe:
                    # Lógica de cobro
                    bal = 0
                    if pts >= 6.6: bal = int(j_costo * ((pts - 6.5) * 10 / 100))
                    elif pts <= 6.3: bal = int(j_costo * ((pts - 6.4) * 10 / 100))
                    
                    # Cambio prestigio
                    p_mod = 0
                    if pts >= 8.0: p_mod = 2
                    elif pts >= 7.0: p_mod = 1
                    elif pts <= 5.9: p_mod = -2
                    elif pts <= 6.7: p_mod = -1
                    
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", (bal, p_mod, u_id), commit=True)
                    # Guardamos el ID único en el detalle para la validación
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                (u_id, id_unico_pago, bal, fecha_hoy), commit=True)
                    cambio = True
    if cambio: st.rerun()

# --- 4. SIDEBAR Y MERCADO ---
st.sidebar.metric("Presupuesto", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("RESET TOTAL"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

with st.expander("🔍 Mercado de Fichajes"):
    if not df_oficial.empty:
        sel = st.selectbox("Elegir Jugador:", options=[""] + df_oficial['Display'].tolist())
        if sel:
            dj = df_oficial[df_oficial['Display'] == sel].iloc[0]
            nom = dj['NombreLimpio']
            v_m_t = int(dj['ValorNum'])
            vendido = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
            disp = 100 - (vendido[0][0] if vendido[0][0] else 0)
            max_f = min(disp, int(prestigio))
            
            if max_f > 0:
                pct = st.select_slider("Participación %:", options=sorted(list(set([1, 5, 10, 25, 50, 75, 100] + [max_f])) if max_f >= 1 else [max_f]))
                costo = (v_m_t * pct) / 100
                total_inv = costo * 1.02
                st.write(f"Inversión total: € {formatear_total(total_inv)}")
                if st.button("FICHAR"):
                    if presupuesto >= total_inv:
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo, dj.iloc[1]), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (total_inv, u_id), commit=True)
                        ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -int(total_inv), fecha_hoy), commit=True)
                        st.rerun()

# --- 5. CARTERA E HISTORIAL ---
st.markdown("### 📋 Mis Jugadores")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    with st.container(border=True):
        c1, c2 = st.columns([3,1])
        c1.markdown(f"**{j_nom}** ({j_club}) - Participación: **{int(j_pct)}%**")
        if c2.button("VENDER", key=f"v_{j_id}"):
            ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_costo * 0.99, u_id), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", int(j_costo * 0.99), fecha_hoy), commit=True)
            st.rerun()

st.divider()
c_a, c_b = st.columns(2)
with c_a:
    st.write("🏆 Ranking")
    r = ejecutar_db("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC")
    st.table(pd.DataFrame(r, columns=['Agente', 'Pts']))
with c_b:
    st.write("📜 Historial (Sin decimales)")
    h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 10", (u_id,))
    df_h = pd.DataFrame(h, columns=['Fecha', 'Evento', 'Monto'])
    df_h['Monto'] = df_h['Monto'].apply(formatear_total)
    st.table(df_h)
