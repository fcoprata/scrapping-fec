# main.py
import json
from flask import Request
from scrapper import extract_all_games, extract_fatcs, extract_historico_completo


def api_fortaleza(request: Request):
    try:
        path = request.path

        if path == "/historico-completo":
            msg = extract_historico_completo()
            return (json.dumps({"message": msg}), 200, {"Content-Type": "application/json"})

        elif path == "/fatcs":
            msg = extract_fatcs()
            status = 200
            if "não encontrado" in msg.lower():
                status = 404
            elif "erro" in msg.lower():
                status = 500
            return (json.dumps({"message": msg}), status, {"Content-Type": "application/json"})

        elif path == "/jogos-pagina":
            msg = extract_all_games()
            return (json.dumps({"message": msg}), 200, {"Content-Type": "application/json"})

        else:
            return (json.dumps({"error": "Rota não encontrada"}), 404, {"Content-Type": "application/json"})

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
