import pandas as pd 
import folium
from streamlit_folium import folium_static
import streamlit as st
import rasterio
import numpy as np
from folium.plugins import Fullscreen, MarkerCluster
import tempfile
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Função para carregar o raster, aplicar uma escala de cores e exibir no mapa
def display_raster(uploaded_file, colormap='viridis'):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    with rasterio.open(tmp_path) as src:
        bounds = src.bounds
        array = src.read(1)  # Lendo a primeira banda

    # Normalizando para valores entre 0 e 1
    array_norm = (array - np.nanmin(array)) / (np.nanmax(array) - np.nanmin(array))

    # Aplicando o colormap escolhido
    cmap = plt.get_cmap(colormap)
    array_colored = cmap(array_norm)

    # Convertendo para uma imagem RGB
    array_colored = (array_colored[:, :, :3] * 255).astype(np.uint8)
    img = Image.fromarray(array_colored)

    # Salvando a imagem gerada
    img_path = tmp_path + ".png"
    img.save(img_path)

    # Criando o mapa folium
    m = folium.Map(location=[(bounds.top + bounds.bottom) / 2, (bounds.left + bounds.right) / 2], zoom_start=10)
    Fullscreen().add_to(m)

    # Adicionando o raster ao mapa como imagem sobreposta
    img_overlay = folium.raster_layers.ImageOverlay(
        image=img_path,
        bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
        opacity=0.6,
        interactive=True,
        cross_origin=False
    )
    img_overlay.add_to(m)

    return m

# Função para exibir prévia do colormap
def show_colormap_preview(colormap):
    cmap = plt.get_cmap(colormap)
    gradient = np.linspace(0, 1, 256).reshape(1, -1)
    gradient = np.vstack((gradient, gradient))
    plt.imshow(gradient, aspect='auto', cmap=cmap)
    plt.axis('off')
    st.pyplot(plt)

# Função para gerar o mapa com clusterização de marcadores

def generate_map_with_clusters(df):
    # Garantir que Latitude e Longitude sejam float, removendo valores inválidos
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Remover linhas onde Latitude ou Longitude são NaN
    df = df.dropna(subset=["Latitude", "Longitude"])

    # Verificar se o DataFrame não está vazio antes de calcular a média
    if df.empty:
        return folium.Map(location=[0, 0], zoom_start=2)  # Mapa padrão se não houver dados válidos

    # Criar o mapa centralizado na média das coordenadas
    mapa = folium.Map(location=[df["Latitude"].mean(), df["Longitude"].mean()], zoom_start=5)
    
    # Criar o agrupamento de marcadores
    marker_cluster = MarkerCluster().add_to(mapa)

    # Adicionar marcadores ao cluster
    for _, row in df.iterrows():
        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=f"{row['Tipo de Fundo']} - {row['Classificação Biogênica']}",
            icon=folium.Icon(color="blue")
        ).add_to(marker_cluster)

    return mapa


# Configuração do app
st.set_page_config(page_title="Cadastro de Dados Marinhos", layout="centered")
st.title("🌊 Cadastro de Dados Marinhos - Iemanjá 🌊")

# Inicializa a sessão de dados
if "dados" not in st.session_state:
    st.session_state.dados = []

# Opções de entrada de dados
opcao = st.radio("Como deseja inserir os dados?", ("Inserir Manualmente", "Carregar Arquivo CSV"))

if opcao == "Inserir Manualmente":
    with st.form("entrada_dados"):
        st.subheader("📌 Inserir Novo Ponto")

        latitude = st.number_input("Latitude", format="%.6f", min_value=-90.0, max_value=90.0)
        longitude = st.number_input("Longitude", format="%.6f", min_value=-180.0, max_value=180.0)

        tipo_fundo = st.selectbox("Tipo de Fundo", ["Sand", "Mud","Coarse","Mixed","Hard/Rock"])
        classificacao_biogenica = st.selectbox("Classificação Biogênica", ["Terrigenous", "Biogenic","Rhodolite","Recifal"])

        submitted = st.form_submit_button("Adicionar Ponto")

        if submitted:
            novo_dado = {
                "Latitude": latitude,
                "Longitude": longitude,
                "Tipo de Fundo": tipo_fundo,
                "Classificação Biogênica": classificacao_biogenica
            }
            st.session_state.dados.append(novo_dado)
            st.success("✅ Ponto cadastrado com sucesso!")

elif opcao == "Carregar Arquivo CSV":
    st.subheader("📂 Enviar Arquivo CSV")
    uploaded_file = st.file_uploader("Escolha um arquivo CSV", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            try:
                df_uploaded = pd.read_csv(uploaded_file, encoding="ISO-8859-1")
            except Exception as e:
                st.error(f"❌ Erro ao carregar o arquivo: {e}")
                df_uploaded = None
        
        if df_uploaded is not None:
            st.write("Pré-visualização dos dados carregados:")
            st.dataframe(df_uploaded.head())

            colunas_disponiveis = df_uploaded.columns.tolist()
            
            col_latitude = st.selectbox("Selecione a coluna para Latitude", colunas_disponiveis)
            col_longitude = st.selectbox("Selecione a coluna para Longitude", colunas_disponiveis)
            col_tipo_fundo = st.selectbox("Selecione a coluna para Tipo de Fundo", colunas_disponiveis)
            col_class_biogenica = st.selectbox("Selecione a coluna para Classificação Biogênica", colunas_disponiveis)

            if st.button("Carregar Dados"):
                df_mapeado = df_uploaded[[col_latitude, col_longitude, col_tipo_fundo, col_class_biogenica]].copy()
                df_mapeado.columns = ["Latitude", "Longitude", "Tipo de Fundo", "Classificação Biogênica"]
                st.session_state.dados.extend(df_mapeado.to_dict(orient="records"))
                st.success("✅ Dados carregados com sucesso!")

# Exibir tabela com os dados inseridos
if st.session_state.dados:
    df = pd.DataFrame(st.session_state.dados)
    st.subheader("📋 Dados Inseridos")
    st.dataframe(df)

    # Botão para baixar os dados como CSV
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ Baixar CSV",
        data=csv,
        file_name="dados_marinhos.csv",
        mime="text/csv"
    )

    # Botão para gerar mapa
    if st.button("📍 Gerar Mapa"):
        st.subheader("🗺️ Mapa dos Pontos Cadastrados")
        mapa = generate_map_with_clusters(df)
        folium_static(mapa)

uploaded_file = st.file_uploader("Faça upload de um arquivo raster", type=["tif"])

# Opções de colormap
colormap_option = st.selectbox("Escolha a escala de cores", ['viridis', 'inferno', 'plasma', 'cividis', 'jet'])

# Mostrar prévia do colormap escolhido
show_colormap_preview(colormap_option)

if uploaded_file:
    mapa = display_raster(uploaded_file, colormap=colormap_option)
    st.components.v1.html(mapa._repr_html_(), height=600)
