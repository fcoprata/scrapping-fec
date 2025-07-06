import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
}

def get_jogos_ano(ano: int) -> list:
    base_url = (
        f"https://www.ogol.com.br/equipe/fortaleza/todos-os-jogos"
        f"?grp=1&ond=&compet_id_jogos=0&ved=&ano={ano}&comfim=0"
        f"&equipa_1=2239&menu=allmatches&type=year&op=ver_confronto"
    )

    jogos = []
    page = 1

    while True:
        url = f"{base_url}&page={page}"
        print(f"📅 Ano {ano} - Página {page}")

        resp = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")

        linhas = soup.select("tr.parent")
        if not linhas:
            break  # Fim da paginação

        for linha in linhas:
            cols = linha.find_all("td")
            if len(cols) < 9:
                continue

            jogo = {
                "ano": ano,
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

        # Avança a página
        page += 1

    return jogos
