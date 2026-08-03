from __future__ import annotations

import gzip
import re
import zlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from zipfile import BadZipFile, ZipFile, ZipInfo

SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
MAX_ARCHIVE_ENTRIES = 5_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_IMPORTED_REQUESTS = 500
MAX_BODY_BYTES = 2_000_000
MAX_RESPONSE_CHARACTERS = 1_000_000
REQUEST_FILE = re.compile(r"(?:^|/)raw/(\d+)_c\.txt$", re.IGNORECASE)
TRANSPORT_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class SazImportError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSazRequest:
    position: int
    name: str
    method: str
    url: str
    request_payload: dict[str, Any]
    response_status: int | None
    response_headers: dict[str, list[str]]
    response_body: str


def parse_saz(content: bytes) -> tuple[ParsedSazRequest, ...]:
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise SazImportError("文件不是有效的 Fiddler SAZ 压缩包") from exc
    with archive:
        infos = archive.infolist()
        _validate_archive(infos)
        names = {_normalized_name(info.filename).lower(): info for info in infos}
        request_files: list[tuple[int, ZipInfo]] = []
        for info in infos:
            normalized = _normalized_name(info.filename)
            match = REQUEST_FILE.search(normalized)
            if match:
                request_files.append((int(match.group(1)), info))
        request_files.sort(key=lambda item: item[0])
        if len(request_files) > MAX_IMPORTED_REQUESTS:
            raise SazImportError(f"SAZ 中的请求数量超过上限 {MAX_IMPORTED_REQUESTS}")

        parsed: list[ParsedSazRequest] = []
        for session_id, request_info in request_files:
            item = _parse_session(
                position=len(parsed) + 1,
                request_bytes=archive.read(request_info),
                response_bytes=_read_optional(
                    archive,
                    names,
                    _session_peer_name(request_info.filename, session_id, "s"),
                ),
            )
            if item is not None:
                parsed.append(item)
        if not parsed:
            raise SazImportError("SAZ 中没有可导入的 HTTP 请求")
        return tuple(parsed)


def _validate_archive(infos: list[ZipInfo]) -> None:
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise SazImportError(f"SAZ 文件条目超过上限 {MAX_ARCHIVE_ENTRIES}")
    total_size = 0
    for info in infos:
        if info.flag_bits & 0x1:
            raise SazImportError("不支持加密的 SAZ 文件")
        normalized = _normalized_name(info.filename)
        if PurePosixPath(normalized).is_absolute() or ".." in PurePosixPath(normalized).parts:
            raise SazImportError("SAZ 文件包含不安全路径")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise SazImportError(f"SAZ 解压后总大小超过 {MAX_ARCHIVE_UNCOMPRESSED_BYTES} bytes")


def _parse_session(
    *,
    position: int,
    request_bytes: bytes,
    response_bytes: bytes | None,
) -> ParsedSazRequest | None:
    request_head, request_body = _split_message(request_bytes)
    request_lines = request_head.decode("iso-8859-1").splitlines()
    if not request_lines:
        return None
    request_line = request_lines[0].lstrip("\ufeff").strip().split(" ", 2)
    if len(request_line) < 2:
        return None
    method = request_line[0].upper()
    if method not in SUPPORTED_METHODS:
        return None
    request_headers = _parse_request_headers(request_lines[1:])
    url = _absolute_url(request_line[1], request_headers)
    if not url:
        return None
    body_mode, body, form_fields = _request_body(
        request_body,
        _first_header(request_headers, "content-type"),
        position,
    )
    safe_headers = {
        name: value
        for name, value in request_headers.items()
        if name.lower() not in TRANSPORT_HEADERS
    }
    response_status, response_headers, response_body = _parse_response(response_bytes)
    path = urlsplit(url).path.rstrip("/") or "/"
    display_path = path.rsplit("/", 1)[-1] or path
    return ParsedSazRequest(
        position=position,
        name=f"{method} {display_path}"[:255],
        method=method,
        url=url,
        request_payload={
            "method": method,
            "url": url,
            "headers": safe_headers,
            "bodyMode": body_mode,
            "body": body,
            "formFields": form_fields,
            "timeoutSeconds": 30,
        },
        response_status=response_status,
        response_headers=response_headers,
        response_body=response_body,
    )


