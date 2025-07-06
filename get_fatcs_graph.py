from bs4 import BeautifulSoup

def get_clean_facts_graphs(soup: BeautifulSoup):
    """
    Localiza a div 'facts_graphs', remove elementos desnecessários
    como 'goal_shadow', 'bars_shadow' e 'span.icn_zerozero', e retorna
    o conteúdo limpo como um BeautifulSoup Tag.
    """
    facts_graphs = soup.find("div", class_="facts_graphs")

    if not facts_graphs:
        return None
    
    for garbage in facts_graphs.find_all(["div"], class_=["goal_shadow", "bars_shadow"]):
        garbage.decompose()

    for span in facts_graphs.find_all("span", class_="icn_zerozero"):
        span.decompose()

    return facts_graphs
