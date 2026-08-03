import type { MarkdownDocumentRecord, MarkdownWorkspace } from '../pages/DataManagementPage/model';
import type { ApiResponse } from '../types';
import { apiClient } from './client';

let workspaceSaveQueue: Promise<unknown> = Promise.resolve();

function unwrap<T>(response: ApiResponse<T>, fallbackMessage: string) {
  if (!response.ok) throw new Error(response.message || fallbackMessage);
  return response.data;
}

export async function getDocumentWorkspace() {
  const { data } = await apiClient.get<ApiResponse<MarkdownWorkspace>>('/documents/workspace', {
    useResponseDelay: false,
  });
  const workspace = unwrap(data, '读取数据库文件失败');
  return {
    ...workspace,
    // The list endpoint deliberately omits large bodies. Keep the existing UI model compatible.
    documents: workspace.documents.map((document) => ({ ...document, content: '' })),
  };
}

export function saveDocumentWorkspace(workspace: MarkdownWorkspace) {
  const operation = workspaceSaveQueue
    .catch(() => undefined)
    .then(async () => {
      const { data } = await apiClient.put<ApiResponse<MarkdownWorkspace>>(
        '/documents/workspace',
        workspace,
        { useResponseDelay: false },
      );
      return unwrap(data, '保存文件到数据库失败');
    });
  workspaceSaveQueue = operation.then(
    () => undefined,
    () => undefined,
  );
  return operation;
}

export async function getStoredDocument(documentId: string) {
  const { data } = await apiClient.get<ApiResponse<MarkdownDocumentRecord>>(
    `/documents/${encodeURIComponent(documentId)}`,
    { useResponseDelay: false },
  );
  return unwrap(data, '读取文件内容失败');
}

export async function createStoredDocument(document: MarkdownDocumentRecord) {
  const { data } = await apiClient.post<ApiResponse<MarkdownDocumentRecord>>(
    '/documents/items',
    document,
    { useResponseDelay: false, timeout: 120_000 },
  );
  return unwrap(data, '创建文件失败');
}

export async function updateStoredDocument(document: MarkdownDocumentRecord) {
  const { data } = await apiClient.put<ApiResponse<MarkdownDocumentRecord>>(
    `/documents/${encodeURIComponent(document.id)}`,
    document,
    { useResponseDelay: false, timeout: 120_000 },
  );
  return unwrap(data, '保存文件失败');
}

export async function deleteStoredDocument(documentId: string) {
  const { data } = await apiClient.delete<ApiResponse<null>>(
    `/documents/${encodeURIComponent(documentId)}`,
    { useResponseDelay: false },
  );
  return unwrap(data, '删除文件失败');
}

export async function moveStoredDocument(documentId: string, folderId: string | null) {
  const { data } = await apiClient.patch<ApiResponse<MarkdownDocumentRecord>>(
    `/documents/${encodeURIComponent(documentId)}`,
    { folderId },
    { useResponseDelay: false },
  );
  return unwrap(data, '移动文件失败');
}

export async function createStoredFolder(folder: MarkdownWorkspace['folders'][number]) {
  const { data } = await apiClient.post<ApiResponse<MarkdownWorkspace['folders'][number]>>(
    '/documents/folders',
    folder,
    { useResponseDelay: false },
  );
  return unwrap(data, '创建文件夹失败');
}

export async function uploadDocumentImage(file: File, documentId?: string) {
  const body = new FormData();
  body.append('file', file);
  if (documentId) body.append('documentId', documentId);
  const { data } = await apiClient.post<
    ApiResponse<{ id: string; name: string; size: number; contentType: string; url: string }>
  >('/documents/assets', body, { useResponseDelay: false, timeout: 120_000 });
  return unwrap(data, '上传图片失败');
}

export async function convertLegacyWordDocument(file: File) {
  const body = new FormData();
  body.append('file', file);
  const { data } = await apiClient.post<ApiResponse<{ html: string; name: string }>>(
    '/documents/import-word',
    body,
    { useResponseDelay: false },
  );
  return unwrap(data, '转换 Word 文件失败');
}

export async function exportWordDocument(fileName: string, html: string) {
  const response = await apiClient.post<ArrayBuffer>(
    '/documents/export-word',
    { name: fileName, html },
    { responseType: 'arraybuffer', useResponseDelay: false, timeout: 45_000 },
  );
  return new Blob([response.data], {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
}
