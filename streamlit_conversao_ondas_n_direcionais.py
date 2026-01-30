import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import butter, filtfilt, welch
from Acesso_Dados_servidor_FTP import *

# =========================
# FUNÇÕES
# =========================
def butter_filter(series, fs, cutoff, btype="low", order=4):
    y = series.astype(float).values
    mask = np.isfinite(y)
    y_f = y[mask]

    if len(y_f) < 10:
        return series

    nyq = 0.5 * fs
    wn = cutoff / nyq
    wn = min(max(wn, 1e-6), 0.99)

    b, a = butter(order, wn, btype=btype)
    y_filt = filtfilt(b, a, y_f)

    out = np.full_like(y, np.nan, dtype=float)
    out[mask] = y_filt
    return pd.Series(out, index=series.index)


def hs_tp_from_window(x, fs=1.0, fmin=0.04, fmax=0.4):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]

    if len(x) < 128:
        return np.nan, np.nan

    x = x - np.mean(x)

    f, Pxx = welch(
        x, fs=fs,
        nperseg=min(256, len(x)),
        detrend="constant",
        scaling="density"
    )

    band = (f >= fmin) & (f <= fmax)
    if band.sum() < 5:
        return np.nan, np.nan

    f_b = f[band]
    P_b = Pxx[band]

    m0 = np.trapz(P_b, f_b)
    if not np.isfinite(m0) or m0 <= 0:
        return np.nan, np.nan

    Hs = 4 * np.sqrt(m0)
    Tp = 1 / f_b[np.argmax(P_b)]

    return Hs, Tp


def calcular_historico_hs_tp(
    df, time_col, signal_col, fs,
    window_sec=1024, step_sec=1024,
    fmin=0.04, fmax=0.4
):
    df2 = df[[time_col, signal_col]].dropna().sort_values(time_col)

    t = df2[time_col].values
    x = df2[signal_col].values

    w = int(window_sec)
    step = int(step_sec)

    out = []
    for end in range(w, len(x) + 1, step):
        start = end - w
        Hs, Tp = hs_tp_from_window(x[start:end], fs, fmin, fmax)
        tstamp = t[end - 1]   # ✅ JANELA CAUSAL (fim da janela)
        out.append([tstamp, Hs, Tp])

    return pd.DataFrame(out, columns=["TIMESTAMP", "Hs_calc", "Tp_calc"])


def plot_compare_with_residual_same_y(df_plot, time_col, calc_col, sensor_col, residual_col, title, ylabel):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_plot[time_col], y=df_plot[calc_col],
        mode="lines", name=f"{calc_col}"
    ))

    fig.add_trace(go.Scatter(
        x=df_plot[time_col], y=df_plot[sensor_col],
        mode="lines", name=f"{sensor_col}"
    ))

    fig.add_trace(go.Scatter(
        x=df_plot[time_col], y=df_plot[residual_col],
        mode="lines", name=f"{residual_col} (calc - sensor)",
        visible="legendonly"
    ))

    fig.add_hline(y=0, line_dash="dash")

    fig.update_layout(
        height=450,
        hovermode="x unified",
        title=title,
        xaxis_title="TIMESTAMP",
        yaxis_title=ylabel
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================
# DADOS
# =========================
df = importar_dados_servidor_ftp()
df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])

fs = 1.0
cutoff_col = "CutOff_Freq_High"

st.title("Aplicativo - Abas: Hs/Tp + Comparação | Gráfico Temporal Variáveis")

if cutoff_col not in df.columns:
    st.error(f"Não achei a coluna '{cutoff_col}'.")
    st.stop()

cutoff_vals = df[cutoff_col].dropna().values
if len(cutoff_vals) == 0:
    st.error(f"A coluna '{cutoff_col}' está vazia.")
    st.stop()

cutoff = float(np.median(cutoff_vals))

# =========================
# ABAS
# =========================
tab1, tab2 = st.tabs(["📌 Hs/Tp + Comparação", "📈 Gráfico Temporal (variáveis)"])

