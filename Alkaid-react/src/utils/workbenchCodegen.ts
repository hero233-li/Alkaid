import type { WorkbenchFormFieldPayload, WorkbenchRequestPayload } from '../types';

export type RequestCodeLanguage = 'shell' | 'javascript' | 'java' | 'python' | 'http';

export const REQUEST_CODE_LANGUAGE_OPTIONS: Array<{ label: string; value: RequestCodeLanguage }> = [
  { label: 'Shell', value: 'shell' },
  { label: 'JavaScript', value: 'javascript' },
  { label: 'Java', value: 'java' },
  { label: 'Python', value: 'python' },
  { label: 'HTTP', value: 'http' },
];

function activeFormFields(payload: WorkbenchRequestPayload) {
  return (payload.formFields || []).filter(
    (field) => field.enabled !== false && field.name?.trim(),
  );
}

function headerEntries(payload: WorkbenchRequestPayload, skipContentType = false) {
  return Object.entries(payload.headers || {}).filter(
    ([name]) => !skipContentType || name.toLowerCase() !== 'content-type',
  );
}

function shellQuote(value: string) {
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function stringLiteral(value: string) {
  return JSON.stringify(value || '');
}

function urlEncodedBody(fields: WorkbenchFormFieldPayload[]) {
  const params = new URLSearchParams();
  fields.forEach((field) => {
    if (field.type !== 'file') {
      params.append(field.name.trim(), field.value || '');
    }
  });
  return params.toString();
}

function requestBody(payload: WorkbenchRequestPayload) {
  if (payload.bodyMode === 'form-urlencoded') {
    const encoded = urlEncodedBody(activeFormFields(payload));
    return encoded || payload.body || '';
  }
  if (payload.bodyMode === 'json' || payload.bodyMode === 'raw') {
    return payload.body || '';
  }
  return '';
}

function generateCurlCode(payload: WorkbenchRequestPayload) {
  const lines = [`curl --location --request ${payload.method} ${shellQuote(payload.url)}`];
  headerEntries(payload, payload.bodyMode === 'form-data').forEach(([name, value]) => {
    lines.push(`  --header ${shellQuote(`${name}: ${value}`)}`);
  });

  if (payload.bodyMode === 'form-data') {
    activeFormFields(payload).forEach((field) => {
      const value = field.type === 'file' ? `@${field.fileName || '<file>'}` : field.value || '';
      lines.push(`  --form ${shellQuote(`${field.name}=${value}`)}`);
    });
  } else if (payload.bodyMode === 'form-urlencoded') {
    const fields = activeFormFields(payload);
    if (fields.length) {
      fields.forEach((field) => {
        if (field.type !== 'file') {
          lines.push(`  --data-urlencode ${shellQuote(`${field.name}=${field.value || ''}`)}`);
        }
      });
    } else if (payload.body) {
      lines.push(`  --data ${shellQuote(payload.body)}`);
    }
  } else if (payload.bodyMode !== 'none' && payload.body) {
    lines.push(`  --data ${shellQuote(payload.body)}`);
  }

  return lines.join(' \\\n');
}

function generateJavascriptCode(payload: WorkbenchRequestPayload) {
  const lines = ['const headers = new Headers();'];
  headerEntries(payload, payload.bodyMode === 'form-data').forEach(([name, value]) => {
    lines.push(`headers.append(${stringLiteral(name)}, ${stringLiteral(value)});`);
  });

  let bodyExpression = '';
  if (payload.bodyMode === 'form-data') {
    lines.push('', 'const formData = new FormData();');
    activeFormFields(payload).forEach((field) => {
      if (field.type === 'file') {
        lines.push(
          `// formData.append(${stringLiteral(field.name)}, fileInput.files[0], ${stringLiteral(field.fileName || 'file')});`,
        );
      } else {
        lines.push(
          `formData.append(${stringLiteral(field.name)}, ${stringLiteral(field.value || '')});`,
        );
      }
    });
    bodyExpression = 'formData';
  } else if (payload.bodyMode === 'form-urlencoded') {
    const fields = activeFormFields(payload);
    if (fields.length) {
      lines.push('', 'const body = new URLSearchParams();');
      fields.forEach((field) => {
        if (field.type !== 'file') {
          lines.push(
            `body.append(${stringLiteral(field.name)}, ${stringLiteral(field.value || '')});`,
          );
        }
      });
      bodyExpression = 'body.toString()';
    } else if (payload.body) {
      bodyExpression = stringLiteral(payload.body);
    }
  } else if (payload.bodyMode !== 'none' && payload.body) {
    bodyExpression = stringLiteral(payload.body);
  }

  lines.push('', 'const requestOptions = {');
  lines.push(`  method: ${stringLiteral(payload.method)},`);
  lines.push('  headers,');
  if (bodyExpression) {
    lines.push(`  body: ${bodyExpression},`);
  }
  lines.push('  redirect: "follow",');
  lines.push('};', '');
  lines.push(`fetch(${stringLiteral(payload.url)}, requestOptions)`);
  lines.push('  .then((response) => response.text())');
  lines.push('  .then((result) => console.log(result))');
  lines.push('  .catch((error) => console.error(error));');
  return lines.join('\n');
}

function generateJavaCode(payload: WorkbenchRequestPayload) {
  const body = requestBody(payload);
  const publisher = body
    ? 'HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8)'
    : 'HttpRequest.BodyPublishers.noBody()';
  const lines = [
    'import java.net.URI;',
    'import java.net.http.HttpClient;',
    'import java.net.http.HttpRequest;',
    'import java.net.http.HttpResponse;',
    'import java.nio.charset.StandardCharsets;',
    'import java.time.Duration;',
    '',
    'HttpClient client = HttpClient.newHttpClient();',
    'HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()',
    `    .uri(URI.create(${stringLiteral(payload.url)}))`,
    `    .timeout(Duration.ofSeconds(${payload.timeoutSeconds || 30}));`,
  ];

  headerEntries(payload, payload.bodyMode === 'form-data').forEach(([name, value]) => {
    lines.push(`requestBuilder.header(${stringLiteral(name)}, ${stringLiteral(value)});`);
  });

  if (payload.bodyMode === 'form-data') {
    lines.push(
      '',
      '// form-data 文件字段需要按本地文件流组装 multipart body，这里先保留字段清单。',
    );
    activeFormFields(payload).forEach((field) => {
      const value = field.type === 'file' ? `@${field.fileName || '<file>'}` : field.value || '';
      lines.push(`// ${field.name}: ${value}`);
    });
  } else if (body) {
    lines.push('', `String body = ${stringLiteral(body)};`);
  }

  lines.push('', 'HttpRequest request = requestBuilder');
  lines.push(
    `    .method(${stringLiteral(payload.method)}, ${payload.bodyMode === 'form-data' ? 'HttpRequest.BodyPublishers.noBody()' : publisher})`,
  );
  lines.push('    .build();', '');
  lines.push(
    'HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));',
  );
  lines.push('System.out.println(response.statusCode());');
  lines.push('System.out.println(response.body());');
  return lines.join('\n');
}

function pythonDict(entries: Array<[string, string]>) {
  if (!entries.length) {
    return '{}';
  }
  return `{\n${entries.map(([name, value]) => `    ${stringLiteral(name)}: ${stringLiteral(value)},`).join('\n')}\n}`;
}

function generatePythonCode(payload: WorkbenchRequestPayload) {
  const skipContentType = payload.bodyMode === 'form-data';
  const lines = [
    'import requests',
    '',
    `url = ${stringLiteral(payload.url)}`,
    `headers = ${pythonDict(headerEntries(payload, skipContentType))}`,
  ];
  const fields = activeFormFields(payload);

  if (payload.bodyMode === 'form-data') {
    const textFields = fields
      .filter((field) => field.type !== 'file')
      .map((field) => [field.name, field.value || ''] as [string, string]);
    const fileFields = fields.filter((field) => field.type === 'file');
    lines.push(`data = ${pythonDict(textFields)}`);
    if (fileFields.length) {
      lines.push('files = {');
      fileFields.forEach((field) => {
        const fileName = field.fileName || 'file';
        lines.push(
          `    ${stringLiteral(field.name)}: (${stringLiteral(fileName)}, open(${stringLiteral(fileName)}, "rb")),`,
        );
      });
      lines.push('}');
      lines.push(
        `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers, data=data, files=files)`,
      );
    } else {
      lines.push(
        `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers, data=data)`,
      );
    }
  } else if (payload.bodyMode === 'form-urlencoded') {
    const dataFields = fields
      .filter((field) => field.type !== 'file')
      .map((field) => [field.name, field.value || ''] as [string, string]);
    if (dataFields.length) {
      lines.push(`data = ${pythonDict(dataFields)}`);
      lines.push(
        `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers, data=data)`,
      );
    } else {
      lines.push(`payload = ${stringLiteral(payload.body || '')}`);
      lines.push(
        `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers, data=payload)`,
      );
    }
  } else if (payload.bodyMode !== 'none' && payload.body) {
    lines.push(`payload = ${stringLiteral(payload.body)}`);
    lines.push(
      `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers, data=payload)`,
    );
  } else {
    lines.push(
      `response = requests.request(${stringLiteral(payload.method)}, url, headers=headers)`,
    );
  }

  lines.push('', 'print(response.status_code)', 'print(response.text)');
  return lines.join('\n');
}

function generateHttpCode(payload: WorkbenchRequestPayload) {
  let path: string;
  let host = '';
  try {
    const parsed = new URL(payload.url);
    path = `${parsed.pathname || '/'}${parsed.search}`;
    host = parsed.host;
  } catch {
    path = payload.url;
  }

  const lines = [`${payload.method} ${path} HTTP/1.1`];
  if (host && !headerEntries(payload).some(([name]) => name.toLowerCase() === 'host')) {
    lines.push(`Host: ${host}`);
  }
  headerEntries(payload).forEach(([name, value]) => {
    lines.push(`${name}: ${value}`);
  });

  const body =
    payload.bodyMode === 'form-data'
      ? activeFormFields(payload)
          .map(
            (field) =>
              `${field.name}=${field.type === 'file' ? `@${field.fileName || '<file>'}` : field.value || ''}`,
          )
          .join('\n')
      : requestBody(payload);
  if (body) {
    lines.push('', body);
  }
  return lines.join('\n');
}

export function generateRequestCode(
  payload: WorkbenchRequestPayload,
  language: RequestCodeLanguage,
) {
  if (language === 'javascript') {
    return generateJavascriptCode(payload);
  }
  if (language === 'java') {
    return generateJavaCode(payload);
  }
  if (language === 'python') {
    return generatePythonCode(payload);
  }
  if (language === 'http') {
    return generateHttpCode(payload);
  }
  return generateCurlCode(payload);
}
