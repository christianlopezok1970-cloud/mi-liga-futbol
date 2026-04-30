import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. BASE DE DATOS ESTABLE ---
DB_NAME = 'agencia_v3_estable.db'

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

# Creación de tablas
ejecutar_db('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)', commit=True)
ejecutar_db('CREATE TABLE IF NOT EXISTS jugadores (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, valor REAL, posicion TEXT, club TEXT)', commit=True)

# --- 2. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def cargar_datos():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        cols = {'Nombre': ['Nombre', 'Jugador'], 'Precio': ['Cotización', 'Cotizacion', 'Precio'], 'Club': ['Club', 'Equipo'], 'Posicion': ['POS', 'Posicion']}
        for oficial, variantes in cols.items():
            for v in variantes:
                if v in df.columns:
                    df.rename(columns={v: oficial}, inplace=True)
                    break
        df['Precio'] = df['Precio'].astype(str).apply(lambda x: re.sub(r'\D', '', x))
        df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0).astype(int)
        return df
    except: return None

df_mercado = cargar_datos()

# --- 3. LÓGICA DE CÁLCULO (PUNTOS Y DINERO) ---
def calcular_resultados(puntaje, valor_jugador):
    # Ganancia por rendimiento (base 6.4)
    pasos = (puntaje - 6.4) / 0.1
    ganancia = int(pasos * 20000)
    # Sueldo del jugador (1.25% de su valor)
    sueldo = valor_jugador * 0.0125
    resultado_neto = int(ganancia - sueldo)
    
    # Ajuste de prestigio
    if puntaje <= 4.9: adj_p = -6
    elif puntaje <= 5.9: adj_p = -2
    elif puntaje <= 6.6: adj_p = 0
    elif puntaje <= 7.4: adj_p = 2
    else: adj_p = 5
    
    return resultado_neto, adj_p

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Agencia Manager", layout="wide")
user_name = st.sidebar.text_input("Tu Nombre de Manager").strip()

if not user_name:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

# Registro/Login
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 40)", (user_name,), commit=True)
u_id, presupuesto, prestigio = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))[0]

# Dashboard Lateral
st.sidebar.metric("Billetera", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")

# --- 5. MERCADO ---
with st.expander("🛒 MERCADO DE PASES"):
    busqueda = st.text_input("🔍 Buscar por nombre:")
    df_f = df_mercado[df_mercado['Nombre'].str.contains(busqueda, case=False, na=False)]
    
    opciones = df_f.apply(lambda x: f"{x['Nombre']} / €{int(x['Precio']):,} / {x['Posicion']} / {x['Club']}", axis=1).tolist()
    
    if opciones:
        seleccion = st.selectbox("Elegir jugador:", opciones)
        if st.button("FICHAR", use_container_width=True, type="primary"):
            tiene = ejecutar_db("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (u_id,))[0][0]
            if tiene >= 1:
                st.error("Ya tienes un jugador.")
            else:
                j_info = df_f.iloc[opciones.index(seleccion)]
                if presupuesto >= j_info['Precio']:
                    ejecutar_db("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)", 
                                (u_id, j_info['Nombre'], j_info['Precio'], j_info['Posicion'], j_info['Club']), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_info['Precio'], u_id), commit=True)
                    st.rerun()
                else:
                    st.error("Fondos insuficientes.")

# --- 6. GESTIÓN DEL JUGADOR ---
st.divider()
plantilla = ejecutar_db("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (u_id,))

if plantilla:
    j_id, j_nom, j_val, j_pos, j_club = plantilla[0]
    st.subheader(f"📋 Gestionando a: {j_nom}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Club:** {j_club} | **Posición:** {j_pos}")
        st.write(f"**Valor de Mercado:** €{int(j_val):,}")
        puntaje = st.number_input("Puntaje de la fecha:", 1.0, 10.0, 6.4, step=0.1)
        neto, adj_p = calcular_resultados(puntaje, j_val)
        
        st.write(f"Balance Fecha: :{'green' if neto >= 0 else 'red'}[€{neto:,}]")
        st.write(f"Ajuste Prestigio: :{'green' if adj_p >= 0 else 'red'}[{adj_p} pts]")

    with col2:
        if st.button("✅ PROCESAR FECHA", type="primary", use_container_width=True):
            nuevo_prestigio = max(1, min(100, prestigio + adj_p))
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", (neto, nuevo_prestigio, u_id), commit=True)
            st.success("¡Fecha procesada!")
            st.rerun()
            
        if st.button("🗑️ VENDER JUGADOR (98% retorno)", use_container_width=True):
            ejecutar_db("DELETE FROM jugadores WHERE id = ?", (j_id,), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_val * 0.98, u_id), commit=True)
            st.rerun()
