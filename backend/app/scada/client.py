from typing import Any

import httpx


class ScadaApiError(Exception):
    """Base exception for Rapid SCADA API errors."""


class ScadaLoginError(ScadaApiError):
    """Raised when Rapid SCADA login fails."""


class ScadaRequestError(ScadaApiError):
    """Raised when a Rapid SCADA API request fails."""


class ScadaApiClient:
    """Read-only Rapid SCADA Web API client."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.timeout = httpx.Timeout(timeout_seconds)

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self) -> "ScadaApiClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def login(self) -> dict[str, Any]:
        """Login to Rapid SCADA and keep session cookies inside the HTTP client."""
        payload_variants = [
            {"Username": self.username, "Password": self.password},
            {"username": self.username, "password": self.password},
        ]

        last_response_text = ""

        for payload in payload_variants:
            try:
                response = await self._client.post("Api/Auth/Login", json=payload)
                last_response_text = response.text
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise ScadaLoginError("Timeout κατά το login στο Rapid SCADA API.") from exc
            except httpx.HTTPStatusError as exc:
                last_response_text = exc.response.text
                continue
            except httpx.RequestError as exc:
                raise ScadaLoginError(
                    f"Αποτυχία σύνδεσης στο Rapid SCADA API: {exc}"
                ) from exc

            data = self._safe_json(response)

            if self._is_success_result(data):
                return data

            last_response_text = response.text

        raise ScadaLoginError(
            "Απέτυχε το login στο Rapid SCADA API. "
            f"Τελευταίο response: {last_response_text[:500]}"
        )

    async def get_current_data(self, cnl_nums: str) -> Any:
        """Read current data for the requested channel numbers."""
        try:
            response = await self._client.get(
                "Api/Main/GetCurData",
                params={"cnlNums": cnl_nums},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ScadaRequestError("Timeout κατά το GetCurData.") from exc
        except httpx.HTTPStatusError as exc:
            raise ScadaRequestError(
                f"Rapid SCADA GetCurData επέστρεψε HTTP {exc.response.status_code}: "
                f"{exc.response.text[:500]}"
            ) from exc
        except httpx.RequestError as exc:
            raise ScadaRequestError(f"Αποτυχία GetCurData: {exc}") from exc

        return self._safe_json(response)

    async def get_raw(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        ) -> httpx.Response:
            """Send a read-only GET request to Rapid SCADA and return the raw response."""
            safe_path = path.lstrip("/")

            try:
                response = await self._client.get(safe_path, params=params)
            except httpx.TimeoutException as exc:
                raise ScadaRequestError(f"Timeout κατά το GET {safe_path}.") from exc
            except httpx.RequestError as exc:
                raise ScadaRequestError(f"Αποτυχία GET {safe_path}: {exc}") from exc

            return response    

    async def logout(self) -> Any:
        """Logout from Rapid SCADA."""
        try:
            response = await self._client.post("Api/Auth/Logout")
            response.raise_for_status()
        except httpx.RequestError:
            return None
        except httpx.HTTPStatusError:
            return None

        return self._safe_json(response)

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {
                "raw_text": response.text,
                "content_type": response.headers.get("content-type"),
            }

    @staticmethod
    def _is_success_result(data: Any) -> bool:
        if not isinstance(data, dict):
            return False

        for key in ("ok", "Ok", "success", "Success", "status", "Status"):
            value = data.get(key)
            if value is True:
                return True

        return False