# -*- coding: utf-8 -*-
"""
Script para extrair autores e afiliações via DOI, geocodificar e gerar mapa
"""

from tqdm import tqdm
import folium
import pandas as pd
import requests
import time

# ---------------------------- Funções ----------------------------

def carregar_dois(caminho_arquivo, n=5):
    """Carrega DOIs do Excel e retorna os primeiros n em formato de lista."""
    df = pd.read_excel(caminho_arquivo)
    dois = df['DOI'].dropna().head(n).tolist()
    return dois

def extrair_informacoes_DOI(dois):
    """
    Extrai informações bibliográficas completas (autor, coautor, título, ano, palavras-chave e resumo)
    para uma lista de DOIs usando a API Crossref.
    """

    registros = []

    for doi in tqdm(dois, desc="Extraindo metadados"):
        url = f"https://api.crossref.org/works/{doi}"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json().get('message', {})

            # Metadados principais
            title = data.get('title', [''])[0]
            year = data.get('issued', {}).get('date-parts', [[None]])[0][0]
            keywords = ', '.join(data.get('subject', []))
            authors = data.get('author', [])

            # Loop pelos autores
            for i, autor in enumerate(authors):
                nome = autor.get('given', '') + ' ' + autor.get('family', '')
                afiliacao = autor.get('affiliation', [{}])[0].get('name', '') if autor.get('affiliation') else ''
                tipo = "Autor Principal" if i == 0 else "Coautor"

                registros.append({
                    'DOI': doi,
                    'Author': nome.strip(),
                    'TipoAutor': tipo,
                    'Affiliation': afiliacao,
                    'Title': title,
                    'Year': year,
                    'Keywords': keywords,
                })

        except Exception as e:
            print(f"⚠️ Erro ao processar DOI {doi}: {e}")
            registros.append({'DOI': doi, 'Erro': str(e)})

    return pd.DataFrame(registros)




geocode_cache = {}

def geocode_affiliation(affiliation):
    """Geocodifica uma afiliação usando Nominatim e cache."""
    if not affiliation:
        return None, None, None, None, None
    if affiliation in geocode_cache:
        return geocode_cache[affiliation]

    words = affiliation.split()
    for n in [3, 2, 1]:
        if len(words) < n:
            continue
        core = " ".join(words[-n:])
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {'q': core, 'format': 'json', 'limit': 1}
            resp = requests.get(url, params=params, headers={'User-Agent': 'PythonGeocoder'})
            resp.raise_for_status()
            data = resp.json()
            if data:
                address = data[0].get('address', {})
                # city = address.get('city') or address.get('town') or address.get('village')
                # country = address.get('country')
                lat = data[0].get('lat')
                lon = data[0].get('lon')
                result = (core, lat, lon)
                geocode_cache[affiliation] = result
                return result
        except Exception as e:
            print(f"Erro ao geocodificar '{core}': {e}")
            time.sleep(1)
            continue
    geocode_cache[affiliation] = (None, None, None, None, None)
    return None, None, None, None, None

def processar_geocoding(df):
    """Geocodifica todas as afiliações únicas do DataFrame."""
    unique_affiliations = df['Affiliation'].dropna().unique()
    for aff in tqdm(unique_affiliations, desc="Geocodificando afiliações"):
        geocode_affiliation(aff)
        time.sleep(1)  # respeitar limite do Nominatim
    df[['Core', 'City', 'Country', 'Latitude', 'Longitude']] = df['Affiliation'].apply(
        lambda x: pd.Series(geocode_cache.get(x, (None, None, None, None, None)))
    )
    return df

def gerar_mapa(df, caminho_html):
    """Gera mapa folium a partir do DataFrame com Latitude e Longitude."""
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df = df.dropna(subset=['Latitude', 'Longitude'])

    mapa = folium.Map(
        location=[df['Latitude'].mean(), df['Longitude'].mean()],
        zoom_start=12
    )
    for idx, row in df.iterrows():
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"Registro {idx}"
        ).add_to(mapa)
    mapa.save(caminho_html)
    print(f"Mapa salvo em {caminho_html}")
    return mapa

def salvar_excel(df, caminho_excel):
    """Salva DataFrame em Excel."""
    df.to_excel(caminho_excel, index=False)
    print(f"Excel salvo em {caminho_excel}")

def estatisticas_validos(df):
    """Imprime estatísticas de valores válidos por coluna."""
    print("\n--- Estatísticas de valores válidos por coluna ---")
    for col in df.columns:
        total = len(df)
        valid = df[col].notna().sum()
        pct = (valid / total) * 100
        print(f"{col}: {valid}/{total} válidos ({pct:.2f}%)")

# ---------------------------- Execução ----------------------------

def extrair_lat_lon_de_DOI(caminho_arquivo, caminho_saida, caminho_mapa, n_DOIs, apenas_principal=False):
    dois = carregar_dois(caminho_arquivo, n=n_DOIs)
    df = extrair_informacoes_DOI(dois)
    df = processar_geocoding(df)

    estatisticas_validos(df)

    salvar_excel(df, caminho_saida)
    gerar_mapa(df, caminho_mapa)
    return df


