import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONEXIÓN LIMPIA ---
# Cambiamos el nombre para asegurar una base de datos nueva
DB_NAME = 'agencia_definitiva.db'
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, posicion TEXT, club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        columnas = {'Nombre': ['Nombre', 'Jugador'], 'Precio': ['Cotización', 'Cotizacion', 'Precio'], 'Club': ['Club', 'Equipo'], 'Posicion': ['POS', 'Posicion']}
        for oficial, variantes in columnas.items():
            for v in variantes:
                if v in df.columns:
                    df.rename(columns={v: oficial}, inplace=True)
                    break
        df['Precio'] = df['Precio'].astype(str).apply(lambda x: re.sub(r'\D', '', x))
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0).astype(int)
        return df
    except: return None

df_mercado = cargar_datos()

def formatear_monto(valor):
    if valor >= 1000000: return f"{valor / 1000000:.1f} M"
    elif valor >= 1000: return f"{int(valor / 1000)} K"
    return str(int(valor))

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Agencia Manager", layout="wide")
user_name = st.sidebar.text_input("Nombre del Agente").strip()

if not user_name:
    st.info("Escribe tu nombre en la izquierda para empezar de cero.")
    st.stop()

# LOGIN
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 40)", (user_name,))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
u_id, presupuesto, prestigio = c.fetchone()

# SIDEBAR
st.sidebar.metric("Billetera", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

# --- 4. MERCADO (CON EL BUSCADOR QUE PEDISTE) ---
with st.expander("🛒 Mercado de Pases"):
    if df_mercado is not None:
        # Buscador por nombre
        bus_nom = st.text_input("🔍 Buscar por nombre:")
        
        df_filtrado = df_mercado[df_mercado['Nombre'].str.contains(bus_nom, case=False, na=False)]
        
        # Formato: nombre-monto-posicion-equipo
        lista = df_filtrado.apply(
            lambda x: f"{x['Nombre']}/ {formatear_monto(x['Precio'])}/ {x['Posicion']}/ {x['Club']}", axis=1
        ).tolist()
        
        seleccion = st.selectbox("Seleccionar Jugador", options=lista)
        
        if st.button("FICHAR JUGADOR", use_container_width=True, type="primary"):
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (u_id,))
            if c.fetchone()[0] >= 1:
                st.error("Ya tienes un jugador.")
            else:
                j_info = df_filtrado.iloc[lista.index(seleccion)]
                if presupuesto < j_info['Precio']:
                    st.error("Dinero insuficiente.")
                else:
                    c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                              (u_id, j_info['Nombre'], j_info['Precio'], j_info['Posicion'], j_info['Club']))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_info['Precio'], u_id))
                    conn.commit()
                    st.rerun()

# --- 5. MI CARTERA ---
st.divider()
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (u_id,))
j = c.fetchone()

if j:
    st.subheader(f"Representando a: {j[1]}")
    if st.button(f"Vender por €{int(j[2]*0.98):,}"):
        c.execute("DELETE FROM jugadores WHERE id = ?", (j[0],))
        c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j[2]*0.98, u_id))
        conn.commit()
        st.rerun()
else:
    st.info("No tienes jugadores contratados.")
