import time
import requests
from config import SLEEP_SECONDS


class BaseScraper:
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self._HEADERS)
        self._last_request_ts: float = 0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS - elapsed)

    def _get(self, url: str) -> requests.Response:
        self._throttle()
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        self._last_request_ts = time.time()
        return response


class JsonApiScraper(BaseScraper):
    """Base for JSON APIs behind Cloudflare (SofaScore). Uses curl_cffi to
    impersonate a real browser's TLS fingerprint."""

    _IMPERSONATE = "chrome"

    def __init__(self):
        super().__init__()
        from curl_cffi import requests as cffi_requests  # lazy: optional dep
        self._cffi = cffi_requests.Session(impersonate=self._IMPERSONATE)

    def _get_json(self, url: str) -> dict:
        self._throttle()
        response = self._cffi.get(url, timeout=20)
        response.raise_for_status()
        self._last_request_ts = time.time()
        return response.json()
