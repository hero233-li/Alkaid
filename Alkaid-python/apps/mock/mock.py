from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

import httpx

MockHandler = Callable[[httpx.Request], httpx.Response]
RouteMatcher = Callable[[httpx.Request], bool]


@dataclass(frozen=True)
class _Route:
    matcher: RouteMatcher
    handler: MockHandler


class MockTransportRouter:
    """Small reusable router for feature-owned httpx mock scenarios."""

    def __init__(self) -> None:
        self._routes: list[_Route] = []

    def register(
        self,
        method: str,
        path: str,
        handler: MockHandler,
        *,
        prefix: bool = False,
    ) -> MockTransportRouter:
        normalized_method = method.upper()

        def matcher(request: httpx.Request) -> bool:
            path_matches = request.url.path.startswith(path) if prefix else request.url.path == path
            return request.method.upper() == normalized_method and path_matches

        self._routes.append(_Route(matcher=matcher, handler=handler))
        return self

    def register_matcher(
        self,
        matcher: RouteMatcher,
        handler: MockHandler,
    ) -> MockTransportRouter:
        self._routes.append(_Route(matcher=matcher, handler=handler))
        return self

    def dispatch(self, request: httpx.Request) -> httpx.Response:
        for route in self._routes:
            if route.matcher(request):
                return route.handler(request)
        return self.json_response(
            {"message": "mock endpoint not found"},
            status_code=404,
        )

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.dispatch)

    @staticmethod
    def json_response(
        body: Any,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | list[tuple[str, str]] | None = None,
    ) -> httpx.Response:
        return httpx.Response(status_code, json=body, headers=headers)

    @staticmethod
    def html_response(
        body: str,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | list[tuple[str, str]] | None = None,
    ) -> httpx.Response:
        return httpx.Response(status_code, text=body, headers=headers)

    @staticmethod
    def parse_form(request: httpx.Request) -> dict[str, list[str]]:
        return parse_qs(request.content.decode("utf-8"), keep_blank_values=True)

    @classmethod
    def parse_json_form_field(cls, request: httpx.Request, field: str) -> Any:
        form = cls.parse_form(request)
        raw = form.get(field, [None])[0]
        if raw is None:
            raise AssertionError(f"{field} is required")
        return json.loads(raw)
