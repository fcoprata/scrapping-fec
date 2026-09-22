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

    def _get(self, url: str, **kwargs) -> requests.Response:
        self._throttle()
        timeout = kwargs.pop("timeout", 20)
        response = self.session.get(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        self._last_request_ts = time.time()
        return response


class JsonApiScraper(BaseScraper):
    """Base for JSON APIs behind Cloudflare (SofaScore). Uses curl_cffi to
    impersonate a real browser's TLS fingerprint."""

    _IMPERSONATE = "chrome"
    _CFFI_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://www.sofascore.com",
        "Referer": "https://www.sofascore.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }

    def __init__(self):
        super().__init__()
        from curl_cffi import requests as cffi_requests  # lazy: optional dep
        self._cffi = cffi_requests.Session(impersonate=self._IMPERSONATE)
        self._cffi.headers.update(self._CFFI_HEADERS)

    def _get_json(self, url: str, max_retries: int = 3) -> dict:
        self._throttle()
        last_err = None
        for attempt in range(max_retries):
            try:
                response = self._cffi.get(url, timeout=25)
                response.raise_for_status()
                self._last_request_ts = time.time()
                return response.json()
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
        raise last_err
