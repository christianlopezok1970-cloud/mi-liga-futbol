@st.cache_data(ttl=300)
def cargar_mercado_oficial(url):
    try:
        # Leemos el CSV
        df = pd.read_csv(url)
        
        # --- ESTO SOLUCIONA EL ERROR ---
        # 1. Quitamos espacios vacíos alrededor de los nombres de las columnas
        df.columns = df.columns.str.strip()
        
        # 2. Convertimos todo a minúsculas y luego ponemos la primera en mayúscula
        # para que coincida con nuestro código (Nombre, Club, Posicion, Precio)
        df.columns = df.columns.str.capitalize()
        
        # Si tu columna se llama "Posición" (con tilde), la normalizamos a "Posicion"
        df.rename(columns={'Posición': 'Posicion'}, inplace=True)
        
        return df
    except Exception as e:
        st.error(f"Error al cargar el Excel: {e}")
        return None
