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

def formatear_abreviado(monto):
    try:
        monto = float(monto)
        if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
        elif monto >= 1_000: return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

def formatear_total(monto):
    try: return f"{int(monto):,}".replace(',', '.')
    except: return "0"

@st.cache_data(ttl=300)
def cargar_datos_completos_google():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = [c.strip() for c in df.columns]
        def limpiar_valor(val):
            try:
                s = str(val).replace('.','').replace(',','')
                return int(''.join(filter(str.isdigit, s)))
            except: return 1000000
        df['ValorNum'] = df.iloc[:, 3].apply(limpiar_valor)
        
        # Display: Nombre (Club) - Valor [Posición]
        df['Display'] = df.iloc[:, 0] + " (" + df.iloc[:, 2] + ") - € " + df['ValorNum'].apply(formatear_abreviado) + " [" + df.iloc[:, 1] + "]"
        
        return df
    except: return pd.DataFrame()

# Tablas
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
    if p >= 7.5: return 2      # Excelente
    if p >= 6.6: return 1      # Bueno
    if p <= 5.9: return -2     # Malo
    if p <= 6.5: return -1     # Regular
    return 0

# --- 3. INTERFAZ ---
st.set_page_config(page_title="World Transfer Market v40", layout="wide")
if 'version' not in st.session_state: st.session_state.version = 0

st.subheader("Transfer Market - Agencia Global")

manager = st.sidebar.text_input("Nombre del Agente:").strip()
if not manager:
    st.info("👋 Ingresa tu nombre para comenzar.")
    st.stop()

datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
if not datos:
    ejecutar_db("INSERT INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 2000000, 10)", (manager,), commit=True)
    st.rerun()

u_id, presupuesto, prestigio = datos[0]

# --- SIDEBAR ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

