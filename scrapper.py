import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging

from get_fatcs_graph import get_clean_facts_graphs
from get_games import get_jogos_pagina
from get_historico import get_jogos_ano

# Configura log
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

URL = "https://www.ogol.com.br/equipe/fortaleza"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
}

try:
    resp = requests.get(URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
except Exception as e:
    logging.error(f"Erro ao carregar página inicial do Fortaleza: {e}")
    soup = None


def extract_historico_completo(start_year=1920, end_year=2025):
    historico = []
    for ano in range(start_year, end_year + 1):
        try:
            jogos = get_jogos_ano(ano)
            historico.extend(jogos)
        except Exception as e:
            logging.warning(f"⚠️ Erro ao processar o ano {ano}: {e}")
            continue

    try:
        df = pd.DataFrame(historico)
        df.to_csv("fortaleza_historico_completo.csv", index=False)
        logging.info("Arquivo 'fortaleza_historico_completo.csv' gerado com sucesso.")
        return "Histórico completo extraído com sucesso!"
    except Exception as e:
        logging.error(f"Erro ao salvar CSV do histórico completo: {e}")
        return "Erro ao salvar o histórico completo."


def extract_fatcs():
    if not soup:
        return "Página inicial não carregada corretamente."

    try:
        facts_graphs = get_clean_facts_graphs(soup)

        if not facts_graphs:
            return "facts_graphs não encontrado."

        graph_games = facts_graphs.find("div", class_="graph_games")
        if graph_games:
            print("Jogos:")
            print(graph_games.get_text(separator="\n", strip=True))

        graph_goals = facts_graphs.find("div", class_="graph_goals")
        if graph_goals:
            print("Gols:")
            print(graph_goals.get_text(separator="\n", strip=True))

        return "Fatos extraídos com sucesso."

    except Exception as e:
        logging.error(f"Erro ao extrair facts_graphs: {e}")
        return "Erro ao extrair fatos do gráfico."


def extract_all_games():
    todos_jogos = []
    try:
        for page in range(1, 20):
            url = (
                "https://www.ogol.com.br/equipe/fortaleza/todos-os-jogos"
                f"?grp=1&ond=&compet_id_jogos=0&epoca_id=154&ano=2025"
                "&ano_fim=2011&type=year&epoca_id_fim=0&comfim=0"
                f"&page={page}"
            )
            logging.info(f"Coletando página {page}")
            jogos = get_jogos_pagina(url)
            todos_jogos.extend(jogos)

        df = pd.DataFrame(todos_jogos)
        df.to_csv("Fortaleza_historico.csv", index=False)
        logging.info("Arquivo 'Fortaleza_historico.csv' gerado com sucesso.")
        return "Extração de jogos por página finalizada com sucesso."
    except Exception as e:
        logging.error(f"Erro ao extrair jogos por página: {e}")
        return "Erro ao extrair todos os jogos."
