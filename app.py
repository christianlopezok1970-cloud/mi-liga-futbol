import streamlit as st
import sqlite3
import pandas as pd

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v30.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

def formatear_monto(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
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
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 2] + ") - € " + df['ValorNum'].apply(formatear_monto)
        return df
    except: return pd.DataFrame()

# Iniciar Tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)

# --- 2. LÓGICA DE JUEGO ---
def calcular_balance_fecha(puntaje, costo_proporcional):
    puntaje = round(float(puntaje), 1)
    if puntaje >= 6.6:
        porcentaje_ganancia = (puntaje - 6.5) * 10
        return int(costo_proporcional * (porcentaje_ganancia / 100))
    elif puntaje <= 6.3:
        porcentaje_perdida = (puntaje - 6.4) * 10
        return int(costo_proporcional * (porcentaje_perdida / 100))
    return 0

def calcular_cambio_prestigio(puntaje):
    p = round(float(puntaje), 1)
    if p < 5.9: return -2
    elif 6.0 <= p <= 6.4: return -1
    elif 7.0 <= p <= 7.9: return 1
    elif p >= 8.0: return 2
    return 0

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market", layout="wide")
if 'version' not in st.session_state: st.session_state.version = 0

st.subheader("🌎 World Transfer Market")

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1000000, 40)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]
st.sidebar.metric("Caja Global", f"€ {formatear_monto(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

# --- 4. SCOUTING ---
df_oficial = cargar_datos_completos_google()

with st.expander("🔍 Scouting y Co-propiedad"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Jugador Autorizado:", options=[""] + df_oficial['Display'].tolist())
        
        if seleccion:
            datos_j = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nombre_real = datos_j.iloc[0]
            
            vendido = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nombre_real,))
            total_vendido = vendido[0][0] if vendido[0][0] else 0
            disponible = 100 - total_vendido
            
            if disponible <= 0:
                st.error(f"🚫 Ficha agotada para {nombre_real}.")
            else:
                st.info(f"📊 Disponible para compra: **{int(disponible)}%**")
                club_j = c1.text_input("Club:", value=datos_j.iloc[1])
                valor_100 = c2.number_input("Valor 100%:", min_value=0, value=int(datos_j['ValorNum']), step=50000)
                
                opciones_posibles = [p for p in [25, 50, 75, 100] if p <= disponible]
                
                if opciones_posibles:
                    pct_compra = c2.select_slider("Porcentaje a adquirir:", options=opciones_posibles)
                    costo_final = (valor_100 * pct_compra) / 100
                    st.write(f"Costo de la operación: **€ {formatear_monto(costo_final)}**")
                    
                    if st.button("CERRAR TRATO", use_container_width=True, type="primary", disabled=(presupuesto < costo_final)):
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                                    (u_id, nombre_real, pct_compra, costo_final, club_j), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
                        st.session_state.version += 1
                        st.rerun()

# --- 5. PANEL DE ACTIVOS ---
st.markdown("##### 📋 Mis Jugadores Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    with st.container(border=True):
        col_info, col_input, col_ops = st.columns([2, 2, 2])
        v_key = f"{st.session_state.version}_{j_id}"
        
        col_info.subheader(j_nom)
        col_info.write(f"🌍 {j_club}")
        
        # --- DATO EN AMARILLO Y MÁS GRANDE ---
        col_info.markdown(
            f"""<div style="font-size:16px; color:#FFD700; font-weight:bold;">
            {int(j_pct)}% | Inversión: € {formatear_monto(j_costo)}
            </div>""", 
            unsafe_allow_html=True
        )
        
        pts_365 = col_input.number_input(f"Score 365", 1.0, 10.0, 6.4, step=0.1, key=f"score_{v_key}")
        balance = calcular_balance_fecha(pts_365, j_costo)
        color_res = "green" if pts_365 >= 6.6 else "red" if pts_365 <= 6.3 else "gray"
        col_input.markdown(f"Resultado: :{color_res}[€ {formatear_monto(balance)}]")
        
        with col_ops:
            confirmar = st.checkbox("Confirmar acción", key=f"check_{v_key}")
            
            if st.button("CARGAR RESULTADO", key=f"res_{v_key}", type="primary", disabled=not confirmar):
                cambio_rep = calcular_cambio_prestigio(pts_365)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                            (balance, cambio_rep, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()
            
            valor_recupero = j_costo * 0.99
            if st.button(f"VENDER (REC. € {formatear_monto(valor_recupero)})", key=f"sell_{v_key}", disabled=not confirmar):
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (valor_recupero, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()
