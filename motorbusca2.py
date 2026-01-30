import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import networkx as nx
import re

# ---------------------------
# FUNÇÕES AUXILIARES
# ---------------------------
def clean_author_string(Author):
    if pd.isna(Author):
        return []
    return [a.strip() for a in re.split(";", str(Author)) if a.strip()]

def build_coauthor_graph(df, top_n_Author=50):
    """Cria grafo de coautoria com top autores, agrupando por DOI."""
    grouped = df.groupby("DOI")["Author"].apply(lambda x: [a.strip() for sub in x for a in clean_author_string(sub)])
    all_authors = [a for sublist in grouped for a in sublist]
    freq = pd.Series(all_authors).value_counts()
    top_authors = set(freq.head(top_n_Author).index.tolist())
    
    G = nx.Graph()
    for a in top_authors:
        G.add_node(a, freq=int(freq[a]) if a in freq.index else 1)
    
    for authors in grouped:
        present = [a for a in authors if a in top_authors]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)
    return G

def calc_frac_safe(doi, autores_por_doi):
    """Evita ZeroDivisionError ao calcular autoria fracionada."""
    count = autores_por_doi.get(doi, 0)
    return 1 / count if count > 0 else 0

# ---------------------------
# CONFIGURAÇÃO DO APP
# ---------------------------
st.set_page_config(page_title="Análise Bibliográfica", layout="wide")
st.title("📚 Análise Bibliográfica — Web of Science")

# ---------------------------
# CARREGAR DADOS
# ---------------------------
caminho_arquivo = r"C:\Users\campo\Desktop\autores_completos_coords_coautores.xlsx"
df = pd.read_excel(caminho_arquivo)

colunas_usadas = ['Author', 'TipoAutor','Affiliation','Title','Year','Latitude','Longitude',
'Article Title', 'Source Title', 'Abstract', 'Publication Year','DOI','Core','Coauthors']
df = df[colunas_usadas]
str_cols = df.select_dtypes(include='object').columns

df['Publication Year'] = pd.to_numeric(df['Publication Year'], errors='coerce')

# Converte para string e substitui valores ausentes por pd.NA
for col in str_cols:
    df[col] = df[col].astype(str).replace('nan', pd.NA)
# ---------------------------
# MENU LATERAL
# ---------------------------
st.sidebar.title("Menu de Navegação")
passo = st.sidebar.radio("Selecione a seção:", ["Resumo", "Análises Estatísticas", "Gráficos"])

# ---------------------------
# ETAPA 1: RESUMO
# ---------------------------
if passo == "Resumo":
    st.subheader("📌 Resumo dos Dados")
    nan_count = df.isna().sum()
    percentual_nan = (nan_count / len(df)) * 100
    tipo_variavel = ['Numérica' if col == 'Publication Year' else 'Texto/Categórica' for col in df.columns]
    
    tabela_resumo = pd.DataFrame({
        'Coluna': df.columns,
        'Tipo Variável': tipo_variavel,
        'NaN Count': nan_count,
        'NaN %': percentual_nan
    })
    st.dataframe(tabela_resumo)

# ---------------------------
# ETAPA 2: ANÁLISES ESTATÍSTICAS
# ---------------------------
elif passo == "Análises Estatísticas":
    st.subheader("📈 Estatísticas Descritivas")

    # Publicações por Ano
    st.markdown("### 🗓️ Publicações por Ano")
    years = df['Publication Year'].dropna()
    if not years.empty:
        st.write(years.describe())

    # Autores
    st.markdown("### 🧑‍🤝‍🧑 Autores")
    author_lists = df['Author'].apply(clean_author_string)
    all_Author = [a for sublist in author_lists for a in sublist]
    Author_series = pd.Series(all_Author)
    st.write(f"Total de autores únicos: {Author_series.nunique()}")
    st.write(f"Top 10 autores:\n{Author_series.value_counts().head(10)}")

    # Abstracts
    st.markdown("### 📰 Abstracts")
    abstracts = df['Abstract'].dropna().astype(str)
    abstract_len = abstracts.apply(lambda x: len(x.split()))
    st.write(f"Média de palavras por abstract: {abstract_len.mean():.2f}")

