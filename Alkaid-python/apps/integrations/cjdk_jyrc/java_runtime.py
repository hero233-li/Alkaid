from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def sdk_dir() -> Path:
    value = str(getattr(settings, "APPLICATION_LINK_JAVA_SDK_DIR", "")).strip()
    if not value:
        raise ImproperlyConfigured("APPLICATION_LINK_JAVA_SDK_DIR 未配置")
    return Path(value)


def executable() -> Path:
    value = str(getattr(settings, "APPLICATION_LINK_JAVA_EXECUTABLE", "")).strip()
    if not value:
        raise ImproperlyConfigured("APPLICATION_LINK_JAVA_EXECUTABLE 未配置")
    return Path(value)


def jar() -> Path:
    value = str(getattr(settings, "APPLICATION_LINK_JAVA_JAR", "")).strip()
    if not value:
        raise ImproperlyConfigured("APPLICATION_LINK_JAVA_JAR 未配置")
    return Path(value)


def main_class() -> str:
    value = str(getattr(settings, "APPLICATION_LINK_JAVA_MAIN_CLASS", "")).strip()
    if not value:
        raise ImproperlyConfigured("APPLICATION_LINK_JAVA_MAIN_CLASS 未配置")
    return value


def output_encoding() -> str:
    return str(getattr(settings, "APPLICATION_LINK_JAVA_OUTPUT_ENCODING", "gbk"))


def timeout_seconds() -> float:
    return float(getattr(settings, "APPLICATION_LINK_JAVA_TIMEOUT_SECONDS", 120))
