import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
# Nombre de la DB exclusivo para este juego nuevo
DB_NAME = 'agencia_afa_v2.db'

def ejecutar_db(query, params=(), commit=False):
    with sqlite3.connect(DB_NAME, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return c.fetchall()

# Creación de tablas
ejecutar_db('''CREATE TABLE IF NOT EXISTS usuarios 
             (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, presupuesto REAL, prestigio INTEGER)''', commit=True)
ejecutar_db('''CREATE TABLE IF NOT EXISTS cartera 
             (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre_jugador TEXT, 
              porcentaje REAL, costo_compra REAL, club TEXT)''', commit=True)

# --- 2. LÓGICA DE RENDIMIENTO (EJE 6.4) ---
def calcular_balance_fecha(puntaje, costo_proporcional):
    # Eje en 6.4: Cada 0.1 de diferencia impacta un 1.5% sobre la inversión proporcional
    diferencia = round(puntaje - 6.4, 1)
    impacto_porcentual = diferencia * 0.15  
    ganancia_o_perdida = costo_proporcional * impacto_porcentual
    return int(ganancia_o_perdida)

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Agente LPF", layout="wide")
st.title("⚽ Agencia LPF: El Factor 6.4")

manager = st.sidebar.text_input("Tu Nombre de Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral para iniciar tu carrera en la Liga Argentina.")
    st.stop()

# Registro/Carga de perfil
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1500000, 40)", (manager,), commit=True)
datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
u_id, presupuesto, prestigio = datos[0]

# Dashboard Lateral
st.sidebar.markdown(f"### Manager: {manager}")
st.sidebar.metric("Presupuesto", f"€{int(presupuesto):,}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")
st.sidebar.divider()

# --- 4. MERCADO DE PORCENTAJES ---
with st.expander("🤝 Adquirir Porcentaje de Jugador"):
    c1, c2 = st.columns(2)
    nombre_j = c1.text_input("Nombre del Jugador:")
    club_j = c1.selectbox("Club LPF:", ["River", "Boca", "Talleres", "Racing", "Independiente", "San Lorenzo", "Estudiantes", "Lanús", "Velez", "Otros"])
    valor_100 = c2.number_input("Valor de Mercado (100%):", min_value=100000, step=50000, value=1000000)
    pct_compra = c2.slider("% de la ficha a comprar:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión requerida por el {pct_compra}%: **€{int(costo_final):,}**")
    
    if st.button("FIRMAR CONTRATO", use_container_width=True, type="primary"):
        if presupuesto >= costo_final:
            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                        (u_id, nombre_j, pct_compra, costo_final, club_j), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
            st.success(f"¡Felicidades! {nombre_j} ahora es parte de tu agencia.")
            st.rerun()
        else:
            st.error("No tienes fondos suficientes.")

# --- 5. PANEL DE SEGUIMIENTO ---
st.header("📈 Rendimiento en Vivo (Eje 6.4)")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera:
    st.warning("Tu cartera está vacía. Empezá a buscar talentos en la LPF.")
else:
    for j_id, j_nom, j_pct, j_costo, j_club in cartera:
        with st.container(border=True):
            col_info, col_input, col_result = st.columns([2, 2, 1])
            
            col_info.subheader(j_nom)
            col_info.write(f"**{j_club}** | Posees el {j_pct}%")
            col_info.caption(f"Inversión original: €{int(j_costo):,}")
            
            pts_365 = col_input.number_input(f"Puntaje 365Scores para {j_nom}:", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            
            # Colores dinámicos
            color = "green" if pts_365 > 6.4 else "red" if pts_365 < 6.4 else "gray"
            col_result.markdown(f"#### Balance:")
            col_result.markdown(f"### :{color}[€{balance:,}]")
            
            if col_result.button("Procesar Fecha", key=f"btn_{j_id}", use_container_width=True):
                nuevo_prestigio = prestigio + (2 if pts_365 >= 7.5 else 1 if balance > 0 else -1 if balance < 0 else 0)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", 
                            (balance, nuevo_prestigio, u_id), commit=True)
                st.toast(f"Liquidación de {j_nom} procesada con éxito.")
                st.rerun()

    if st.sidebar.button("🗑️ Resetear Juego (Borrar todo)"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 1500000, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
        st.rerun()