st.sidebar.divider()
if prestigio >= 1:
    with st.sidebar.popover("💰 Solicitar Crédito"):
        if st.button("Confirmar (€ 150.000 x -1 Rep)"):
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + 150000, prestigio = prestigio - 1 WHERE id = ?", (u_id,), commit=True)
            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                        (u_id, "Crédito Bancario", 150000, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
            st.session_state.version += 1
            st.rerun()

if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    with st.sidebar.expander("⚠️ ZONA DE PELIGRO"):
        if st.text_input("Escribe 'BORRAR' para confirmar:").upper() == "BORRAR":
            if st.button("EJECUTAR RESET TOTAL"):
                ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
                ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
                st.session_state.version += 1
                st.rerun()

# --- 4. SCOUTING Y COMPRA ---
df_oficial = cargar_datos_completos_google()
with st.expander("🔍 Scouting y Co-propiedad"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Buscar Jugador:", options=[""] + df_oficial['Display'].tolist(), key=f"sel_{st.session_state.version}")
        
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj.iloc[0]
            valor_mercado_total = int(dj['ValorNum'])
            
            existe = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
            if existe:
                st.warning(f"⚠️ Ya tienes a {nom} en tu cartera.")
            else:
                vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                disp_mercado = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                
                # Límite por prestigio
                limite_agente = int(prestigio)
                disp_final = min(disp_mercado, limite_agente)
                
                if disp_final <= 0:
                    st.error(f"🚫 No puedes representar a este jugador. Tu prestigio ({prestigio}) es insuficiente o no hay stock disponible.")
                else:
                    st.info(f"📊 Capacidad actual: {disp_final}% (basado en tu Reputación)")
                    
                    opciones = [p for p in [1, 5, 10, 25, 50, 75, 100] if p <= disp_final]
                    if disp_final not in opciones:
                        opciones.append(disp_final)
                        opciones.sort()

                    pct = c2.select_slider("Porcentaje a adquirir:", opciones, key=f"pct_{st.session_state.version}")
                    
                    # LÓGICA OPCIÓN B: 2% Gastos Administrativos sobre el valor TOTAL[cite: 1]
                    costo_ficha = (valor_mercado_total * pct) / 100
                    gastos_admin = valor_mercado_total * 0.02
                    inversion_total = costo_ficha + gastos_admin
                    
                    st.write(f"Costo Ficha ({pct}%): **€ {formatear_total(costo_ficha)}**")
                    st.write(f"Gastos Admin (2% del Total): **€ {formatear_total(gastos_admin)}**")
                    st.markdown(f"### Inversión Total: € {formatear_total(inversion_total)}")
                    
                    if st.button("FICHAR JUGADOR", type="primary"):
                        if presupuesto >= inversion_total:
                            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                                        (u_id, nom, pct, inversion_total, dj.iloc[2]), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inversion_total, u_id), commit=True)
                            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                        (u_id, f"Compra {int(pct)}% {nom}", -inversion_total, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                            st.success("✅ Trato cerrado con éxito.")
                            st.session_state.version += 1
                            st.rerun()
                        else:
                            st.error("❌ Fondos insuficientes en la Caja Global.")

# --- 5. PANEL DE ACTIVOS ---
st.markdown("##### 📋 Mis Jugadores Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera:
    st.write("No tienes jugadores en tu cartera actual.")

for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    v_key = f"v{st.session_state.version}_{j_id}"
    with st.container(border=True):
        col_info, col_input, col_ops = st.columns([2, 2, 2])
        
        with col_info:
            st.subheader(j_nom)
            st.write(f"🌍 {j_club}")
            st.markdown(f'<div style="font-size:16px; color:#FFD700; font-weight:bold;">{int(j_pct)}% | Inversión: € {formatear_total(j_costo)}</div>', unsafe_allow_html=True)
        
        with col_input:
            pts = st.number_input(f"Score Jornada", 1.0, 10.0, 6.4, 0.1, key=f"score_{v_key}")
            bal = calcular_balance_fecha(pts, j_costo)
            st.markdown(f"Resultado: :{'green' if pts>=6.6 else 'red' if pts<=6.3 else 'gray'}[€ {formatear_total(bal)}]")
        
        with col_ops:
            conf = st.checkbox("Confirmar acción", key=f"check_{v_key}", value=False)
            valor_venta = j_costo * 0.99
            texto_venta = f"VENDER (€ {formatear_total(valor_venta)})"
            
            c_c1, c_c2 = st.columns(2)
            if c_c1.button("CARGAR", key=f"btn_r_{v_key}", type="primary", disabled=not conf, use_container_width=True):
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio + ? WHERE id = ?", 
                            (bal, calcular_cambio_prestigio(pts), u_id), commit=True)
                if bal != 0:
                    ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                (u_id, f"Rendimiento {j_nom}", bal, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.session_state.version += 1
                st.rerun()
            
            if c_c2.button(texto_venta, key=f"btn_v_{v_key}", disabled=not conf, use_container_width=True):
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                            (u_id, f"Venta {int(j_pct)}% {j_nom}", valor_venta, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (valor_venta, u_id), commit=True)
                st.session_state.version += 1
                st.rerun()

# --- 6. RANKING Y HISTORIAL ---
st.divider()
c_rank, c_hist = st.columns(2)

with c_rank:
    with st.expander("🏆 Ranking de Agentes"):
        usuarios_raw = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios")
        df_ranking = pd.DataFrame(usuarios_raw, columns=['Agente', 'Reputación', 'Presupuesto'])
        df_ranking = df_ranking.sort_values(by='Reputación', ascending=False).reset_index(drop=True)
        df_ranking.index += 1
        df_ranking['Presupuesto'] = df_ranking['Presupuesto'].apply(lambda x: f"€ {formatear_total(x)}")
        st.table(df_ranking)

with c_hist:
    with st.expander("📜 Historial de Operaciones"):
        historial_raw = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 20", (u_id,))
        if historial_raw:
            df_hist = pd.DataFrame(historial_raw, columns=['Fecha', 'Detalle', 'Monto'])
            df_hist['Monto'] = df_hist['Monto'].apply(lambda x: f"{'🟢' if x>0 else '🔴'} € {formatear_total(x)}")
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.write("No hay operaciones registradas.")
