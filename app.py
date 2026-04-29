import streamlit as st
import sqlite3

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)''')

try:
    c.execute("ALTER TABLE jugadores ADD COLUMN valor_anterior REAL")
except:
    pass

c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, valor_anterior REAL, posicion TEXT, 
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. FUNCIONES DE LÓGICA ---
def calcular_nuevo_valor(valor_actual, puntaje):
    # Ecuación: (Puntaje - 6.4) / 0.1 * (1% del valor)
    diferencia_pasos = (puntaje - 6.4) / 0.1
    variacion = diferencia_pasos * (valor_actual / 100)
    return int(max(0, valor_actual + variacion))

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
            val_int = int(nuevo_valor)
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, valor_anterior, posicion) VALUES (?,?,?,?,?)",
                      (user_id, nuevo_nombre, val_int, val_int, nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - nuevo_valor, user_id))
            conn.commit()
            st.rerun()

# --- 5. LISTA DE JUGADORES ---
st.header("📋 Tu Equipo")

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
            col_info, col_pts, col_btns = st.columns([2, 1, 1])
            emoji = "🧤" if j_posicion == "Arquero" else "🛡️" if j_posicion == "Defensor" else "⚙️" if j_posicion == "Mediocampista" else "⚽"
            
            # Información del jugador
            col_info.write(f"### {emoji} {j_nombre}")
            col_info.write(f"**{j_posicion}**")
            col_info.write(f"Actual: **€{int(j_valor):,}** | Anterior: €{int(j_valor_ant):,}")
            
            # Selector de puntos con botones + / -
            puntos = col_pts.number_input("Puntos", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            
            # Botones de acción
            if col_btns.button("✅ Aplicar", key=f"a_{j_id}", use_container_width=True):
                v_nuevo = calcular_nuevo_valor(j_valor, puntos)
                c.execute("UPDATE jugadores SET valor_anterior = ?, valor = ? WHERE id = ?", (j_valor, v_nuevo, j_id))
                conn.commit()
                st.rerun()
                
            if col_btns.button("🗑️ Vender", key=f"v_{j_id}", use_container_width=True):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_valor, user_id))
                conn.commit()
                st.rerun()
            st.divider()
