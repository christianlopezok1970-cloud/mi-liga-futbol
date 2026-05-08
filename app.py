import streamlit as st
import pandas as pd
import random
import os
import json

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="AFA Manager 2026", layout="wide")

# Persistencia de usuarios en archivo local
DB_FILE = "usuarios_db.json"

def cargar_usuarios():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {"admin": "1234"}
    return {"admin": "1234"}

def guardar_usuario(user, password):
    usuarios = cargar_usuarios()
    usuarios[user] = password
    with open(DB_FILE, "w") as f:
        json.dump(usuarios, f)

# --- 2. LOGIN Y REGISTRO AUTOMÁTICO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'ultimo_giro' not in st.session_state:
    st.session_state.ultimo_giro = None

if not st.session_state.autenticado:
    with st.sidebar:
        st.title("🛡️ ACCESO / REGISTRO")
        st.info("Si no tienes cuenta, ingresa un usuario y clave para registrarte.")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar / Crear Cuenta"):
            if u and p:
                usuarios = cargar_usuarios()
                if u in usuarios:
                    if usuarios[u] == p:
                        st.session_state.autenticado = True
                        st.session_state.usuario = u
                        st.rerun()
                    else:
                        st.error("Contraseña incorrecta.")
                else:
                    guardar_usuario(u, p)
                    st.session_state.autenticado = True
                    st.session_state.usuario = u
                    st.success(f"¡Usuario {u} registrado!")
                    st.rerun()
            else:
                st.warning("Completa ambos campos.")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ2VmykJ-6g-KVHVS3doLPVdxGA09KgOByjy67lnJW-VlJxLWgukpKAUM1PmeTOKbPtH1fNDSUyCBTO/pub?output=csv"
    try:
        df = pd.read_csv(url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame(columns=["Jugador", "POS", "Nivel", "Equipo", "Score"])

df_base = load_data()

# --- 4. ESTADO DEL JUEGO ---
if 'creditos' not in st.session_state: st.session_state.creditos = 1000
if 'titulares' not in st.session_state: st.session_state.titulares = []
if 'suplentes' not in st.session_state: st.session_state.suplentes = []
if 'historial' not in st.session_state: st.session_state.historial = []

# --- 5. LÓGICA Y TU ARREGLO DE ESTRELLAS ---
def formato_nivel(n):
    try: 
        n = int(n)
    except: 
        return f"{n}★"
    
    # Tu arreglo con los colores solicitados
    if n == 5: return "★★★★★"
    if n == 4: return "★★★★"
    if n == 3: return "★★★"
    if n == 2: return "★★"
    if n == 1: return "★"
    return f"{n}★"

def ordenar_titulares():
    # Orden táctico: Arquero -> Defensor -> Volante -> Delantero
    orden = {'ARQ': 0, 'DEF': 1, 'VOL': 2, 'DEL': 3}
    st.session_state.titulares.sort(key=lambda x: orden.get(x['POS'], 99))

# --- 6. PANEL LATERAL (SIDEBAR) ---
with st.sidebar:
    st.write(f"🎮 **Manager:** {st.session_state.usuario}")
    st.metric("Presupuesto", f"{st.session_state.creditos} c")
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    st.divider()
    
    # RULETA (Ahora visible)
    st.subheader("🎡 Ruleta de Créditos")
    if st.session_state.ultimo_giro is not None:
        res = st.session_state.ultimo_giro
        if res > 0: st.success(f"¡Último giro: +{res}c! 🤑")
        elif res < 0: st.error(f"¡Último giro: {res}c! 💸")
        else: st.info("¡Último giro: 0c! 😐")

    if st.button("GIRAR RULETA 🎲"):
        resultado = random.choices([0, 1, -1, 3], weights=[0.50, 0.25, 0.20, 0.05])[0]
        st.session_state.creditos += resultado
        st.session_state.ultimo_giro = resultado
        st.session_state.historial.insert(0, f"Ruleta: {resultado}c")
        st.rerun()

    st.divider()
    
    # MERCADO DE PACKS
    if st.button("🛒 COMPRAR PACK (100c)"):
        if st.session_state.creditos >= 100:
            if len(st.session_state.suplentes) < 25:
                st.session_state.creditos -= 100
                st.session_state.ultimo_giro = None
                nuevos = df_base.sample(n=2).to_dict('records')
                st.session_state.suplentes.extend(nuevos)
                st.session_state.historial.insert(0, f"Pack: {nuevos[0]['Jugador']} y {nuevos[1]['Jugador']}")
                st.toast("¡Pack abierto!")
                st.rerun()
            else:
                st.warning("Banco lleno (Máx 25)")
        else:
            st.error("Créditos insuficientes")

# --- 7. CUERPO PRINCIPAL ---
st.title("⚽ AFA Manager Pro 2026")

# Listado Titulares (Compacto)
st.subheader("🔝 Once Titular (1-4-4-2)")
if st.session_state.titulares:
    ordenar_titulares()
    df_t = pd.DataFrame(st.session_state.titulares)
    df_t['Rareza'] = df_t['Nivel'].apply(formato_nivel)
    st.dataframe(
        df_t[['POS', 'Jugador', 'Equipo', 'Rareza', 'Score']], 
        use_container_width=True, 
        hide_index=True, 
        height=422
    )
    
    quitar = st.selectbox("Mandar al banco:", [j['Jugador'] for j in st.session_state.titulares], key="q_tit")
    if st.button("Bajar al banco ⬇️"):
        idx = next(i for i, j in enumerate(st.session_state.titulares) if j['Jugador'] == quitar)
        st.session_state.suplentes.append(st.session_state.titulares.pop(idx))
        st.rerun()
else:
    st.info("Armá tu equipo seleccionando jugadores del banco.")

st.divider()

# Listado Suplentes (Compacto)
st.subheader("⏬ Banco de Suplentes")
if st.session_state.suplentes:
    df_s = pd.DataFrame(st.session_state.suplentes)
    df_s['Rareza'] = df_s['Nivel'].apply(formato_nivel)
    st.dataframe(
        df_s[['Jugador', 'POS', 'Rareza', 'Equipo']], 
        use_container_width=True, 
        hide_index=True, 
        height=300
    )

    c1, c2 = st.columns(2)
    with c1:
        st.write("**Táctica**")
        subir = st.selectbox("Subir al Once:", [j['Jugador'] for j in st.session_state.suplentes], key="s_sup")
        if st.button("Poner de Titular ⬆️"):
            idx = next(i for i, j in enumerate(st.session_state.suplentes) if j['Jugador'] == subir)
            j = st.session_state.suplentes[idx]
            conteo = [p['POS'] for p in st.session_state.titulares].count(j['POS'])
            limites = {'ARQ': 1, 'DEF': 4, 'VOL': 4, 'DEL': 2}
            
            if conteo < limites.get(j['POS'], 0):
                st.session_state.titulares.append(st.session_state.suplentes.pop(idx))
                st.rerun()
            else:
                st.error(f"Límite de {j['POS']} alcanzado.")

    with c2:
        st.write("**Ventas**")
        vender = st.selectbox("Vender Jugador:", [j['Jugador'] for j in st.session_state.suplentes], key="v_sup")
        if st.button("VENDER JUGADOR 💰"):
            idx = next(i for i, j in enumerate(st.session_state.suplentes) if j['Jugador'] == vender)
            pago = int(st.session_state.suplentes[idx]['Nivel']) * 20
            st.session_state.creditos += pago
            st.session_state.historial.insert(0, f"Venta: {st.session_state.suplentes[idx]['Jugador']} (+{pago}c)")
            st.session_state.suplentes.pop(idx)
            st.rerun()

with st.expander("📜 Ver Historial de Movimientos"):
    for h in st.session_state.historial:
        st.write(f"- {h}")
