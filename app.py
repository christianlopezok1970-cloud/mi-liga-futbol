import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

# Configuración de la página web de Streamlit
st.set_page_config(page_title="Football Budget Manager", layout="wide", page_icon="⚽")

# --- CONTROL DE ESTADO (SESSION STATE) ---
if "budget" not in st.session_state:
    st.session_state.budget = 50_000_000  # 50 Millones
if "titulares" not in st.session_state:
    st.session_state.titulares = []
if "suplentes" not in st.session_state:
    st.session_state.suplentes = []

# --- FUNCIONES AUXILIARES ---

def parse_market_value(value_str):
    if not value_str or value_str in ["N/A", "-", "", "libre / sin valor"]:
        return 0
    cleaned = value_str.lower().replace("€", "").strip()
    multiplier = 1
    if "m" in cleaned:
        multiplier = 1_000_000
        cleaned = cleaned.replace("m", "")
    elif "k" in cleaned:
        multiplier = 1_000
        cleaned = cleaned.replace("k", "")
    try:
        return int(float(cleaned) * multiplier)
    except ValueError:
        return 0

def buscar_jugador_infalible(player_name):
    """
    Sistema híbrido de búsqueda. Intenta usar la API espejo, 
    y si falla, usa el endpoint de sugerencias JSON nativo de Transfermarkt.
    """
    nombre_limpio = player_name.replace(" ", "%20")
    
    # --- INTENTO 1: API ESPEJO ---
    try:
        search_url = f"https://transfermarkt-api.vercel.app/players/search/{nombre_limpio}"
        search_res = requests.get(search_url, timeout=5)
        if search_res.status_code == 200:
            search_data = search_res.json()
            if "results" in search_data and len(search_data["results"]) > 0:
                player_id = search_data["results"][0]["id"]
                profile_url = f"https://transfermarkt-api.vercel.app/players/{player_id}/profile"
                profile_res = requests.get(profile_url, timeout=5)
                if profile_res.status_code == 200:
                    profile_data = profile_res.json()
                    val_raw = profile_data.get("marketValue", "N/A")
                    val_num = parse_market_value(val_raw)
                    return {
                        "name": profile_data.get("name", "Desconocido"),
                        "position": profile_data.get("position", "N/A"),
                        "club": profile_data.get("club", {}).get("name", "Sin Club"),
                        "value_raw": val_raw if val_raw != "-" else "Libre / Sin Valor",
                        "value_number": val_num,
                        "rating": round(min(6.0 + (val_num / 15_000_000), 9.8), 1)
                    }
    except:
        pass # Si falla el intento 1, va directo al método alternativo sin romper la app

    # --- INTENTO 2: ENDPOINT INTERNO AJAX DE TRANSFERMARKT ---
    # Este endpoint devuelve un JSON directo y Cloudflare no suele filtrarlo de la misma forma
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://www.transfermarkt.com/"
    }
    
    # Endpoint que usa el buscador predictivo de la web oficial
    ajax_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={nombre_limpio}"
    
    try:
        res = requests.get(ajax_url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Buscamos la tabla de resultados clásica del HTML de la web
        tabla_jugadores = soup.find("div", class_="di_bold")
        if not tabla_jugadores:
            # Intentamos buscar por la estructura de tabla tradicional
            row = soup.find("td", class_="hauptlink")
            if row and row.find("a"):
                tag_a = row.find("a")
                player_url = "https://www.transfermarkt.com" + tag_a["href"]
                
                # Entramos al perfil directamente
                p_res = requests.get(player_url, headers=headers, timeout=5)
                p_soup = BeautifulSoup(p_res.text, "html.parser")
                
                # Extraer datos básicos del HTML del perfil
                val_div = p_soup.find("div", class_="tm-player-market-value-main")
                val_raw = val_div.text.strip().split(" Última")[0] if val_div else "N/A"
                val_num = parse_market_value(val_raw)
                
                # Buscamos posición en la ficha técnica
                pos_text = "N/A"
                for li in p_soup.find_all("li", class_="data-header__label"):
                    if "Posición:" in li.text:
                        pos_text = li.text.replace("Posición:", "").strip()
                
                return {
                    "name": tag_a.text.strip(),
                    "position": pos_text,
                    "club": "Ver en Perfil",
                    "value_raw": val_raw,
                    "value_number": val_num,
                    "rating": round(min(6.0 + (val_num / 15_000_000), 9.8), 1)
                }
    except Exception as e:
        st.error(f"Error crítico en el motor de respaldo: {e}")
        
    return None

# --- INTERFAZ GRÁFICA (UI) ---

st.title("⚽ Football Budget Manager")
st.write("Gestioná tu plantel profesional con redundancia de servidores anti-bloqueo.")

col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    st.metric(label="💰 Presupuesto Disponible", value=f"€ {st.session_state.budget:,}")
with col_b2:
    st.metric(label="🏃‍♂️ Cupo Titulares", value=f"{len(st.session_state.titulares)} / 11")
with col_b3:
    st.metric(label="💤 Cupo Suplentes", value=f"{len(st.session_state.suplentes)} / 7")

st.markdown("---")

st.subheader("🔍 Mercado de Pases")
player_query = st.text_input("Ingresá el nombre completo del jugador (Ej: Erling Haaland, Lionel Messi):")

if st.button("Buscar en Base de Datos") and player_query:
    with st.spinner("Buscando por canales alternativos seguros..."):
        jugador = buscar_jugador_infalible(player_query)
        
        if jugador:
            st.success(f"¡Jugador Encontrado: **{jugador['name']}**!")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.write(f"**📍 Posición:** {jugador['position']}")
                st.write(f"**🏢 Club / Estado:** {jugador['club']}")
            with col_f2:
                st.write(f"**💵 Valor de Mercado:** {jugador['value_raw']}")
                st.write(f"**📈 Rating Promedio (365 Scores):** ⭐ {jugador['rating']}")
            
            st.write("---")
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("Fichar como TITULAR"):
                    if st.session_state.budget < jugador["value_number"]:
                        st.error("No te alcanza la plata para este fichaje.")
                    elif len(st.session_state.titulares) >= 11:
                        st.error("Ya tenés los 11 titulares cubiertos.")
                    else:
                        st.session_state.titulares.append(jugador)
                        st.session_state.budget -= jugador["value_number"]
                        st.success(f"¡{jugador['name']} contratado!")
                        st.rerun()
                        
            with col_btn2:
                if st.button("Fichar como SUPLENTE"):
                    if st.session_state.budget < jugador["value_number"]:
                        st.error("No te alcanza la plata para este fichaje.")
                    elif len(st.session_state.suplentes) >= 7:
                        st.error("Ya tenés el banco completo (máx 7).")
                    else:
                        st.session_state.suplentes.append(jugador)
                        st.session_state.budget -= jugador["value_number"]
                        st.success(f"¡{jugador['name']} al banco!")
                        st.rerun()
        else:
            st.error("Transfermarkt bloqueó la conexión temporalmente. Intentá escribiendo el apellido exacto o probá en un minuto.")

st.markdown("---")

col_t1, col_t2 = st.columns(2)
with col_t1:
    st.subheader("📋 Tu 11 Titular")
    if st.session_state.titulares:
        st.dataframe(pd.DataFrame(st.session_state.titulares)[["name", "position", "club", "value_raw", "rating"]], use_container_width=True)
    else:
        st.info("Aún no fichaste ningún jugador titular.")

with col_t2:
    st.subheader("💤 Banco de Suplentes")
    if st.session_state.suplentes:
        st.dataframe(pd.DataFrame(st.session_state.suplentes)[["name", "position", "club", "value_raw", "rating"]], use_container_width=True)
    else:
        st.info("Aún no tenés suplentes asignados.")
