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

# --- 2. LÓGICA DE NEGOCIO ---
MONTO_MULTA = 200000 

def calcular_nuevo_valor(valor_actual, puntaje):
    diferencia_pasos = (puntaje - 6.4) / 0.1
    variacion = diferencia_pasos * (valor_actual / 100)
    return int(max(0, valor_actual + variacion))

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Football Market Manager", layout="wide")
st.title("⚽ Football Market Manager")

user_name = st.sidebar.text_input("Ingresa tu nombre de Usuario").strip()

if not user_name:
    st.info("👋 Ingresa tu nombre en la barra lateral para comenzar.")
    st.stop()

PRESUPUESTO_INICIAL = 11000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_data = c.fetchone()
user_id, presupuesto = user_data

# --- SIDEBAR: ESTADO Y SEGURIDAD ---
st.sidebar.success(f"Club: {user_name}")
st.sidebar.metric("Presupuesto Actual", f"€{int(presupuesto):,}")

st.sidebar.divider()
# ZONA DE PELIGRO CON CONFIRMACIÓN
with st.sidebar.expander("⚠️ Zona de Peligro"):
    st.write("Esta acción es irreversible.")
    confirmar_reset = st.checkbox("Confirmar que quiero borrar todo")
    if st.button("🚨 Resetear Mi Club", disabled=not confirmar_reset):
        c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
        conn.commit()
        st.toast("El club ha sido reiniciado.", icon="♻️")
        st.rerun()

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
            st.error("Fondos insuficientes.")
        elif len(plantilla) >= 11:
            st.error("Plantilla llena (11/11).")
        elif plantilla.count(nueva_pos) >= POSICIONES_PERMITIDAS[nueva_pos]:
            st.error(f"Límite de {nueva_pos} alcanzado.")
        else:
            val_int = int(nuevo_valor)
            c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, valor_anterior, posicion) VALUES (?,?,?,?,?)",
                      (user_id, nuevo_nombre, val_int, val_int, nueva_pos))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - nuevo_valor, user_id))
            conn.commit()
            st.rerun()

# --- 5. LISTA DE JUGADORES ---
st.header("📋 Tu Equipo")

c.execute("SELECT id, nombre, valor, valor_anterior, posicion FROM jugadores WHERE usuario_id = ? ORDER BY CASE posicion WHEN 'Arquero' THEN 1 WHEN 'Defensor' THEN 2 WHEN 'Mediocampista' THEN 3 WHEN 'Delantero' THEN 4 END", (user_id,))
jugadores = c.fetchall()
total_jugadores = len(jugadores)

if total_jugadores < 11:
    faltantes = 11 - total_jugadores
    multa_jornada = faltantes * MONTO_MULTA
    st.warning(f"⚠️ Equipo incompleto ({total_jugadores}/11). Multa de €{multa_jornada:,} al aplicar puntos.")

if not jugadores:
    st.write("Aún no tienes jugadores fichados.")
else:
    for j_id, j_nombre, j_valor, j_valor_ant, j_posicion in jugadores:
        with st.container():
            col_info, col_pts, col_btns = st.columns([2, 1, 1])
            emoji = "🧤" if j_posicion == "Arquero" else "🛡️" if j_posicion == "Defensor" else "⚙️" if j_posicion == "Mediocampista" else "⚽"
            
            col_info.write(f"### {emoji} {j_nombre}")
            col_info.write(f"**{j_posicion}**")
            col_info.write(f"Actual: **€{int(j_valor):,}** | Anterior: €{int(j_valor_ant):,}")
            
            puntos = col_pts.number_input("Puntos", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            
            if col_btns.button("✅ Aplicar", key=f"a_{j_id}", use_container_width=True):
                v_nuevo = calcular_nuevo_valor(j_valor, puntos)
                multa_a_descontar = (11 - total_jugadores) * MONTO_MULTA if total_jugadores < 11 else 0
                
                # Evitamos presupuesto negativo si querés (opcional, aquí lo resto directo)
                nuevo_presupuesto = presupuesto - multa_a_descontar
                
                c.execute("UPDATE jugadores SET valor_anterior = ?, valor = ? WHERE id = ?", (j_valor, v_nuevo, j_id))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_presupuesto, user_id))
                conn.commit()
                
                if multa_a_descontar > 0:
                    st.toast(f"🛑 Multa de €{multa_a_descontar:,} cobrada.", icon="💸")
                st.rerun()
                
            if col_btns.button("🗑️ Vender", key=f"v_{j_id}", use_container_width=True):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_valor, user_id))
                conn.commit()
                st.rerun()
            st.divider()
