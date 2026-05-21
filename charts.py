"""
Kripto Coin Analiz Uygulaması — Dashboard Modülü (Bölüm: Grafikler)
Plotly ile mum grafikleri ve teknik indikatör grafikleri.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def create_candlestick_chart(df: pd.DataFrame, indicators: dict, coin: str, tf: str) -> go.Figure:
    """Mum grafiği + EMA + Bollinger Bands + Hacim."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.75, 0.25],
                        subplot_titles=[f"{coin} — {tf} Mum Grafiği", "Hacim"])

    # Mum grafiği
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Fiyat",
        increasing_line_color="#00E676", decreasing_line_color="#FF5252",
        increasing_fillcolor="rgba(0,230,118,0.53)", decreasing_fillcolor="rgba(255,82,82,0.53)",
    ), row=1, col=1)

    # EMA çizgileri
    ema_colors = {9: "#FFD740", 21: "#448AFF", 50: "#B388FF", 200: "#FF6E40"}
    ema_series = indicators.get("ema_series", {})
    for period, color in ema_colors.items():
        series = ema_series.get(period)
        if series is not None and not series.empty:
            fig.add_trace(go.Scatter(
                x=series.index, y=series, name=f"EMA {period}",
                line=dict(color=color, width=1.5), opacity=0.8,
            ), row=1, col=1)

    # Bollinger Bands
    bb = indicators.get("bb_series")
    if bb is not None and not bb.empty:
        cols = bb.columns.tolist()
        fig.add_trace(go.Scatter(x=bb.index, y=bb[cols[2]], name="BB Üst",
                                 line=dict(color="#B388FF", width=1, dash="dot"), opacity=0.5), row=1, col=1)
        fig.add_trace(go.Scatter(x=bb.index, y=bb[cols[0]], name="BB Alt",
                                 line=dict(color="#B388FF", width=1, dash="dot"), opacity=0.5,
                                 fill="tonexty", fillcolor="rgba(179,136,255,0.05)"), row=1, col=1)

    # Hacim
    colors = ["#00E676" if c >= o else "#FF5252" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Hacim",
                         marker_color=colors, opacity=0.6), row=2, col=1)

    fig.update_layout(
        template="plotly_dark", height=600,
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(color="#B0BEC5"), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=40, b=20),
    )
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E")
    return fig


def create_rsi_chart(indicators: dict) -> go.Figure:
    """RSI grafiği."""
    rsi_series = indicators.get("rsi_series")
    fig = go.Figure()
    if rsi_series is not None and not rsi_series.empty:
        fig.add_trace(go.Scatter(x=rsi_series.index, y=rsi_series, name="RSI",
                                 line=dict(color="#448AFF", width=2)))
        fig.add_hline(y=70, line_dash="dash", line_color="#FF5252", opacity=0.5,
                      annotation_text="Aşırı Alım (70)")
        fig.add_hline(y=30, line_dash="dash", line_color="#00E676", opacity=0.5,
                      annotation_text="Aşırı Satım (30)")
        fig.add_hrect(y0=30, y1=70, fillcolor="#448AFF", opacity=0.03)
    fig.update_layout(
        template="plotly_dark", height=200, title="RSI (14)",
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(color="#B0BEC5", size=11),
        margin=dict(l=50, r=20, t=35, b=20), showlegend=False,
    )
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E", range=[0, 100])
    return fig


def create_macd_chart(indicators: dict) -> go.Figure:
    """MACD grafiği."""
    macd_series = indicators.get("macd_series")
    fig = go.Figure()
    if macd_series is not None and not macd_series.empty:
        cols = macd_series.columns.tolist()
        fig.add_trace(go.Scatter(x=macd_series.index, y=macd_series[cols[0]],
                                 name="MACD", line=dict(color="#448AFF", width=2)))
        fig.add_trace(go.Scatter(x=macd_series.index, y=macd_series[cols[1]],
                                 name="Sinyal", line=dict(color="#FF6E40", width=2)))
        hist = macd_series[cols[2]]
        colors = ["#00E676" if v >= 0 else "#FF5252" for v in hist]
        fig.add_trace(go.Bar(x=macd_series.index, y=hist, name="Histogram",
                             marker_color=colors, opacity=0.5))
    fig.update_layout(
        template="plotly_dark", height=200, title="MACD (12, 26, 9)",
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(color="#B0BEC5", size=11),
        margin=dict(l=50, r=20, t=35, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E")
    return fig
