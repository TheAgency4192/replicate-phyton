import os
from json import JSONDecodeError

import httpx
import requests
from requests.adapters import HTTPAdapter, Retry

from replicate.__about__ import __version__
from replicate.exceptions import ReplicateError
from replicate.model import ModelCollection
from replicate.prediction import PredictionCollection


class Client:
    def __init__(self, api_token=None) -> None:
        super().__init__()
        # Client is instantiated at import time, so do as little as possible.
        # This includes resolving environment variables -- they might be set programmatically.
        self.api_token = api_token
        self.base_url = os.environ.get(
            "REPLICATE_API_BASE_URL", "https://api.replicate.com"
        )
        self.poll_interval = float(os.environ.get("REPLICATE_POLL_INTERVAL", "0.5"))

        max_retries: int = 5
        self.httpx_transport = httpx.AsyncHTTPTransport(retries=max_retries)

        # TODO: make thread safe
        self.read_session = requests.Session()
        read_retries = Retry(
            total=5,
            backoff_factor=2,
            # Only retry 500s on GET so we don't unintionally mutute data
            method_whitelist=["GET"],
            # https://support.cloudflare.com/hc/en-us/articles/115003011431-Troubleshooting-Cloudflare-5XX-errors
            status_forcelist=[
                429,
                500,
                502,
                503,
                504,
                520,
                521,
                522,
                523,
                524,
                526,
                527,
            ],
        )
        self.read_session.mount("http://", HTTPAdapter(max_retries=read_retries))
        self.read_session.mount("https://", HTTPAdapter(max_retries=read_retries))

        self.write_session = requests.Session()
        write_retries = Retry(
            total=5,
            backoff_factor=2,
            method_whitelist=["POST", "PUT"],
            # Only retry POST/PUT requests on rate limits, so we don't unintionally mutute data
            status_forcelist=[429],
        )
        self.write_session.mount("http://", HTTPAdapter(max_retries=write_retries))
        self.write_session.mount("https://", HTTPAdapter(max_retries=write_retries))

    def _request(self, method: str, path: str, **kwargs):
        # from requests.Session
        if method in ["GET", "OPTIONS"]:
            kwargs.setdefault("allow_redirects", True)
        if method in ["HEAD"]:
            kwargs.setdefault("allow_redirects", False)
        kwargs.setdefault("headers", {})
        kwargs["headers"].update(self._headers())
        session = self.read_session
        if method in ["POST", "PUT", "DELETE", "PATCH"]:
            session = self.write_session
        resp = session.request(method, self.base_url + path, **kwargs)
        if 400 <= resp.status_code < 600:
            try:
                raise ReplicateError(resp.json()["detail"])
            except (JSONDecodeError, KeyError):
                pass
            raise ReplicateError(f"HTTP error: {resp.status_code, resp.reason}")
        return resp

    async def _request_async(self, method: str, path: str, **kwargs):
        # from requests.Session
        if method in ["GET", "OPTIONS"]:
            kwargs.setdefault("allow_redirects", True)
        if method in ["HEAD"]:
            kwargs.setdefault("allow_redirects", False)
        kwargs.setdefault("headers", {})
        kwargs["headers"].update(self._headers())

        async with httpx.AsyncClient(
            follow_redirects=True,
            transport=self.httpx_transport,
        ) as client:
            if "allow_redirects" in kwargs:
                kwargs.pop("allow_redirects")

            resp = await client.request(method, self.base_url + path, **kwargs)

        if 400 <= resp.status_code < 600:
            try:
                raise ReplicateError(resp.json()["detail"])
            except (JSONDecodeError, KeyError):
                pass
            raise ReplicateError(f"HTTP error: {resp.status_code, resp.reason}")
        return resp

    def _headers(self):
        return {
            "Authorization": f"Token {self._api_token()}",
            "User-Agent": f"replicate-python@{__version__}",
        }

    def _api_token(self):
        token = self.api_token
        # Evaluate lazily in case environment variable is set with dotenv, or something
        if token is None:
            token = os.environ.get("REPLICATE_API_TOKEN")
        if not token:
            raise ReplicateError(
                """No API token provided. You need to set the REPLICATE_API_TOKEN environment variable or create a client with `replicate.Client(api_token=...)`.

You can find your API key on https://replicate.com"""
            )
        return token

    @property
    def models(self) -> ModelCollection:
        return ModelCollection(client=self)

    @property
    def predictions(self) -> PredictionCollection:
        return PredictionCollection(client=self)
