export const API_PROGRESS_EVENT = 'alioth:api-progress';

export interface ApiProgressDetail {
  pending: number;
  delayMs: number;
}

export function emitApiProgress(detail: ApiProgressDetail) {
  window.dispatchEvent(new CustomEvent<ApiProgressDetail>(API_PROGRESS_EVENT, { detail }));
}
