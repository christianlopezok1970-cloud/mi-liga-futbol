import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v43.db' 
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
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
        elif monto >= 1_000: 
            # Evita el 1200K, lo pasa a 1,2M si supera los 999K
            if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
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
        
        # --- LÓGICA DE MERCADO DESDE EXCEL (CELDA J1 / COLUMNA 9) ---
        estado_mercado = "ABIERTO"
        if len(df.columns) >= 10: # Verificamos que llegue hasta la columna J
            valor_mercado = str(df.iloc[0, 9]).upper().strip() # Fila 0, Columna 9 (J1)
            if "CERRADO" in valor_mercado:
                estado_mercado = "CERRADO"
        
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 1] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 2] + "]"
        df['ScoreOficial'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0)
        return df, estado_mercado
    except Exception as e:
        return pd.DataFrame(), "ABIERTO"

# Tablas con soporte para Password
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

# --- 3. LOGIN ---
st.set_page_config(page_title="Pro Fútbol Manager v43", layout="wide")
st.sidebar.title("🔐 Acceso")
manager = st.sidebar.text_input("Agente:").strip()
password = st.sidebar.text_input("Contraseña:", type="password").strip()

if not manager or not password:
    st.info("👋 Ingresa tus credenciales para continuar.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio, password FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, password, presupuesto, prestigio) VALUES (?, ?, 2000000, 10)", (manager, password), commit=True)
    st.success("Cuenta creada correctamente.")
    st.rerun()
else:
    u_id, presupuesto, prestigio, u_pass = datos[0]
    if password != u_pass:
        st.error("Contraseña incorrecta.")
        st.stop()

df_oficial, estado_mercado = cargar_datos_completos_google()

# --- 4. AUTO-JORNADA (Sin duplicados)[cite: 3] ---
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    for j_nom, j_costo in cartera_activa:
        match = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
        if not match.empty:
            pts_oficial = float(match['ScoreOficial'].values[0])
            if pts_oficial > 0:
                check_detalle = f"Jornada: {j_nom.strip()}"
                ya_cobrado = ejecutar_db("SELECT id FROM historial WHERE usuario_id = ? AND detalle = ? AND fecha LIKE ?", (u_id, check_detalle, f"{fecha_hoy}%"))
                if not ya_cobrado:
                    bal = calcular_balance_fecha(pts_oficial, j_costo)
                    pres_mod = calcular_cambio_prestigio(pts_oficial)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", (bal, pres_mod, u_id), commit=True)
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, check_detalle, bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                    st.toast(f"✅ Procesado: {j_nom}")
    
    datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE id = ?", (u_id,))
    u_id, presupuesto, prestigio = datos[0][0], datos[0][1], datos[0][2]

# --- 5. SIDEBAR: MÉTRICAS Y PRÉSTAMO[cite: 2] ---
st.sidebar.metric("Caja", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

with st.sidebar.expander("🏦 Préstamo (-1 Rep = €100K)"):
    monto_p = st.number_input("Cantidad:", min_value=0, step=100000)
    if st.button("Solicitar Préstamo"):
        costo_rep = int(monto_p / 100000)
        if prestigio >= costo_rep:
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio - ? WHERE id = ?", (monto_p, costo_rep, u_id), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, "Préstamo Bancario", monto_p, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
            st.rerun()
        else: st.error("Reputación insuficiente.")

# --- 6. MERCADO (LIMITADO POR REPUTACIÓN Y EXCEL) ---
st.subheader("🔍 Mercado de Fichajes")
if estado_mercado == "CERRADO":
    st.error("🚨 EL MERCADO ESTÁ CERRADO DESDE LA CENTRAL.")
else:
    with st.expander("Panel de Scouting"):
        seleccion = st.selectbox("Elegir Jugador:", options=[""] + df_oficial['Display'].tolist())
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj.iloc[0]
            if ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom)):
                st.warning("Ya tienes a este jugador.")
            else:
                v_m_t = int(dj['ValorNum'])
                vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                disp_m = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                
                # Ajuste de porcentaje según Reputación[cite: 1, 3]
                max_permitido = min(disp_m, int(prestigio))
                
                if max_permitido > 0:
                    lista_pct = sorted(list(set([o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_permitido] + [max_permitido])))
                    pct = st.select_slider("Porcentaje:", lista_pct)
                    costo_f = (v_m_t * pct) / 100
                    inv = costo_f + (v_m_t * 0.02)
                    st.info(f"Costo: € {formatear_total(costo_f)} | Gastos 2%: € {formatear_total(v_m_t * 0.02)}")
                    if st.button("CONFIRMAR FICHAJE"):
                        if presupuesto >= inv:
                            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv, u_id), commit=True)
                            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Fichaje {nom}", -inv, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                            st.rerun()
                else: st.error("No tienes suficiente reputación para este stock.")

# --- 7. CARTERA (VENTA 99% Y SEGURIDAD)[cite: 2, 3] ---
st.divider()
st.subheader("📋 Mi Cartera")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"**{j_nom}** ({j_club}) | **{int(j_pct)}%** | Inv: €{formatear_total(j_costo)}")
        seguridad = c2.checkbox("Confirmar", key=f"s_{j_id}")
        v_final = j_costo * 0.99
        if c2.button(f"Vender €{formatear_total(v_final)}", key=f"v_{j_id}", disabled=not seguridad):
            ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (v_final, u_id), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", v_final, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
            st.rerun()

# --- 8. RANKING E HISTORIAL ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    with st.expander("🏆 Top Agentes"):
        rank = ejecutar_db("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC")
        st.table(pd.DataFrame(rank, columns=['Agente', 'Rep']))
with c2:
    with st.expander("📜 Últimos Movimientos"):
        hist = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 5", (u_id,))
        st.table(pd.DataFrame(hist, columns=['Fecha', 'Detalle', '€']))
