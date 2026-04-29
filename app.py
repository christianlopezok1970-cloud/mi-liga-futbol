import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)')

# Agregamos la columna 'titular' si no existe
try:
    c.execute("ALTER TABLE jugadores ADD COLUMN titular INTEGER DEFAULT 0")
except:
    pass

c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, valor_anterior REAL, posicion TEXT, club TEXT, titular INTEGER DEFAULT 0,
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
MONTO_MULTA = 200000 

def calcular_nuevo_valor(valor_actual, puntaje):
    diff = (puntaje - 6.4) / 0.1
    var = diff * (valor_actual / 100)
    return int(max(0, valor_actual + var))

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Liga Argentina Manager", layout="wide")
st.title("⚽ Liga Argentina Manager")

user_name = st.sidebar.text_input("Usuario").strip()
if not user_name:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

PRESUPUESTO_INICIAL = 11000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto = c.fetchone()

# Sidebar Info
st.sidebar.success(f"Usuario: {user_name}")
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

# --- 5. MERCADO DE PASES (Cupo 25) ---
with st.expander("🛒 Mercado de Pases (Cupo: 25 jugadores)"):
    if df_mercado is not None:
        opciones = df_mercado.apply(lambda x: f"{x['Nombre']} ({x['Club']}) - {x['Posicion']} - €{int(x['Precio']):,}", axis=1).tolist()
        seleccion = st.selectbox("Buscar jugador:", options=opciones)
        
        if st.button("Fichar"):
            idx = opciones.index(seleccion)
            j_info = df_mercado.iloc[idx]
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
            total_actual = c.fetchone()[0]
            
            if presupuesto < int(j_info['Precio']):
                st.error("Dinero insuficiente.")
            elif total_actual >= 25:
                st.error("Plantilla completa (máx 25).")
            else:
                c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, valor_anterior, posicion, club, titular) VALUES (?,?,?,?,?,?,0)",
                          (user_id, j_info['Nombre'], int(j_info['Precio']), int(j_info['Precio']), j_info['Posicion'], j_info['Club']))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - int(j_info['Precio']), user_id))
                conn.commit()
                st.rerun()

# --- 6. GESTIÓN DE EQUIPO ---
st.divider()

# Consultar jugadores
def obtener_plantilla(uid, es_titular):
    query = f"SELECT id, nombre, valor, posicion, club, titular FROM jugadores WHERE usuario_id = ? AND titular = {es_titular} ORDER BY posicion ASC"
    c.execute(query, (uid,))
    return c.fetchall()

titulares = obtener_plantilla(user_id, 1)
suplentes = obtener_plantilla(user_id, 0)

col_t, col_s = st.columns(2)

# --- COLUMNA TITULARES ---
with col_t:
    st.header(f"👕 Titulares ({len(titulares)}/11)")
    if len(titulares) < 11:
        st.warning(f"Faltan {11 - len(titulares)} titulares. Se aplicará multa al puntuar.")
    
    for j_id, j_nom, j_val, j_pos, j_club, _ in titulares:
        with st.expander(f"{j_pos} | {j_nom} ({j_club})"):
            pts = st.number_input("Puntos", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Aplicar", key=f"a_{j_id}"):
                v_n = calcular_nuevo_valor(j_val, pts)
                multa = (11 - len(titulares)) * MONTO_MULTA if len(titulares) < 11 else 0
                c.execute("UPDATE jugadores SET valor_anterior = valor, valor = ? WHERE id = ?", (v_n, j_id))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - multa, user_id))
                conn.commit()
                st.rerun()
            if c2.button("🪑 Al Banco", key=f"b_{j_id}"):
                c.execute("UPDATE jugadores SET titular = 0 WHERE id = ?", (j_id,))
                conn.commit()
                st.rerun()

# --- COLUMNA SUPLENTES ---
with col_s:
    st.header(f"👟 Suplentes ({len(suplentes)})")
    for j_id, j_nom, j_val, j_pos, j_club, _ in suplentes:
        with st.expander(f"{j_pos} | {j_nom} ({j_club})"):
            st.write(f"Valor: €{int(j_val):,}")
            c1, c2 = st.columns(2)
            if c1.button("🔝 A Titular", key=f"t_{j_id}"):
                if len(titulares) >= 11:
                    st.error("Ya hay 11 titulares.")
                else:
                    c.execute("UPDATE jugadores SET titular = 1 WHERE id = ?", (j_id,))
                    conn.commit()
                    st.rerun()
            if c2.button("🗑️ Vender", key=f"v_{j_id}"):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_val, user_id))
                conn.commit()
                st.rerun()

# --- SIDEBAR: RESET ---
st.sidebar.divider()
if st.sidebar.button("🚨 Borrar Equipo"):
    c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
    conn.commit()
    st.rerun()
