import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
import re
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urlparse
from pathlib import Path

# Cargar el CSS desde el archivo
def load_css():
    css_file = Path(__file__).parent / "styles" / "styles.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def main():
    # Cargar CSS
    load_css()
    

    
    # Footer
    st.markdown("""
    <div class='footer' style="text-align: center; margin-top: 20px;">
        <img src="images/Captura de pantalla 2024-11-23 172217.png" alt="Logo" style="width: 100px;"><br>
        <p>Desarrollado con ❤️ por Marce Data</p>
    </div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

# Leer API_KEY desde secrets.toml
API_KEY = st.secrets["API_KEY"]

# Lista de dominios a excluir
EXCLUDED_DOMAINS = ["tripadvisor.com", "yelp.com", "booking.com"]

# Rotación de User-Agent
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0 Safari/537.36'
]

# Validación de URL
def is_valid_url(url):
    parsed = urlparse(url)
    if not (bool(parsed.netloc) and bool(parsed.scheme)):
        return False
    for domain in EXCLUDED_DOMAINS:
        if domain in parsed.netloc:
            return False
    return True

# Búsqueda con SerpAPI
def search_google(query, api_key, lat=None, lon=None, radius=10, num_results=10):
    search_url = "https://serpapi.com/search"
    
    # Parámetros base
    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query.strip(),  # Eliminar espacios extras
        "num": num_results,
        "hl": "es",  # Idioma español
        "gl": "ar",  # País Argentina
    }
    
    if lat and lon:
        # Usar "Mar del Plata, Argentina" como ubicación para búsquedas en esa área
        params["location"] = "Mar del Plata, Buenos Aires, Argentina"
        
        # Agregar las coordenadas como parte de la consulta
        params["q"] = f"{query.strip()} cerca de Mar del Plata"
        
        if radius:
            params["radius"] = f"{radius}000"  # Convertir km a metros
    
    try:
        st.write("Parámetros de búsqueda:", params)  # Debug info
        
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        
        # Debug info
        st.write("Status Code:", response.status_code)
        st.write("URL final:", response.url)
        
        data = response.json()
        if "error" in data:
            st.error(f"Error de SerpAPI: {data['error']}")
            return []
            
        # Intentar obtener diferentes tipos de resultados
        all_results = []
        
        # Obtener resultados orgánicos
        organic_results = data.get("organic_results", [])
        for result in organic_results:
            if "link" in result and is_valid_url(result["link"]):
                all_results.append(result["link"])
                
        # Obtener resultados locales si están disponibles
        local_results = data.get("local_results", [])
        for result in local_results:
            if "website" in result and is_valid_url(result["website"]):
                all_results.append(result["website"])
        
        st.write(f"Total de URLs encontradas: {len(all_results)}")
        return list(set(all_results))  # Eliminar duplicados
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error en la petición HTTP: {str(e)}")
        if 'response' in locals():
            st.write("Respuesta completa:", response.text)
        return []
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return []

# Extracción de correos electrónicos
def extract_emails_from_html(html):
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return set(re.findall(email_regex, html))

# Proceso de URLs
def process_url(url):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        time.sleep(2)  # Retraso entre solicitudes
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            emails = extract_emails_from_html(response.text)
            return emails
    except Exception as e:
        print(f"Error al procesar {url}: {e}")
    return []

# Scraping de correos desde URLs
def scrape_emails_from_urls(urls):
    emails = set()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_url, url) for url in urls]
        for future in futures:
            emails.update(future.result() or [])
    return emails

# Interfaz de usuario en Streamlit
st.title("Scraping de Correos Electrónicos con Filtro Geográfico")

# Entrada del usuario
query = st.text_input("Consulta de búsqueda")
radius = st.slider("Radio de búsqueda (en km):", 1, 50, 10)
num_results = st.number_input("Número de resultados:", min_value=1, max_value=100, value=10)

# Inicializar el mapa con Folium
st.subheader("Selecciona un punto en el mapa para filtrar los resultados")
m = folium.Map(location=[-38.0, -57.5], zoom_start=11)  # Centrado en Mar del Plata
m.add_child(folium.LatLngPopup())

# Renderizar el mapa usando st_folium
map_data = st_folium(m, height=600)

# Botón de búsqueda y procesamiento
if st.button("Buscar correos"):
    if not query:
        st.warning("Por favor, ingresa una consulta de búsqueda.")
    elif map_data['last_clicked']:
        lat = map_data['last_clicked']['lat']
        lon = map_data['last_clicked']['lng']
        
        st.write(f"Ubicación seleccionada: Latitud {lat}, Longitud {lon}")
        
        with st.spinner('Buscando resultados...'):
            urls = search_google(query, API_KEY, lat, lon, radius, num_results)
            
            if urls:
                st.write(f"URLs encontradas: {len(urls)}")
                emails = scrape_emails_from_urls(urls)
                
                if emails:
                    df = pd.DataFrame({"Correo Electrónico": list(emails)})
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("Descargar correos como CSV", csv, "emails.csv", "text/csv")
                else:
                    st.warning("No se encontraron correos en las URLs procesadas.")
            else:
                st.warning("No se encontraron URLs para procesar.")
    else:
        st.warning("Haz clic en el mapa para seleccionar una ubicación.")
