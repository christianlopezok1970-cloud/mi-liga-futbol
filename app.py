import streamlit as st
import sqlite3
import pandas as pd

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL)')
c.execute('''CREATE TABLE IF NOT EXISTS jugadores 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, 
              valor REAL, valor_anterior REAL, posicion TEXT, club TEXT,
              FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
conn.commit()

# --- 2. FUNCIÓN PARA CARGAR TU EXCEL (GOOGLE SHEETS CSV) ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

@st.cache_data(ttl=300)
def cargar_mercado_oficial(url):
    try:
        df = pd.read_csv(url)
        # Limpieza inicial de espacios en los nombres de las columnas
        df.columns = df.columns.str.strip()

        # SISTEMA ANTI-ERROR DE COLUMNAS: Mapeamos posibles nombres
        mapeo = {
            'Nombre': ['Nombre', 'Jugador', 'Jugadores', 'NOMBRE', 'nombre'],
            'Club': ['Club', 'Equipo', 'Institucion', 'CLUB', 'club', 'Institución'],
            'Posicion': ['Posicion', 'Posición', 'Puesto', 'POSICION', 'posicion', 'Pos'],
            'Precio': ['Precio', 'Valor', 'Costo', 'PRECIO', 'precio', 'Monto']
        }

        for oficial, variantes in mapeo.items():
            for variante in variantes:
                if variante in df.columns:
                    df.rename(columns={variante: oficial}, inplace=True)
                    break
        
        return df
    except Exception as e:
        st.error(f"Error crítico al leer el Excel: {e}")
        return None

df_mercado = cargar_mercado_oficial(SHEET_CSV_URL)

# --- 3. LÓGICA DE NEGOCIO ---
MONTO_MULTA = 200000 

def calcular_nuevo_valor(valor_actual, puntaje):
    # Eje en 6.4: cada 0.1 de diferencia varía 1% el valor
    diff_pasos = (puntaje - 6.4) / 0.1
    variacion = diff_pasos * (valor_actual / 100)
    return int(max(0, valor_actual + variacion))

# --- 4. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Liga Argentina Manager", layout="wide")
st.title("⚽ Liga Argentina Manager")

user_name = st.sidebar.text_input("Usuario").strip()

if not user_name:
    st.info("👋 Ingresa tu nombre en la barra lateral para gestionar tu equipo.")
    st.stop()

# Inicialización de usuario
PRESUPUESTO_INICIAL = 11000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()

c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto = c.fetchone()

# Sidebar: Estado y Borrado Seguro
st.sidebar.success(f"Club: {user_name}")
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

st.sidebar.divider()
with st.sidebar.expander("⚠️ Borrar Equipo"):
    st.write("Se eliminarán tus jugadores y volverás a €11M.")
    confirmar = st.checkbox("Confirmar eliminación total")
    if st.button("🚨 Ejecutar Borrado", disabled=not confirmar):
        c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
        conn.commit()
        st.rerun()

# --- 5. MERCADO DE PASES (Lógica ARQ, DEF, VOL, DEL) ---
st.subheader("🛒 Mercado de Pases")

if df_mercado is not None:
    try:
        # Cupos basados en tus siglas
        LIMITES = {"ARQ": 1, "DEF": 4, "VOL": 4, "DEL": 2}

        # Verificamos si las columnas necesarias existen tras el mapeo
        columnas_ok = all(col in df_mercado.columns for col in ['Nombre', 'Club', 'Posicion', 'Precio'])
        
        if not columnas_ok:
            st.error("No se encuentran las columnas 'Nombre', 'Club', 'Posicion' o 'Precio' en tu Excel.")
            st.write("Columnas detectadas:", df_mercado.columns.tolist())
        else:
            # Crear lista desplegable
            opciones = df_mercado.apply(
                lambda x: f"{x['Nombre']} ({x['Club']}) - {x['Posicion']} - €{int(x['Precio']):,}", axis=1
            ).tolist()
            
            seleccion = st.selectbox("Busca y selecciona un jugador:", options=opciones)
            
            if st.button("Confirmar Fichaje"):
                idx = opciones.index(seleccion)
                j_info = df_mercado.iloc[idx]
                
                c.execute("SELECT posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
                actuales = [row[0] for row in c.fetchall()]
                
                precio_fch = int(j_info['Precio'])
                pos_sigla = str(j_info['Posicion']).strip()

                if presupuesto < precio_fch:
                    st.error("Presupuesto insuficiente.")
                elif len(actuales) >= 11:
                    st.error("Tu plantilla ya está completa (11/11).")
                elif actuales.count(pos_sigla) >= LIMITES.get(pos_sigla, 0):
                    st.error(f"Cupo lleno para {pos_sigla}. Máximo: {LIMITES.get(pos_sigla)}")
                else:
                    c.execute("""INSERT INTO jugadores (usuario_id, nombre, valor, valor_anterior, posicion, club) 
                                 VALUES (?, ?, ?, ?, ?, ?)""", 
                              (user_id, j_info['Nombre'], precio_fch, precio_fch, pos_sigla, j_info['Club']))
                    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - precio_fch, user_id))
                    conn.commit()
                    st.success(f"¡{j_info['Nombre']} fichado!")
                    st.rerun()
    except Exception as e:
        st.error(f"Error al procesar el Excel: {e}")

# --- 6. GESTIÓN DEL EQUIPO ---
st.header("📋 Tu Equipo")

# Orden: ARQ -> DEF -> VOL -> DEL
query = """
    SELECT id, nombre, valor, valor_anterior, posicion, club FROM jugadores 
    WHERE usuario_id = ? 
    ORDER BY CASE posicion
        WHEN 'ARQ' THEN 1
        WHEN 'DEF' THEN 2
        WHEN 'VOL' THEN 3
        WHEN 'DEL' THEN 4
    END
"""
c.execute(query, (user_id,))
jugadores = c.fetchall()

if len(jugadores) < 11:
    faltan = 11 - len(jugadores)
    st.warning(f"⚠️ Equipo incompleto ({len(jugadores)}/11). Multa de €{int(faltan * MONTO_MULTA):,} por cada 'Aplicar'.")

if not jugadores:
    st.info("No tienes jugadores. Ficha desde el Mercado de Pases.")
else:
    for j_id, j_nom, j_val, j_ant, j_pos, j_club in jugadores:
        with st.container():
            col_info, col_pts, col_btns = st.columns([2, 1, 1])
            
            with col_info:
                emoji = "🧤" if j_pos == "ARQ" else "🛡️" if j_pos == "DEF" else "⚙️" if j_pos == "VOL" else "⚽"
                st.markdown(f"### {emoji} {j_nom}")
                st.write(f"🏠 {j_club} | **{j_pos}**")
                st.write(f"**Valor: €{int(j_val):,}** (Prev: €{int(j_ant or j_val):,})")
            
            with col_pts:
                pts = st.number_input("Puntos", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            
            with col_btns:
                if st.button("✅ Aplicar", key=f"a_{j_id}", use_container_width=True):
                    v_nuevo = calcular_nuevo_valor(j_val, pts)
                    multa = (11 - len(jugadores)) * MONTO_MULTA if len(jugadores) < 11 else 0
                    
                    c.execute("UPDATE jugadores SET valor_anterior = ?, valor = ? WHERE id = ?", (j_val, v_nuevo, j_id))
                    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - multa, user_id))
                    conn.commit()
                    
                    if multa > 0:
                        st.toast(f"🛑 Multa de €{multa:,} aplicada.", icon="💸")
                    st.rerun()
                
                if st.button("🗑️ Vender", key=f"v_{j_id}", use_container_width=True):
                    c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + j_val, user_id))
                    conn.commit()
                    st.rerun()
            st.divider()
