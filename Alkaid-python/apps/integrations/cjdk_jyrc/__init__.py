"""CJDK-JYRC product application integration.

The product flow generates an application link through the local Java SDK,
opens it to establish one HTTP session, and then reuses that session for
agreement query, preview and reading.
"""

from apps.integrations.cjdk_jyrc import config as config
from apps.integrations.cjdk_jyrc import java_runtime as _java_runtime

# Compatibility bridge for the JavaGateway implementation. Keeping the
# runtime settings in a small module avoids mixing executable configuration
# with the agreement HTTP environment mapping.
config.java_sdk_dir = _java_runtime.sdk_dir
config.java_executable = _java_runtime.executable
config.java_jar = _java_runtime.jar
config.java_main_class = _java_runtime.main_class
config.java_output_encoding = _java_runtime.output_encoding
config.java_timeout_seconds = _java_runtime.timeout_seconds
