import streamlit as st
import sqlite3
import pandas as pd

# --- 1. CONFIGURACIÓN DE BASE DE DATOS Y LISTADO EXTERNO ---
DB_NAME = 'agencia_global_v21.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

@st.cache_data(ttl=300)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error cargando base de datos oficial: {e}")
        return pd.DataFrame()

ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT, liga TEXT)''', commit=True)

# --- 2. LÓGICA FINANCIERA (FORMATO RESUMIDO M/K) ---
def formatear_monto(monto):
    monto = float(monto)
    if monto >= 1_000_000:
        return f"{monto / 1_000_000:.1f} M".replace('.', ',')
    elif monto >= 1_000:
        return f"{monto / 1_000:.0f} K"
    else:
        return f"{monto:.0f}"

def calcular_balance_fecha(puntaje, costo_proporcional):
    puntaje = round(float(puntaje), 1)
    if puntaje >= 6.6:
        porcentaje_ganancia = (puntaje - 6.5) * 10
        return int(costo_proporcional * (porcentaje_ganancia / 100))
    elif puntaje <= 6.3:
        porcentaje_perdida = (puntaje - 6.4) * 10
        return int(costo_proporcional * (porcentaje_perdida / 100))
    else:
        return 0

def calcular_cambio_prestigio(puntaje):
    p = round(float(puntaje), 1)
    if p < 5.9: return -2
    elif 6.0 <= p <= 6.4: return -1
    elif 6.5 <= p <= 6.9: return 0
    elif 7.0 <= p <= 7.9: return 1
    elif p >= 8.0: return 2
    return 0

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market", layout="wide")

if 'version' not in st.session_state:
    st.session_state.version = 0

st.subheader("🌎 World Transfer Market")

manager = st.sidebar.text_input("Nombre del Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1000000, 40)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR ---
st.sidebar.markdown(f"### Agente: {manager}")
st.sidebar.metric("Caja Global", f"€ {formatear_monto(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

st.sidebar.divider()
if prestigio >= 1:
    with st.sidebar.popover("💰 Pedir Crédito"):
        st.write("Solicitar **€ 150.000**")
        if st.button("CONFIRMAR CRÉDITO"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 150000, prestigio = prestigio - 1 WHERE id = ?", (u_id,), commit=True)
            st.session_state.version += 1
            st.rerun()

# Reset Seguro
st.sidebar.divider()
bloqueo_reset = st.sidebar.toggle("🔒 Bloquear Reset", value=True)
if not bloqueo_reset:
    with st.sidebar.expander("⚠️ RESET"):
        clave = st.text_input("Palabra clave:").upper()
        if st.button("BORRAR TODO", disabled=(clave != "BORRAR")):
            ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = 1000000, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
            st.session_state.version += 1
            st.rerun()

# --- 4. SCOUTING ---
df_oficial = cargar_datos_completos_google()

with st.expander("🔍 Scouting"):
    if df_oficial.empty:
        st.warning("No se pudo leer el listado.")
    else:
        df_oficial['Display'] = df_oficial.iloc[:, 0] + " (" + df_oficial.iloc[:, 2] + ")"
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Jugador Autorizado:", options=[""] + df_oficial['Display'].tolist())
        
        if seleccion:
            datos_j = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nombre_real = datos_j.iloc[0]
            equipo_sugerido = datos_j.iloc[1]
            try:
                cotizacion_raw = str(datos_j.iloc[3]).replace('.','').replace(',','')
                cotizacion_sugerida = int(''.join(filter(str.isdigit, cotizacion_raw)))
            except:
                cotizacion_sugerida = 1000000

            club_j = c1.text_input("Club:", value=equipo_sugerido)
            liga_j = c1.text_input("Liga:")
            
            valor_100 = c2.number_input("Valor 100%:", min_value=0, value=cotizacion_sugerida, step=50000)
            pct_compra = c2.slider("% de la ficha:", 5, 100, 10)
            
            costo_final = (valor_100 * pct_compra) / 100
            st.write(f"Inversión: **€ {formatear_monto(costo_final)}**")
            
            if st.button("CERRAR TRATO", use_container_width=True, type="primary", disabled=(presupuesto < costo_final)):
                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club, liga) VALUES (?,?,?,?,?,?)",
                            (u_id, nombre_real, pct_compra, costo_final, club_j, liga_j), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()

# --- 5. PANEL DE ACTIVOS ---
st.markdown("##### 📋 Jugadores Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club, liga FROM cartera WHERE usuario_id = ?", (u_id,))

for j_id, j_nom, j_pct, j_costo, j_club, j_liga in cartera:
    with st.container(border=True):
        col_info, col_input, col_ops = st.columns([2, 2, 2])
        v_key = f"{st.session_state.version}_{j_id}"
        
        col_info.subheader(j_nom)
        col_info.write(f"🌍 **{j_club}**")
        col_info.caption(f"{j_pct}% | € {formatear_monto(j_costo)}")
        
        pts_365 = col_input.number_input(f"Score 365", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{v_key}")
        balance = calcular_balance_fecha(pts_365, j_costo)
        color_bal = "green" if pts_365 >= 6.6 else "red" if pts_365 <= 6.3 else "gray"
        col_input.markdown(f"Rendimiento: :{color_bal}[€ {formatear_monto(balance)}]")
        
        with col_ops:
            confirmar = st.checkbox("Confirmar", key=f"conf_{v_key}")
            recupero = j_costo * 0.99
            
            if st.button("CARGAR RENDIMIENTO", key=f"btn_p_{v_key}", disabled=not confirmar, type="primary"):
                cambio_rep = calcular_cambio_prestigio(pts_365)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                            (balance, cambio_rep, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()

            if st.button(f"VENDER (€ {formatear_monto(recupero)})", key=f"btn_v_{v_key}", disabled=not confirmar):
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()
