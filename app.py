import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_afa_v5.db'

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

# Creación de tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)

# --- 2. FUNCIONES DE FORMATO Y LÓGICA ---
def formatear_monto(monto):
    monto = float(monto)
    abs_monto = abs(monto)
    if abs_monto >= 1_000_000:
        return f"{monto / 1_000_000:.1f} M"
    elif abs_monto >= 1_000:
        return f"{int(monto / 1_000)} K"
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
st.set_page_config(page_title="Agente LPF Pro", layout="wide")
st.title("⚽ Agencia LPF: Gestión y Préstamos")

manager = st.sidebar.text_input("Tu Nombre de Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral para iniciar.")
    st.stop()

# Registro/Carga de perfil (Presupuesto inicial 1M)
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1000000, 40)", (manager,), commit=True)
datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR: DASHBOARD Y PRÉSTAMOS ---
st.sidebar.markdown(f"### Manager: {manager}")
st.sidebar.metric("Presupuesto", f"€{formatear_monto(presupuesto)}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

st.sidebar.divider()
st.sidebar.subheader("🏦 Financiamiento")
if prestigio >= 10:
    if st.sidebar.button("Pedir Préstamo (1M)", help="Recibe 1M a cambio de 10 pts de prestigio"):
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 1000000, prestigio = prestigio - 10 WHERE id = ?", (u_id,), commit=True)
        st.toast("✅ Préstamo concedido. -10 Prestigio.")
        st.rerun()
else:
    st.sidebar.error("Prestigio insuficiente para préstamos.")

# --- 4. MERCADO DE PORCENTAJES ---
with st.expander("🤝 Adquirir Porcentaje de Jugador"):
    c1, c2 = st.columns(2)
    nombre_j = c1.text_input("Nombre del Jugador:")
    club_j = c1.selectbox("Club LPF:", ["River", "Boca", "Talleres", "Racing", "Independiente", "San Lorenzo", "Estudiantes", "Lanús", "Velez", "Otros"])
    valor_100 = c2.number_input("Valor de Mercado (100%):", min_value=10000, step=50000, value=1000000)
    pct_compra = c2.slider("% de la ficha:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión requerida: **€{formatear_monto(costo_final)}**")
    
    # Validación de presupuesto
    puedo_comprar = presupuesto >= costo_final
    if not puedo_comprar:
        st.warning("⚠️ Fondos insuficientes para este contrato.")

    if st.button("FIRMAR CONTRATO", use_container_width=True, type="primary", disabled=not puedo_comprar):
        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                    (u_id, nombre_j, pct_compra, costo_final, club_j), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
        st.success(f"¡{nombre_j} agregado a tu agencia!")
        st.rerun()

# --- 5. PANEL DE SEGUIMIENTO ---
st.header("📈 Cartera de Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera:
    st.warning("No tienes jugadores en tu agencia.")
else:
    for j_id, j_nom, j_pct, j_costo, j_club in cartera:
        with st.container(border=True):
            col_info, col_input, col_ops = st.columns([2, 2, 2])
            
            col_info.subheader(j_nom)
            col_info.write(f"**{j_club}** | Propiedad: {j_pct}%")
            col_info.caption(f"Costo proporcional: €{formatear_monto(j_costo)}")
            
            pts_365 = col_input.number_input(f"Score 365 ({j_nom})", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            
            color_bal = "gray"
            if pts_365 >= 6.6: color_bal = "green"
            elif pts_365 <= 6.3: color_bal = "red"
            
            col_input.markdown(f"Rendimiento: :{color_bal}[€{formatear_monto(balance)}]")
            
            with col_ops:
                confirmar = st.checkbox("Confirmar acción", key=f"conf_{j_id}")
                c_btn1, c_btn2 = st.columns(2)
                
                if c_btn1.button("PROCESAR", key=f"proc_{j_id}", disabled=not confirmar, use_container_width=True):
                    # El prestigio cambia según el rendimiento
                    cambio_prestigio = 1 if pts_365 >= 7.0 else -1 if pts_365 <= 5.5 else 0
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                                (balance, cambio_prestigio, u_id), commit=True)
                    st.rerun()

                if c_btn2.button("VENDER", key=f"vend_{j_id}", disabled=not confirmar, use_container_width=True, type="secondary"):
                    # Recupera el 98%
                    recupero = j_costo * 0.98
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                    st.rerun()

# Reset Total en Sidebar
if st.sidebar.button("Reiniciar Sistema"):
    ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
    ejecutar_db("UPDATE usuarios SET presupuesto = 1000000, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
    st.rerun()