# =========================
# TAB 1 - SEU CÓDIGO ORIGINAL (COMPARAÇÃO)
# =========================
with tab1:
    st.subheader("Hs / Tp (janela causal) + Comparação + Residual (mesma escala Y)")

    st.write(f"Cutoff usado: **{cutoff:.4f} Hz** | fs = **{fs} Hz**")

    # =========================
    # SINAL BASE
    # =========================
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if cutoff_col in num_cols:
        num_cols.remove(cutoff_col)

    col_onda = st.selectbox(
        "Coluna base do sinal de onda:",
        options=num_cols,
        key="col_onda_tab1"
    )

    # =========================
    # FILTRO (ondas = passa-baixa)
    # =========================
    sinal = df[col_onda]
    ondas = butter_filter(sinal, fs, cutoff, btype="low", order=4)

    # =========================
    # HISTÓRICO Hs/Tp
    # =========================
    step_sec = st.number_input("Passo entre janelas (s)", 128, 4096, 1024, key="step_sec_tab1")
    fmin = st.number_input("fmin (Hz)", value=0.04, key="fmin_tab1")
    fmax = st.number_input("fmax (Hz)", value=0.40, key="fmax_tab1")

    df_hs_tp = calcular_historico_hs_tp(
        df.assign(ondas=ondas),
        time_col="TIMESTAMP",
        signal_col="ondas",
        fs=fs,
        window_sec=1024,
        step_sec=int(step_sec),
        fmin=float(fmin),
        fmax=float(fmax)
    )

    st.subheader("Série calculada (Hs_calc / Tp_calc)")
    st.dataframe(df_hs_tp)

    # =========================
    # COMPARAÇÃO COM SENSOR
    # =========================
    st.subheader("Comparação com Sign_Height / Peak_Period")

    tem_hs = "Sign_Height" in df.columns
    tem_tp = "Peak_Period" in df.columns

    if not (tem_hs or tem_tp):
        st.warning("Não encontrei 'Sign_Height' e/ou 'Peak_Period' no dataframe.")
        st.stop()

    cols_ref = ["TIMESTAMP"]
    if tem_hs:
        cols_ref.append("Sign_Height")
    if tem_tp:
        cols_ref.append("Peak_Period")

    df_ref = df[cols_ref].dropna().sort_values("TIMESTAMP").copy()

    tol = pd.Timedelta(seconds=int(step_sec // 2))

    df_comp = pd.merge_asof(
        df_hs_tp.sort_values("TIMESTAMP"),
        df_ref.sort_values("TIMESTAMP"),
        on="TIMESTAMP",
        direction="nearest",
        tolerance=tol
    )

    # Residuais
    if tem_hs:
        df_comp["Residual_Hs"] = df_comp["Hs_calc"] - df_comp["Sign_Height"]
    if tem_tp:
        df_comp["Residual_Tp"] = df_comp["Tp_calc"] - df_comp["Peak_Period"]

    st.write(f"Merge por tempo com tolerância: **±{tol.total_seconds()} s**")
    st.dataframe(df_comp)

    # =========================
    # GRÁFICOS (mesma escala Y)
    # =========================
    if tem_hs:
        plot_compare_with_residual_same_y(
            df_comp,
            time_col="TIMESTAMP",
            calc_col="Hs_calc",
            sensor_col="Sign_Height",
            residual_col="Residual_Hs",
            title="Hs: calculado vs sensor + residual (mesmo eixo Y)",
            ylabel="Hs / Residual (m)"
        )

    if tem_tp:
        plot_compare_with_residual_same_y(
            df_comp,
            time_col="TIMESTAMP",
            calc_col="Tp_calc",
            sensor_col="Peak_Period",
            residual_col="Residual_Tp",
            title="Tp: calculado vs sensor + residual (mesmo eixo Y)",
            ylabel="Tp / Residual (s)"
        )

    # =========================
    # MÉTRICAS
    # =========================
    st.subheader("Métricas")

    if tem_hs and "Residual_Hs" in df_comp:
        r = df_comp["Residual_Hs"].dropna()
        st.write("Hs → MAE:", float(r.abs().mean()),
                 "| Bias:", float(r.mean()),
                 "| RMSE:", float(np.sqrt((r**2).mean())))

    if tem_tp and "Residual_Tp" in df_comp:
        r = df_comp["Residual_Tp"].dropna()
        st.write("Tp → MAE:", float(r.abs().mean()),
                 "| Bias:", float(r.mean()),
                 "| RMSE:", float(np.sqrt((r**2).mean())))


# =========================
# TAB 2 - GRÁFICO TEMPORAL LIVRE (MULTIVARIÁVEL)
# =========================
with tab2:
    st.subheader("Gráfico temporal - escolha e remova variáveis")

    # Variáveis numéricas para plot
    variaveis = df.select_dtypes(include="number").columns.tolist()

    # remove coluna de cutoff pra não poluir
    if cutoff_col in variaveis:
        variaveis.remove(cutoff_col)

    selecionadas = st.multiselect(
        "Selecione variáveis para plotar:",
        options=variaveis,
        default=[],
        key="multiselect_variaveis_tab2"
    )

    if not selecionadas:
        st.info("Selecione uma ou mais variáveis para exibir no gráfico.")
    else:
        fig2 = go.Figure()

        for col in selecionadas:
            fig2.add_trace(go.Scatter(
                x=df["TIMESTAMP"],
                y=df[col],
                mode="lines",
                name=col
            ))

        fig2.update_layout(
            xaxis_title="TIMESTAMP",
            yaxis_title="Valor",
            hovermode="x unified",
            legend_title="Variáveis",
            height=600
        )

        st.plotly_chart(fig2, use_container_width=True)
