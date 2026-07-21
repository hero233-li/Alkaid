export const API_RESPONSE_DELAY_MS = 1000;

export const ENABLE_HIGH_FREQUENCY =
  String(import.meta.env.VITE_ENABLE_HIGH_FREQUENCY || '').toLowerCase() === 'true';
