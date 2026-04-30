import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS (NUEVA) ---
DB_NAME = 'manager_final.db'

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
                  valor REAL, posicion TEXT, club TEXT)''')
    conn.commit()
    return conn

conn = init_db()
c = conn.cursor()

# --- 2. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        # Mapeo de columnas para que coincidan con tu Excel
        mapeo = {
            'Nombre': ['Nombre', 'Jugador'],
            'Precio': ['Cotización', 'Cotizacion', 'Precio'],
            'Club': ['Club', 'Equipo'],
            'Posicion': ['POS', 'Posicion']
        }
        for oficial, variantes in mapeo.items():
            for v in variantes:
                if v in df.columns:
                    df.rename(columns={v: oficial}, inplace=True)
                    break
        # Limpiar precios
        df['Precio'] = df['Precio'].astype(str).apply(lambda x: re.sub(r'\D', '', x))
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return None

df_mercado = cargar_datos()

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Liga Manager Pro", layout="wide")
st.title("⚽ Liga Manager: Edición 2026")

# Login lateral
st.sidebar.header("Acceso Manager")
user_name = st.sidebar.text_input("Tu Nombre").strip()

if not user_name:
    st.info("👋 Por favor, escribe tu nombre en la barra lateral para iniciar tu carrera.")
    st.stop()

# Crear o recuperar usuario
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 40)", (user_name,))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
u_id, presupuesto, prestigio = c.fetchone()

# Mostrar estado en Sidebar
st.sidebar.divider()
st.sidebar.metric("Billetera", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

# --- 4. MERCADO DE PASES ---
st.header("🛒 Mercado de Pases")
with st.container(border=True):
    if df_mercado is not None:
        # Buscador Dinámico
        busqueda = st.text_input("🔍 Buscar por nombre del jugador:")
        
        # Filtro de datos
        df_f = df_mercado[df_mercado['Nombre'].str.contains(busqueda, case=False, na=False)]
        
        # Formato solicitado: Nombre / Precio / Posición / Club
        opciones = df_f.apply(lambda x: f"{x['Nombre']} / €{int(x['Precio']):,} / {x['Posicion']} / {x['Club']}", axis=1).tolist()
        
        if opciones:
            seleccion = st.selectbox("Selecciona un jugador para fichar:", opciones)
            if st.button("FICHAR JUGADOR", type="primary", use_container_width=True):
                # Verificar si ya tiene un jugador
                c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (u_id,))
                if c.fetchone()[0] >= 1:
                    st.error("⚠️ Ya tienes un jugador contratado. Debes venderlo antes de fichar otro.")
                else:
                    # Obtener info del seleccionado
                    j_info = df_f.iloc[opciones.index(seleccion)]
                    if presupuesto < j_info['Precio']:
                        st.error("❌ No tienes fondos suficientes.")
                    else:
                        # Ejecutar Fichaje
                        c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                                  (u_id, j_info['Nombre'], j_info['Precio'], j_info['Posicion'], j_info['Club']))
                        c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_info['Precio'], u_id))
                        conn.commit()
                        st.success(f"✅ ¡{j_info['Nombre']} fichado con éxito!")
                        st.rerun()
        else:
            st.write("No se encontraron jugadores con ese nombre.")

# --- 5. TU JUGADOR ACTUAL ---
st.header("📋 Tu Representado")
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (u_id,))
jugador = c.fetchone()

if jugador:
    j_id, j_nom, j_val, j_pos, j_club = jugador
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(j_nom)
            st.write(f"**Club:** {j_club} | **Posición:** {j_pos}")
            st.write(f"**Valor de Mercado:** €{int(j_val):,}")
        
        with col2:
            st.write("Acciones de Agente:")
            if st.button("🗑️ Vender Jugador (98% retorno)", use_container_width=True):
                # Venta con pequeña comisión
                retorno = j_val * 0.98
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (retorno, u_id))
                conn.commit()
                st.rerun()
else:
    st.info("No tienes jugadores en tu cartera. Ve al Mercado de Pases para fichar uno.")

# --- 6. RANKING ---
st.sidebar.divider()
if st.sidebar.button("🏆 Ver Ranking Global"):
    c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 10")
    for r, (n, p) in enumerate(c.fetchall(), 1):
        st.sidebar.write(f"{r}. {n} - {p} pts")
    
