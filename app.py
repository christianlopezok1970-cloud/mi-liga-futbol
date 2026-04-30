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
st.set_page_config(page_title="Agencia de Representantes", layout="wide")
st.markdown("## 💼 Agencia de Representantes")

user_name = st.sidebar.text_input("Nombre del Agente").strip()
if not user_name:
    st.info("👋 Ingresa tu nombre para gestionar tu agencia.")
    st.sidebar.divider()
    st.sidebar.subheader("🏆 Ranking de Agencias")
    c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 5")
    for i, (n, p) in enumerate(c.fetchall(), 1):
        st.sidebar.write(f"{i}. {n} ({p} pts)")
    st.stop()

# Inicializar Usuario
PRESUPUESTO_INICIAL = 2000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, ?, 40)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto, prestigio = c.fetchone()

# --- 5. LÓGICA DE RANGOS Y BENEFICIOS ---
if prestigio >= 85:
    rango, color, cupo_maximo = "💎 MAGNATE DEL MERCADO", "#40E0D0", 4
elif prestigio >= 70:
    rango, color, cupo_maximo = "🏢 SOCIO DE AGENCIA ELITE", "#00FF00", 3
elif prestigio >= 45:
    rango, color, cupo_maximo = "🤝 BRÓKER DE TRANSFERENCIAS", "#FFFF00", 2
else:
    rango, color, cupo_maximo = "👟 PROMOTOR DE JUVENILES", "#FF4B4B", 1

# --- 6. SIDEBAR ---
st.sidebar.markdown(f"""
    <div style="background-color: #000; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #333;">
        <p style="color: #666; margin: 0; font-size: 12px; letter-spacing: 2px;">PRESTIGIO</p>
        <h1 style="color: {color}; margin: 0; font-size: 60px;">{prestigio}</h1>
        <p style="color: {color}; font-weight: bold; font-size: 14px; margin: 0; text-transform: uppercase;">{rango}</p>
        <p style="color: #888; font-size: 11px; margin-top: 5px;">Cartera Máxima: {cupo_maximo} Clientes</p>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.metric("Billetera", f"€{int(presupuesto):,}")

# Préstamo
with st.sidebar.expander("💰 Solicitar Capital"):
    if st.button("PEDIR €1M (Cuesta -5 Prestigio)", use_container_width=True):
        c.execute("UPDATE usuarios SET presupuesto = presupuesto + 1000000, prestigio = MAX(1, prestigio - 5) WHERE id = ?", (user_id,))
        conn.commit()
        st.rerun()

# Ranking
st.sidebar.subheader("🏆 Top Agencias")
c.execute("SELECT nombre, prestigio FROM usuarios ORDER BY prestigio DESC LIMIT 5")
for i, (nom, pres) in enumerate(c.fetchall(), 1):
    st.sidebar.write(f"{i}. {nom} ({pres} pts)")

# --- 7. MERCADO DE PASES CON FILTROS ---
with st.expander("🛒 Buscar Nuevos Clientes"):
    if df_mercado is not None:
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            bus_nom = st.text_input("🔍 Nombre:", key=f"bn_{st.session_state.version}")
        with col_f2:
            p_min = st.number_input("Min €:", 0, value=0, step=100000)
        with col_f3:
            p_max = st.number_input("Max €:", 0, value=int(df_mercado['Precio'].max()), step=100000)

        df_f = df_mercado[(df_mercado['Nombre'].str.contains(bus_nom, case=False, na=False)) & (df_mercado['Precio'].between(p_min, p_max))]
        
        if not df_f.empty:
            opciones = df_f.apply(lambda x: f"{x['Nombre']}/ {formatear_monto(x['Precio'])}/ {x['Posicion']}/ {x['Club']}", axis=1).tolist()
            sel = st.selectbox("Seleccionar:", opciones)
            j_data = df_f.iloc[opciones.index(sel)]
            
            st.markdown(f"""<div style="background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;">
                <h4 style="margin: 0;">{j_data['Nombre']}</h4>
                <p style="margin: 0; opacity: 0.7;">{j_data['Club']} | {j_data['Posicion']}</p>
                <h3 style="margin: 0;">Costo: €{formatear_monto(j_data['Precio'])}</h3>
            </div>""", unsafe_allow_html=True)

            if st.button("FIRMAR CONTRATO", use_container_width=True, type="primary"):
                c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
                if c.fetchone()[0] >= cupo_maximo:
                    st.error(f"⚠️ Cartera llena. {rango} solo permite {cupo_maximo} clientes.")
                elif presupuesto < j_data['Precio']:
                    st.error("Dinero insuficiente.")
                else:
                    c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                              (user_id, j_data['Nombre'], j_data['Precio'], j_data['Posicion'], j_data['Club']))
                    c.execute("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (j_data['Precio'], user_id))
                    conn.commit()
                    forzar_limpieza()
                    st.rerun()

# --- 8. GESTIÓN DE CARTERA (CLIENTES) ---
st.divider()
st.subheader(f"📋 Clientes en Cartera")
c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ?", (user_id,))
mis_jugadores = c.fetchall()

if not mis_jugadores:
    st.info("Aún no representas a ningún jugador. Ve al mercado para buscar clientes.")
else:
    # Mostramos los jugadores en columnas para aprovechar el espacio
    cols = st.columns(len(mis_jugadores))
    for idx, (j_id, j_nom, j_val, j_pos, j_club) in enumerate(mis_jugadores):
        with cols[idx]:
            with st.container(border=True):
                st.write(f"**{j_nom}**")
                st.caption(f"{j_pos} | {j_club}")
                st.write(f"Valor: €{formatear_monto(j_val)}")
                
                pts = st.number_input(f"Puntaje", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
                neto = calcular_resultado_neto(pts, j_val)
                ajuste_p = calcular_ajuste_prestigio(pts)
                
                st.markdown(f"Neto: :{'green' if neto>=0 else 'red'}[€{neto:,}]")
                
                if st.button(f"PROCESAR FECHA", key=f"btn_{j_id}", use_container_width=True):
                    nuevo_pres = presupuesto + neto
                    nuevo_pres_total = max(0, nuevo_pres)
                    nuevo_pres_final = prestigio + ajuste_p
                    c.execute("UPDATE usuarios SET presupuesto = ?, prestigio = MAX(1, MIN(100, ?)) WHERE id = ?", 
                             (nuevo_pres, nuevo_pres_final, user_id))
                    conn.commit()
                    st.rerun()
                
                if st.checkbox("Vender (98%)", key=f"vchk_{j_id}"):
                    if st.button("CONFIRMAR VENTA", key=f"vbtn_{j_id}", type="primary"):
                        c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                        c.execute("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (j_val * 0.98, user_id))
                        conn.commit()
                        st.rerun()

# --- 9. ADMINISTRACIÓN (BORRAR USUARIOS) ---
st.sidebar.divider()
with st.sidebar.expander("⚙️ Admin Sistema"):
    c.execute("SELECT nombre FROM usuarios")
    lista_u = [r[0] for r in c.fetchall()]
    u_del = st.selectbox("Borrar Usuario:", lista_u)
    if st.button("ELIMINAR DEFINITIVAMENTE", type="primary"):
        c.execute("DELETE FROM jugadores WHERE usuario_id = (SELECT id FROM usuarios WHERE nombre = ?)", (u_del,))
        c.execute("DELETE FROM usuarios WHERE nombre = ?", (u_del,))
        conn.commit()
        st.rerun()
