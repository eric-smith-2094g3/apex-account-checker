import time

try:
    import httpx
except ImportError as _exc:
    import sys
    sys.exit(f"missing dependency '{_exc.name}'. run: pip install -r requirements.txt")

class ApexAPIError(Exception):
    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")

class ApexAPI:
    BASE = "https://api.mozambiquehe.re/bridge"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _sleep_for_attempt(self, attempt: int):
        time.sleep(1.0 * (attempt + 1))

    def get_player(self, platform: str, username: str) -> dict:
        params = {
            "auth": self.api_key,
            "player": username,
            "platform": platform,
        }
        last_exc = None
        with httpx.Client(timeout=30.0) as client:
            for attempt in range(3):
                try:
                    r = client.get(self.BASE, params=params)
                    r.raise_for_status()
                    return r.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        retry_after = 2
                        try:
                            retry_after = int(e.response.headers.get("Retry-After", "2"))
                        except ValueError:
                            pass
                        time.sleep(retry_after)
                        continue
                    if e.response.status_code == 404:
                        raise ApexAPIError("not_found")
                    if e.response.status_code == 403:
                        raise ApexAPIError("forbidden", "api key rejected")
                    if e.response.status_code >= 500:
                        last_exc = e
                        self._sleep_for_attempt(attempt)
                        continue
                    raise ApexAPIError(f"error_{e.response.status_code}")
                except httpx.RequestError as e:
                    last_exc = e
                    self._sleep_for_attempt(attempt)
                    continue

        raise ApexAPIError("error", str(last_exc))
