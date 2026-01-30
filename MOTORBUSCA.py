
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
def clean_author_string(authors):
    if pd.isna(authors):
        return []
    return [a.strip() for a in re.split(";", str(authors)) if a.strip()]

def build_coauthor_graph(df, top_n_authors=50):
    """Cria um grafo de coautoria baseado nos autores mais frequentes."""
    author_lists = df["Authors"].fillna("").apply(clean_author_string)
    all_authors = [auth for sub in author_lists for auth in sub]
    freq = pd.Series(all_authors).value_counts()
    top_authors = set(freq.head(top_n_authors).index.tolist())
    
    G = nx.Graph()
    for a in top_authors:
        G.add_node(a, freq=int(freq[a]) if a in freq.index else 1)
    for authors in author_lists:
        present = [a for a in authors if a in top_authors]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)
    return G

# ---------------------------
# CONFIGURAÇÃO DO APP
# ---------------------------
st.set_page_config(page_title="Análise Bibliográfica", layout="wide")
st.title("📚 Análise Bibliográfica — Web of Science")

# ---------------------------
# CARREGAR DADOS
# ---------------------------
caminho_arquivo = r"C:\Users\campo\Downloads\savedrecs.xls"
df = pd.read_excel(caminho_arquivo)

colunas_usadas = ['Authors', 'Article Title', 'Source Title', 'Abstract', 'Publication Year']
df = df[colunas_usadas]

df['Publication Year'] = pd.to_numeric(df['Publication Year'], errors='coerce')
for col in ['Authors', 'Article Title', 'Source Title', 'Abstract']:
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

    st.markdown("### 🗓️ Publicações por Ano")
    years = df['Publication Year'].dropna()
    if not years.empty:
        st.write(years.describe())

    st.markdown("### 🧑‍🤝‍🧑 Autores")
    author_lists = df['Authors'].apply(clean_author_string)
    all_authors = [a for sublist in author_lists for a in sublist]
    authors_series = pd.Series(all_authors)
    st.write(f"Total de autores únicos: {authors_series.nunique()}")
    st.write(f"Top 10 autores:\n{authors_series.value_counts().head(10)}")

    st.markdown("### 📰 Abstracts")
    abstracts = df['Abstract'].dropna().astype(str)
    abstract_len = abstracts.apply(lambda x: len(x.split()))
    st.write(f"Média de palavras por abstract: {abstract_len.mean():.2f}")

# ---------------------------
# ETAPA 3: GRÁFICOS
# ---------------------------
elif passo == "Gráficos":
    st.subheader("📊 Visualizações")

    # --- Publicações por ano ---
    years = df['Publication Year'].dropna()
    if not years.empty:
        fig_year = px.histogram(years, nbins=len(years.unique()), title="Distribuição de Publicações por Ano")
        st.plotly_chart(fig_year)

    # --- Nuvem de palavras ---
    st.markdown("### ☁️ Nuvem de Palavras - Abstracts")
    text = " ".join(df['Abstract'].dropna().tolist())
    if text.strip():
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis("off")
        st.pyplot(fig)

    # --- Rede de coautoria ---
    # --- Rede de Coautoria (hover mostra nome) ---
        # --- Rede de Coautoria (hover mostra nome + controle de compactação) ---
    st.markdown("### 🧑‍🤝‍🧑 Rede de Coautoria (Top 50 autores)")
    
    # Controle lateral para ajustar a distância entre grupos
    st.sidebar.markdown("#### 🎚️ Ajuste da Rede de Coautoria")
    k_value = st.sidebar.slider(
        "Compactação dos Nós (menor = mais próximos)",
        min_value=0.05, max_value=0.5, value=0.15, step=0.01
    )
    
    # Construir o grafo de coautoria
    G = build_coauthor_graph(df, top_n_authors=1200)
    
    # Layout do grafo - usa o valor do slider
    pos = nx.spring_layout(G, seed=42, k=k_value, iterations=100)
    
    # Arestas (ligações entre autores)
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Nós (autores)
    node_x, node_y, hover_text, node_size = [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        hover_text.append(f"{node} ({G.nodes[node]['freq']} publicações)")
        node_size.append(G.nodes[node]['freq'] ** 0.8)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',  # Mostra o nome apenas ao passar o mouse
        text=hover_text,
        marker=dict(
            size=node_size,
            color='skyblue',
            opacity=0.85,
            line=dict(width=1, color='darkblue')
        )
    )
    
    # Montagem final
    fig_coauthors = go.Figure(data=[edge_trace, node_trace])
    fig_coauthors.update_layout(
        title=f"Rede de Coautoria (k={k_value:.2f}) — passe o mouse para ver os autores",
        showlegend=False,
        hovermode='closest',
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white'
    )
    
    st.plotly_chart(fig_coauthors, use_container_width=True)
    # ---------------------------
    # 🏆 RANKING DE AUTORES
    # ---------------------------
    st.markdown("### 🏆 Ranking de Autores — Publicações e Colaborações")

    # Calcular número de publicações por autor
    author_counts = pd.Series(
        [a for sub in df['Authors'].apply(clean_author_string) for a in sub]
    ).value_counts()

    # Métricas de conectividade na rede
    degree_dict = dict(G.degree())  # número de conexões diretas
    centrality_dict = nx.degree_centrality(G)  # medida de influência

    # Combinar tudo em um DataFrame
    ranking_df = pd.DataFrame({
        'Autor': list(author_counts.index),
        'Publicações': author_counts.values,
        'Colaborações': [degree_dict.get(a, 0) for a in author_counts.index],
        'Centralidade': [centrality_dict.get(a, 0) for a in author_counts.index]
    }) 

    # Ordenar por publicações e colaborações
    ranking_df = ranking_df.sort_values(
        by=['Publicações', 'Colaborações'],
        ascending=False
    ).head(50).reset_index(drop=True)

    st.dataframe(ranking_df, use_container_width=True)

    # Gráfico de barras com plotly
    st.markdown("#### 📊 Top 20 Autores por Número de Publicações")
    fig_rank = px.bar(
        ranking_df.head(20),
        x='Publicações',
        y='Autor',
        orientation='h',
        text='Colaborações',
        title='Autores mais produtivos e colaborativos',
        labels={'Publicações': 'Nº de Publicações', 'Autor': 'Autor'},
    )
    fig_rank.update_traces(textposition='outside')
    fig_rank.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_rank, use_container_width=True)
