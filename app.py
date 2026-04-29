import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)''')
# Añadimos la columna 'valor_anterior' a la tabla de jugadores
try:
    c.execute("ALTER TABLE jugadores ADD COLUMN valor_anterior REAL")
except:
    pass # Si ya existe, no hace nada

c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, valor_anterior REAL, posicion TEXT, 
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. FUNCIONES DE LÓGICA ---
def calcular_nuevo_valor(valor_actual, puntaje):
    diferencia_pasos = (puntaje - 6.4) / 0.1
    variacion = diferencia_pasos * (valor_actual / 100)
    return int(max(0, valor_actual + variacion)) # Convertimos a entero (sin decimales)

# --- 3. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Football Market Manager", layout="wide")
st.title("⚽ Football Market Manager")

user_name = st.sidebar.text_input("Ingresa tu nombre de Usuario").strip()

if not user_name:
    st.info("👋 ¡Bienvenido! Ingresa tu nombre en la barra lateral para empezar.")
    st.stop()

PRESUPUESTO_INICIAL = 11000000

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_data = c.fetchone()
user_id, presupuesto = user_data

# --- SIDEBAR: HERRAMIENTAS ---
st.sidebar.divider()
if st.sidebar.button("🚨 Resetear Mi Club"):
    c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
    conn.commit()
    st.rerun()

st.sidebar.divider()
st.sidebar.success(f"Club: {user_name}")
st.sidebar.metric("Presupuesto Actual", f"€{int(presupuesto):,}")

# --- 4. GESTIÓN DE FICHAJES ---
POSICIONES_PERMITIDAS = {"Arquero": 1, "Defensor": 4, "Mediocampista": 4, "Delantero": 2}

with st.expander("➕ Fichar Nuevo Jugador"):
    col1, col2, col3 = st.columns(3)
    nuevo_nombre = col1.text_input("Nombre")
    nuevo_valor = col2.number_input("Precio (€)", min_value=0, step=100000)
    nueva_pos = col3.selectbox("Posición", list(POSICIONES_PERMITIDAS.keys()))
    
    if st.button("Confirmar Compra"):
        c.execute("SELECT posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
        plantilla = [row[0] for row in c.fetchall()]
        
        if presupuesto < nuevo_valor:
            st.error("No tienes dinero suficiente.")
        elif len(plantilla) >= 11:
            st.error("Plantilla completa (11/11).")
        elif plantilla.count(nueva_pos) >= POSICIONES_PERMITIDAS[nueva_pos]:
            st.error(f"Límite alcanzado para {nueva_pos}.")
        else:
            # Al comprar, el valor anterior es el mismo que el inicial
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, valor_anterior, posicion) VALUES (?,?,?,?,?)",
                      (user_id, nuevo_nombre, int(nuevo_valor), int(nuevo_valor), nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - nuevo_valor, user_id))
            conn.commit()
            st.rerun()

# --- 5. LISTA DE JUGADORES ---
st.header("📋 Tu Equipo") # Cambio de título solicitado

query = """
    SELECT id, nombre, valor, valor_anterior, posicion FROM jugadores 
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
    for j_id, j_nombre, j_valor, j_valor_ant, j_posicion in jugadores:
        with st.container():
            col_info, col_sim = st.columns([2, 3])
            emoji = "🧤" if j_posicion == "Arquero" else "🛡️" if j_posicion == "Defensor" else "⚙️" if j_posicion == "Mediocampista" else "⚽"
            
            col_info.write(f"### {emoji} {j_nombre}")
            col_info.write(f"**{j_posicion}**")
            col_info.write(f"Valor Actual: **€{int(j_valor):,}**")
            if j_valor_ant:
                col_info.write(f"Valor Fecha Anterior: €{int(j_valor_ant):,}")
            
            p_sim = col_sim.slider(f"Puntos", 1.0, 10.0, 6.4, step=0.1, key=f"s_{j_id}")
            v_proy = calcular_nuevo_valor(j_valor, p_sim)
            diff = v_proy - j_valor
            
            color = "green" if diff >= 0 else "red"
            col_sim.markdown(f"Nuevo Proyectado: **€{int(v_proy):,}** (<span style='color:{color}'>{'++' if diff >= 0 else ''}{int(diff):,}</span>)", unsafe_allow_html=True)
            
            c1, c2 = col_sim.columns(2)
            if c1.button("✅ Aplicar", key=f"a_{j_id}"):
                # Al aplicar, el valor actual pasa a ser el anterior
                c.execute("UPDATE jugadores SET valor_anterior = ?, valor = ? WHERE id = ?", (j_valor, v_proy, j_id))
                conn.commit()
                st.rerun()
            if c2.button("🗑️ Vender", key=f"v_{j_id}"):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_valor, user_id))
                conn.commit()
                st.rerun()
            st.divider()
