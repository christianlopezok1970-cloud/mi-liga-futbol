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
st.title("⚽ Football Market Manager")

# Login de Usuario
user_name = st.sidebar.text_input("Ingresa tu nombre de Usuario").strip()

if not user_name:
    st.info("👋 ¡Bienvenido! Por favor, ingresa tu nombre en la barra lateral para empezar a gestionar tu equipo.")
    st.stop() # Esto detiene el código aquí hasta que haya un nombre

# Crear o cargar usuario (Ahora sí definimos user_id)
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, 50000000.0))
conn.commit()
c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_data = c.fetchone()
user_id, presupuesto = user_data

st.sidebar.success(f"Conectado como: {user_name}")
st.sidebar.metric("Presupuesto Actual", f"€{presupuesto:,.2f}")

# --- 4. GESTIÓN DE FICHAJES ---
POSICIONES_PERMITIDAS = {"Arquero": 2, "Defensor": 8, "Mediocampista": 8, "Delantero": 4}

with st.expander("➕ Fichar Nuevo Jugador"):
    col1, col2, col3 = st.columns(3)
    nuevo_nombre = col1.text_input("Nombre")
    nuevo_valor = col2.number_input("Precio (€)", min_value=0.0, step=100000.0)
    nueva_pos = col3.selectbox("Posición", list(POSICIONES_PERMITIDAS.keys()))
    
    if st.button("Confirmar Compra"):
        c.execute("SELECT posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
        plantilla = [row[0] for row in c.fetchall()]
        
        if presupuesto < nuevo_valor:
            st.error("No tienes suficiente dinero.")
        elif len(plantilla) >= 22:
            st.error("Plantilla completa (22/22).")
        elif plantilla.count(nueva_pos) >= POSICIONES_PERMITIDAS[nueva_pos]:
            st.error(f"Cupo de {nueva_pos} lleno.")
        else:
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion) VALUES (?,?,?,?)",
                      (user_id, nuevo_nombre, nuevo_valor, nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - nuevo_valor, user_id))
            conn.commit()
            st.success(f"¡{nuevo_nombre} fichado!")
            st.rerun()

# --- 5. LISTA DE JUGADORES Y SIMULADOR ---
st.header("📋 Tu Equipo")
c.execute("SELECT id, nombre, valor, posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
jugadores = c.fetchall()

if not jugadores:
    st.write("No tienes jugadores. ¡Ve al mercado para fichar!")
else:
    for j_id, j_nombre, j_valor, j_posicion in jugadores:
        with st.container():
            col_info, col_sim = st.columns([2, 3])
            col_info.write(f"**{j_nombre}**\n{j_posicion}\n€{j_valor:,.2f}")
            
            p_sim = col_sim.slider(f"Puntaje", 1.0, 10.0, 6.4, step=0.1, key=f"s_{j_id}")
            v_proy = calcular_nuevo_valor(j_valor, p_sim)
            diff = v_proy - j_valor
            
            col_sim.caption(f"Proyección: €{v_proy:,.2f} ({'+' if diff >= 0 else ''}{diff:,.2f})")
            
            c1, c2 = col_sim.columns(2)
            if c1.button("✅ Aplicar", key=f"a_{j_id}"):
                c.execute("UPDATE jugadores SET valor = ? WHERE id = ?", (v_proy, j_id))
                conn.commit()
                st.rerun()
            if c2.button("🗑️ Vender", key=f"v_{j_id}"):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_valor, user_id))
                conn.commit()
                st.rerun()
            st.divider()
