import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONEXIÓN ESTRUCTURADA ---
# Usamos un nombre nuevo para asegurar frescura total
DB_NAME = 'agencia_reinicio.db'
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, posicion TEXT, club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. CARGA Y LIMPIEZA DE DATOS ---
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

# --- 3. LOGIN Y PERFIL ---
st.set_page_config(page_title="Agencia Manager", layout="wide")
user_name = st.sidebar.text_input("Nombre del Agente").strip()

if not user_name:
    st.warning("⚠️ Ingresa tu nombre en la izquierda para resetear tu carrera.")
    st.stop()

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 40)", (user_name,))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
u_id, presupuesto, prestigio = c.fetchone()

st.sidebar.subheader(f"Agente: {user_name}")
st.sidebar.metric("Billetera", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

# --- 4. MERCADO DE PASES ---
with st.expander("🛒 MERCADO (Fichaje de Clientes)"):
    if df_mercado is not None:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            bus_nom = st.text_input("🔍 Buscar por nombre:")
        with col_f2:
            p_min = st.number_input("Precio Mín €:", 0, value=0, step=100000)
            
        # Filtrado dinámico
        df_f = df_mercado[
            (df_mercado['Nombre'].str.contains(bus_nom, case=False, na=False)) & 
            (df_mercado['Precio'] >= p_min)
        ]
        
        # Formato solicitado: Nombre / Monto / Posición / Equipo
        lista = df_f.apply(
            lambda x: f"{x['Nombre']}/ {formatear_monto(x['Precio'])}/ {x['Posicion']}/ {x['Club']}", axis=1
        ).tolist()
        
        if lista:
            seleccion = st.selectbox("Elegir jugador:", options=lista)
            if st.button("CONFIRMAR FICHAJE", use_container_width=True, type="primary"):
                c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (u_id,))
                if c.fetchone()[0] >= 1:
                    st.error("Ya tienes un jugador contratado.")
                else:
                    j_info = df_f.iloc[lista.index(seleccion)]
                    if presupuesto < j_info['Precio']:
                        st.error("Fondos insuficientes.")
                    else:
                        c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                                  (u_id, j_info['Nombre'], j_info['Precio'], j_info['Posicion'], j_info['Club']))
                        c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_info['Precio'], u_id))
                        conn.commit()
                        st.rerun()
        else:
            st.write("No se encontraron jugadores.")

# --- 5. GESTIÓN DE JUGADOR ---
st.divider()
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (u_id,))
j = c.fetchone()

if j:
    st.subheader(f"📋 Tu representado: {j[1]}")
    with st.container(border=True):
        st.write(f"**Club:** {j[4]} | **Valor:** €{formatear_monto(j[2])}")
        if st.button("VENDER JUGADOR (Recuperas 98%)", type="primary"):
            c.execute("DELETE FROM jugadores WHERE id = ?", (j[0],))
            c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j[2]*0.98, u_id))
            conn.commit()
            st.rerun()
else:
    st.info("No tienes jugadores en cartera actualmente.")