# ---------------------------
# ETAPA 3: GRÁFICOS COM ABAS E NEUROPSICOLOGIA
# ---------------------------
elif passo == "Gráficos":
    st.subheader("📊 Visualizações Interativas")
    
    # Criar abas
    tab1, tab2, tab3, tab4,tab5,tab6,tab7= st.tabs([
        "Publicações por Ano",
        "Nuvem de Palavras",
        "Rede de Coautoria",
        "Ranking de Autores",
        "Mapa de distribuição",
        "Mapa_coautoria",
        "Mapa Animado"
    ])

    # --- Aba 1: Publicações por Ano ---
    with tab1:
        st.markdown("#### Distribuição de Publicações ao Longo dos Anos")
        years = df['Publication Year'].dropna()
        if not years.empty:
            fig_year = px.histogram(years, nbins=len(years.unique()),
                                    title="Distribuição de Publicações por Ano",
                                    labels={'value': 'Ano', 'count': 'Publicações'})
            st.plotly_chart(fig_year, use_container_width=True)

    # --- Aba 2: Nuvem de Palavras ---
    with tab2:
        st.markdown("#### Nuvem de Palavras dos Abstracts")
        text = " ".join(df['Abstract'].dropna().tolist())
        if text.strip():
            wc = WordCloud(width=800, height=400, background_color="white").generate(text)
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.imshow(wc, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig)

    # --- Aba 3: Rede de Coautoria ---
    with tab3:
        st.markdown("#### Rede de Coautoria (Top 50 autores)")
        st.sidebar.markdown("#### 🎚️ Ajuste da Rede de Coautoria")
        k_value = st.sidebar.slider("Compactação dos Nós", 0.05, 0.5, 0.15, 0.01)

        G = build_coauthor_graph(df, top_n_Author=50)
        pos = nx.spring_layout(G, seed=42, k=k_value, iterations=100)

        # Arestas
        edge_x, edge_y = [], []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'),
                                hoverinfo='none', mode='lines')

        # Nós
        node_x, node_y, hover_text, node_size = [], [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            hover_text.append(f"{node} ({G.nodes[node]['freq']} publicações)")
            node_size.append(G.nodes[node]['freq'] ** 0.8)

        node_trace = go.Scatter(x=node_x, y=node_y, mode='markers', hoverinfo='text',
                                text=hover_text,
                                marker=dict(size=node_size, color='skyblue', opacity=0.85,
                                            line=dict(width=1, color='darkblue')))

        fig_coAuthor = go.Figure(data=[edge_trace, node_trace])
        fig_coAuthor.update_layout(title=f"Rede de Coautoria (k={k_value:.2f}) — passe o mouse para ver os autores",
                                   showlegend=False, hovermode='closest',
                                   margin=dict(l=10, r=10, t=40, b=10),
                                   xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                   yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                   plot_bgcolor='white')
        st.plotly_chart(fig_coAuthor, use_container_width=True)

    # --- Aba 4: Ranking de Autores ---
    with tab4:
        st.markdown("#### Autores mais produtivos e colaborativos")

        # Contagem de autores por DOI
        autores_por_doi = df.groupby('DOI')['Author'].count().to_dict()
        df_temp = df.copy()
        df_temp['Frac'] = df_temp['DOI'].map(lambda doi: calc_frac_safe(doi, autores_por_doi))

        total_artigos = df_temp.groupby('Author')['DOI'].nunique()
        frac_autor = df_temp.groupby('Author')['Frac'].sum()

        df_rank = pd.DataFrame({
            'Autor': total_artigos.index,
            'Total Artigos': total_artigos.values,
            'Autoria Fracionada': frac_autor.values
        }).sort_values(by='Total Artigos', ascending=False).reset_index(drop=True)

        # Top 20
        top_n = 20
        df_top = df_rank.head(top_n)

        # Gráfico de colunas duplas
        fig_rank = go.Figure(data=[
            go.Bar(name='Total Artigos', x=df_top['Autor'], y=df_top['Total Artigos'], marker_color='royalblue'),
            go.Bar(name='Autoria Fracionada', x=df_top['Autor'], y=df_top['Autoria Fracionada'], marker_color='orange')
        ])
        fig_rank.update_layout(barmode='group', title='Total de Artigos x Autoria Fracionada',
                               xaxis_title='Autor', yaxis_title='Contagem', xaxis_tickangle=-45)
        st.plotly_chart(fig_rank, use_container_width=True)

        st.markdown("##### Valores detalhados")
        st.dataframe(df_top, use_container_width=True)
    # --- Aba 5: Mapa de Publicações ---
    with tab5:
        st.markdown("#### Localização das Publicações")
        
        # Verifica se existem as colunas Latitude e Longitude
        if 'Latitude' in df.columns and 'Longitude' in df.columns:
            df_map = df.dropna(subset=['Latitude', 'Longitude']).copy()
            
            # Controle para filtrar apenas autores principais, se desejar
            autor_filtro = st.selectbox("Filtrar por Autor (opcional):", ["Todos"] + sorted(df_map['Author'].unique()))
            if autor_filtro != "Todos":
                df_map = df_map[df_map['Author'] == autor_filtro]
            
            if not df_map.empty:
                fig_map = px.scatter_geo(
                    df_map,
                    lat='Latitude',
                    lon='Longitude',
                    hover_name='Author',
                    hover_data=['Article Title', 'DOI', 'Publication Year'],
                    color='Publication Year',
                    size_max=15,
                    projection="natural earth",
                    title="Mapa das Publicações"
                )
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.info("Não há dados para exibir no mapa com o filtro selecionado.")
        else:
            st.warning("As colunas 'Latitude' e 'Longitude' não estão presentes no DataFrame.")
    # --- Aba 6: Mapa + Rede de Coautoria ---
# --- Aba 6: Mapa + Rede de Coautoria com Afiliacao ---
    with tab6:
        st.markdown("#### Rede de Coautoria Georreferenciada — Top Autores com Afiliacao")
        
        if all(col in df.columns for col in ['Latitude', 'Longitude', 'Author', 'Affiliation']):
            df_map = df.dropna(subset=['Latitude', 'Longitude', 'Affiliation']).copy()
            
            # Top N autores (até 1200)
            top_n = st.slider("Top N Autores para o mapa", 5, 1200, 100, step=10)
            author_counts = df_map['Author'].value_counts().head(top_n).index.tolist()
            df_map_top = df_map[df_map['Author'].isin(author_counts)]
            
            # Construir grafo de coautoria apenas com autores no topo
            G_map = build_coauthor_graph(df_map_top, top_n_Author=top_n)
            
            # Layout baseado em coordenadas reais
            pos_map = {row['Author']: (row['Longitude'], row['Latitude'])
                       for _, row in df_map_top.drop_duplicates('Author').iterrows()
                       if row['Author'] in G_map.nodes()}
            
            # Arestas
            edge_x, edge_y = [], []
            for edge in G_map.edges():
                if edge[0] in pos_map and edge[1] in pos_map:
                    x0, y0 = pos_map[edge[0]]
                    x1, y1 = pos_map[edge[1]]
                    edge_x += [x0, x1, None]
                    edge_y += [y0, y1, None]
            
            edge_trace = go.Scattergeo(
                lon=edge_x, lat=edge_y,
                mode='lines',
                line=dict(width=1, color='blue'),
                hoverinfo='none'
            )
            
            # Nós
            node_x, node_y, hover_text, node_size = [], [], [], []
            for node in G_map.nodes():
                row = df_map_top[df_map_top['Author'] == node].iloc[0]
                if node in pos_map:
                    lon, lat = pos_map[node]
                    node_x.append(lon)
                    node_y.append(lat)
                    hover_text.append(f"{node} ({G_map.nodes[node]['freq']} publicações)<br>Afiliacao: {row['Affiliation']}")
                    node_size.append(G_map.nodes[node]['freq']**0.5 * 3)  # escala visível
            
            node_trace = go.Scattergeo(
                lon=node_x, lat=node_y,
                mode='markers',
                marker=dict(size=node_size, color='orange', line=dict(width=1, color='darkred')),
                hoverinfo='text',
                text=hover_text
            )
            
            fig_map_coauthor = go.Figure(data=[edge_trace, node_trace])
            fig_map_coauthor.update_layout(
                title=f"Rede de Coautoria Georreferenciada — Top {top_n} autores",
                geo=dict(
                    scope='world',
                    showland=True,
                    landcolor="LightGreen",
                    showcountries=True
                ),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            
            st.plotly_chart(fig_map_coauthor, use_container_width=True)
            
        else:
            st.warning("As colunas 'Latitude', 'Longitude' ou 'Affiliation' não estão presentes no DataFrame.")
# --- Aba 7: Mapa Animado das Publicações ---
# --- Aba 7: Mapa Animado das Publicações ---
    with tab7:
        st.markdown("#### 🌍 Evolução Geográfica das Publicações por Ano")
        
        if all(col in df.columns for col in ['Latitude', 'Longitude', 'Author', 'Publication Year']):
            df_map_anim = df.dropna(subset=['Latitude', 'Longitude', 'Publication Year']).copy()
            
            # Converter ano para inteiro
            df_map_anim['Publication Year'] = df_map_anim['Publication Year'].astype(int)
            
            # Ordenar os anos
            df_map_anim = df_map_anim.sort_values('Publication Year')
            
            # Selecionar Top N autores
            top_n = st.slider("Top N autores no mapa animado", 5, 500, 100, step=10)
            top_authors = df_map_anim['Author'].value_counts().head(top_n).index.tolist()
            df_map_anim_top = df_map_anim[df_map_anim['Author'].isin(top_authors)]
            
            # Para garantir que cada frame só mostre o ano correto
            df_map_anim_top['Publication Year'] = df_map_anim_top['Publication Year'].astype(str)
            
            # Mapa animado
            fig_anim = px.scatter_geo(
                df_map_anim_top,
                lat='Latitude',
                lon='Longitude',
                color='Author',
                hover_name='Author',
                hover_data={'Publication Year': True, 'Affiliation': True},
                animation_frame='Publication Year',
                size_max=12,
                projection="natural earth",
                title="Evolução das Publicações no Tempo"
            )
            
            fig_anim.update_layout(
                legend_title_text='Autor',
                margin=dict(l=10, r=10, t=40, b=10),
            )
            
            st.plotly_chart(fig_anim, use_container_width=True)
        else:
            st.warning("As colunas 'Latitude', 'Longitude', 'Author' ou 'Publication Year' não estão presentes no DataFrame.")
