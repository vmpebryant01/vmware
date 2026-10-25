"""HTTPS transport and component authentication. Author: Paul Bryant."""

import base64
import json
import os
import socket
import ssl
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener


class ApiError(RuntimeError):
    """A sanitized API failure that does not include response bodies or secrets."""

    def __init__(self, message, status=None, category=None):
        super().__init__(message)
        self.status = status
        self.category = category


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpClient:
    def __init__(self, target, timeout=30, retries=2):
        self.target = target
        self.timeout = timeout
        self.retries = retries
        self.headers = {"Accept": "application/json"}
        self._owns_session = False
        self._product_state = {}
        self.collection_metadata = {}
        verify = target.get("verify_tls", True)
        if verify is not True and not isinstance(verify, str):
            raise ApiError("TLS verification must be enabled.")
        try:
            context = ssl.create_default_context(cafile=verify if isinstance(verify, str) else None)
        except (OSError, ssl.SSLError) as exc:
            raise ApiError("Cannot load the trusted CA bundle.", category="tls") from exc
        # Explicit target credentials, no ambient proxy or netrc credentials.
        self.opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), NoRedirect())

    def request(self, method, path, params=None, body=None, headers=None, include_headers=False):
        """Allow inventory GETs, exact read-query POSTs, and documented session calls."""
        component = self.target["component"]
        allowed = {("sddc_manager", "POST", "/v1/tokens"),
                   ("vcenter", "POST", "/api/session"),
                   ("vcenter", "DELETE", "/api/session")}
        from .products import module_for
        product = module_for(component)
        if product is not None:
            allowed.update(product.ALLOWED_OPERATIONS)
        product_allowed = product is not None and hasattr(product, "allow_request") and product.allow_request(component, method, path)
        from . import assurance, activity
        query_modules = (assurance, activity) + ((product,) if product is not None else ())
        query_allowed = any(hasattr(module, "allow_query") and module.allow_query(component, method, path, params, body)
                            for module in query_modules)
        if method != "GET" and (component, method, path) not in allowed and not product_allowed and not query_allowed:
            raise ApiError("Only inventory reads and documented authentication calls are allowed.")
        if (not path.startswith("/") or path.startswith("//") or "\\" in path
                or "?" in path or "#" in path or any(c.isspace() for c in path)):
            raise ApiError("An API path must be relative to the configured HTTPS origin.")
        url = self.target["url"] + path
        if params:
            def query_value(value):
                return str(value).lower() if type(value) is bool else value
            encoded_params = {key: [query_value(item) for item in value] if isinstance(value, list)
                              else query_value(value) for key, value in params.items()}
            url += "?" + urlencode(encoded_params, doseq=True)
        request_headers = dict(self.headers)
        request_headers.update(headers or {})
        for value in request_headers.values():
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ApiError("Invalid authentication or request header value.")
            try:
                value.encode("latin-1")
            except UnicodeError:
                raise ApiError("Invalid authentication or request header encoding.") from None
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        attempts = self.retries + 1 if method == "GET" else 1
        for attempt in range(attempts):
            retry_delay = min(2 ** attempt, 30)
            try:
                req = Request(url, data=data, headers=request_headers, method=method)
                with self.opener.open(req, timeout=self.timeout) as response:
                    # Bound memory use; fail explicitly rather than exporting a truncated response.
                    payload = response.read(64 * 1024 * 1024 + 1)
                    if len(payload) > 64 * 1024 * 1024:
                        raise ApiError("API response exceeds the 64 MiB limit; narrow the query scope.")
                    if not payload:
                        return (None, {key.lower(): value for key, value in response.headers.items()}) if include_headers else None
                    try:
                        def reject_constant(value):
                            raise ValueError("Nonfinite JSON number")
                        document = json.loads(payload, parse_constant=reject_constant)
                        return (document, {key.lower(): value for key, value in response.headers.items()}) if include_headers else document
                    except (UnicodeError, ValueError) as exc:
                        raise ApiError("API returned a response that is not valid JSON.") from exc
            except HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                exc.close()
                if status in (429, 502, 503, 504) and attempt + 1 < attempts:
                    if retry_after.isdigit():
                        retry_delay = min(int(retry_after), 30)
                else:
                    hints = {401: "Authentication failed or expired.",
                             403: "The account cannot read this resource.",
                             404: "Endpoint unavailable; check component version and scope."}
                    message = hints.get(status, "API request failed.")
                    if 300 <= status < 400:
                        message = "Redirect refused; configure the direct component HTTPS endpoint."
                    raise ApiError(f"HTTP {status}. {message}", status=status, category="http") from None
            except ssl.SSLError:
                raise ApiError("TLS verification or negotiation failed; check the trusted CA bundle.", category="tls") from None
            except URLError as exc:
                if isinstance(exc.reason, ssl.SSLError):
                    raise ApiError("TLS verification or negotiation failed; check the trusted CA bundle.", category="tls") from None
                if attempt + 1 == attempts:
                    raise ApiError("Connection failed; check DNS, network access, and the endpoint.", category="network") from None
            except (TimeoutError, socket.timeout, ConnectionError, HTTPException):
                if attempt + 1 == attempts:
                    raise ApiError("The connection timed out or was interrupted.", category="network") from None
            time.sleep(retry_delay)
        raise ApiError("API request failed after retries.")

    def authenticate(self):
        from .products import module_for
        product = module_for(self.target["component"])
        if product is not None:
            product.authenticate(self)
            return
        username = os.environ.get(self.target["username_env"])
        password = os.environ.get(self.target["password_env"])
        if not username or not password:
            raise ApiError("Required username/password environment variables are missing or empty.")
        component = self.target["component"]
        if component != "sddc_manager" and ":" in username:
            raise ApiError("Basic authentication usernames cannot contain a colon.")
        self.headers.pop("Authorization", None)
        self.headers.pop("vmware-api-session-id", None)
        if component == "sddc_manager":
            token = self.request("POST", "/v1/tokens", body={"username": username, "password": password})
            if not isinstance(token, dict) or not isinstance(token.get("accessToken"), str) or not token["accessToken"]:
                raise ApiError("SDDC Manager did not return a usable access token.")
            self.headers["Authorization"] = "Bearer " + token["accessToken"]
        else:
            basic = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            if component == "nsx":
                self.headers["Authorization"] = "Basic " + basic
            elif component == "vcenter":
                token = self.request("POST", "/api/session", headers={"Authorization": "Basic " + basic})
                if not isinstance(token, str) or not token:
                    raise ApiError("vCenter did not return a usable session token.")
                self.headers["vmware-api-session-id"] = token
                self._owns_session = True
            else:
                raise ApiError("Unknown component.")

    def get(self, path, params=None):
        try:
            return self.request("GET", path, params=params)
        except ApiError as exc:
            if exc.status != 401 or self.target["component"] not in ("sddc_manager", "vcenter"):
                raise
        # Retry an expired token once, without retrying failed logins in a loop.
        self.authenticate()
        return self.request("GET", path, params=params)

    def close(self):
        try:
            from .products import module_for
            product = module_for(self.target["component"])
            if product is not None and hasattr(product, "close"):
                product.close(self)
            elif self._owns_session:
                self.request("DELETE", "/api/session")
        finally:
            self._owns_session = False
            self.headers.clear()
            self._product_state.clear()
