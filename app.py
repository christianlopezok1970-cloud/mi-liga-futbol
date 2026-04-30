import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER DEFAULT 40)''')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, posicion TEXT, club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. CARGA DE DATOS ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

@st.cache_data(ttl=300)
def cargar_mercado_oficial(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        mapeo = {'Nombre': ['Nombre', 'Jugador'], 'Club': ['Club', 'Equipo'], 'Posicion': ['POS', 'Posicion'], 'Precio': ['Cotización', 'Cotizacion', 'Precio']}
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

# --- 3. FUNCIONES AUXILIARES ---
def formatear_monto(valor):
    if valor >= 1000000: return f"{valor / 1000000:.1f} M"
    elif valor >= 1000: return f"{int(valor / 1000)} K"
    return str(int(valor))

def calcular_resultado_neto(puntaje, valor_jugador):
    pasos = (puntaje - 6.4) / 0.1
    ganancia_puntos = int(pasos * 20000) 
    costo_sueldo = valor_jugador * 0.0125 
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

if 'version' not in st.session_state:
    st.session_state.version = 0

def forzar_limpieza():
    st.session_state.version += 1

# --- 4. INTERFAZ Y LOGIN ---
st.set_page_config(page_title="Representante de Fútbol", layout="wide")
st.markdown("## ⚽ Agencia de Jugadores")

user_name = st.sidebar.text_input("Tu Nombre").strip()
if not user_name:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

# Datos del Usuario
PRESUPUESTO_INICIAL = 2000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, ?, 40)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto, prestigio = c.fetchone()

# Estilo de Prestigio
color_p = "#FF4B4B"
if prestigio >= 90: color_p = "#40E0D0"
elif prestigio >= 60: color_p = "#00FF00"
elif prestigio >= 40: color_p = "#FFA500"

st.sidebar.markdown(f"""
    <div style="background-color: #000; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #333;">
        <p style="color: #666; margin: 0; font-size: 12px; letter-spacing: 2px;">PRESTIGIO</p>
        <h1 style="color: {color_p}; margin: 0; font-size: 60px;">{prestigio}</h1>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

# --- 5. MERCADO DE PASES ---
with st.expander("🛒 Mercado de Pases"):
    if df_mercado is not None:
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            bus_nom = st.text_input("🔍 Buscar:", key=f"bn_{st.session_state.version}")
        with col_f2:
            p_min = st.number_input("Min €:", 0, value=0, step=100000)
        with col_f3:
            p_max = st.number_input("Max €:", 0, value=int(df_mercado['Precio'].max()), step=100000)

        df_f = df_mercado[(df_mercado['Nombre'].str.contains(bus_nom, case=False, na=False)) & (df_mercado['Precio'].between(p_min, p_max))]
        
        if not df_f.empty:
            # Orden solicitado: Nombre / Monto / Posición / Equipo
            opciones = df_f.apply(lambda x: f"{x['Nombre']}/ {formatear_monto(x['Precio'])}/ {x['Posicion']}/ {x['Club']}", axis=1).tolist()
            sel = st.selectbox("Seleccionar jugador:", opciones)
            j_data = df_f.iloc[opciones.index(sel)]
            
            st.markdown(f"""<div style="background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-top: 10px;">
                <h4 style="margin: 0; color: #FFF;">{j_data['Nombre']}</h4>
                <p style="margin: 5px 0; color: #FFF; opacity: 0.7;">{j_data['Club']} | {j_data['Posicion']}</p>
                <h3 style="margin: 0; color: #FFF;">Precio: €{formatear_monto(j_data['Precio'])}</h3>
            </div>""", unsafe_allow_html=True)

            if st.button("CONFIRMAR FICHAJE", use_container_width=True, type="primary"):
                c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
                if c.fetchone()[0] >= 1:
                    st.error("Ya tienes un jugador en tu cartera.")
                elif presupuesto < j_data['Precio']:
                    st.error("Presupuesto insuficiente.")
                else:
                    c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                              (user_id, j_data['Nombre'], j_data['Precio'], j_data['Posicion'], j_data['Club']))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_data['Precio'], user_id))
                    conn.commit()
                    forzar_limpieza()
                    st.rerun()

# --- 6. GESTIÓN DEL JUGADOR ---
st.divider()
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (user_id,))
jugador = c.fetchone()

if not jugador:
    st.info("No tienes jugadores asignados.")
else:
    j_id, j_nom, j_val, j_pos, j_club = jugador
    st.subheader(f"📋 Cliente: {j_nom}")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Club:** {j_club}")
            st.write(f"**Posición:** {j_pos}")
            st.write(f"**Valor de Mercado:** €{formatear_monto(j_val)}")
        
        with col2:
            pts = st.number_input("Puntaje de la fecha:", 1.0, 10.0, 6.4, step=0.1)
            neto = calcular_resultado_neto(pts, j_val)
            ajuste_p = calcular_ajuste_prestigio(pts)
            st.markdown(f"**Resultado Económico:** :{'green' if neto>=0 else 'red'}[€{neto:,}]")
            st.markdown(f"**Impacto Prestigio:** :{'green' if ajuste_p>=0 else 'red'}[{ajuste_p} pts]")

        st.divider()
        b1, b2 = st.columns(2)
        with b1:
            if st.checkbox("Vender jugador (Comisión 2%)"):
                if st.button("VENDER AHORA", type="primary", use_container_width=True):
                    c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_val * 0.98, user_id))
                    conn.commit()
                    st.rerun()
        with b2:
            if st.button("✅ PROCESAR FECHA", type="primary", use_container_width=True):
                nuevo_prestigio = max(1, min(100, prestigio + ajuste_p))
                c.execute("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", (neto, nuevo_prestigio, user_id))
                conn.commit()
                st.rerun()

# --- 7. ADMIN ---
st.sidebar.divider()
with st.sidebar.expander("⚙️ Administración"):
    c.execute("SELECT nombre FROM usuarios")
    lista_u = [r[0] for r in c.fetchall()]
    u_del = st.selectbox("Eliminar Usuario:", lista_u)
    if st.button("BORRAR DEFINITIVAMENTE", type="primary", use_container_width=True):
        c.execute("DELETE FROM jugadores WHERE usuario_id = (SELECT id FROM usuarios WHERE nombre = ?)", (u_del,))
        c.execute("DELETE FROM usuarios WHERE nombre = ?", (u_del,))
        conn.commit()
        st.rerun()
