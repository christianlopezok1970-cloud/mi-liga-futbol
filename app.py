import streamlit as st
import sqlite3
import pandas as pd
import re

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
PORCENTAJE_SUELDO = 0.0125 # 1.25%

def calcular_resultado_neto(puntaje, valor_jugador):
    # Rendimiento: cada 0.1 sobre 6.4 = €20.000
    pasos = (puntaje - 6.4) / 0.1
    ganancia_puntos = int(pasos * VALOR_POR_PASO)
    
    # Sueldo automático 1.25%
    costo_sueldo = valor_jugador * PORCENTAJE_SUELDO
    
    return int(ganancia_puntos - costo_sueldo)

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Liga Argentina Manager", layout="wide")
st.title("⚽ Liga Argentina Manager")

user_name = st.sidebar.text_input("Usuario").strip()
if not user_name:
    st.info("👋 Ingresa tu nombre en la barra lateral para comenzar.")
    st.stop()

# Presupuesto Inicial
PRESUPUESTO_INICIAL = 2000000
c.execute("INSERT OR IGNORE INTO usuarios (nombre, presupuesto) VALUES (?, ?)", (user_name, PRESUPUESTO_INICIAL))
conn.commit()
c.execute("SELECT id, presupuesto FROM usuarios WHERE nombre = ?", (user_name,))
user_id, presupuesto = c.fetchone()

st.sidebar.success(f"Usuario: {user_name}")
st.sidebar.metric("Tu Dinero", f"€{int(presupuesto):,}")

# --- 5. MERCADO DE PASES (Cupo 1) ---
with st.expander("🛒 Mercado de Pases (Cupo: 1 jugador)"):
    if df_mercado is not None:
        opciones = df_mercado.apply(lambda x: f"{x['Nombre']} ({x['Club']}) - {x['Posicion']} - €{int(x['Precio']):,}", axis=1).tolist()
        seleccion = st.selectbox("Buscar jugador para fichar:", options=opciones)
        
        if st.button("Confirmar Fichaje"):
            idx = opciones.index(seleccion)
            j_info = df_mercado.iloc[idx]
            
            c.execute("SELECT COUNT(*) FROM jugadores WHERE usuario_id = ?", (user_id,))
            if c.fetchone()[0] >= 1:
                st.error("Ya tienes 1 jugador fichado.")
            elif presupuesto < int(j_info['Precio']):
                st.error("No tienes fondos suficientes.")
            else:
                c.execute("INSERT INTO jugadores (usuario_id, nombre, valor, posicion, club) VALUES (?,?,?,?,?)",
                          (user_id, j_info['Nombre'], int(j_info['Precio']), j_info['Posicion'], j_info['Club']))
                c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto - int(j_info['Precio']), user_id))
                conn.commit()
                st.rerun()

# --- 6. GESTIÓN DE PLANTEL (Ordenado por Posición) ---
st.divider()
st.header("📋 Tu Jugador")

c.execute("SELECT id, nombre, valor, posicion, club FROM jugadores WHERE usuario_id = ? ORDER BY posicion ASC", (user_id,))
plantel = c.fetchall()

if not plantel:
    st.info("No tienes ningún jugador fichado.")
else:
    for j_id, j_nom, j_val, j_pos, j_club in plantel:
        with st.expander(f"{j_pos} | {j_nom} ({j_club})", expanded=True):
            st.write(f"**Valor de Fichaje:** €{int(j_val):,}")
            st.write(f"**Sueldo x partido (1.25%):** €{int(j_val * PORCENTAJE_SUELDO):,}")
            
            pts = st.number_input("Puntaje obtenido:", 1.0, 10.0, 6.4, step=0.1, key=f"p_{j_id}")
            neto_final = calcular_resultado_neto(pts, j_val)
            
            if neto_final >= 0:
                st.write(f"📊 Balance de fecha: **+€{neto_final:,}**")
            else:
                st.write(f"📊 Balance de fecha: **-€{abs(neto_final):,}**")
            
            col1, col2 = st.columns(2)
            
            # Botón: Cargar Puntos
            if col1.button("✅ Cargar Puntos", key=f"a_{j_id}"):
                if (presupuesto + neto_final) < 0:
                    st.error("Error: Saldo insuficiente para pagar el sueldo.")
                else:
                    nuevo_presupuesto = presupuesto + neto_final
                    c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_presupuesto, user_id))
                    conn.commit()
                    st.rerun()
                
            # Botón: Venta con Confirmación
            with col2:
                # Al vender recupera: Valor original - 1 sueldo
                monto_recuperado = j_val - (j_val * PORCENTAJE_SUELDO)
                
                confirmar_v = st.checkbox(f"Vender por €{int(monto_recuperado):,}", key=f"conf_{j_id}")
                
                if st.button("🗑️ Confirmar Venta", key=f"v_{j_id}", disabled=not confirmar_v, type="primary"):
                    if (presupuesto + monto_recuperado) < 0:
                        st.error("No puedes vender: la comisión te dejaría en negativo.")
                    else:
                        c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
                        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (presupuesto + monto_recuperado, user_id))
                        conn.commit()
                        st.rerun()

# --- 7. SIDEBAR REINICIO ---
st.sidebar.divider()
with st.sidebar.expander("🚨 Reiniciar Perfil"):
    confirmar_r = st.checkbox("Confirmar reinicio")
    if st.button("REINICIAR TODO", disabled=not confirmar_r, type="primary"):
        c.execute("DELETE FROM jugadores WHERE usuario_id = ?", (user_id,))
        c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (PRESUPUESTO_INICIAL, user_id))
        conn.commit()
        st.rerun()
