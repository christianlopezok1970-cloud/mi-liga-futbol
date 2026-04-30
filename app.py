import streamlit as st
import sqlite3
import pandas as pd
import re

# --- CONFIGURACIÓN DE BASE DE DATOS ---
# Usamos un nombre nuevo para evitar conflictos con archivos viejos
DB_NAME = 'db_limpia_v1.db'

def conectar():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def crear_tablas():
    conn = conectar()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
                  valor REAL, posicion TEXT, club TEXT)''')
    conn.commit()
    conn.close()

crear_tablas()

# --- CARGA DE DATOS DEL EXCEL ---
@st.cache_data(ttl=600)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        # Normalizamos nombres de columnas
        cols = {'Nombre': ['Nombre', 'Jugador'], 'Precio': ['Cotización', 'Cotizacion', 'Precio'], 'Club': ['Club', 'Equipo']}
        for oficial, variantes in cols.items():
            for v in variantes:
                if v in df.columns:
                    df.rename(columns={v: oficial}, inplace=True)
                    break
        
        # Limpieza CRÍTICA para evitar el ValueError:
        if 'Precio' in df.columns:
            df['Precio'] = df['Precio'].astype(str).apply(lambda x: re.sub(r'\D', '', x))
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return None

df_mercado = cargar_datos()

# --- INTERFAZ ---
st.set_page_config(page_title="Agencia Manager", layout="wide")
st.title("⚽ Manager: Inicio desde Cero")

nombre_usuario = st.sidebar.text_input("Tu Nombre de Agente:").strip()

if not nombre_usuario:
    st.info("Escribe tu nombre en la barra lateral para empezar.")
    st.stop()

# Manejo de Usuario
conn = conectar()
c = conn.cursor()
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 40)", (nombre_usuario,))
conn.commit()

c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (nombre_usuario,))
u_id, presupuesto, prestigio = c.fetchone()

st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

# --- MERCADO ---
st.subheader("🛒 Buscar Jugador")
if df_mercado is not None:
    busqueda = st.text_input("🔍 Escribe el nombre del jugador:")
    df_f = df_mercado[df_mercado['Nombre'].str.contains(busqueda, case=False, na=False)]
    
    # Formato: Nombre | Precio | Club
    opciones = df_f.apply(lambda x: f"{x['Nombre']} | €{int(x.get('Precio', 0)):,} | {x.get('Club', 'Libre')}", axis=1).tolist()
    
    if opciones:
        seleccion = st.selectbox("Selecciona para contratar:", opciones)
        if st.button("FICHAR JUGADOR"):
            # Verificar si ya tiene uno
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (u_id,))
            if c.fetchone()[0] > 0:
                st.error("Ya tienes un jugador contratado.")
            else:
                idx = opciones.index(seleccion)
                j_info = df_f.iloc[idx]
                precio_j = int(j_info.get('Precio', 0))
                
                if presupuesto >= precio_j:
                    c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, club) VALUES (?,?,?,?)",
                              (u_id, j_info['Nombre'], precio_j, j_info.get('Club', 'Libre')))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (precio_j, u_id))
                    conn.commit()
                    st.success("¡Fichado!")
                    st.rerun()
                else:
                    st.error("No tienes dinero suficiente.")

# --- TU CARTERA ---
st.divider()
c.execute("SELECT id, nombre, valor, club FROM jugadores WHERE usuario_id = ?", (u_id,))
jugador = c.fetchone()

if jugador:
    st.subheader(f"📋 Representando a: {jugador[1]}")
    # Aquí es donde fallaba antes, ahora usamos una variable segura
    valor_seguro = int(jugador[2]) if jugador[2] else 0
    st.write(f"**Club:** {jugador[3]} | **Valor:** €{valor_seguro:,}")
    
    if st.button("VENDER JUGADOR"):
        c.execute("DELETE FROM jugadores WHERE id = ?", (jugador[0],))
        c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (valor_seguro * 0.98, u_id))
        conn.commit()
        st.rerun()
else:
    st.write("No tienes jugadores contratados.")

conn.close()
