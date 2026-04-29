import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, posicion TEXT, FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
# Tabla para el "Deshacer" (Undo)
c.execute('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, presupuesto_ant REAL, datos_jugadores_json TEXT)''')
conn.commit()

# --- 2. FUNCIONES DE LÓGICA ---
def calcular_nuevo_valor(valor_actual, puntaje):
    diferencia_pasos = (puntaje - 6.4) / 0.1
    variacion = diferencia_pasos * (valor_actual / 100)
    return max(0, valor_actual + variacion)

def guardar_estado(u_id, pres):
    # Guardamos una foto del equipo actual antes de cambiar nada (simplificado para este ejemplo)
    # En una app compleja usaríamos JSON, aquí permitiremos deshacer el Presupuesto y advertir cambios.
    st.session_state['last_presupuesto'] = pres

# --- 3. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Football Market Manager", layout="wide")
st.title("⚽ Football Market Manager")

user_name = st.sidebar.text_input("Ingresa tu nombre de Usuario").strip()

if not user_name:
    st.info("👋 ¡Bienvenido! Ingresa tu nombre para gestionar tu equipo.")
    st.stop()

PRESUPUESTO_INICIAL = 11000000.0

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_data = c.fetchone()
user_id, presupuesto = user_data

# --- SECCIÓN DE HERRAMIENTAS (RESET Y REPARAR) ---
st.sidebar.divider()
st.sidebar.subheader("⚙️ Herramientas de Control")

# BOTÓN RESET
if st.sidebar.button("🚨 Resetear Mi Club", help="Borra todos tus jugadores y vuelve el dinero a 11M"):
    c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
    conn.commit()
    st.sidebar.warning("Club reseteado con éxito.")
    st.rerun()

# BOTÓN DESHACER (Simple)
if st.sidebar.button("🔙 Deshacer Última Venta/Compra"):
    st.sidebar.info("Esta función requiere un historial de transacciones. Por ahora, si te equivocaste, ¡usa el Reset o vende al jugador!")

st.sidebar.divider()
st.sidebar.success(f"Club: {user_name}")
st.sidebar.metric("Presupuesto Actual", f"€{presupuesto:,.2f}")

# --- 4. GESTIÓN DE FICHAJES ---
POSICIONES_PERMITIDAS = {"Arquero": 1, "Defensor": 4, "Mediocampista": 4, "Delantero": 2}

with st.expander("➕ Fichar Nuevo Jugador"):
    col1, col2, col3 = st.columns(3)
    nuevo_nombre = col1.text_input("Nombre del Jugador")
    nuevo_valor = col2.number_input("Precio de Mercado (€)", min_value=0.0, step=100000.0)
    nueva_pos = col3.selectbox("Posición", list(POSICIONES_PERMITIDAS.keys()))
    
    if st.button("Confirmar Compra"):
        c.execute("SELECT posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
        plantilla = [row[0] for row in c.fetchall()]
        
        if presupuesto < nuevo_valor:
            st.error("No tienes suficiente dinero.")
        elif len(plantilla) >= 11:
            st.error("Plantilla de 11 completa.")
        elif plantilla.count(nueva_pos) >= POSICIONES_PERMITIDAS[nueva_pos]:
            st.error(f"Cupo de {nueva_pos} lleno.")
        else:
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion) VALUES (?,?,?,?)",
                      (user_id, nuevo_nombre, nuevo_valor, nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - nuevo_valor, user_id))
            conn.commit()
            st.success("Fichaje exitoso.")
            st.rerun()

# --- 5. LISTA DE JUGADORES ---
st.header("📋 Tu Formación (1-4-4-2)")

query = """
    SELECT id, nombre, valor, posicion 
    FROM jugadores 
    WHERE usuario_id = ? 
    ORDER BY CASE posicion
        WHEN 'Arquero' THEN 1
        WHEN 'Defensor' THEN 2
        WHEN 'Mediocampista' THEN 3
        WHEN 'Delantero' THEN 4
    END
"""
c.execute(query, (user_id,))
jugadores = c.fetchall()

if not jugadores:
    st.write("Aún no tienes jugadores fichados.")
else:
    for j_id, j_nombre, j_valor, j_posicion in jugadores:
        with st.container():
            col_info, col_sim = st.columns([2, 3])
            emoji = "🧤" if j_posicion == "Arquero" else "🛡️" if j_posicion == "Defensor" else "⚙️" if j_posicion == "Mediocampista" else "⚽"
            
            col_info.write(f"### {emoji} {j_nombre}")
            col_info.write(f"**{j_posicion}**")
            col_info.write(f"Valor actual: **€{j_valor:,.2f}**")
            
            p_sim = col_sim.slider(f"Puntaje para {j_nombre}", 1.0, 10.0, 6.4, step=0.1, key=f"s_{j_id}")
            v_proy = calcular_nuevo_valor(j_valor, p_sim)
            diff = v_proy - j_valor
            
            color = "green" if diff >= 0 else "red"
            col_sim.markdown(f"Valor Proyectado: **€{v_proy:,.2f}** (<span style='color:{color}'>{'++' if diff >= 0 else ''}{diff:,.2f}</span>)", unsafe_allow_html=True)
            
            c1, c2 = col_sim.columns(2)
            if c1.button("✅ Aplicar Jornada", key=f"a_{j_id}"):
                c.execute("UPDATE jugadores SET
