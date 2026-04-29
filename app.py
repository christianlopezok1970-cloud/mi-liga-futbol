import streamlit as st
import sqlite3
import pandas as pd
# --- NUEVA SECCIÓN DE GESTIÓN CON SIMULADOR ---
st.header("📋 Tu Plantilla y Simulador")
c.execute("SELECT id, nombre, valor, posicion FROM jugadores WHERE usuario_id = ?", (user_id,))
jugadores = c.fetchall()

for j_id, j_nombre, j_valor, j_posicion in jugadores:
    with st.expander(f"{j_nombre} ({j_posicion}) - €{j_valor:,.2f}"):
        st.subheader("Simulador de Rendimiento")
        
        # El slider ahora actúa como simulador en tiempo real
        puntaje_sim = st.slider("Simular puntaje del partido", 1.0, 10.0, 6.4, step=0.1, key=f"sim_{j_id}")
        
        # Cálculo de la proyección
        nuevo_valor_proyectado = calcular_nuevo_valor(j_valor, puntaje_sim)
        diferencia = nuevo_valor_proyectado - j_valor
        color = "green" if diferencia >= 0 else "red"
        
        # Mostrar el resultado antes de confirmar
        st.markdown(f"**Proyección:** El valor pasaría a: <span style='color:{color}'>€{nuevo_valor_proyectado:,.2f}</span>", unsafe_index=True, unsafe_allow_html=True)
        st.caption(f"Variación estimada: {'+' if diferencia >= 0 else ''}€{diferencia:,.2f}")

        # Botones de acción real
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("✅ Confirmar Fecha (Aplicar)", key=f"apply_{j_id}"):
            c.execute("UPDATE jugadores SET valor = ? WHERE id = ?", (nuevo_valor_proyectado, j_id))
            conn.commit()
            st.success("¡Datos actualizados!")
            st.rerun()
            
        if col_btn2.button("🗑️ Vender Jugador", key=f"sell_{j_id}"):
            nuevo_p = presupuesto + j_valor
            c.execute("DELETE FROM jugadores WHERE id = ?", (j_id,))
            c.execute("UPDATE usuarios SET presupuesto = ? WHERE id = ?", (nuevo_p, user_id))
            conn.commit()
            st.rerun()
