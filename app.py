import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = 'agencia_global_v41.db'
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
        if monto >= 1_000_000: 
            return f"{monto / 1_000_000:.1f}M".replace('.0M', 'M').replace('.', ',')
        elif monto >= 1_000: 
            if monto >= 1_000_000: return f"{monto / 1_000_000:.1f}M".replace('.', ',')
            return f"{monto / 1_000:.0f}K"
        return f"{monto:.0f}"
    except: return "0"

def formatear_total(monto):
    try: return f"{int(float(monto)):,}".replace(',', '.')
    except: return "0"

st.subheader("🔍 Mercado de Fichajes")

# 2. Usa el estado_mercado que leíste del Excel
if estado_mercado == "CERRADO":
    st.error("🚨 EL MERCADO ESTÁ ACTUALMENTE CERRADO. No se permiten nuevas contrataciones.")
else:
    with st.expander("🔍 Scouting y Mercado"):
        if not df_oficial.empty:
            c1, c2 = st.columns(2)
            seleccion = c1.selectbox("Buscar Jugador:", options=[""] + df_oficial['Display'].tolist())
            
            if seleccion:
                dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
                nom = dj.iloc[0]
                
                # Bloqueo de duplicados: Verificar si ya lo tienes en cartera
                ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
                
                if ya_lo_tiene:
                    st.warning(f"⚠️ Ya representas a {nom}.")
                else:
                    v_m_t = int(dj['ValorNum'])
                    # Verificar stock global disponible en la DB
                    vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                    stock_disponible = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                    
                    # El porcentaje máximo a comprar se limita por tu Reputación
                    max_fichaje = min(stock_disponible, int(prestigio))
                    
                    if max_fichaje > 0:
                        # Opciones dinámicas para el slider
                        opciones_pct = sorted(list(set([o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_fichaje] + [max_fichaje])))
                        
                        pct = c2.select_slider("Participación a adquirir:", opciones_pct)
                        costo_f = (v_m_t * pct) / 100
                        inv_total = costo_f + (v_m_t * 0.02) # Ficha + 2% de gestión
                        
                        st.info(f"Costo Ficha: € {formatear_total(costo_f)} | Gestión (2%): € {formatear_total(v_m_t * 0.02)}")
                        
                        if st.button("FICHAR JUGADOR", type="primary"):
                            if presupuesto >= inv_total:
                                # Insertar en cartera
                                ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", 
                                           (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                                # Restar de presupuesto
                                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv_total, u_id), commit=True)
                                # Registrar en historial[cite: 1]
                                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", 
                                           (u_id, f"Compra {pct}% {nom}", -inv_total, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                                st.success(f"🤝 ¡Contrato firmado con {nom}!")
                                st.rerun()
                            else:
                                st.error("❌ Fondos insuficientes en la Caja Global.")
                    else:
                        st.error(f"🚫 No puedes fichar a este jugador (Stock: {stock_disponible}% | Tu Reputación: {prestigio}).")

# --- 5. SIDEBAR (Métricas + Préstamo)[cite: 2] ---
st.sidebar.metric("Caja Global", f"€ {formatear_total(presupuesto)}")
st.sidebar.metric("Reputación", f"{prestigio} pts")

with st.sidebar.expander("🏦 Préstamo Bancario"):
    st.caption("€ 100.000 = -1 de Reputación")
    monto_p = st.number_input("Monto (€):", min_value=0, step=100000)
    if st.button("Confirmar Préstamo"):
        if monto_p >= 100000:
            costo_rep = int(monto_p / 100000)
            if prestigio >= costo_rep:
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ?, prestigio = prestigio - ? WHERE id = ?", (monto_p, costo_rep, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Préstamo (-{costo_rep} Rep)", monto_p, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()
            else:
                st.error("Reputación insuficiente.")

st.sidebar.divider()
if not st.sidebar.toggle("🔒 Bloquear Reset", value=True):
    if st.sidebar.button("RESET TOTAL"):
        ejecutar_db("DELETE FROM cartera WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("DELETE FROM historial WHERE usuario_id = ?", (u_id,), commit=True)
        ejecutar_db("UPDATE usuarios SET presupuesto = 2000000, prestigio = 10 WHERE id = ?", (u_id,), commit=True)
        st.rerun()

# --- 6. SCOUTING Y MERCADO (Ajustado a Reputación)[cite: 1, 3] ---
with st.expander("🔍 Scouting y Mercado"):
    if not df_oficial.empty:
        c1, c2 = st.columns(2)
        seleccion = c1.selectbox("Buscar Jugador:", options=[""] + df_oficial['Display'].tolist())
        if seleccion:
            dj = df_oficial[df_oficial['Display'] == seleccion].iloc[0]
            nom = dj.iloc[0]
            
            ya_lo_tiene = ejecutar_db("SELECT id FROM cartera WHERE usuario_id = ? AND nombre_jugador = ?", (u_id, nom))
            if ya_lo_tiene:
                st.warning(f"⚠️ Ya representas a {nom}.")
            else:
                v_m_t = int(dj['ValorNum'])
                vendido_p = ejecutar_db("SELECT SUM(porcentaje) FROM cartera WHERE nombre_jugador = ?", (nom,))
                stock_disponible = 100 - (vendido_p[0][0] if vendido_p[0][0] else 0)
                
                max_fichaje = min(stock_disponible, int(prestigio))
                
                if max_fichaje > 0:
                    opciones_fichaje = [o for o in [1, 5, 10, 25, 50, 75, 100] if o <= max_fichaje]
                    if not opciones_fichaje or max_fichaje not in opciones_fichaje:
                        opciones_fichaje.append(max_fichaje)
                    opciones_fichaje = sorted(list(set(opciones_fichaje)))

                    pct = c2.select_slider("Porcentaje a adquirir:", opciones_fichaje)
                    costo_f = (v_m_t * pct) / 100
                    inv_total = costo_f + (v_m_t * 0.02)
                    
                    st.info(f"Ficha: € {formatear_total(costo_f)} | Gastos Admin (2%): € {formatear_total(v_m_t * 0.02)}")
                    if st.button("FICHAR JUGADOR", type="primary"):
                        if presupuesto >= inv_total:
                            ejecutar_db("INSERT INTO cartera (usuario_id, nombre_jugador, porcentaje, costo_compra, club) VALUES (?,?,?,?,?)", (u_id, nom, pct, costo_f, dj.iloc[1]), commit=True)
                            ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto - ? WHERE id = ?", (inv_total, u_id), commit=True)
                            ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Compra {pct}% {nom}", -inv_total, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                            st.rerun()
                else:
                    st.error("Reputación insuficiente.")

# --- 7. MIS REPRESENTADOS (Venta al 99% y Doble Seguridad)[cite: 2, 3] ---
st.markdown("### 📋 Mis Representados")
cartera = ejecutar_db("SELECT id, nombre_jugador, porcentaje, costo_compra, club FROM cartera WHERE usuario_id = ?", (u_id,))
for j_id, j_nom, j_pct, j_costo, j_club in cartera:
    info = df_oficial[df_oficial.iloc[:, 0].str.strip() == j_nom.strip()]
    score = info['ScoreOficial'].values[0] if not info.empty else 0
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"#### {j_nom} <small>({j_club})</small>", unsafe_allow_html=True)
            st.markdown(f"**Participación:** {int(j_pct)}%")
            st.write(f"Inversión: € {formatear_total(j_costo)} | Score: {score}")
        with c2:
            confirmar_v = st.checkbox("Confirmar Venta", key=f"chk_{j_id}")
            valor_salida = j_costo * 0.99
            if st.button(f"VENDER €{formatear_total(valor_salida)}", key=f"btn_{j_id}", disabled=not confirmar_v):
                ejecutar_db("DELETE FROM cartera WHERE id = ?", (j_id,), commit=True)
                ejecutar_db("UPDATE usuarios SET presupuesto = presupuesto + ? WHERE id = ?", (valor_salida, u_id), commit=True)
                ejecutar_db("INSERT INTO historial (usuario_id, detalle, monto, fecha) VALUES (?,?,?,?)", (u_id, f"Venta {j_nom}", valor_salida, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
                st.rerun()

# --- 8. RANKING E HISTORIAL ---
st.divider()
c_rank, c_hist = st.columns(2)
with c_rank:
    with st.expander("🏆 Ranking"):
        res = ejecutar_db("SELECT nombre, prestigio, presupuesto FROM usuarios ORDER BY prestigio DESC")
        st.table(pd.DataFrame(res, columns=['Agente', 'Rep', 'Caja']))
with c_hist:
    with st.expander("📜 Historial"):
        h = ejecutar_db("SELECT fecha, detalle, monto FROM historial WHERE usuario_id = ? ORDER BY id DESC LIMIT 15", (u_id,))
        st.dataframe(pd.DataFrame(h, columns=['Fecha', 'Evento', 'Monto']), hide_index=True)
