import base64
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile


class WordImportError(ValueError):
    pass


_IMAGE_SOURCE = re.compile(r'(?P<prefix>src=["\'])(?P<path>[^"\']+)(?P<suffix>["\'])', re.I)


def _office_binary() -> str:
    configured = os.getenv("LIBREOFFICE_BINARY", "").strip().strip('"')
    if configured and Path(configured).is_file():
        return configured
    command_candidates = [configured, "libreoffice", "soffice"]
    for command in command_candidates:
        if not command:
            continue
        resolved = shutil.which(command)
        if resolved:
            return resolved

    program_files = [
        os.getenv("PROGRAMFILES", ""),
        os.getenv("PROGRAMFILES(X86)", ""),
        os.getenv("LOCALAPPDATA", ""),
    ]
    path_candidates = [
        *(Path(root) / "LibreOffice" / "program" / "soffice.exe" for root in program_files if root),
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("/usr/bin/libreoffice"),
        Path("/usr/local/bin/libreoffice"),
        Path("/snap/bin/libreoffice"),
    ]
    for candidate in path_candidates:
        if candidate.is_file():
            return str(candidate)

    raise WordImportError(
        "未找到 LibreOffice"
    )


def _word_powershell_binary() -> str | None:
    """Return PowerShell on Windows, where an installed Word can do the conversion."""
    if not sys.platform.startswith("win"):
        return None
    configured = os.getenv("POWERSHELL_BINARY", "").strip().strip('"')
    for command in (configured, "pwsh.exe", "powershell.exe", "pwsh", "powershell"):
        if not command:
            continue
        resolved = shutil.which(command)
        if resolved:
            return resolved
    return None


def _textutil_binary() -> str | None:
    """Return the built-in macOS document converter when it is available."""
    configured = os.getenv("TEXTUTIL_BINARY", "").strip().strip('"')
    if configured and Path(configured).is_file():
        return configured
    resolved = shutil.which("textutil")
    if resolved:
        return resolved
    candidate = Path("/usr/bin/textutil")
    return str(candidate) if candidate.is_file() else None


def _conversion_backend() -> tuple[str, str]:
    try:
        return "libreoffice", _office_binary()
    except WordImportError:
        pass

    word_powershell = _word_powershell_binary()
    if word_powershell:
        return "word", word_powershell

    textutil = _textutil_binary()
    if textutil:
        return "textutil", textutil

    raise WordImportError(
        "服务器缺少 Word 转换能力；Windows 请安装 Microsoft Word 或 LibreOffice，"
        "macOS 可使用系统自带 textutil，也可配置 LIBREOFFICE_BINARY"
    )


_WORD_CONVERT_SCRIPT = r"""
param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][int]$Format
)
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($InputPath, $false, $true)
    $document.SaveAs2($OutputPath, $Format)
}
finally {
    if ($null -ne $document) { $document.Close($false) }
    if ($null -ne $word) { $word.Quit() }
    if ($null -ne $document) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
""".strip()


def _run_conversion(
    backend: str,
    binary: str,
    input_path: Path,
    output_path: Path,
    output_dir: Path,
    *,
    export_docx: bool,
) -> subprocess.CompletedProcess[bytes]:
    if backend == "libreoffice":
        target_format = "docx:Office Open XML Text" if export_docx else "html"
        command = [
            binary,
            "--headless",
            f"-env:UserInstallation={output_dir.joinpath('office-profile').as_uri()}",
            "--convert-to",
            target_format,
            "--outdir",
            str(output_dir),
            str(input_path),
        ]
    elif backend == "word":
        script_path = output_dir / "convert-word.ps1"
        script_path.write_text(_WORD_CONVERT_SCRIPT, encoding="utf-8")
        # Word SaveFormat: 10 = filtered HTML; 16 = default DOCX document.
        command = [
            binary,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-InputPath",
            str(input_path),
            "-OutputPath",
            str(output_path),
            "-Format",
            "16" if export_docx else "10",
        ]
    else:
        command = [
            binary,
            "-convert",
            "docx" if export_docx else "html",
            "-output",
            str(output_path),
            str(input_path),
        ]
    return subprocess.run(command, check=False, capture_output=True, timeout=30)


def _inline_local_images(html: str, output_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        source = match.group("path")
        if source.startswith(("data:", "http://", "https://")):
            return match.group(0)
        image_path = (output_dir / source).resolve()
        if output_dir.resolve() not in image_path.parents or not image_path.is_file():
            return match.group(0)
        mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f'{match.group("prefix")}data:{mime_type};base64,{encoded}{match.group("suffix")}'

    return _IMAGE_SOURCE.sub(replace, html)


def convert_legacy_word_to_html(uploaded_file: UploadedFile) -> str:
    if uploaded_file.size > 128 * 1024 * 1024:
        raise WordImportError("Word 文件不能超过 128 MB")
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".doc", ".docx"}:
        raise WordImportError("请选择 .doc 或 .docx 文件")
    backend, conversion_binary = _conversion_backend()

    with tempfile.TemporaryDirectory(prefix="alioth-word-") as temporary_directory:
        output_dir = Path(temporary_directory)
        input_path = output_dir / f"input{suffix}"
        with input_path.open("wb") as target:
            for chunk in uploaded_file.chunks():
                target.write(chunk)
        html_path = output_dir / "input.html"
        try:
            completed = _run_conversion(
                backend,
                conversion_binary,
                input_path,
                html_path,
                output_dir,
                export_docx=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WordImportError("Word 文件转换超时或转换组件不可用") from exc
        if not html_path.is_file():
            html_path = next(output_dir.glob("*.html"), html_path)
        if completed.returncode != 0 or not html_path.is_file():
            if backend == "word":
                raise WordImportError(
                    "无法调用 Microsoft Word 转换文件，请确认 Word 已安装、文件未损坏，"
                    "且服务账户可启动 Word"
                )
            raise WordImportError("无法读取该 Word 文件，请确认文件未损坏或未加密")
        html = html_path.read_text(encoding="utf-8", errors="replace")
        return _inline_local_images(html, output_dir)


def convert_html_to_docx(html: str) -> bytes:
    encoded = html.encode("utf-8")
    if len(encoded) > 128 * 1024 * 1024:
        raise WordImportError("在线 Word 内容不能超过 128 MB")
    backend, conversion_binary = _conversion_backend()
    document_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Microsoft YaHei', SimSun, sans-serif; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 6px 8px; border: 1px solid #999; }}
    img {{ max-width: 100%; height: auto; }}
  </style>
</head>
<body>{html}</body>
</html>"""

    with tempfile.TemporaryDirectory(prefix="alioth-word-export-") as temporary_directory:
        output_dir = Path(temporary_directory)
        input_path = output_dir / "document.html"
        input_path.write_text(document_html, encoding="utf-8")
        docx_path = output_dir / "document.docx"
        try:
            completed = _run_conversion(
                backend,
                conversion_binary,
                input_path,
                docx_path,
                output_dir,
                export_docx=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WordImportError("Word 文件导出超时或转换组件不可用") from exc
        if completed.returncode != 0 or not docx_path.is_file():
            raise WordImportError("无法生成 .docx 文件")
        return docx_path.read_bytes()
