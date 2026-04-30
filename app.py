import streamlit as st
import sqlite3
import pandas as pd
import re

# --- CONFIGURACIÓN DE CONTROL ---
MERCADO_ABIERTO = True 

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, posicion TEXT, club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. FUNCIÓN PARA CARGAR EL EXCEL ---
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

def calcular_ganancia(puntaje):
    # Calcula cuánto dinero se suma/resta al presupuesto
    pasos = (puntaje - 6.4) / 0.1
    return int(pasos * VALOR_POR_PASO)

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Liga Argentina Manager", layout="wide")
st.title("⚽ Liga Argentina Manager")

user_name = st.sidebar.text_input("Usuario").strip()
if not user_name:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

PRESUPUESTO_INICIAL = 2000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto = c.fetchone()

st.sidebar.success(f"Usuario: {user_name}")
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

# --- BOTÓN PAGAR SUELDOS ---
st.sidebar.divider()
if st.sidebar.button("💸 Pagar Sueldos (0.1%)"):
    c.execute("SELECT valor FROM jugadores WHERE usuario_id = ?", (user_id,))
    valores = c.fetchall()
    if valores:
        total_sueldos = sum(v[0] for v in valores) * 0.001
        nuevo_presupuesto = presupuesto - total_sueldos
        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_presupuesto, user_id))
        conn.commit()
        st.sidebar.warning(f"Sueldos pagados: -€{int(total_sueldos):,}")
        st.rerun()

# --- 5. MERCADO DE PASES (LIMITE 1 JUGADOR) ---
with st.expander("🛒 Mercado de Pases (Cupo: 1 jugador)"):
    if not MERCADO_ABIERTO:
        st.warning("Mercado cerrado.")
    elif df_mercado is not None:
        opciones = df_mercado.apply(lambda x: f"{x['Nombre']} ({x['Club']}) - {x['Posicion']} - €{int(x['Precio']):,}", axis=1).tolist()
        seleccion = st.selectbox("Buscar jugador:", options=opciones)
        
        if st.button("Confirmar Fichaje"):
            idx = opciones.index(seleccion)
            j_info = df_mercado.iloc[idx]
            
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
            if c.fetchone()[0] >= 1:
                st.error("Ya tienes 1 jugador. Véndelo para comprar otro.")
            elif presupuesto < int(j_info['Precio']):
                st.error("Dinero insuficiente.")
            else:
                c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                          (user_id, j_info['Nombre'], int(j_info['Precio']), j_info['Posicion'], j_info['Club']))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - int(j_info['Precio']), user_id))
                conn.commit()
                st.success("Fichaje exitoso!")
                st.rerun()

# --- 6. GESTIÓN DE PLANTEL ---
st.divider()
st.header("📋 Tu Jugador")

c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (user_id,))
plantel = c.fetchall()

if not plantel:
    st.info("No tienes ningún jugador.")
else:
    for j_id, j_nom, j_val, j_pos, j_club in plantel:
        with st.expander(f"{j_pos} | {j_nom} ({j_club})", expanded=True):
            st.write(f"**Valor del Jugador (Fijo): €{int(j_val):,}**")
            st.write(f"Sueldo (0.1%): €{int(j_val * 0.001):,}")
            
            pts = st.number_input("Puntos obtenidos", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            ganancia_neta = calcular_ganancia(pts)
            
            if ganancia_neta >= 0:
                st.write(f"💰 Ganancia estimada: **+€{ganancia_neta:,}**")
            else:
                st.write(f"📉 Pérdida estimada: **-€{abs(ganancia_neta):,}**")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Cargar Puntos", key=f"a_{j_id}"):
                nuevo_presupuesto = presupuesto + ganancia_neta
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_presupuesto, user_id))
                conn.commit()
                st.toast(f"Presupuesto actualizado: {ganancia_neta}")
                st.rerun()
                
            if MERCADO_ABIERTO:
                if c2.button("🗑️ Vender", key=f"v_{j_id}"):
                    # Al vender, recuperas exactamente lo que valía el jugador
                    c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_val, user_id))
                    conn.commit()
                    st.rerun()

# --- SIDEBAR: RESET ---
st.sidebar.divider()
with st.sidebar.expander("🚨 Reiniciar Perfil"):
    confirmar = st.checkbox("Confirmar borrado")
    if st.button("BORRAR TODO", disabled=not confirmar, type="primary"):
        c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
        conn.commit()
        st.rerun()
