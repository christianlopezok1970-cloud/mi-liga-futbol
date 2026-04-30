import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v11.db'

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

# Tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT, liga TEXT)''', commit=True)

# --- 2. LÓGICA FINANCIERA ---
def formatear_monto(monto):
    monto = float(monto)
    abs_monto = abs(monto)
    if abs_monto >= 1_000_000:
        return f"{monto / 1_000_000:.1f} M"
    elif abs_monto >= 1_000:
        return f"{int(abs_monto / 1_000)} K"
    return f"{int(monto)}"

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

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market", layout="wide")

if 'version' not in st.session_state:
    st.session_state.version = 0

# TÍTULO PRINCIPAL (H3)
st.subheader("🌎 World Transfer Market")

manager = st.sidebar.text_input("Nombre del Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral.")
    st.stop()

# Registro/Carga
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1000000, 40)", (manager,), commit=True)
datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR ---
st.sidebar.markdown(f"### Agente: {manager}")
st.sidebar.metric("Caja Global", f"€{formatear_monto(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

st.sidebar.divider()
if prestigio >= 10:
    with st.sidebar.popover("💰 Pedir Crédito"):
        st.warning("¿Confirmas la inyección de capital?")
        st.write("Recibirás **1.0 M**. Costo: **-10 pts**.")
        if st.button("CONFIRMAR"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 1000000, prestigio = prestigio - 10 WHERE id = ?", (u_id,), commit=True)
            st.session_state.version += 1
            st.rerun()

st.sidebar.divider()
with st.sidebar.expander("⚠️ Zona de Peligro"):
    st.write("Escribe **BORRAR** para resetear:")
    clave = st.text_input("Palabra clave", key="reset_key").upper()
    if st.button("RESETEAR TODO EL JUEGO", type="secondary", disabled=(clave != "BORRAR")):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 1000000, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
        st.session_state.version += 1
        st.rerun()

# --- 4. SCOUTING ---
with st.expander("🔍 Scouting Global"):
    c1, c2 = st.columns(2)
    nombre_j = c1.text_input("Jugador:")
    club_j = c1.text_input("Club:")
    liga_j = c1.text_input("Liga:")
    valor_100 = c2.number_input("Valor 100%:", min_value=10000, step=50000, value=1000000)
    pct_compra = c2.slider("% adquirido:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión: **€{formatear_monto(costo_final)}**")
    
    if st.button("CERRAR TRATO", use_container_width=True, type="primary", disabled=(presupuesto < costo_final)):
        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club, liga) VALUES (?,?,?,?,?,?)",
                    (u_id, nombre_j, pct_compra, costo_final, club_j, liga_j), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
        st.session_state.version += 1
        st.rerun()

# --- 5. PANEL DE ACTIVOS ---
# TÍTULO REDUCIDO (H5) Y RENOMBRADO
st.markdown("##### 📋 Jugadores Representados")

cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club, liga FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera:
    st.warning("No tienes activos.")
else:
    for j_id, j_nom, j_pct, j_costo, j_club, j_liga in cartera:
        with st.container(border=True):
            col_info, col_input, col_ops = st.columns([2, 2, 2])
            v_key = f"{st.session_state.version}_{j_id}"
            
            col_info.subheader(j_nom)
            col_info.write(f"🌍 **{j_club}** ({j_liga})")
            col_info.caption(f"{j_pct}% | €{formatear_monto(j_costo)}")
            
            pts_365 = col_input.number_input(f"Score 365", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{v_key}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            color_bal = "green" if pts_365 >= 6.6 else "red" if pts_365 <= 6.3 else "gray"
            col_input.markdown(f"Rendimiento: :{color_bal}[€{formatear_monto(balance)}]")
            
            with col_ops:
                confirmar = st.checkbox("Confirmar", key=f"conf_{v_key}")
                if st.button("CARGAR RENDIMIENTO", key=f"btn_p_{v_key}", disabled=not confirmar, use_container_width=True, type="primary"):
                    cambio_rep = 1 if pts_365 >= 7.0 else -1 if pts_365 <= 5.5 else 0
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                                (balance, cambio_rep, u_id), commit=True)
                    st.session_state.version += 1
                    st.rerun()

                if st.button("VENDER", key=f"btn_v_{v_key}", disabled=not confirmar, use_container_width=True):
                    recupero = j_costo * 0.98
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                    st.session_state.version += 1
                    st.rerun()
