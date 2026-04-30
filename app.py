import streamlit as st
import sqlite3
import pandas as pd
import re

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_afa_v3.db'

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

# --- 2. FUNCIONES DE FORMATO Y LÓGICA ---
def formatear_monto(monto):
    monto = float(monto)
    if monto >= 1_000_000:
        return f"{monto / 1_000_000:.1f} M"
    elif monto >= 1_000:
        return f"{int(monto / 1_000)} K"
    return f"{int(monto)}"

def calcular_balance_fecha(puntaje, costo_proporcional):
    # Eje en 6.4
    diferencia = round(puntaje - 6.4, 1)
    impacto_porcentual = diferencia * 0.15  
    ganancia_o_perdida = costo_proporcional * impacto_porcentual
    return int(ganancia_o_perdida)

# --- 3. INTERFAZ ---
st.set_page_config(page_title="Agente LPF Pro", layout="wide")
st.title("⚽ Agencia LPF: Gestión de Activos")

manager = st.sidebar.text_input("Tu Nombre de Agente:").strip()

if not manager:
    st.info("👋 Ingresa tu nombre en la barra lateral para iniciar.")
    st.stop()

# Registro/Carga de perfil
ejecutar_db("INSERT OR IGNORE INTO usuarios (nombre, presupuesto, prestigio) VALUES (?, 1500000, 40)", (manager,), commit=True)
datos = ejecutar_db("SELECT id, presupuesto, prestigio FROM usuarios WHERE nombre = ?", (manager,))
u_id, presupuesto, prestigio = datos[0]

# Dashboard Lateral
st.sidebar.markdown(f"### Manager: {manager}")
st.sidebar.metric("Presupuesto", f"€{formatear_monto(presupuesto)}")
st.sidebar.metric("Prestigio", f"{prestigio} pts")
st.sidebar.divider()

# --- 4. MERCADO DE PORCENTAJES ---
with st.expander("🤝 Adquirir Porcentaje de Jugador"):
    c1, c2 = st.columns(2)
    nombre_j = c1.text_input("Nombre del Jugador:")
    club_j = c1.selectbox("Club LPF:", ["River", "Boca", "Talleres", "Racing", "Independiente", "San Lorenzo", "Estudiantes", "Lanús", "Velez", "Otros"])
    valor_100 = c2.number_input("Valor de Mercado (100%):", min_value=10000, step=50000, value=1000000)
    pct_compra = c2.slider("% de la ficha:", 5, 100, 10)
    
    costo_final = (valor_100 * pct_compra) / 100
    st.write(f"Inversión: **€{formatear_monto(costo_final)}**")
    
    if st.button("FIRMAR CONTRATO", use_container_width=True, type="primary"):
        if presupuesto >= costo_final:
            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)",
                        (u_id, nombre_j, pct_compra, costo_final, club_j), commit=True)
            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (costo_final, u_id), commit=True)
            st.success(f"¡{nombre_j} agregado a la cartera!")
            st.rerun()
        else:
            st.error("Presupuesto insuficiente.")

# --- 5. PANEL DE SEGUIMIENTO ---
st.header("📈 Cartera de Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))

if not cartera:
    st.warning("No tienes jugadores en tu agencia.")
else:
    for j_id, j_nom, j_pct, j_costo, j_club in cartera:
        with st.container(border=True):
            col_info, col_input, col_ops = st.columns([2, 2, 2])
            
            # Columna 1: Info
            col_info.subheader(j_nom)
            col_info.write(f"**{j_club}** | Propiedad: {j_pct}%")
            col_info.caption(f"Inversión: €{formatear_monto(j_costo)}")
            
            # Columna 2: Puntaje y Balance
            pts_365 = col_input.number_input(f"Score 365 ({j_nom})", 1.0, 10.0, 6.4, step=0.1, key=f"pts_{j_id}")
            balance = calcular_balance_fecha(pts_365, j_costo)
            color = "green" if pts_365 > 6.4 else "red" if pts_365 < 6.4 else "gray"
            col_input.markdown(f"Balance: :{color}[€{formatear_monto(balance)}]")
            
            # Columna 3: Doble Seguridad (Procesar y Vender)
            with col_ops:
                # Procesar Partido
                conf_proc = st.checkbox("Confirmar Fecha", key=f"conf_p_{j_id}")
                if st.button(f"PROCESAR", key=f"btn_p_{j_id}", disabled=not conf_proc, use_container_width=True):
                    nuevo_prestigio = prestigio + (1 if balance > 0 else -1 if balance < 0 else 0)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = ? WHERE id = ?", 
                                (balance, nuevo_prestigio, u_id), commit=True)
                    st.rerun()
                
                st.divider()
                
                # Vender Jugador
                conf_vende = st.checkbox("Confirmar Venta", key=f"conf_v_{j_id}")
                if st.button(f"VENDER (98%)", key=f"btn_v_{j_id}", disabled=not conf_vende, use_container_width=True, type="secondary"):
                    # Se recupera la inversión original menos 2% de comisión
                    recupero = j_costo * 0.98
                    ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                    ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (recupero, u_id), commit=True)
                    st.rerun()

# Botón de Reset Total
if st.sidebar.button("Reiniciar Agencia (Borrar Todo)"):
    ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
    ejecutar_db("UPDATE usuarios SET presupuesto = 1500000, prestigio = 40 WHERE id = ?", (u_id,), commit=True)
    st.rerun()
    
