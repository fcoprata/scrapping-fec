import math
from typing import List, Optional
import plotly.graph_objects as go

SITUATION_PT = {
    "regular": "Bola Rolando",
    "assisted": "Assistida",
    "fast-break": "Contra-Ataque",
    "set-piece": "Bola Parada",
    "corner": "Escanteio",
    "free-kick": "Falta Direta",
    "penalty": "Pênalti",
    "throw-in-set-piece": "Lateral Longo",
}

BODY_PART_PT = {
    "right-foot": "Pé Direito",
    "left-foot": "Pé Esquerdo",
    "head": "Cabeça",
    "other": "Outro",
    "other-body-part": "Outro",
}

SHOT_TYPE_PT = {
    "goal": "Gol",
    "miss": "Para Fora",
    "save": "Defesa",
    "block": "Bloqueado",
    "post": "Na Trave",
    "blocked-off-line": "Salvo na Linha",
}


def create_2d_pitch_figure(
    shots: List[dict],
    title: str = "Campo 2D — Mapa de Finalizações & Assistências",
    show_trajectories: bool = True,
    show_assists: bool = True,
    pitch_theme: str = "grass",  # "grass" ou "dark"
    height: int = 560,
) -> go.Figure:
    """Cria uma visualização interativa do meio-campo ofensivo (Campo 2D) com Plotly.
    
    Coordenadas:
    - x: largura do campo de 0 (linha lateral esquerda) a 100 (linha lateral direita). Centro = 50.
    - y: distância da linha do gol de 0 (linha do gol alvo) a 50 (linha de meio-campo).
    """
    fig = go.Figure()

    # Cores do gramado
    bg_color = "#163E20" if pitch_theme == "grass" else "#0F172A"
    band_color = "#194423" if pitch_theme == "grass" else "#141E33"
    line_color = "rgba(255, 255, 255, 0.85)"

    # 1. Fundo e faixas de grama (corte de grama alternado a cada 10% do campo)
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=100, y1=50,
        fillcolor=bg_color, line=dict(color=line_color, width=2.5),
        layer="below",
    )
    for band_y in (0, 20, 40):
        fig.add_shape(
            type="rect", x0=0, y0=band_y, x1=100, y1=band_y + 10,
            fillcolor=band_color, line=dict(width=0),
            layer="below",
        )

    # 2. Linha de Meio-Campo (y = 50)
    fig.add_shape(
        type="line", x0=0, y0=50, x1=100, y1=50,
        line=dict(color=line_color, width=2.5),
    )

    # Círculo central (meio círculo visível no meio-campo)
    # Raio do círculo central oficial: 9.15m de 105m = ~8.7% do campo
    theta = [i * math.pi / 100 for i in range(101)]
    fig.add_trace(go.Scatter(
        x=[50 + 8.7 * math.cos(t) for t in theta],
        y=[50 - 8.7 * math.sin(t) for t in theta],
        mode="lines",
        line=dict(color=line_color, width=2),
        hoverinfo="skip",
        showlegend=False,
    ))

    # 3. Grande Área (Penalty Box)
    # 40.32m de 68m = ~59.3% largura (20.35 a 79.65). 16.5m de 105m = ~15.7% profundidade
    fig.add_shape(
        type="rect", x0=20.35, y0=0, x1=79.65, y1=15.7,
        line=dict(color=line_color, width=2),
    )

    # 4. Pequena Área (6-yard Box)
    # 18.32m de 68m = ~27% largura (36.5 a 63.5). 5.5m de 105m = ~5.24% profundidade
    fig.add_shape(
        type="rect", x0=36.5, y0=0, x1=63.5, y1=5.24,
        line=dict(color=line_color, width=2),
    )

    # 5. Marca do Pênalti (11m de 105m = y = 10.5, x = 50)
    fig.add_shape(
        type="circle", x0=49.4, y0=10.0, x1=50.6, y1=11.0,
        fillcolor=line_color, line=dict(color=line_color),
    )

    # 6. Meia-lua da Grande Área (Penalty Arc)
    # Círculo com raio 8.7m centrado em (50, 10.5), cortado em y >= 15.7
    arc_x, arc_y = [], []
    for deg in range(0, 181, 2):
        rad = math.radians(deg)
        px = 50 + 8.7 * math.cos(rad)
        py = 10.5 + 8.7 * math.sin(rad)
        if py >= 15.6:
            arc_x.append(px)
            arc_y.append(py)
    if arc_x:
        fig.add_trace(go.Scatter(
            x=arc_x, y=arc_y, mode="lines",
            line=dict(color=line_color, width=2),
            hoverinfo="skip", showlegend=False,
        ))

    # 7. Meta / Traves do Gol
    # 7.32m de 68m = 10.76% largura (44.62 a 55.38)
    fig.add_shape(
        type="rect", x0=44.62, y0=-2.2, x1=55.38, y1=0,
        fillcolor="rgba(255, 255, 255, 0.4)",
        line=dict(color="#FFFFFF", width=3),
    )

    # 8. Traçados de Trajetórias de Chute e Assistências
    for s in shots:
        sh_x, sh_y = s.get("x"), s.get("y")
        if sh_x is None or sh_y is None:
            continue

        # Trajetória do chute até o gol/linha
        end_x, end_y = s.get("end_x"), s.get("end_y")
        if show_trajectories and end_x is not None and end_y is not None:
            t_color = "rgba(245, 158, 11, 0.65)" if s.get("is_goal") else "rgba(255, 255, 255, 0.22)"
            t_width = 2.2 if s.get("is_goal") else 1.0
            fig.add_trace(go.Scatter(
                x=[sh_x, end_x], y=[sh_y, end_y],
                mode="lines",
                line=dict(color=t_color, width=t_width),
                hoverinfo="skip", showlegend=False,
            ))

        # Assistência conectada ao gol
        pass_start = s.get("pass_start")
        if show_assists and s.get("is_goal") and pass_start:
            # Converter coordenadas do passe (x=length de 100 a 0, y=largura de 0 a 100)
            ast_x = pass_start.get("y", 50)
            ast_y = min(48.0, max(0.0, 100.0 - float(pass_start.get("x", 80))))
            ast_name = s.get("assist_name") or "Assistência"

            # Linha de passe (pontilhada em Ciano brilhante)
            fig.add_trace(go.Scatter(
                x=[ast_x, sh_x], y=[ast_y, sh_y],
                mode="lines+markers",
                marker=dict(size=[7, 0], color="#06B6D4", symbol="circle"),
                line=dict(color="#06B6D4", width=2.5, dash="dot"),
                name=f"Passe: {ast_name}",
                text=f"👟 <b>Passe p/ Gol: {ast_name}</b><br>Finalizado por: {s.get('player_name')}",
                hoverinfo="text",
                showlegend=False,
            ))

    # 9. Plotagem das Finalizações (Pontos no Campo)
    groups = {
        "goal": {"name": "⚽ Gol", "color": "#F59E0B", "symbol": "star", "shots": []},
        "save": {"name": "🧤 Defendido", "color": "#3B82F6", "symbol": "circle", "shots": []},
        "block": {"name": "🛡️ Bloqueado", "color": "#A855F7", "symbol": "diamond", "shots": []},
        "miss": {"name": "❌ Para Fora / Trave", "color": "#EF4444", "symbol": "x", "shots": []},
    }

    for s in shots:
        sh_x, sh_y = s.get("x"), s.get("y")
        if sh_x is None or sh_y is None:
            continue
        stype = s.get("shot_type")
        if s.get("is_goal"):
            grp = "goal"
        elif stype == "save":
            grp = "save"
        elif stype in ("block", "blocked-off-line"):
            grp = "block"
        else:
            grp = "miss"
        groups[grp]["shots"].append(s)

    for grp_key, grp_data in groups.items():
        grp_shots = grp_data["shots"]
        if not grp_shots:
            continue

        xs = [s["x"] for s in grp_shots]
        ys = [s["y"] for s in grp_shots]
        xgs = [s.get("xg") or 0.05 for s in grp_shots]
        sizes = [max(10, min(int(xg_val * 48) + 8, 36)) for xg_val in xgs]

        hover_texts = []
        for s in grp_shots:
            ast_txt = f"<br>🎯 Assistência: <b>{s['assist_name']}</b>" if s.get("assist_name") else ""
            xg_val = float(s.get("xg") or 0.0)
            xgot_val = float(s.get("xgot") or 0.0)
            sit_pt = SITUATION_PT.get(s.get("situation", ""), (s.get("situation") or "Bola Rolando").replace("-", " ").title())
            body_pt = BODY_PART_PT.get(s.get("body_part", ""), (s.get("body_part") or "Pé").replace("-", " ").title())
            hover_texts.append(
                f"<b>{s.get('player_name', 'Jogador')}</b> ({s.get('minute', '?')}')<br>"
                f"Resultado: <b>{grp_data['name']}</b><br>"
                f"xG: <b>{xg_val:.3f}</b> | xGOT: <b>{xgot_val:.3f}</b><br>"
                f"Situação: <b>{sit_pt}</b> | Parte: <b>{body_pt}</b>"
                f"{ast_txt}"
            )

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers",
            name=f"{grp_data['name']} ({len(grp_shots)})",
            marker=dict(
                size=sizes,
                color=grp_data["color"],
                symbol=grp_data["symbol"],
                line=dict(color="#FFFFFF", width=1.5),
                opacity=0.9 if grp_key == "goal" else 0.75,
            ),
            text=hover_texts,
            hoverinfo="text",
        ))

    # Configuração de eixos do campo (manter proporção real de futebol)
    fig.update_xaxes(
        range=[-3, 103],
        showgrid=False,
        zeroline=False,
        visible=False,
    )
    fig.update_yaxes(
        range=[-4, 54],
        showgrid=False,
        zeroline=False,
        visible=False,
        scaleanchor="x",
        scaleratio=1.0,
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#1E293B")),
        height=height,
        margin=dict(l=10, r=10, t=45, b=10),
        plot_bgcolor="#FFFFFF",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(size=12),
        ),
    )
    return fig
