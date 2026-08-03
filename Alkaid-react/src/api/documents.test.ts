import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { getDocumentWorkspace, getStoredDocument, saveDocumentWorkspace } from './documents';

const workspace = {
  documents: [
    {
      id: 'document-1',
      name: '说明.md',
      content: '# 说明',
      size: 8,
      kind: 'document' as const,
      source: 'created' as const,
      folderId: null,
      createdAt: '2026-08-02T10:00:00.000Z',
      updatedAt: '2026-08-02T10:00:00.000Z',
      lastOpenedAt: '2026-08-02T10:00:00.000Z',
    },
  ],
  folders: [],
};

describe('document persistence api', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('loads and replaces the MySQL-backed workspace', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { ok: true, message: '', data: workspace },
    });
    const put = vi.spyOn(apiClient, 'put').mockResolvedValue({
      data: { ok: true, message: '', data: workspace },
    });

    await expect(getDocumentWorkspace()).resolves.toEqual({
      ...workspace,
      documents: [{ ...workspace.documents[0], content: '' }],
    });
    await expect(saveDocumentWorkspace(workspace)).resolves.toEqual(workspace);
    expect(get).toHaveBeenCalledWith('/documents/workspace', { useResponseDelay: false });
    expect(put).toHaveBeenCalledWith('/documents/workspace', workspace, {
      useResponseDelay: false,
    });
  });

  it('reads one document for viewing or editing', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { ok: true, message: '', data: workspace.documents[0] },
    });

    await expect(getStoredDocument('document-1')).resolves.toEqual(workspace.documents[0]);
    expect(get).toHaveBeenCalledWith('/documents/document-1', { useResponseDelay: false });
  });

  it('serializes workspace writes so an older response cannot overwrite a newer save', async () => {
    let resolveFirst!: (value: {
      data: { ok: boolean; message: string; data: typeof workspace };
    }) => void;
    const firstResponse = new Promise<{
      data: { ok: boolean; message: string; data: typeof workspace };
    }>((resolve) => {
      resolveFirst = resolve;
    });
    const newerWorkspace = {
      ...workspace,
      documents: [{ ...workspace.documents[0], content: '最新内容' }],
    };
    const put = vi
      .spyOn(apiClient, 'put')
      .mockImplementationOnce(() => firstResponse)
      .mockResolvedValueOnce({ data: { ok: true, message: '', data: newerWorkspace } });

    const olderSave = saveDocumentWorkspace(workspace);
    const newerSave = saveDocumentWorkspace(newerWorkspace);
    await vi.waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    resolveFirst({ data: { ok: true, message: '', data: workspace } });

    await expect(olderSave).resolves.toEqual(workspace);
    await expect(newerSave).resolves.toEqual(newerWorkspace);
    expect(put).toHaveBeenCalledTimes(2);
  });
});
