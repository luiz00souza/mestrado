import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import tempfile
import os

# Configuração da página
st.set_page_config(page_title="Visualizador de Shapefiles", layout="wide")

st.title("Visualizador de Shapefiles - Seus Arquivos")

# Upload dos arquivos do shapefile
uploaded_files = st.file_uploader(
    "Faça upload dos arquivos do shapefile (.shp, .shx, .dbf, .prj)", 
    type=["shp", "shx", "dbf", "prj"], 
    accept_multiple_files=True
)

# Definir uma lista de cores para as camadas
cores = ["blue", "green", "red", "purple", "orange", "darkblue", "darkgreen", "darkred", "pink", "darkpurple"]

if uploaded_files:
    # Criar um diretório temporário para salvar os arquivos
    with tempfile.TemporaryDirectory() as tmpdir:
        file_paths = {}

        # Salvar os arquivos temporariamente
        for uploaded_file in uploaded_files:
            file_path = os.path.join(tmpdir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            file_paths[uploaded_file.name.split(".")[-1]] = file_path

        # Verificar se temos os arquivos essenciais (.shp, .shx, .dbf)
        required_extensions = ["shp", "shx", "dbf"]
        if all(ext in file_paths for ext in required_extensions):
            # Criar o mapa inicial
            shp_path = file_paths["shp"]
            gdf = gpd.read_file(shp_path)
            
            # Criar um mapa centralizado na média dos centroides das geometrias
            center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
            m = folium.Map(location=center, zoom_start=6)

            # Adicionar os shapefiles ao mapa com cores diferentes
            color_index = 0
            for uploaded_file in uploaded_files:
                if uploaded_file.name.endswith('.shp'):
                    shp_path = os.path.join(tmpdir, uploaded_file.name)
                    gdf = gpd.read_file(shp_path)

                    # Escolher um atributo para ser exibido no popup (pega a primeira coluna não-geométrica)
                    atributo_legenda = gdf.columns[0] if len(gdf.columns) > 1 else "Sem Atributos"

                    # Definir a cor para a camada
                    cor = cores[color_index % len(cores)]  # A cor será alternada entre as cores definidas
                    color_index += 1

                    # Adicionar cada shapefile ao mapa com a cor definida
                    geojson = folium.GeoJson(
                        gdf,
                        name=f"Camada {uploaded_file.name}",
                        tooltip=folium.GeoJsonTooltip(fields=[atributo_legenda], aliases=["Atributo:"]),
                        popup=folium.GeoJsonPopup(fields=[atributo_legenda]),
                        style_function=lambda feature, cor=cor: {
                            "fillColor": cor,
                            "color": "black",
                            "weight": 1,
                            "fillOpacity": 0.5,
                        },
                    ).add_to(m)

            # Adicionar um controle de camadas
            folium.LayerControl().add_to(m)

            # Criar uma legenda personalizada
            legenda_html = """
            <div style="
                position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 100px; 
                background-color: white; z-index:9999; font-size:14px;
                border:2px solid black; padding: 10px;">
                <b>Legenda:</b><br>
                <i style="background:blue; width:10px; height:10px; display:inline-block;"></i> Área do Shapefile<br>
                <i style="background:black; width:10px; height:10px; display:inline-block;"></i> Contorno
            </div>
            """
            m.get_root().html.add_child(folium.Element(legenda_html))

            # Exibir o mapa no Streamlit
            st_folium(m, width=800, height=500)
        else:
            st.error("Os arquivos .shp, .shx e .dbf são obrigatórios para carregar o shapefile.")
