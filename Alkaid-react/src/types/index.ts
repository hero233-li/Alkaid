export interface ApiResponse<T> {
  ok: boolean;
  code?: string;
  message: string;
  data: T;
}

export interface ReleaseNote {
  id: number;
  version: string;
  content: string;
  createdBy?: number;
  createdAt: string;
}

export interface WorkbenchRequestPayload {
  method: string;
  url: string;
  headers: Record<string, string>;
  bodyMode: WorkbenchBodyMode;
  body: string;
  formFields: WorkbenchFormFieldPayload[];
  timeoutSeconds: number;
}

export type WorkbenchBodyMode = 'none' | 'json' | 'form-urlencoded' | 'form-data' | 'raw';

export type WorkbenchFormFieldType = 'text' | 'file';

export interface WorkbenchFormFieldPayload {
  id: string;
  enabled: boolean;
  type: WorkbenchFormFieldType;
  name: string;
  value: string;
  filePartName?: string;
  fileName?: string;
  contentType?: string;
}

export interface WorkbenchResponsePayload {
  success: boolean;
  statusCode: number;
  durationMs: number;
  headers: Record<string, string[]>;
  body: string;
  errorMessage?: string;
  historyId?: number;
}

export interface WorkbenchHistoryItem {
  id: number;
  name: string;
  method: string;
  url: string;
  responseStatus?: number;
  durationMs?: number;
  success: boolean;
  errorMessage?: string;
  createdAt: string;
}

export interface WorkbenchHistoryDetail extends WorkbenchHistoryItem {
  requestHeaders: Record<string, string>;
  requestPayload: WorkbenchRequestPayload;
  responseHeaders: Record<string, string[]>;
  responseBody: string;
}

export interface WorkbenchPackageRequestItem {
  id: number;
  packageId: number;
  position: number;
  name: string;
  method: string;
  url: string;
  responseStatus?: number;
}

export interface WorkbenchPackage {
  id: number;
  name: string;
  sourceFilename: string;
  requestCount: number;
  createdAt: string;
  requests: WorkbenchPackageRequestItem[];
}

export interface WorkbenchPackageRequestDetail extends WorkbenchPackageRequestItem {
  requestPayload: WorkbenchRequestPayload;
  response: WorkbenchResponsePayload;
}
