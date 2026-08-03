function randomHex(bytes: number) {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.getRandomValues === 'function') {
    const values = new Uint8Array(bytes);
    cryptoApi.getRandomValues(values);
    return Array.from(values, (value) => value.toString(16).padStart(2, '0')).join('');
  }
  return Array.from({ length: bytes * 2 }, () => Math.floor(Math.random() * 16).toString(16)).join(
    '',
  );
}

export function createRequestId() {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }
  const timestamp = Date.now().toString(16).padStart(12, '0');
  return `${timestamp}-${randomHex(10)}`;
}

export function createWorkflowHeaders() {
  const requestId = createRequestId();
  return {
    'X-Idempotency-Key': requestId,
    'X-Trace-ID': requestId.split('-').join(''),
  };
}
