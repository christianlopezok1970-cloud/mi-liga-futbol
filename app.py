import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v15.db'

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT, liga TEXT)''', commit=True)

# --- 2. LÓGICA FINANCIERA ---
def formatear_monto(monto):
    return f"{int(monto):,}".replace(",", ".")

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
        st.caption("Costo: -1 punto de reputación.")
        if st.button("CONFIRMAR CRÉDITO"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 150000, prestigio = prestigio - 1 WHERE id = ?", (u_id,), commit=True)
            st.session_state.version += 1
            st.rerun()

# --- 4. SCOUTING (CON LISTADO DE JUGADORES) ---
# Obtenemos la lista de jugadores actuales para el buscador
lista_jugadores_db = ejecutar_db("SELECT DISTINCT nombre_jugador FROM cartera WHERE usuario_id = ?", (u_id,))
opciones_jugadores = [j[0] for j in lista_jugadores_db]

with st.expander("🔍 Scouting"):
    c1, c2 = st.columns(2)
    
    # Campo con sugerencias de jugadores ya subidos
    nombre_j = c1.selectbox("Jugador (selecciona o escribe):", 
                             options=[""] + opciones_jugadores, 
                             index=0, 
                             help="Puedes elegir uno existente o escribir uno nuevo",
                             placeholder="Escribe el nombre del jugador...",
                             label_visibility="visible")
    
    # Si el selectbox está vacío, permitimos entrada manual
    if nombre_j == "":
        nombre_j = c1.text_input("Nombre del nuevo jugador:")

    club_j = c1.text_input("Club:")
    liga_j = c1.text_input("Liga:")
    
    valor_100 = c2.number_input("Valor 100%:", min_value=0, step=50000, value=1000000)
    pct_compra = c2.slider("% adquirido:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión total: **€ {formatear_monto(costo_final)}**")
    
    if st.button("CERRAR TRATO", use_container_width=True, type="primary", disabled=(presupuesto < costo_final or nombre_j == "")):
        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club, liga) VALUES (?,?,?,?,?,?)",
                    (u_id, nombre_j, pct_compra, costo_final, club_j, liga_j), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
        st.session_state.version += 1
        st.rerun()

# --- 5. PANEL DE ACTIVOS ---
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
            col_info.caption(f"{j_pct}% | € {formatear_monto(j_costo)}")
            
            pts_365 = col_input.number_input(f"Score 365", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{v_key}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            color_bal = "green" if pts_365 >= 6.6 else "red" if pts_365 <= 6.3 else "gray"
            col_input.markdown(f"Rendimiento: :{color_bal}[€ {formatear_monto(balance)}]")
            
            with col_ops:
                confirmar = st.checkbox("Confirmar", key=f"conf_{v_key}")
                
                perdida_venta = j_costo * 0.01
                recupero = j_costo - perdida_venta
                
                if confirmar:
                    st.error(f"⚠️ Pérdida por venta: € {formatear_monto(perdida_venta)}")

                if st.button("CARGAR RENDIMIENTO", key=f"btn_p_{v_key}", disabled=not confirmar, use_container_width=True, type="primary"):
                    cambio_rep = calcular_cambio_prestigio(pts_365)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                                (balance, cambio_rep, u_id), commit=True)
                    st.session_state.version += 1
                    st.rerun()

                if st.button(f"VENDER (Recibes € {formatear_monto(recupero)})", key=f"btn_v_{v_key}", disabled=not confirmar, use_container_width=True):
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                    st.session_state.version += 1
                    st.rerun()
