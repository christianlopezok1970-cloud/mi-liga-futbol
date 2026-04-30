import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
conn = sqlite3.connect('liga_futbol.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER DEFAULT 40)')
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

# --- 4. GESTIÓN DE RESET DE COMPONENTES ---
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
    # --- MOSTRAR RANKING INCLUSO SIN LOGIN ---
    st.sidebar.divider()
    st.sidebar.subheader("🏆 Top Managers")
    c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 5")
    for i, (n, p) in enumerate(c.fetchall(), 1):
        st.sidebar.write(f"{i}. {n} ({p} pts)")
    st.stop()

PRESUPUESTO_INICIAL = 2000000
PRESTIGIO_INICIAL = 40

c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, ?, ?)", (user_name, PRESUPUESTO_INICIAL, PRESTIGIO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto, prestigio = c.fetchone()

# Estilo Prestigio
color_numero = "#FF0000"
if prestigio >= 90: color_numero = "#40E0D0"
elif prestigio >= 80: color_numero = "#00FF00"
elif prestigio >= 60: color_numero = "#FFFF00"
elif prestigio >= 40: color_numero = "#FFA500"

st.sidebar.markdown(f"""
    <div style="background-color: #000000; padding: 25px 10px; border-radius: 15px; text-align: center; border: 1px solid #333;">
        <p style="color: #666666; margin: 0; font-weight: bold; font-size: 12px; letter-spacing: 3px; text-transform: uppercase;">Prestigio</p>
        <h1 style="color: {color_numero}; margin: 0; font-size: 80px; font-weight: 900; font-family: 'Arial Black', sans-serif; line-height: 1;">{prestigio}</h1>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")

# --- PRÉSTAMO ---
with st.sidebar.expander("💰 Solicitar Préstamo"):
    conf_prestamo = st.checkbox("Confirmar condiciones", key=f"pres_{st.session_state.version}")
    if st.button("PEDIR PRÉSTAMO", disabled=not conf_prestamo, use_container_width=True):
        c.execute("UPDATE usuarios SET presupuesto = presupuesto + 1000000, prestigio = MAX(1, prestigio - 5) WHERE id = ?", (user_id,))
        conn.commit()
        forzar_limpieza()
        st.rerun()

# --- RANKING ---
st.sidebar.divider()
st.sidebar.subheader("🏆 Ranking")
c.execute("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC, presupuesto DESC LIMIT 5")
for i, (nom, pres, plata) in enumerate(c.fetchall(), 1):
    medalla = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
    st.sidebar.markdown(f"{medalla} **{nom}** ({pres} pts)")

# --- BORRAR USUARIO (ADMIN) ---
st.sidebar.divider()
with st.sidebar.expander("⚙️ Administrar Usuarios"):
    c.execute("SELECT nombre FROM usuarios")
    todos_usuarios = [row[0] for row in c.fetchall()]
    usuario_a_borrar = st.selectbox("Seleccionar usuario para eliminar:", todos_usuarios)
    
    conf_borrar = st.checkbox(f"Confirmar eliminar a {usuario_a_borrar}", key=f"del_{st.session_state.version}")
    
    if st.button("ELIMINAR USUARIO DEFINITIVAMENTE", disabled=not conf_borrar, type="primary", use_container_width=True):
        # Primero borramos sus jugadores por la integridad de la base de datos
        c.execute("DELETE FROM jugadores WHERE usuario_id = (SELECT id FROM usuarios WHERE nombre = ?)", (usuario_a_borrar,))
        # Luego borramos al usuario
        c.execute("DELETE FROM usuarios WHERE nombre = ?", (usuario_a_borrar,))
        conn.commit()
        st.success(f"Usuario {usuario_a_borrar} eliminado.")
        forzar_limpieza()
        st.rerun()

# --- 6. MERCADO DE PASES CON FILTROS ---
with st.expander("🛒 Mercado de Pases (Cupo: 1 jugador)"):
    if df_mercado is not None:
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            busqueda_nombre = st.text_input("🔍 Buscar por nombre:", placeholder="Ej: Messi")
        
        with col_f2:
            # Filtro por precio máximo basado en el presupuesto actual
            precio_max = st.slider("💰 Precio máximo (€):", 
                                  min_value=0, 
                                  max_value=int(df_mercado['Precio'].max()), 
                                  value=int(df_mercado['Precio'].max()),
                                  step=100000)

        # Aplicar filtros al DataFrame
        df_filtrado = df_mercado[
            (df_mercado['Nombre'].str.contains(busqueda_nombre, case=False, na=False)) &
            (df_mercado['Precio'] <= precio_max)
        ]

        if not df_filtrado.empty:
            # Lista para el selectbox con el precio visible desde el inicio
            opciones_busqueda = df_filtrado.apply(
                lambda x: f"€{int(x['Precio']):,} - {x['Nombre']} ({x['Club']})", axis=1
            ).tolist()
            
            seleccion_previa = st.selectbox("Seleccionar jugador de la lista filtrada:", options=opciones_busqueda)
            
            # Obtener datos del seleccionado
            indice = opciones_busqueda.index(seleccion_previa)
            j_info = df_filtrado.iloc[indice]
            
            # Ficha de Contrato (Diseño blanco)
            st.markdown(f"""
                <div style="background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-top: 10px;">
                    <h4 style="margin: 0; color: #FFFFFF; font-weight: 600;">{j_info['Nombre']}</h4>
                    <p style="margin: 5px 0; color: #FFFFFF; opacity: 0.7; font-size: 14px;">{j_info['Club']} | {j_info['Posicion']}</p>
                    <h3 style="margin: 0; color: #FFFFFF; font-weight: 700;">Precio: €{int(j_info['Precio']):,}</h3>
                </div>
            """, unsafe_allow_html=True)
            
            st.write("") 

            if st.button("CONFIRMAR FICHAJE", use_container_width=True, type="primary"):
                c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
                if c.fetchone()[0] >= 1:
                    st.error("Ya tienes un jugador. Debes venderlo primero.")
                else:
                    if presupuesto < int(j_info['Precio']):
                        st.error("Presupuesto insuficiente.")
                    else:
                        c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                                  (user_id, j_info['Nombre'], int(j_info['Precio']), j_info['Posicion'], j_info['Club']))
                        c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (int(j_info['Precio']), user_id))
                        conn.commit()
                        st.success(f"¡{j_info['Nombre']} contratado!")
                        st.rerun()
        else:
            st.warning("No hay jugadores que coincidan con tu búsqueda o presupuesto.")

# --- 7. GESTIÓN DEL JUGADOR ---
st.divider()
st.markdown("### 📋 Gestión del Jugador")
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (user_id,))
jugador = c.fetchone()

if not jugador:
    st.info("Sin jugador asignado.")
else:
    j_id, j_nom, j_val, j_pos, j_club = jugador
    with st.expander(f"{j_pos} | {j_nom.upper()} ({j_club})", expanded=True):
        st.write(f"**Valor:** :orange[€{int(j_val):,}]")
        pts = st.number_input("Puntaje:", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
        neto = calcular_resultado_neto(pts, j_val)
        ajuste_p = calcular_ajuste_prestigio(pts)
        
        st.markdown(f"**Balance:** :{'green' if neto >= 0 else 'red'}[€{neto:,}]")
        st.markdown(f"**Prestigio:** :{'green' if ajuste_p >= 0 else 'red'}[{ajuste_p} pts]")
        
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            cv = st.checkbox(f"Vender por €{int(j_val*0.98):,}", key=f"v_{st.session_state.version}")
            if st.button("🗑️ Vender", disabled=not cv, use_container_width=True):
                c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_val*0.98, user_id))
                conn.commit()
                forzar_limpieza()
                st.rerun()
        with col2:
            cp = st.checkbox("Confirmar Fecha", key=f"p_{st.session_state.version}")
            if st.button("✅ PROCESAR", disabled=not cp, type="primary", use_container_width=True):
                nuevo_p = max(1, min(100, prestigio + ajuste_p))
                c.execute("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", (neto, nuevo_p, user_id))
                conn.commit()
                forzar_limpieza()
                st.rerun()

# --- 8. REINICIO PERSONAL ---
st.sidebar.divider()
with st.sidebar.expander("Reiniciar Mi Carrera"):
    cr = st.checkbox("Borrar mis datos", key=f"r_{st.session_state.version}")
    if st.button("REINICIAR", disabled=not cr, type="primary", use_container_width=True):
        c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
        c.execute("UPDATE usuarios SET presupuesto = ?, prestigio = ? WHERE id = ?", (PRESUPUESTO_INICIAL, PRESTIGIO_INICIAL, user_id))
        conn.commit()
        forzar_limpieza()
        st.rerun()
