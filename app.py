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
conn.commit()

# --- 2. FUNCIONES DE LÓGICA ---
def calcular_nuevo_valor(valor_actual, puntaje):
    # Ecuación: (Puntaje - 6.4) / 0.1 * (1% del valor)
    diferencia_pasos = (puntaje - 6.4) / 0.1
    variacion = diferencia_pasos * (valor_actual / 100)
    return max(0, valor_actual + variacion)

# --- 3. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Football Market Manager", layout="wide")
st.title("⚽ Football Market Manager")

# Login de Usuario
user_name = st.sidebar.text_input("Ingresa tu nombre de Usuario").strip()

if not user_name:
    st.info("👋 ¡Bienvenido! Por favor, ingresa tu nombre en la barra lateral para empezar a gestionar tu equipo.")
    st.stop()

# --- CAMBIO AQUÍ: Presupuesto inicial a 11.000.000 ---
PRESUPUESTO_INICIAL = 11000000.0

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_data = c.fetchone()
user_id, presupuesto = user_data

st.sidebar.success(f"Conectado como: {user_name}")
st.sidebar.metric("Presupuesto Actual", f"€{presupuesto:,.2f}")

# --- CAMBIO AQUÍ: Nuevos topes de posición (Total 11 jugadores) ---
POSICIONES_PERMITIDAS = {
    "Arquero": 1,
    "Defensor": 4,
    "Mediocampista": 4,
    "Delantero": 2
}

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
            st.error("Ya tienes los 11 jugadores permitidos.")
        elif plantilla.count(nueva_pos) >= POSICIONES_PERMITIDAS[nueva_pos]:
            st.error(f"Ya has alcanzado el límite de {nueva_pos}s ({POSICIONES_PERMITIDAS[nueva_pos]}).")
        else:
            nuevo_presupuesto = presupuesto - nuevo_valor
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion) VALUES (?,?,?,?)",
                      (user_id, nuevo_nombre, nuevo_valor, nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_presupuesto, user_id))
            conn.commit()
            st.success(f"¡{nuevo_nombre} fichado correctamente!")
            st.rerun()

# --- 5. LISTA DE JUGADORES Y SIMULADOR ---
st.header("📋 Tu Equipo (Titulares)")
c.execute("SELECT id, nombre, valor, posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
jugadores = c.fetchall()

if not jugadores:
    st.write("No tienes jugadores en tu plantilla.")
else:
    # Mostrar contador de posiciones
    c_arq = sum(1 for j in jugadores if j[3] == "Arquero")
    c_def = sum(1 for j in jugadores if j[3] == "Defensor")
    c_med = sum(1 for j in jugadores if j[3] == "Mediocampista")
    c_del = sum(1 for j in jugadores if j[3] == "Delantero")
    
    st.write(f"📊 **Formación actual:** {c_arq} ARQ | {c_def} DEF | {c_med} MED | {c_del} DEL (Total: {len(jugadores)}/11)")

    for j_id, j_nombre, j_valor
