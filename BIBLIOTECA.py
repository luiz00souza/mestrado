# -*- coding: utf-8 -*- 
"""
Biblioteca Digital — Streamlit
Modo Dark Forçado + Autoload CSV + Gerenciamento Completo
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Biblioteca Digital", layout="wide", page_icon="📚")

# --- CSS modo dark global ---
st.markdown("""
    <style>
    body, .main, .block-container { background-color: #121212 !important; color: #e0f7fa !important; }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #1e1e1e; }
    ::-webkit-scrollbar-thumb { background: #888; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #555; }
    h1, h2, h3, h4, h5, h6, p, span, div { color: #e0f7fa !important; }
    .book-card {
        background-color: rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 20px;
        margin: 10px;
        transition: all 0.3s ease;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
    .book-card:hover {
        transform: scale(1.03);
        box-shadow: 0 6px 20px rgba(0,0,0,0.25);
        background-color: rgba(255,255,255,0.12);
    }
    .book-title { font-size: 20px; font-weight: 600; color: #eaf6f6; }
    .book-author { color: #b3e5e5; font-size: 14px; margin-bottom: 4px; }
    .book-desc { color: #d9e9e9; font-size: 14px; margin-top: 10px; line-height: 1.4; }
    .book-link {
        display: inline-block;
        margin-top: 12px;
        padding: 8px 14px;
        background-color: #29b6f6;
        color: white;
        border-radius: 12px;
        text-decoration: none;
        font-weight: 500;
        transition: 0.3s;
    }
    .book-link:hover { background-color: #4dd0e1; }
</style>
""", unsafe_allow_html=True)

# --- Título ---
st.markdown("<h1 style='text-align:center;'>📚 Biblioteca Digital</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Explore e descubra conhecimento com leveza e clareza mental</p>", unsafe_allow_html=True)

# --- Carregar CSV ---
CSV_PATH = "biblioteca.csv"

@st.cache_data(ttl=600)
def carregar_csv(path):
    try:
        df = pd.read_csv(path, sep=";")
        df.columns = [c.strip().capitalize() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Não foi possível carregar o CSV: {e}")
        return pd.DataFrame()

df = carregar_csv(CSV_PATH)

# --- Exibição de livros com filtro e busca ---
if not df.empty:
    categorias = df["Categoria"].dropna().unique()
    filtro_categoria = st.multiselect("Filtrar por categoria:", categorias)
    busca = st.text_input("🔎 Buscar por palavra-chave (título, autor, descrição):")

    df_filtrado = df.copy()
    if filtro_categoria:
        df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_categoria)]
    if busca:
        busca_lower = busca.lower()
        df_filtrado = df_filtrado[df_filtrado.apply(lambda x: busca_lower in str(x).lower(), axis=1)]

    if not df_filtrado.empty:
        cols = st.columns(3)
        for i, (_, row) in enumerate(df_filtrado.iterrows()):
            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div class='book-card'>
                        <div class='book-title'>{row['Título']}</div>
                        <div class='book-author'>{row['Autor']} ({row['Ano']})</div>
                        <div class='book-desc'>{row['Descrição']}</div>
                        <a href='{row['Link']}' target='_blank' class='book-link'>Acessar</a>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        st.warning("Nenhum item encontrado para os filtros aplicados.")
else:
    st.info("Biblioteca vazia ou CSV não encontrado 📁")

# --- Seção de Gerenciamento de Biblioteca ---
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h2>⚙️ Gerenciar Biblioteca</h2>", unsafe_allow_html=True)

# --- Adicionar livro ---
with st.expander("➕ Adicionar novo livro"):
    novo_titulo = st.text_input("Título")
    novo_autor = st.text_input("Autor")
    novo_ano = st.text_input("Ano")
    nova_categoria = st.text_input("Categoria")
    nova_desc = st.text_area("Descrição")
    novo_link = st.text_input("Link")

    if st.button("Adicionar Livro"):
        if novo_titulo and novo_autor:
            novo_item = {
                "Título": novo_titulo,
                "Autor": novo_autor,
                "Ano": novo_ano,
                "Categoria": nova_categoria,
                "Descrição": nova_desc,
                "Link": novo_link
            }
            df = pd.concat([df, pd.DataFrame([novo_item])], ignore_index=True)
            df.to_csv(CSV_PATH, sep=";", index=False)
            st.success(f"Livro '{novo_titulo}' adicionado com sucesso!")
        else:
            st.error("Título e Autor são obrigatórios!")

# --- Remover livro ---
with st.expander("🗑️ Remover livro existente"):
    if not df.empty:
        opcoes_remover = df["Título"].tolist()
        livro_remover = st.selectbox("Selecione o livro para remover:", opcoes_remover)
        if st.button("Remover Livro"):
            df = df[df["Título"] != livro_remover]
            df.to_csv(CSV_PATH, sep=";", index=False)
            st.success(f"Livro '{livro_remover}' removido com sucesso!")
    else:
        st.info("Nenhum livro disponível para remover.")

# --- Editar livro ---
with st.expander("✏️ Editar livro existente"):
    if not df.empty:
        opcoes_editar = df["Título"].tolist()
        livro_editar = st.selectbox("Selecione o livro para editar:", opcoes_editar)
        if livro_editar:
            # Carrega os valores atuais
            livro_atual = df[df["Título"] == livro_editar].iloc[0]
            editar_titulo = st.text_input("Título", livro_atual["Título"])
            editar_autor = st.text_input("Autor", livro_atual["Autor"])
            editar_ano = st.text_input("Ano", livro_atual["Ano"])
            editar_categoria = st.text_input("Categoria", livro_atual["Categoria"])
            editar_desc = st.text_area("Descrição", livro_atual["Descrição"])
            editar_link = st.text_input("Link", livro_atual["Link"])

            if st.button("Salvar Alterações"):
                df.loc[df["Título"] == livro_editar, ["Título","Autor","Ano","Categoria","Descrição","Link"]] = [
                    editar_titulo, editar_autor, editar_ano, editar_categoria, editar_desc, editar_link
                ]
                df.to_csv(CSV_PATH, sep=";", index=False)
                st.success(f"Livro '{editar_titulo}' atualizado com sucesso!")
    else:
        st.info("Nenhum livro disponível para editar.")
