import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_afa_v4.db'

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
    prefijo = "-" if monto < 0 else ""
    abs_monto = abs(monto)
    
    if abs_monto >= 1_000_000:
        return f"{prefijo}{abs_monto / 1_000_000:.1f} M"
    elif abs_monto >= 1_000:
        return f"{prefijo}{int(abs_monto / 1_000)} K"
    return f"{prefijo}{int(abs_monto)}"

def calcular_balance_fecha(puntaje, costo_proporcional):
    puntaje = round(float(puntaje), 1)
    # Eje 6.4 y 6.5 = 0
    if puntaje >= 6.6:
        # 6.6 es 1%, 6.7 es 2%... (puntaje - 6.5) * 10
        porcentaje_ganancia = (puntaje - 6.5) * 10
        return int(costo_proporcional * (porcentaje_ganancia / 100))
    elif puntaje <= 6.3:
        # 6.3 es -1%, 6.2 es -2%... (puntaje - 6.4) * 10
        porcentaje_perdida = (puntaje - 6.4) * 10
        return int(costo_proporcional * (porcentaje_perdida / 100))
    else:
        return 0

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Agente LPF Pro", layout="wide")
st.title("⚽ Agencia LPF: Gestión de Activos")

manager = st.sidebar.text_input("Tu Nombre de Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral para iniciar.")
    st.stop()

# Registro/Carga de perfil (Presupuesto inicial 0)
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 0, 40)", (manager,), commit=True)
datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
u_id, presupuesto, prestigio = datos[0]

# Dashboard Lateral
st.sidebar.markdown(f"### Manager: {manager}")
color_presu = "red" if presupuesto < 0 else "white"
st.sidebar.markdown(f"Presupuesto: :{color_presu}[€{formatear_monto(presupuesto)}]")
st.sidebar.metric("Prestigio", f"{prestigio} pts")
st.sidebar.divider()

# --- 4. MERCADO DE PORCENTAJES ---
with st.expander("🤝 Adquirir Porcentaje de Jugador"):
    c1, c2 = st.columns(2)
    nombre_j = c1.text_input("Nombre del Jugador:")
    club_j = c1.selectbox("Club LPF:", ["River", "Boca", "Talleres", "Racing", "Independiente", "San Lorenzo", "Estudiantes", "Lanús", "Velez", "Otros"])
    valor_100 = c2.number_input("Valor de Mercado (100%):", min_value=10000, step=50000, value=1000000)
    pct_compra = c2.slider("% de la ficha:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión (Se restará de tu saldo): **€{formatear_monto(costo_final)}**")
    
    if st.button("FIRMAR CONTRATO", use_container_width=True, type="primary"):
        ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                    (u_id, nombre_j, pct_compra, costo_final, club_j), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
        st.success(f"¡{nombre_j} agregado! Tu saldo ahora es negativo.")
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
            
            # Columna 1: Info
            col_info.subheader(j_nom)
            col_info.write(f"**{j_club}** | Propiedad: {j_pct}%")
            col_info.caption(f"Costo proporcional: €{formatear_monto(j_costo)}")
            
            # Columna 2: Puntaje y Balance
            pts_365 = col_input.number_input(f"Score 365 ({j_nom})", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            
            # Lógica de color según el eje solicitado
            color_bal = "gray"
            if pts_365 >= 6.6: color_bal = "green"
            elif pts_365 <= 6.3: color_bal = "red"
            
            col_input.markdown(f"Rendimiento: :{color_bal}[€{formatear_monto(balance)}]")
            
            # Columna 3: Doble Seguridad y Reset
            with col_ops:
                # Procesar Partido
                confirmar = st.checkbox("Confirmar acción", key=f"conf_{j_id}")
                
                c_btn1, c_btn2 = st.columns(2)
                
                if c_btn1.button("PROCESAR", key=f"proc_{j_id}", disabled=not confirmar, use_container_width=True):
                    nuevo_prestigio = prestigio + (1 if balance > 0 else -1 if balance < 0 else 0)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", 
                                (balance, nuevo_prestigio, u_id), commit=True)
                    # El st.rerun() limpia automáticamente los checkboxes
                    st.rerun()

                if c_btn2.button("VENDER", key=f"vend_{j_id}", disabled=not confirmar, use_container_width=True, type="secondary"):
                    # Recupera el 98% del valor de compra
                    recupero = j_costo * 0.98
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                    st.rerun()

# Reset Total (Opcional)
if st.sidebar.button("Reiniciar Sistema"):
    ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
    ejecutar_db("UPDATE usuarios SET presupuesto = 0, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
    st.rerun()
