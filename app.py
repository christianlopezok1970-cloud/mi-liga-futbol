import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import random

st.set_page_config(page_title="Football Budget Manager", layout="wide")

# Configuración inicial de variables globales en memoria (Session State)
if "budget" not in st.session_state:
    st.session_state.budget = 50000000  # Ejemplo: 50 Millones iniciales
if "titulares" not in st.session_state:
    st.session_state.titulares = []
if "suplentes" not in st.session_state:
    st.session_state.suplentes = []

# Función para limpiar el valor de Transfermarkt (como hacías en TypeScript)
def parse_market_value(value_str):
    if not value_str or value_str in ["N/A", "-", ""]:
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
    except:
        return 0

# Función de scraping (reemplaza a Axios/Cheerio de tu server.ts)
def search_transfermarkt(player_name):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={player_name.replace(' ', '+')}"
    
    try:
        res = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Lógica para obtener el primer resultado de la tabla
        player_row = soup.find("table", class_="items")
        if player_row:
            first_player = player_row.find("td", class_="hauptlink").find("a")
            player_url = "https://www.transfermarkt.com" + first_player["href"]
            
            # Entrar al perfil del jugador
            player_res = requests.get(player_url, headers=headers)
            player_soup = BeautifulSoup(player_res.text, "html.parser")
            
            # Extraer valor de mercado
            value_div = player_soup.find("div", class_="tm-player-market-value-main")
            value_raw = value_div.text.strip() if value_div else "N/A"
            
            return {
                "name": first_player.text.strip(),
                "value_raw": value_raw,
                "value_number": parse_market_value(value_raw),
                "rating": round(random.uniform(6.5, 9.0), 1) # Simulación 365 Scores
            }
    except Exception as e:
        return None
    return None

# INTERFAZ DE USUARIO (UI)
st.title("⚽ Football Budget Manager (Streamlit)")

# Mostrar Presupuesto con formato de dinero
st.metric(label="💰 Presupuesto Restante", value=f"€ {st.session_state.budget:,}")

# Buscador
player_query = st.text_input("Buscar jugador en Transfermarkt:")
if st.button("Buscar") and player_query:
    result = search_transfermarkt(player_query)
    if result:
        st.success(f"¡Jugador encontrado: **{result['name']}**!")
        st.write(f"Valor de mercado: {result['value_raw']} (Numérico: €{result['value_number']:,})")
        st.write(f"Rating simulado 365 Scores: {result['rating']}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Fichar como Titular"):
                if st.session_state.budget >= result["value_number"] and len(st.session_state.titulares) < 11:
                    st.session_state.titulares.append(result)
                    st.session_state.budget -= result["value_number"]
                    st.rerun()
                else:
                    st.error("Presupuesto insuficiente o cupo de 11 titulares lleno.")
        with col2:
            if st.button("Fichar como Suplente"):
                if st.session_state.budget >= result["value_number"] and len(st.session_state.suplentes) < 7:
                    st.session_state.suplentes.append(result)
                    st.session_state.budget -= result["value_number"]
                    st.rerun()
                else:
                    st.error("Presupuesto insuficiente o cupo de 7 suplentes lleno.")
    else:
        st.error("No se encontró el jugador.")

# Tablas de la Plantilla
st.subheader("📋 11 Titulares")
if st.session_state.titulares:
    st.table(pd.DataFrame(st.session_state.titulares)[["name", "value_raw", "rating"]])

st.subheader("💤 Suplentes")
if st.session_state.suplentes:
    st.table(pd.DataFrame(st.session_state.suplentes)[["name", "value_raw", "rating"]])
