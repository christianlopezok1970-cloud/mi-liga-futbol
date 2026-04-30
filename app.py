import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
# Cambiamos el nombre a v2 para evitar el OperationalError de archivos bloqueados
conn = sqlite3.connect('liga_manager_v2.db', check_same_thread=False)
c = conn.cursor()

# Ejecutamos las creaciones de tablas por separado para asegurar estabilidad
c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, 
              nombre TEXT UNIQUE, 
              presupuesto REAL, 
              prestigio INTEGER DEFAULT 40)''')

c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, 
              usuario_id INTEGER, 
              nombre TEXT, 
              valor REAL, 
              posicion TEXT, 
              club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. CARGA DE DATOS ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

@st.cache_data(ttl=300)
def cargar_mercado_oficial(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        mapeo = {
            'Nombre': ['Nombre', 'Jugador'], 
            'Club': ['Club', 'Equipo'], 
            'Posicion': ['POS', 'Posicion'], 
            'Precio': ['Cotización', 'Cotizacion', 'Precio']
        }
        for oficial, variantes in mapeo.items():
            for variante in variantes:
                if variante in df.columns:
                    df.rename(columns={variante: oficial}, inplace=True)
                    break
        if 'Precio' in df.columns:
            df['Precio'] = df['Precio'].astype(str).apply(lambda x: re.sub(r'\D', '', x))
            df['Precio'] = pd.to_numeric(df['Precio'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Error al cargar Excel: {e}")
        return None

df_mercado = cargar_mercado_oficial(SHEET_CSV_URL)

# --- 3. LÓGICA DE NEGOCIO ---
VALOR_POR_PASO = 20000 
PORCENTAJE_SUELDO = 0.0125 

def calcular_resultado_neto(puntaje, valor_jugador):
    pasos = (puntaje - 6.4) / 0.1
    ganancia_puntos = int(pasos * VALOR_POR_PASO)
    costo_sueldo = valor_jugador * PORCENTAJE_SUELDO
    return int(ganancia_puntos - costo_sueldo)

def calcular_ajuste_prestigio(pts):
    if pts <= 4.9: return -6
    elif 5.0 <= pts <= 5.5: return -4
    elif 5.6 <= pts <= 5.9: return -2
    elif 6.0 <= pts <= 6.3: return -1
    elif 6.4 <= pts <= 6.6: return 0
    elif 6.7 <= pts <= 6.9: return 1
    elif 7.0 <= pts <= 7.4: return 2
    elif 7.5 <= pts <= 7.9: return 3
    elif 8.0 <= pts <= 10.0: return 5
    return 0

# --- 4. GESTIÓN DE SESIÓN ---
if 'version' not in st.session_state:
    st.session_state.version = 0

def forzar_limpieza():
    st.session_state.version += 1

# --- 5. INTERFAZ ---
st.set_page_config(page_title="Liga Argentina Manager", layout="wide")
st.markdown("## ⚽ Liga Argentina Manager")

user_name = st.sidebar.text_input("Usuario").strip()

if not user_name:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.sidebar.divider()
    st.sidebar.subheader("🏆 Top Managers")
    c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 5")
    for i, (n, p) in enumerate(c.fetchall(), 1):
        st.sidebar.write(f"{i}. {n} ({p} pts)")
    st.stop()

# Inicialización de datos
PRESUPUESTO_INICIAL = 2000000
PRESTIGIO_INICIAL = 40

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, ?, ?)", 
          (user_name, PRESUPUESTO_INICIAL, PRESTIGIO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto, prestigio = c.fetchone()

# Estilo de la tarjeta de Prestigio
color_numero = "#FF4B4B"
if prestigio >= 90: color_numero = "#40E0D0"
elif prestigio >= 80: color_numero = "#00FF00"
elif prestigio >= 60: color_numero = "#FFFF00"
elif prestigio >= 40: color_numero = "#FFA500"

st.sidebar.markdown(f"""
    <div style="background-color: #000000; padding: 25px 10px; border-radius: 15px; text-align: center; border: 1px solid #333;">
        <p style="color: #666666; margin: 0; font-weight: bold; font-size: 12px; letter-spacing: 3px; text-transform: uppercase;">Prestigio</p>
        <h1 style="color: {color_numero}; margin: 0; font-size: 80px; font-weight: 900; line-height: 1;">{prestigio}</h1>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

# --- PRÉSTAMO ---
with st.sidebar.expander("💰 Solicitar Préstamo"):
    conf_prestamo = st.checkbox("Confirmar condiciones (-5 prestigio)", key=f"pres_{st.session_state.version}")
    if st.button("PEDIR €1.000.000", disabled=not conf_prestamo, use_container_width=True):
        c.execute("UPDATE usuarios SET presupuesto = presupuesto + 1000000, prestigio = MAX(1, prestigio - 5) WHERE id = ?", (user_id,))
        conn.commit()
        forzar_limpieza()
        st.rerun()

# --- 6. MERCADO ---
with st.expander("🛒 Mercado de Pases"):
    if df_mercado is not None:
        opciones = df_mercado.apply(lambda x: f"{x['Nombre']} ({x['Club']}) - €{int(x['Precio']):,}", axis=1).tolist()
        seleccion = st.selectbox("Buscar jugador:", options=opciones)
        
        if st.button("Confirmar Fichaje", use_container_width=True, type="primary"):
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
            if c.fetchone()[0] >= 1:
                st.error("⚠️ Ya tienes un jugador contratado.")
            else:
                j_info = df_mercado.iloc[opciones.index(seleccion)]
                if presupuesto < int(j_info['Precio']):
                    st.error("❌ Presupuesto insuficiente.")
                else:
                    c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                              (user_id, j_info['Nombre'], int(j_info['Precio']), j_info['Posicion'], j_info['Club']))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (int(j_info['Precio']), user_id))
                    conn.commit()
                    st.rerun()

# --- 7. GESTIÓN DEL JUGADOR ---
st.divider()
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (user_id,))
jugador = c.fetchone()

if not jugador:
    st.info("💡 No tienes ningún jugador asignado. Ve al Mercado de Pases.")
else:
    j_id, j_nom, j_val, j_pos, j_club = jugador
    st.markdown(f"### 📋 Gestionando a: {j_nom}")
    with st.container(border=True):
        st.write(f"**Club:** {j_club} | **Posición:** {j_pos}")
        st.write(f"**Valor de mercado:** €{int(j_val):,}")
        
        pts = st.number_input("Puntaje de la fecha:", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
        neto = calcular_resultado_neto(pts, j_val)
        ajuste_p = calcular_ajuste_prestigio(pts)
        
        col_res1, col_res2 = st.columns(2)
        col_res1.markdown(f"**Balance:** :{'green' if neto >= 0 else 'red'}[€{neto:,}]")
        col_res2.markdown(f"**Prestigio:** :{'green' if ajuste_p >= 0 else 'red'}[{ajuste_p} pts]")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox(f"Vender por €{int(j_val*0.98):,}"):
                if st.button("🗑️ Confirmar Venta", use_container_width=True):
                    c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_val*0.98, user_id))
                    conn.commit()
                    st.rerun()
        with c2:
            if st.button("✅ PROCESAR FECHA", type="primary", use_container_width=True):
                nuevo_p = max(1, min(100, prestigio + ajuste_p))
                c.execute("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", (neto, nuevo_p, user_id))
                conn.commit()
                st.rerun()

# --- RANKING LATERAL ---
st.sidebar.divider()
st.sidebar.subheader("🏆 Ranking Global")
c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 5")
for i, (nom, pres) in enumerate(c.fetchall(), 1):
    st.sidebar.write(f"{i}. {nom} ({pres} pts)")
