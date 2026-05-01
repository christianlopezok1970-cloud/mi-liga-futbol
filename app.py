import streamlit as st
import sqlite3
import pandas as pd

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v27.db'
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

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market", layout="wide")
if 'version' not in st.session_state: st.session_state.version = 0

st.subheader("🌎 World Transfer Market - Co-propiedad")

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1000000, 40)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]
st.sidebar.metric("Caja Global", f"€ {formatear_monto(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

# --- 4. SCOUTING MULTI-AGENTE ---
df_oficial = cargar_datos_completos_google()

with st.expander("🔍 Scouting"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Jugador Autorizado:", options=[""] + df_oficial['Display'].tolist())
        
        if seleccion:
            datos_j = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nombre_real = datos_j.iloc[0]
            
            # --- CÁLCULO DE PORCENTAJE DISPONIBLE ---
            vendido = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nombre_real,))
            total_vendido = vendido[0][0] if vendido[0][0] else 0
            disponible = 100 - total_vendido
            
            if disponible <= 0:
                st.error(f"🚫 Ficha agotada. El 100% de {nombre_real} ya pertenece a otros agentes.")
                compra_bloqueada = True
            else:
                st.info(f"📊 Ficha disponible en el mercado: **{int(disponible)}%**")
                compra_bloqueada = False

                club_j = c1.text_input("Club:", value=datos_j.iloc[1])
                valor_100 = c2.number_input("Valor 100%:", min_value=0, value=int(datos_j['ValorNum']), step=50000)
                
                # Solo permitimos opciones que no superen lo disponible
                opciones_posibles = [p for p in [25, 50, 75, 100] if p <= disponible]
                
                if not opciones_posibles:
                    st.warning("No puedes comprar el mínimo (25%) porque queda muy poco disponible.")
                    compra_bloqueada = True
                    pct_compra = 0
                else:
                    pct_compra = c2.select_slider("Adquirir porcentaje:", options=opciones_posibles)
                    costo_final = (valor_100 * pct_compra) / 100
                    st.write(f"Inversión: **€ {formatear_monto(costo_final)}**")
                    
                    if st.button("CERRAR TRATO", use_container_width=True, type="primary", 
                                 disabled=(presupuesto < costo_final or compra_bloqueada)):
                        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                                    (u_id, nombre_real, pct_compra, costo_final, club_j), commit=True)
                        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
                        st.rerun()

# --- 5. PANEL DE ACTIVOS ---
st.markdown("##### 📋 Mis Jugadores Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    with st.container(border=True):
        col_info, col_input, col_ops = st.columns([2, 2, 2])
        col_info.subheader(j_nom)
        col_info.caption(f"{int(j_pct)}% de la ficha | € {formatear_monto(j_costo)}")
        
        pts_365 = col_input.number_input(f"Score", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
        balance = calcular_balance_fecha(pts_365, j_costo)
        col_input.write(f"Rendimiento: € {formatear_monto(balance)}")
        
        if col_ops.button("CARGAR RESULTADO", key=f"btn_{j_id}"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (balance, u_id), commit=True)
            st.rerun()
