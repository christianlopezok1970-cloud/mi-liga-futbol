import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v40.db'
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQed5yx4ReWBiR2IFct9y1jkLGVF9SIbn3RbzNYYZLJPhhcq_yy0WuTZWd0vVJAZ2kvD_walSrs-J-S/pub?output=csv"

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

def formatear_total(monto):
    try: return f"{int(monto):,}".replace(',', '.')
    except: return "0"

@st.cache_data(ttl=300)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        # Limpieza de valores
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        # LEER COLUMNA "Puntaje" (Asumimos que es la columna F o índice 5)
        # Ajusta el índice si tu columna "Puntaje" está en otro lugar
        df['ScoreOficial'] = pd.to_numeric(df['Puntaje'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

# Tablas iniciales
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS historial 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, detalle TEXT, monto REAL, fecha TEXT)''', commit=True)

# --- 2. LÓGICA DE NEGOCIO ---
def calcular_balance_fecha(pts, costo):
    pts = round(float(pts), 1)
    if pts >= 6.6: return int(costo * ((pts - 6.5) * 10 / 100))
    elif pts <= 6.3: return int(costo * ((pts - 6.4) * 10 / 100))
    return 0

def calcular_cambio_prestigio(pts):
    p = round(float(pts), 1)
    if p >= 8.0: return 2
    if p >= 7.0: return 1
    if p <= 5.9: return -2
    if p <= 6.7: return -1
    return 0

# --- 3. INTERFAZ Y LOGIN ---
st.set_page_config(page_title="Pro Fútbol Manager v40", layout="wide")
if 'version' not in st.session_state: st.session_state.version = 0

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 10)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]
df_oficial = cargar_datos_completos_google()

# --- 4. PROCESAMIENTO AUTOMÁTICO (EL CORAZÓN DEL CAMBIO) ---
# Se ejecuta solo si hay datos del Excel y el usuario está logueado
if not df_oficial.empty:
    cartera_activa = ejecutar_db("SELECT nombre_jugador, costo_compra FROM cartera WHERE usuario_id = ?", (u_id,))
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    actualizaciones = 0

    for j_nom, j_costo in cartera_activa:
        # Buscar score en el Excel
        match = df_oficial[df_oficial.iloc[:, 0] == j_nom]
        if not match.empty:
            pts_oficial = float(match['ScoreOficial'].values[0])
            
            # Solo procesar si el admin puso un puntaje > 0
            if pts_oficial > 0:
                # Verificar si ya se cobró HOY este jugador específico
                ya_cobrado = ejecutar_db(
                    "SELECT id FROM historial WHERE usuario_id = ? AND detalle LIKE ? AND fecha LIKE ?", 
                    (u_id, f"Auto-Jornada: {j_nom}%", f"{fecha_hoy}%")
                )
                
                if not ya_cobrado:
                    bal = calcular_balance_fecha(pts_oficial, j_costo)
                    pres_mod = calcular_cambio_prestigio(pts_oficial)
                    
                    # Aplicar cambios
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                                (bal, pres_mod, u_id), commit=True)
                    
                    # Guardar en historial con marca "Auto-Jornada" para control
                    detalle = f"Auto-Jornada: {j_nom} (Score: {pts_oficial}) | € {formatear_total(bal)}"
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                (u_id, detalle, bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                    actualizaciones += 1

    if actualizaciones > 0:
        st.toast(f"✅ ¡Jornada procesada! {actualizaciones} jugadores actualizados.", icon="⚽")
        # Refrescar datos de la sesión para mostrar el nuevo presupuesto inmediatamente
        datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
        u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR Y RESTO DE LA INTERFAZ ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

# [Aquí iría el resto del código de Scouting y Ranking, pero sin botones de Cargar]
st.write("### 📋 Mis Jugadores Representados")
cartera_visual = ejecutar_db("SELECT nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

for j_nom, j_pct, j_costo, j_club in cartera_visual:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"**{j_nom}** ({j_club})")
        c1.write(f"Participación: {int(j_pct)}% | Inversión: € {formatear_total(j_costo)}")
        
        # Mostrar el score que hay actualmente en el Excel[cite: 2]
        score_actual = df_oficial[df_oficial.iloc[:, 0] == j_nom]['ScoreOficial'].values[0] if not df_oficial.empty else 0
        c2.info(f"Puntaje en Excel: {score_actual}")