def _request_body(
    body: bytes,
    content_type: str,
    position: int,
) -> tuple[str, str, list[dict[str, Any]]]:
    if not body:
        return "none", "", []
    if len(body) > MAX_BODY_BYTES:
        raise SazImportError(f"第 {position} 个请求体超过 {MAX_BODY_BYTES} bytes")
    text = _decode_text(body, content_type)
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/x-www-form-urlencoded":
        fields = [
            {
                "id": f"saz-{position}-{index}",
                "enabled": True,
                "type": "text",
                "name": name,
                "value": value,
            }
            for index, (name, value) in enumerate(parse_qsl(text, keep_blank_values=True), start=1)
        ]
        return "form-urlencoded", "", fields
    if media_type == "application/json" or media_type.endswith("+json"):
        return "json", text, []
    return "raw", text, []


def _parse_response(
    response_bytes: bytes | None,
) -> tuple[int | None, dict[str, list[str]], str]:
    if not response_bytes:
        return None, {}, ""
    head, body = _split_message(response_bytes)
    lines = head.decode("iso-8859-1").splitlines()
    status: int | None = None
    if lines:
        parts = lines[0].split(" ", 2)
        if len(parts) > 1 and parts[1].isdigit():
            status = int(parts[1])
    headers = _parse_response_headers(lines[1:])
    encoding = _first_response_header(headers, "content-encoding").lower()
    try:
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)
    except (OSError, zlib.error):
        pass
    text = _decode_text(body, _first_response_header(headers, "content-type"))
    return status, headers, text[:MAX_RESPONSE_CHARACTERS]


def _split_message(content: bytes) -> tuple[bytes, bytes]:
    for separator in (b"\r\n\r\n", b"\n\n"):
        if separator in content:
            head, body = content.split(separator, 1)
            return head, body
    return content, b""


def _parse_request_headers(lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    current_name: str | None = None
    for line in lines:
        if line[:1] in {" ", "\t"} and current_name:
            headers[current_name] = f"{headers[current_name]} {line.strip()}"
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        current_name = name.strip()
        if not current_name:
            continue
        separator = "; " if current_name.lower() == "cookie" else ", "
        if current_name in headers:
            headers[current_name] = f"{headers[current_name]}{separator}{value.strip()}"
        else:
            headers[current_name] = value.strip()
    return headers


def _parse_response_headers(lines: list[str]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    current_name: str | None = None
    for line in lines:
        if line[:1] in {" ", "\t"} and current_name:
            headers[current_name][-1] = f"{headers[current_name][-1]} {line.strip()}"
            continue
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        current_name = name.strip().lower()
        if current_name:
            headers.setdefault(current_name, []).append(value.strip())
    return headers


def _absolute_url(target: str, headers: dict[str, str]) -> str | None:
    if target.startswith(("http://", "https://")):
        return target
    original = _first_header(headers, "x-original-url")
    if original.startswith(("http://", "https://")):
        return original
    host = _first_header(headers, "host")
    if not host:
        return None
    protocol = "https" if host.rsplit(":", 1)[-1] == "443" else "http"
    path = target if target.startswith("/") else f"/{target}"
    return f"{protocol}://{host}{path}"


def _decode_text(content: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
    encodings = [charset_match.group(1).strip("\"'")] if charset_match else []
    encodings.extend(["utf-8", "gb18030", "iso-8859-1"])
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def _first_header(headers: dict[str, str], name: str) -> str:
    return next((value for key, value in headers.items() if key.lower() == name), "")


def _first_response_header(headers: dict[str, list[str]], name: str) -> str:
    values = headers.get(name.lower(), [])
    return values[0] if values else ""


def _normalized_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _session_peer_name(request_name: str, session_id: int, suffix: str) -> str:
    normalized = _normalized_name(request_name)
    prefix = normalized[: normalized.lower().rfind("raw/")]
    return f"{prefix}raw/{session_id}_{suffix}.txt".lower()


def _read_optional(
    archive: ZipFile,
    names: dict[str, ZipInfo],
    normalized_name: str,
) -> bytes | None:
    info = names.get(normalized_name)
    return archive.read(info) if info else None