def preencher_coords_com_coautores(df):
    """
    Preenche Latitude/Longitude ausentes usando informações dos coautores.
    Supõe que o df tenha colunas:
    ['DOI', 'Author', 'Coauthors', 'Latitude', 'Longitude']
    """
    df = df.copy()
    
    for i, row in df.iterrows():
        # Se já tem coordenadas, pula
        if pd.notnull(row.get('Latitude')) and pd.notnull(row.get('Longitude')):
            continue
        
        # Se não há coautores, pula
        coautores = row.get('Coauthors')
        if pd.isna(coautores):
            continue
        
        # Divide coautores em lista
        lista_coautores = [a.strip() for a in str(coautores).split(';') if a.strip()]
        
        # Busca na própria tabela informações de coautores com coords válidas
        for nome in lista_coautores:
            linha_coautor = df[
                (df['Author'].str.contains(nome, case=False, na=False)) &
                (df['Latitude'].notna()) &
                (df['Longitude'].notna())
            ]
            
            if not linha_coautor.empty:
                df.at[i, 'Latitude'] = linha_coautor.iloc[0]['Latitude']
                df.at[i, 'Longitude'] = linha_coautor.iloc[0]['Longitude']
                break  # para no primeiro coautor com coordenadas válidas
    
    return df

def completar_informacoes_por_DOI(df_principal, df_secundaria, coluna_chave='DOI'):
    """
    Completa informações no df_principal com base no df_secundaria, usando a coluna DOI como chave.
    - Assume que df_secundaria já está filtrado.
    - Preenche TODAS as linhas do df_principal que compartilham o mesmo DOI.
    """

    # Garantir que a chave esteja no formato string
    df_principal[coluna_chave] = df_principal[coluna_chave].astype(str)
    df_secundaria[coluna_chave] = df_secundaria[coluna_chave].astype(str)

    # Garantir unicidade por DOI no df_secundaria (mantém a primeira ocorrência)
    df_secundaria = df_secundaria.drop_duplicates(subset=[coluna_chave], keep='first')

    # Evitar sobrescrever a coluna 'Authors' principal
    if 'Authors' in df_secundaria.columns:
        df_secundaria = df_secundaria.rename(columns={'Authors': 'Coauthors_sec'})

    # Merge (replicará automaticamente para DOIs repetidos no principal)
    df_completo = pd.merge(df_principal, df_secundaria, on=coluna_chave, how='left', suffixes=('', '_sec'))

    # Preencher valores nulos da principal com os da secundária
    for col in df_secundaria.columns:
        if col in [coluna_chave, 'Coauthors_sec']:
            continue
        col_sec = col + '_sec'
        if col_sec in df_completo.columns:
            df_completo[col] = df_completo[col].combine_first(df_completo[col_sec])
            df_completo.drop(columns=[col_sec], inplace=True)

    # Incorporar coautores
    if 'Coauthors_sec' in df_completo.columns:
        if 'Coauthors' not in df_completo.columns:
            df_completo['Coauthors'] = df_completo['Coauthors_sec']
        df_completo.drop(columns=['Coauthors_sec'], inplace=True)

    return df_completo




# Exemplo de uso: apenas o autor principal

#%%
def estatisticas_geocoding(df):
    """Mostra estatísticas detalhadas sobre a geocodificação."""
    print("\n--- Estatísticas de Geocodificação ---")

    # Autores principais
    df_autor = df[df['TipoAutor'] == 'Autor Principal']
    total_autor = len(df_autor)
    validos_autor = df_autor['Latitude'].notna().sum()
    pct_autor = (validos_autor / total_autor * 100) if total_autor > 0 else 0

    print(f"✅ Autores principais com lat/lon válidas: {validos_autor}/{total_autor} ({pct_autor:.2f}%)")

    # Cobertura por DOI (pelo menos um autor com lat/lon)
    df_doi = df.groupby('DOI')['Latitude'].apply(lambda x: x.notna().any()).reset_index()
    total_doi = len(df_doi)
    validos_doi = df_doi['Latitude'].sum()
    pct_doi = (validos_doi / total_doi * 100) if total_doi > 0 else 0

    print(f"🌍 DOIs com pelo menos um autor com lat/lon válidas: {validos_doi}/{total_doi} ({pct_doi:.2f}%)")

    return {
        'pct_autores_principais': pct_autor,
        'pct_dois_geocodificados': pct_doi
    }
df = extrair_lat_lon_de_DOI(
    caminho_arquivo=r"C:\Users\campo\Downloads\savedrecs.xls",
    caminho_saida=r"C:\Users\campo\autores_afiliacoes_geocodificadas.xlsx",
    caminho_mapa=r"C:\Users\campo\Desktop\mapa_microdados_eficiencia_2021.html",
    n_DOIs=234,
    apenas_principal=True
)
stats = estatisticas_geocoding(df)
print(stats)
colunas_filtro = ['Authors', 'Article Title', 'Source Title', 'Abstract', 'Publication Year','DOI']

df_1 = pd.read_excel(r"C:\Users\campo\Downloads\savedrecs.xls", usecols=colunas_filtro)  # tabela secundária
df_2 = pd.read_excel(r"C:\Users\campo\autores_afiliacoes_geocodificadas.xlsx")  # prioritária



df_completo = completar_informacoes_por_DOI(
    df_principal=df_2,
    df_secundaria=df_1
    )



df_completo.to_excel(r"C:\Users\campo\Desktop\autores_completos_coords_coautores.xlsx", index=False)
# print("✅ Coordenadas complementadas com sucesso usando coautores!")
