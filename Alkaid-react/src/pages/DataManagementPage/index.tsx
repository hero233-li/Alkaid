import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Empty, Input, Modal, Select, Tag, Tooltip, Typography, message } from 'antd';
import {
  Clock3,
  Database,
  Download,
  FilePlus2,
  FileText,
  FolderOpen,
  Pencil,
  RefreshCw,
  Search,
  Sheet,
  Trash2,
} from 'lucide-react';
import {
  createStoredDocument,
  convertLegacyWordDocument,
  deleteStoredDocument,
  exportWordDocument,
  getDocumentWorkspace,
  getStoredDocument,
  saveDocumentWorkspace,
  updateStoredDocument,
} from '../../api/documents';
import {
  MAX_MARKDOWN_FILE_SIZE,
  MAX_RECENT_MARKDOWN_FILES,
  MARKDOWN_CREATE_REQUESTED_EVENT,
  MARKDOWN_EDIT_REQUESTED_EVENT,
  MARKDOWN_WORKSPACE_CHANGED_EVENT,
  clearMarkdownEditRequest,
  consumeMarkdownCreationRequest,
  createMarkdownContentDocument,
  createMultidimensionalTableDocument,
  createOpenedMarkdownDocument,
  createSpreadsheetDocument,
  createWordDocument,
  createUniqueMarkdownFileName,
  createUniqueSpreadsheetFileName,
  createUniqueWordFileName,
  formatFileSize,
  getMarkdownDocumentKindLabel,
  isSupportedDataFileName,
  loadMarkdownWorkspace,
  loadRecentMarkdownDocuments,
  parseMultidimensionalTable,
  parseSpreadsheetWorkbook,
  peekMarkdownEditRequest,
  saveMarkdownWorkspace,
  upsertRecentMarkdownDocument,
  type MarkdownDocumentKind,
  type MarkdownDocumentRecord,
  type MultidimensionalTableData,
  type SpreadsheetWorkbook,
  normalizeWordFileName,
} from './model';
import DocumentDesigner from './DocumentDesigner';
import MultidimensionalTableDesigner from './MultidimensionalTableDesigner';
import SpreadsheetDesigner from './SpreadsheetDesigner';
import MarkdownPreview from './MarkdownPreview';
import { importSpreadsheetXlsx } from './spreadsheetXlsx';
import { sanitizeWordHtml } from './wordDocument';
import './styles.css';

type SortMode = 'opened' | 'updated' | 'name';
type KindFilter = 'all' | MarkdownDocumentKind;

interface LocalReadonlyPreview {
  kind: 'pdf';
  name: string;
  size: number;
  url?: string;
}

const MAX_OFFICE_PREVIEW_SIZE = 128 * 1024 * 1024;

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function getDateGroup(value: string) {
  const elapsedDays = Math.max(0, (Date.now() - new Date(value).getTime()) / 86_400_000);
  if (elapsedDays <= 7) return '7天内';
  if (elapsedDays <= 31) return '1个月内';
  return '更早';
}

