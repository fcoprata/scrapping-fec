import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
}


def get_jogos_pagina(url: str):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    jogos = []

    linhas = soup.select("tr.parent")

    for linha in linhas:
        cols = linha.find_all("td")
        if len(cols) < 9:
            continue  

        jogo = {
            "resultado": cols[0].get_text(strip=True),
            "data": cols[1].get_text(strip=True),
            "hora": cols[2].get_text(strip=True),
            "local": cols[3].get_text(strip=True).replace("(", "").replace(")", ""),
            "adversario": cols[5].get_text(strip=True),
            "placar": cols[6].get_text(strip=True),
            "competicao": cols[7].get_text(strip=True),
            "rodada": cols[8].get_text(strip=True)
        }

        jogos.append(jogo)

    return jogos
