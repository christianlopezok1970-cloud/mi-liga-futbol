import streamlit as st
import requests
import pandas as pd

# Configuración de la página web de Streamlit
st.set_page_config(page_title="Football Budget Manager", layout="wide", page_icon="⚽")

# --- CONTROL DE ESTADO (SESSION STATE) ---
# Inicializamos las variables en memoria si es la primera vez que se ejecuta la app
if "budget" not in st.session_state:
    st.session_state.budget = 50_000_000  # Presupuesto inicial: 50 Millones
if "titulares" not in st.session_state:
    st.session_state.titulares = []
if "suplentes" not in st.session_state:
    st.session_state.suplentes = []

# --- FUNCIONES AUXILIARES ---

def parse_market_value(value_str):
    """
    Convierte el texto de valor de mercado (ej: '€15.00m' o '€500k') 
    en un número entero operable matemáticamente.
    """
    if not value_str or value_str in ["N/A", "-", ""]:
        return 0
    
    # Limpiamos el string dejando solo los números, puntos y letras multiplicadoras
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

def buscar_jugador_api(player_name):
    """
    Se conecta a la API espejo de Transfermarkt para buscar al jugador, 
    extraer su ID, y luego traer su perfil completo con el valor real.
    """
    # 1. Endpoint de búsqueda por texto
    search_url = f"https://transfermarkt-api.vercel.app/players/search/{player_name.replace(' ', '%20')}"
    
    try:
        search_res = requests.get(search_url)
        if search_res.status_code == 200:
            search_data = search_res.json()
            
            # Verificamos si la API devolvió resultados válidos
            if "results" in search_data and len(search_data["results"]) > 0:
                primer_resultado = search_data["results"][0]
                player_id = primer_resultado["id"]
                
                # 2. Con el ID del jugador, consultamos su perfil específico para el valor exacto
                profile_url = f"https://transfermarkt-api.vercel.app/players/{player_id}/profile"
                profile_res = requests.get(profile_url)
                
                if profile_res.status_code == 200:
                    profile_data = profile_res.json()
                    
                    value_raw = profile_data.get("marketValue", "N/A")
                    value_numeric = parse_market_value(value_raw)
                    
                    # Simulación de puntaje 365 Scores (entre 6.0 y 9.5) basado en su valor
                    base_rating = 6.0 + (value_numeric / 15_000_000)
                    rating_final = round(min(base_rating, 9.8), 1)
                    
                    return {
                        "name": profile_data.get("name", "Desconocido"),
                        "position": profile_data.get("position", "N/A"),
                        "club": profile_data.get("club", {}).get("name", "Sin Club"),
                        "value_raw": value_raw if value_raw != "-" else "Libre / Sin Valor",
                        "value_number": value_numeric,
                        "rating": rating_final
                    }
        return None
    except Exception as e:
        st.error(class_name=f"Error de conexión con el servidor de datos: {e}")
        return None

# --- INTERFAZ GRÁFICA (UI) ---

st.title("⚽ Football Budget Manager")
st.write("Gestioná tu plantel profesional con datos en tiempo real sin bloqueos.")

# Fila superior de estadísticas en tiempo real
col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    st.metric(label="💰 Presupuesto Disponible", value=f"€ {st.session_state.budget:,}")
with col_b2:
    total_titulares = len(st.session_state.titulares)
    st.metric(label="🏃‍♂️ Cupo Titulares", value=f"{total_titulares} / 11")
with col_b3:
    total_suplentes = len(st.session_state.suplentes)
    st.metric(label="💤 Cupo Suplentes", value=f"{total_suplentes} / 7")

st.markdown("---")

# Buscador de jugadores
st.subheader("🔍 Mercado de Pases")
player_query = st.text_input("Ingresá el nombre del jugador real que querés buscar:")

if st.button("Buscar en Base de Datos") and player_query:
    with st.spinner("Conectando con Transfermarkt..."):
        jugador = buscar_jugador_api(player_query)
        
        if jugador:
            st.success(f"¡Jugador Encontrado: **{jugador['name']}**!")
            
            # Mostramos la ficha técnica del jugador encontrado
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                st.write(f"**📍 Posición:** {jugador['position']}")
                st.write(f"**🏢 Club Actual:** {jugador['club']}")
            with col_f2:
                st.write(f"**💵 Valor de Mercado:** {jugador['value_raw']}")
                st.write(f"**📈 Rating Promedio (365 Scores):** ⭐ {jugador['rating']}")
            
            # Acciones de fichaje
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
                        st.success(f"¡{jugador['name']} agregado a los titulares!")
                        st.rerun()
                        
            with col_btn2:
                if st.button("Fichar como SUPLENTE"):
                    if st.session_state.budget < jugador["value_number"]:
                        st.error("No te alcanza la plata para este fichaje.")
                    elif len(st.session_state.suplentes) >= 7:
                        st.error("Ya tenés el banco de suplentes completo (máx 7).")
                    else:
                        st.session_state.suplentes.append(jugador)
                        st.session_state.budget -= jugador["value_number"]
                        st.success(f"¡{jugador['name']} agregado al banco!")
                        st.rerun()
        else:
            st.error("No se encontraron resultados para ese nombre o el servidor está saturado. Intentá con otro nombre.")

st.markdown("---")

# --- VISUALIZACIÓN DEL EQUIPO ACTUAL ---

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("📋 Tu 11 Titular")
    if st.session_state.titulares:
        df_titulares = pd.DataFrame(st.session_state.titulares)
        st.dataframe(df_titulares[["name", "position", "club", "value_raw", "rating"]], use_container_width=True)
    else:
        st.info("Aún no fichaste ningún jugador titular.")

with col_t2:
    st.subheader("💤 Banco de Suplentes")
    if st.session_state.suplentes:
        df_suplentes = pd.DataFrame(st.session_state.suplentes)
        st.dataframe(df_suplentes[["name", "position", "club", "value_raw", "rating"]], use_container_width=True)
    else:
        st.info("Aún no tenés suplentes asignados.")