async function downloadDocument(document: MarkdownDocumentRecord) {
  const completeDocument = document.content ? document : await getStoredDocument(document.id);
  const blob =
    completeDocument.kind === 'word'
      ? await exportWordDocument(completeDocument.name, completeDocument.content)
      : new Blob([completeDocument.content], {
          type:
            completeDocument.kind === 'spreadsheet'
              ? 'application/json;charset=utf-8'
              : 'text/markdown;charset=utf-8',
        });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download =
    completeDocument.kind === 'word'
      ? normalizeWordFileName(completeDocument.name)
      : completeDocument.name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function DataManagementPage() {
  const [messageApi, messageContextHolder] = message.useMessage();
  const [modalApi, modalContextHolder] = Modal.useModal();
  const [documents, setDocuments] = useState<MarkdownDocumentRecord[]>(() =>
    loadRecentMarkdownDocuments(),
  );
  const [initialEditingDocument] = useState<MarkdownDocumentRecord | null>(() => {
    // Do not consume this request during a state initializer. React StrictMode
    // invokes initializers more than once in development, so the discarded
    // render could otherwise take the request away from the committed page.
    const requestedDocumentId = peekMarkdownEditRequest();
    return requestedDocumentId
      ? loadRecentMarkdownDocuments().find((document) => document.id === requestedDocumentId) ||
          null
      : null;
  });
  const [query, setQuery] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('opened');
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [creationViewOpen, setCreationViewOpen] = useState(() =>
    initialEditingDocument ? false : consumeMarkdownCreationRequest(),
  );
  const [documentDesignerOpen, setDocumentDesignerOpen] = useState(false);
  const [wordDesignerOpen, setWordDesignerOpen] = useState(false);
  const [multidimensionalDesignerOpen, setMultidimensionalDesignerOpen] = useState(false);
  const [spreadsheetDesignerOpen, setSpreadsheetDesignerOpen] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<MarkdownDocumentRecord | null>(null);
  const [editingDocument, setEditingDocument] = useState<MarkdownDocumentRecord | null>(
    initialEditingDocument,
  );
  const [importedSpreadsheet, setImportedSpreadsheet] = useState<SpreadsheetWorkbook | null>(null);
  const [importedSpreadsheetName, setImportedSpreadsheetName] = useState<string>();
  const [localReadonlyPreview, setLocalReadonlyPreview] = useState<LocalReadonlyPreview | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialEditingDocument) {
      clearMarkdownEditRequest(initialEditingDocument.id);
      void getStoredDocument(initialEditingDocument.id)
        .then((document) => {
          setEditingDocument(document);
          setDocumentDesignerOpen(document.kind === 'document');
          setWordDesignerOpen(document.kind === 'word');
          setMultidimensionalDesignerOpen(document.kind === 'multidimensional-table');
          setSpreadsheetDesignerOpen(document.kind === 'spreadsheet');
        })
        .catch(() => messageApi.error('读取文件正文失败，无法进入编辑页面'));
    }
  }, [initialEditingDocument, messageApi]);

  useEffect(
    () => () => {
      if (localReadonlyPreview?.url) URL.revokeObjectURL(localReadonlyPreview.url);
    },
    [localReadonlyPreview],
  );

  useEffect(() => {
    const reloadDocuments = () => setDocuments(loadRecentMarkdownDocuments());
    const openCreationView = () => {
      consumeMarkdownCreationRequest();
      setDocumentDesignerOpen(false);
      setWordDesignerOpen(false);
      setMultidimensionalDesignerOpen(false);
      setSpreadsheetDesignerOpen(false);
      setCreationViewOpen(true);
    };
    const openRequestedDocument = async () => {
      const requestedDocumentId = peekMarkdownEditRequest();
      if (!requestedDocumentId) return;
      const latestDocuments = loadRecentMarkdownDocuments();
      const metadata = latestDocuments.find((document) => document.id === requestedDocumentId);
      if (!metadata) return;
      let requestedDocument: MarkdownDocumentRecord;
      try {
        requestedDocument = await getStoredDocument(requestedDocumentId);
      } catch {
        messageApi.error('读取文件正文失败，无法进入编辑页面');
        return;
      }
      setDocuments(latestDocuments);
      setEditingDocument(requestedDocument);
      setPreviewDocument(null);
      setCreationViewOpen(false);
      setDocumentDesignerOpen(requestedDocument.kind === 'document');
      setWordDesignerOpen(requestedDocument.kind === 'word');
      setMultidimensionalDesignerOpen(requestedDocument.kind === 'multidimensional-table');
      setSpreadsheetDesignerOpen(requestedDocument.kind === 'spreadsheet');
      clearMarkdownEditRequest(requestedDocumentId);
    };
    window.addEventListener(MARKDOWN_WORKSPACE_CHANGED_EVENT, reloadDocuments);
    window.addEventListener(MARKDOWN_CREATE_REQUESTED_EVENT, openCreationView);
    const handleEditRequest = () => void openRequestedDocument();
    window.addEventListener(MARKDOWN_EDIT_REQUESTED_EVENT, handleEditRequest);
    window.addEventListener('storage', reloadDocuments);
    return () => {
      window.removeEventListener(MARKDOWN_WORKSPACE_CHANGED_EVENT, reloadDocuments);
      window.removeEventListener(MARKDOWN_CREATE_REQUESTED_EVENT, openCreationView);
      window.removeEventListener(MARKDOWN_EDIT_REQUESTED_EVENT, handleEditRequest);
      window.removeEventListener('storage', reloadDocuments);
    };
  }, [messageApi]);

  useEffect(() => {
    let cancelled = false;
    const hydrateFromDatabase = async () => {
      try {
        const remoteWorkspace = await getDocumentWorkspace();
        const localWorkspace = loadMarkdownWorkspace();
        const shouldImportLocal =
          remoteWorkspace.documents.length === 0 &&
          remoteWorkspace.folders.length === 0 &&
          (localWorkspace.documents.length > 0 || localWorkspace.folders.length > 0);
        const workspace = shouldImportLocal
          ? await saveDocumentWorkspace(localWorkspace)
          : remoteWorkspace;
        if (cancelled) return;
        saveMarkdownWorkspace(workspace);
        setDocuments(workspace.documents);
      } catch {
        if (!cancelled) messageApi.warning('MySQL 文档服务暂不可用，当前使用浏览器缓存');
      }
    };
    void hydrateFromDatabase();
    return () => {
      cancelled = true;
    };
  }, [messageApi]);

  const visibleDocuments = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase();
    const result = documents.filter((document) => {
      const matchesKind = kindFilter === 'all' || document.kind === kindFilter;
      const searchableText = `${document.name} ${getMarkdownDocumentKindLabel(document.kind)}`;
      return matchesKind && searchableText.toLocaleLowerCase().includes(keyword);
    });
    return result
      .sort((left, right) => {
        if (sortMode === 'name') return left.name.localeCompare(right.name, 'zh-CN');
        const field = sortMode === 'updated' ? 'updatedAt' : 'lastOpenedAt';
        return right[field].localeCompare(left[field]);
      })
      .slice(0, MAX_RECENT_MARKDOWN_FILES);
  }, [documents, kindFilter, query, sortMode]);

  const groupedDocuments = useMemo(() => {
    const groups = new Map<string, MarkdownDocumentRecord[]>();
    visibleDocuments.forEach((document) => {
      const group = getDateGroup(document.lastOpenedAt);
      groups.set(group, [...(groups.get(group) || []), document]);
    });
    return ['7天内', '1个月内', '更早']
      .map((label) => ({ label, documents: groups.get(label) || [] }))
      .filter((group) => group.documents.length > 0);
  }, [visibleDocuments]);

  const persistDocuments = (nextDocuments: MarkdownDocumentRecord[]) => {
    const metadataOnly = nextDocuments.map((document) => ({ ...document, content: '' }));
    setDocuments(metadataOnly);
    const nextWorkspace = { ...loadMarkdownWorkspace(), documents: metadataOnly };
    saveMarkdownWorkspace(nextWorkspace);
    const previousById = new Map(documents.map((document) => [document.id, document]));
    const nextIds = new Set(nextDocuments.map((document) => document.id));
    const writes = nextDocuments
      .filter((document) => previousById.get(document.id) !== document)
      .map((document) =>
        previousById.has(document.id)
          ? updateStoredDocument(document)
          : createStoredDocument(document),
      );
    const deletes = documents
      .filter((document) => !nextIds.has(document.id))
      .map((document) => deleteStoredDocument(document.id));
    void Promise.all([...writes, ...deletes]).catch(() =>
      messageApi.error('写入 MySQL 失败，请稍后重试'),
    );
  };

  const openDocumentPreview = async (document: MarkdownDocumentRecord) => {
    let storedDocument = document;
    try {
      storedDocument = await getStoredDocument(document.id);
    } catch {
      messageApi.warning('数据库读取失败，已显示浏览器缓存版本');
    }
    const refreshedDocument = { ...storedDocument, lastOpenedAt: new Date().toISOString() };
    const nextDocuments = upsertRecentMarkdownDocument(documents, refreshedDocument);
    persistDocuments(nextDocuments);
    setPreviewDocument(refreshedDocument);
  };

  const selectDocumentKind = (kind: MarkdownDocumentKind) => {
    setEditingDocument(null);
    setImportedSpreadsheet(null);
    setImportedSpreadsheetName(undefined);
    setCreationViewOpen(false);
    setDocumentDesignerOpen(false);
    setWordDesignerOpen(false);
    setMultidimensionalDesignerOpen(false);
    setSpreadsheetDesignerOpen(false);
    if (kind === 'word') {
      setWordDesignerOpen(true);
      return;
    }
    if (kind === 'multidimensional-table') {
      setMultidimensionalDesignerOpen(true);
      return;
    }
    if (kind === 'spreadsheet') {
      setSpreadsheetDesignerOpen(true);
      return;
    }
    setDocumentDesignerOpen(true);
  };

  const saveDesignedDocument = (fileName: string, content: string) => {
    const uniqueFileName = createUniqueMarkdownFileName(
      fileName,
      documents
        .filter((document) => document.id !== editingDocument?.id)
        .map((document) => document.name),
    );
    const createdDocument = createMarkdownContentDocument(uniqueFileName, content);
    const document = editingDocument
      ? {
          ...createdDocument,
          id: editingDocument.id,
          source: editingDocument.source,
          folderId: editingDocument.folderId,
          createdAt: editingDocument.createdAt,
        }
      : createdDocument;
    persistDocuments(
      upsertRecentMarkdownDocument(
        documents.filter((item) => item.id !== editingDocument?.id),
        document,
      ),
    );
    setDocumentDesignerOpen(false);
    setEditingDocument(null);
    setPreviewDocument(document);
    messageApi.success(`已保存文档 ${document.name}`);
  };

  const saveWordDocument = (fileName: string, html: string) => {
    const uniqueFileName = createUniqueWordFileName(
      fileName,
      documents
        .filter((document) => document.id !== editingDocument?.id)
        .map((document) => document.name),
    );
    const createdDocument = createWordDocument(
      uniqueFileName,
      sanitizeWordHtml(html),
      editingDocument?.source || 'created',
    );
    const document = editingDocument
      ? {
          ...createdDocument,
          id: editingDocument.id,
          folderId: editingDocument.folderId,
          createdAt: editingDocument.createdAt,
        }
      : createdDocument;
    persistDocuments(
      upsertRecentMarkdownDocument(
        documents.filter((item) => item.id !== editingDocument?.id),
        document,
      ),
    );
    setWordDesignerOpen(false);
    setEditingDocument(null);
    setPreviewDocument(document);
    messageApi.success(`已保存在线 Word ${document.name}`);
  };

  const saveDesignedMultidimensionalTable = (fileName: string, data: MultidimensionalTableData) => {
    const uniqueFileName = createUniqueMarkdownFileName(
      fileName,
      documents
        .filter((document) => document.id !== editingDocument?.id)
        .map((document) => document.name),
    );
    const createdDocument = createMultidimensionalTableDocument(uniqueFileName, data);
    const document = editingDocument
      ? {
          ...createdDocument,
          id: editingDocument.id,
          source: editingDocument.source,
          folderId: editingDocument.folderId,
          createdAt: editingDocument.createdAt,
        }
      : createdDocument;
    persistDocuments(
      upsertRecentMarkdownDocument(
        documents.filter((item) => item.id !== editingDocument?.id),
        document,
      ),
    );
    setMultidimensionalDesignerOpen(false);
    setEditingDocument(null);
    setPreviewDocument(document);
    messageApi.success(`已保存多维表格 ${document.name}`);
  };

  const saveSpreadsheet = (fileName: string, workbook: SpreadsheetWorkbook) => {
    const uniqueFileName = createUniqueSpreadsheetFileName(
      fileName,
      documents
        .filter((document) => document.id !== editingDocument?.id)
        .map((document) => document.name),
    );
    const createdDocument = createSpreadsheetDocument(uniqueFileName, workbook);
    const document = editingDocument
      ? {
          ...createdDocument,
          id: editingDocument.id,
          source: editingDocument.source,
          folderId: editingDocument.folderId,
          createdAt: editingDocument.createdAt,
        }
      : createdDocument;
    persistDocuments(
      upsertRecentMarkdownDocument(
        documents.filter((item) => item.id !== editingDocument?.id),
        document,
      ),
    );
    setSpreadsheetDesignerOpen(false);
    setImportedSpreadsheet(null);
    setImportedSpreadsheetName(undefined);
    setEditingDocument(null);
    setPreviewDocument(document);
    messageApi.success(`已保存在线表格 ${document.name}`);
  };

  const editPreviewDocument = () => {
    if (!previewDocument) return;
    setEditingDocument(previewDocument);
    setImportedSpreadsheet(null);
    setImportedSpreadsheetName(undefined);
    setPreviewDocument(null);
    setCreationViewOpen(false);
    if (previewDocument.kind === 'word') setWordDesignerOpen(true);
    else if (previewDocument.kind === 'multidimensional-table')
      setMultidimensionalDesignerOpen(true);
    else if (previewDocument.kind === 'spreadsheet') setSpreadsheetDesignerOpen(true);
    else setDocumentDesignerOpen(true);
  };

  const openImportedWord = (file: File, html: string) => {
    const uniqueFileName = createUniqueWordFileName(
      file.name,
      documents.map((document) => document.name),
    );
    const importedDocument = {
      ...createWordDocument(uniqueFileName, sanitizeWordHtml(html), 'opened'),
      updatedAt: file.lastModified
        ? new Date(file.lastModified).toISOString()
        : new Date().toISOString(),
    };
    persistDocuments(upsertRecentMarkdownDocument(documents, importedDocument));
    setLocalReadonlyPreview(null);
    setPreviewDocument(importedDocument);
    messageApi.success(`已导入在线 Word：${importedDocument.name}`);
  };

  const openLocalFile = async (file?: File) => {
    if (!file) return;
    if (/\.pdf$/i.test(file.name)) {
      if (file.size > MAX_OFFICE_PREVIEW_SIZE) {
        messageApi.error(`PDF 文件不能超过 ${formatFileSize(MAX_OFFICE_PREVIEW_SIZE)}`);
        return;
      }
      setPreviewDocument(null);
      setLocalReadonlyPreview({
        kind: 'pdf',
        name: file.name,
        size: file.size,
        url: URL.createObjectURL(file),
      });
      messageApi.success(`已打开 PDF：${file.name}`);
      return;
    }
    if (/\.docx$/i.test(file.name)) {
      if (file.size > MAX_OFFICE_PREVIEW_SIZE) {
        messageApi.error(`Word 文件不能超过 ${formatFileSize(MAX_OFFICE_PREVIEW_SIZE)}`);
        return;
      }
      try {
        const mammoth = await import('mammoth');
        const result = await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() });
        openImportedWord(file, result.value);
      } catch {
        messageApi.error('无法读取该 Word 文件，请确认文件未损坏或未加密');
      }
      return;
    }
    if (/\.doc$/i.test(file.name)) {
      if (file.size > MAX_OFFICE_PREVIEW_SIZE) {
        messageApi.error(`Word 文件不能超过 ${formatFileSize(MAX_OFFICE_PREVIEW_SIZE)}`);
        return;
      }
      try {
        const result = await convertLegacyWordDocument(file);
        openImportedWord(file, result.html);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : '无法读取该 .doc 文件');
      }
      return;
    }
    if (/\.xlsx$/i.test(file.name)) {
      if (file.size > 10 * 1024 * 1024) {
        messageApi.error('.xlsx 文件不能超过 10 MB');
        return;
      }
      try {
        const workbook = await importSpreadsheetXlsx(await file.arrayBuffer());
        setImportedSpreadsheet(workbook);
        setImportedSpreadsheetName(file.name.replace(/\.xlsx$/i, ''));
        setEditingDocument(null);
        setPreviewDocument(null);
        setCreationViewOpen(false);
        setSpreadsheetDesignerOpen(true);
        messageApi.success(`已导入 ${workbook.sheets.length} 个工作表`);
      } catch {
        messageApi.error('无法读取该 .xlsx 文件，请确认文件未损坏');
      }
      return;
    }
    if (!isSupportedDataFileName(file.name)) {
      messageApi.error('请选择 Markdown、在线工作簿、.xlsx、.doc/.docx 或 .pdf 文件');
      return;
    }
    if (file.size > MAX_MARKDOWN_FILE_SIZE) {
      messageApi.error(`文件不能超过 ${formatFileSize(MAX_MARKDOWN_FILE_SIZE)}`);
      return;
    }
    try {
      const content = await file.text();
      const document = createOpenedMarkdownDocument(file, content);
      persistDocuments(upsertRecentMarkdownDocument(documents, document));
      setPreviewDocument(document);
      messageApi.success(`已打开 ${document.name}`);
    } catch {
      messageApi.error('文件读取失败，请重新选择');
    }
  };

  const removeDocument = (document: MarkdownDocumentRecord) => {
    modalApi.confirm({
      title: `从最近文件中移除“${document.name}”？`,
      content: '删除后将无法继续从“我的文档”和最近文件中查看该文件。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => {
        persistDocuments(documents.filter((item) => item.id !== document.id));
        if (previewDocument?.id === document.id) setPreviewDocument(null);
      },
    });
  };

  const designerOpen =
    documentDesignerOpen ||
    wordDesignerOpen ||
    multidimensionalDesignerOpen ||
    spreadsheetDesignerOpen;

  return (
    <div className="page-surface data-management-page">
      {messageContextHolder}
      {modalContextHolder}
      <div className={`data-management-shell ${designerOpen ? 'is-designer' : ''}`}>
        {!designerOpen && (
          <aside className="data-management-sidebar">
            <Button
              className="data-management-primary-action"
              type="primary"
              size="large"
              icon={<FilePlus2 size={19} />}
              onClick={() => {
                setDocumentDesignerOpen(false);
                setWordDesignerOpen(false);
                setMultidimensionalDesignerOpen(false);
                setSpreadsheetDesignerOpen(false);
                setCreationViewOpen(true);
              }}
            >
              新建
            </Button>
            <Button
              className="data-management-open-action"
              size="large"
              icon={<FolderOpen size={19} />}
              onClick={() => fileInputRef.current?.click()}
            >
              打开本地文件
            </Button>
            <input
              ref={fileInputRef}
              className="data-management-file-input"
              type="file"
              accept=".md,.markdown,.sheet.json,.xlsx,.doc,.docx,.pdf,text/markdown,text/plain,application/json,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                void openLocalFile(event.target.files?.[0]);
                event.target.value = '';
              }}
            />

            <div className="data-management-nav-item is-active">
              <Clock3 size={18} />
              <span>最近文件</span>
              <span className="data-management-count">
                {Math.min(documents.length, MAX_RECENT_MARKDOWN_FILES)}
              </span>
            </div>
          </aside>
        )}

        <main className={`data-management-content ${designerOpen ? 'is-designer' : ''}`}>
          {documentDesignerOpen ? (
            <DocumentDesigner
              initialFileName={editingDocument?.name}
              initialContent={editingDocument?.content}
              onBack={() => {
                setDocumentDesignerOpen(false);
                if (editingDocument) setPreviewDocument(editingDocument);
                else setCreationViewOpen(false);
                setEditingDocument(null);
              }}
              onSave={saveDesignedDocument}
            />
          ) : wordDesignerOpen ? (
            <DocumentDesigner
              storageFormat="word"
              initialFileName={editingDocument?.name}
              initialContent={editingDocument?.content}
              onBack={() => {
                setWordDesignerOpen(false);
                if (editingDocument) setPreviewDocument(editingDocument);
                else setCreationViewOpen(false);
                setEditingDocument(null);
              }}
              onSave={saveWordDocument}
            />
          ) : multidimensionalDesignerOpen ? (
            <MultidimensionalTableDesigner
              initialFileName={editingDocument?.name}
              initialData={
                editingDocument ? parseMultidimensionalTable(editingDocument.content) : undefined
              }
              onBack={() => {
                setMultidimensionalDesignerOpen(false);
                if (editingDocument) setPreviewDocument(editingDocument);
                else setCreationViewOpen(false);
                setEditingDocument(null);
              }}
              onSave={saveDesignedMultidimensionalTable}
            />
          ) : spreadsheetDesignerOpen ? (
            <SpreadsheetDesigner
              initialFileName={editingDocument?.name || importedSpreadsheetName}
              initialWorkbook={
                editingDocument
                  ? parseSpreadsheetWorkbook(editingDocument.content)
                  : importedSpreadsheet || undefined
              }
              onBack={() => {
                setSpreadsheetDesignerOpen(false);
                if (editingDocument) setPreviewDocument(editingDocument);
                else setCreationViewOpen(false);
                setEditingDocument(null);
                setImportedSpreadsheet(null);
                setImportedSpreadsheetName(undefined);
              }}
              onSave={saveSpreadsheet}
            />
          ) : (
            <>
              <div className="data-management-heading">
                <div>
                  <Typography.Title level={3}>最近文件</Typography.Title>
                  <Typography.Text type="secondary">
                    在这里创建或打开文档与工作簿；全部文件可在“我的文档”中整理
                  </Typography.Text>
                </div>
                <Button
                  icon={<RefreshCw size={16} />}
                  onClick={() => {
                    setDocuments(loadRecentMarkdownDocuments());
                    messageApi.success('最近文件已刷新');
                  }}
                >
                  刷新
                </Button>
              </div>

              <div className="data-management-toolbar">
                <Input
                  allowClear
                  value={query}
                  prefix={<Search size={16} />}
                  placeholder="搜索最近文件"
                  onChange={(event) => setQuery(event.target.value)}
                />
                <Select<KindFilter>
                  value={kindFilter}
                  aria-label="最近文件类型"
                  options={[
                    { label: '全部类型', value: 'all' },
                    { label: '文档', value: 'document' },
                    { label: '在线 Word', value: 'word' },
                    { label: '多维表格', value: 'multidimensional-table' },
                    { label: '在线表格', value: 'spreadsheet' },
                  ]}
                  onChange={setKindFilter}
                />
                <Select<SortMode>
                  value={sortMode}
                  aria-label="最近文件排序方式"
                  options={[
                    { label: '按最近打开', value: 'opened' },
                    { label: '按最近修改', value: 'updated' },
                    { label: '按文件名称', value: 'name' },
                  ]}
                  onChange={setSortMode}
                />
              </div>

              <div className="data-management-list-head" aria-hidden="true">
                <span>文件名称</span>
                <span>类型</span>
                <span>来源</span>
                <span>大小</span>
                <span>最近修改</span>
                <span>操作</span>
              </div>

              {groupedDocuments.length ? (
                <div className="data-management-groups">
                  {groupedDocuments.map((group) => (
                    <section key={group.label} className="data-management-group">
                      <Typography.Title level={5}>{group.label}</Typography.Title>
                      <div className="data-management-file-list">
                        {group.documents.map((document) => (
                          <div key={document.id} className="data-management-file-row">
                            <button
                              type="button"
                              className="data-management-file-main"
                              onClick={() => openDocumentPreview(document)}
                            >
                              <span className={`data-management-file-icon is-${document.kind}`}>
                                {document.kind === 'multidimensional-table' ? (
                                  <Database size={21} />
                                ) : document.kind === 'spreadsheet' ? (
                                  <Sheet size={21} />
                                ) : (
                                  <FileText size={21} />
                                )}
                              </span>
                              <span className="data-management-file-name" title={document.name}>
                                {document.name}
                              </span>
                            </button>
                            <span>
                              <Tag
                                color={
                                  document.kind === 'multidimensional-table'
                                    ? 'cyan'
                                    : document.kind === 'spreadsheet'
                                      ? 'lime'
                                      : 'blue'
                                }
                              >
                                {getMarkdownDocumentKindLabel(document.kind)}
                              </Tag>
                            </span>
                            <span>
                              <Tag color={document.source === 'created' ? 'blue' : 'default'}>
                                {document.source === 'created' ? '新建' : '本地打开'}
                              </Tag>
                            </span>
                            <Typography.Text type="secondary">
                              {formatFileSize(document.size)}
                            </Typography.Text>
                            <Typography.Text type="secondary">
                              {formatDateTime(document.updatedAt)}
                            </Typography.Text>
                            <span className="data-management-file-actions">
                              <Tooltip title="下载文件">
                                <Button
                                  type="text"
                                  aria-label={`下载 ${document.name}`}
                                  icon={<Download size={17} />}
                                  onClick={() =>
                                    void downloadDocument(document).catch((error) =>
                                      messageApi.error(
                                        error instanceof Error ? error.message : '文件导出失败',
                                      ),
                                    )
                                  }
                                />
                              </Tooltip>
                              <Tooltip title="删除浏览器中的文件">
                                <Button
                                  type="text"
                                  danger
                                  aria-label={`删除 ${document.name}`}
                                  icon={<Trash2 size={17} />}
                                  onClick={() => removeDocument(document)}
                                />
                              </Tooltip>
                            </span>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="data-management-empty">
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={query ? '没有匹配的文件' : '还没有最近文件'}
                  >
                    {!query && (
                      <Button
                        type="primary"
                        icon={<FilePlus2 size={16} />}
                        onClick={() => setCreationViewOpen(true)}
                      >
                        新建第一个文件
                      </Button>
                    )}
                  </Empty>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      <Modal
        className="data-management-create-modal"
        title="新建文件"
        open={creationViewOpen && !designerOpen}
        width={720}
        footer={null}
        onCancel={() => setCreationViewOpen(false)}
      >
        <Typography.Paragraph type="secondary">
          可新建 Markdown 文档、在线 Word、在线表格与多维表格，保存后统一写入数据库。
        </Typography.Paragraph>
        <div className="data-management-create-options">
          <button
            type="button"
            className="data-management-create-card is-document"
            onClick={() => selectDocumentKind('document')}
          >
            <span className="data-management-create-card-icon">
              <FileText size={30} />
            </span>
            <span className="data-management-create-card-title">文档</span>
            <span className="data-management-create-card-description">说明、笔记和长文本内容</span>
          </button>
          <button
            type="button"
            className="data-management-create-card is-word"
            onClick={() => selectDocumentKind('word')}
          >
            <span className="data-management-create-card-icon">
              <FileText size={30} />
            </span>
            <span className="data-management-create-card-title">在线 Word</span>
            <span className="data-management-create-card-description">
              富文本排版、Word 导入、预览与编辑
            </span>
          </button>
          <button
            type="button"
            className="data-management-create-card is-multidimensional"
            onClick={() => selectDocumentKind('multidimensional-table')}
          >
            <span className="data-management-create-card-icon">
              <Database size={30} />
            </span>
            <span className="data-management-create-card-title">多维表格</span>
            <span className="data-management-create-card-description">
              字段类型、记录视图和结构化数据
            </span>
          </button>
          <button
            type="button"
            className="data-management-create-card is-spreadsheet"
            onClick={() => selectDocumentKind('spreadsheet')}
          >
            <span className="data-management-create-card-icon">
              <Sheet size={30} />
            </span>
            <span className="data-management-create-card-title">在线表格</span>
            <span className="data-management-create-card-description">
              Excel 式选择、公式、合并和格式
            </span>
          </button>
        </div>
      </Modal>

      <Modal
        className={`data-management-document-preview-modal ${previewDocument?.kind === 'word' ? 'is-word' : ''}`}
        title={previewDocument?.name}
        open={Boolean(previewDocument)}
        width="min(1000px, calc(100vw - 48px))"
        footer={[
          <Button key="close" onClick={() => setPreviewDocument(null)}>
            关闭
          </Button>,
          <Button
            key="download"
            onClick={() =>
              previewDocument &&
              void downloadDocument(previewDocument).catch((error) =>
                messageApi.error(error instanceof Error ? error.message : '文件导出失败'),
              )
            }
          >
            下载文件
          </Button>,
          <Button
            key="edit"
            type="primary"
            icon={<Pencil size={16} />}
            onClick={editPreviewDocument}
          >
            编辑
          </Button>,
        ]}
        onCancel={() => setPreviewDocument(null)}
      >
        <div className="data-management-preview-meta">
          <Tag
            color={
              previewDocument?.kind === 'multidimensional-table'
                ? 'cyan'
                : previewDocument?.kind === 'spreadsheet'
                  ? 'lime'
                  : 'blue'
            }
          >
            {previewDocument ? getMarkdownDocumentKindLabel(previewDocument.kind) : ''}
          </Tag>
          <Tag>
            {previewDocument?.kind === 'spreadsheet'
              ? 'JSON 工作簿'
              : previewDocument?.kind === 'word'
                ? 'Word 富文本'
                : 'Markdown'}
          </Tag>
          <Typography.Text type="secondary">
            {previewDocument ? formatFileSize(previewDocument.size) : ''}
          </Typography.Text>
        </div>
        <MarkdownPreview
          content={previewDocument?.content || ''}
          kind={previewDocument?.kind || 'document'}
        />
      </Modal>

      <Modal
        className="data-management-office-preview-modal"
        title={localReadonlyPreview?.name}
        open={Boolean(localReadonlyPreview)}
        width="min(1100px, calc(100vw - 48px))"
        footer={<Button onClick={() => setLocalReadonlyPreview(null)}>关闭</Button>}
        onCancel={() => setLocalReadonlyPreview(null)}
      >
        <div className="data-management-preview-meta">
          <Tag color="red">PDF</Tag>
          <Tag>本地只读预览</Tag>
          <Typography.Text type="secondary">
            {localReadonlyPreview ? formatFileSize(localReadonlyPreview.size) : ''}
          </Typography.Text>
        </div>
        <iframe
          className="data-management-pdf-preview"
          src={localReadonlyPreview?.url}
          title={`PDF 预览：${localReadonlyPreview?.name || ''}`}
        />
      </Modal>
    </div>
  );
}
