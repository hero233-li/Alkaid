import { useEffect, useMemo, useState } from 'react';
import { Button, Empty, Input, Modal, Select, Spin, Tag, Tooltip, Typography, message } from 'antd';
import {
  ChevronRight,
  Database,
  Download,
  FilePlus2,
  Files,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Home,
  MoveRight,
  Pencil,
  Search,
  Sheet,
} from 'lucide-react';
import {
  createStoredFolder,
  exportWordDocument,
  getDocumentWorkspace,
  getStoredDocument,
  moveStoredDocument,
  saveDocumentWorkspace,
} from '../../api/documents';
import {
  MARKDOWN_WORKSPACE_CHANGED_EVENT,
  createMarkdownFolder,
  createUniqueMarkdownFolderName,
  formatFileSize,
  getMarkdownDocumentKindLabel,
  getMarkdownFolderPath,
  loadMarkdownWorkspace,
  moveMarkdownDocument,
  normalizeWordFileName,
  requestMarkdownCreation,
  requestMarkdownEdit,
  saveMarkdownWorkspace,
  type MarkdownDocumentRecord,
  type MarkdownFolderRecord,
  type MarkdownWorkspace,
  type MarkdownDocumentKind,
} from '../DataManagementPage/model';
import MarkdownPreview from '../DataManagementPage/MarkdownPreview';
import './styles.css';

type DocumentLocation = 'all' | 'root' | string;
type KindFilter = 'all' | MarkdownDocumentKind;

interface FolderNode {
  folder: MarkdownFolderRecord;
  children: FolderNode[];
}

interface MyDocumentsPageProps {
  onCreateDocument: () => void;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function buildFolderTree(
  folders: MarkdownFolderRecord[],
  parentId: string | null = null,
  visited = new Set<string>(),
): FolderNode[] {
  return folders
    .filter((folder) => folder.parentId === parentId && !visited.has(folder.id))
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
    .map((folder) => {
      const nextVisited = new Set(visited).add(folder.id);
      return { folder, children: buildFolderTree(folders, folder.id, nextVisited) };
    });
}

function flattenFolderOptions(folders: MarkdownFolderRecord[]) {
  return folders
    .map((folder) => ({
      label: getMarkdownFolderPath(folder.id, folders),
      value: folder.id,
    }))
    .sort((left, right) => left.label.localeCompare(right.label, 'zh-CN'));
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

function FolderNavigation({
  nodes,
  selectedLocation,
  onSelect,
  depth = 0,
}: {
  nodes: FolderNode[];
  selectedLocation: DocumentLocation;
  onSelect: (folderId: string) => void;
  depth?: number;
}) {
  return nodes.map((node) => (
    <div key={node.folder.id}>
      <button
        type="button"
        className={`my-documents-location ${selectedLocation === node.folder.id ? 'is-active' : ''}`}
        style={{ paddingLeft: 14 + depth * 18 }}
        onClick={() => onSelect(node.folder.id)}
      >
        <Folder size={17} />
        <span title={node.folder.name}>{node.folder.name}</span>
      </button>
      {node.children.length > 0 && (
        <FolderNavigation
          nodes={node.children}
          selectedLocation={selectedLocation}
          onSelect={onSelect}
          depth={depth + 1}
        />
      )}
    </div>
  ));
}

export default function MyDocumentsPage({ onCreateDocument }: MyDocumentsPageProps) {
  const [messageApi, messageContextHolder] = message.useMessage();
  const [workspace, setWorkspace] = useState<MarkdownWorkspace>(() => loadMarkdownWorkspace());
  const [selectedLocation, setSelectedLocation] = useState<DocumentLocation>('all');
  const [query, setQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('新建文件夹');
  const [movingDocument, setMovingDocument] = useState<MarkdownDocumentRecord | null>(null);
  const [moveTarget, setMoveTarget] = useState<string>('root');
  const [previewDocument, setPreviewDocument] = useState<MarkdownDocumentRecord | null>(null);
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);

  useEffect(() => {
    const reloadWorkspace = () => setWorkspace(loadMarkdownWorkspace());
    window.addEventListener(MARKDOWN_WORKSPACE_CHANGED_EVENT, reloadWorkspace);
    window.addEventListener('storage', reloadWorkspace);
    return () => {
      window.removeEventListener(MARKDOWN_WORKSPACE_CHANGED_EVENT, reloadWorkspace);
      window.removeEventListener('storage', reloadWorkspace);
    };
  }, []);

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
        const nextWorkspace = shouldImportLocal
          ? await saveDocumentWorkspace(localWorkspace)
          : remoteWorkspace;
        if (cancelled) return;
        saveMarkdownWorkspace(nextWorkspace);
        setWorkspace(nextWorkspace);
      } catch {
        if (!cancelled) messageApi.warning('MySQL 文档服务暂不可用，当前使用浏览器缓存');
      } finally {
        if (!cancelled) setWorkspaceReady(true);
      }
    };
    void hydrateFromDatabase();
    return () => {
      cancelled = true;
    };
  }, [messageApi]);

  useEffect(() => {
    if (
      selectedLocation !== 'all' &&
      selectedLocation !== 'root' &&
      !workspace.folders.some((folder) => folder.id === selectedLocation)
    ) {
      setSelectedLocation('all');
    }
  }, [selectedLocation, workspace.folders]);

  const folderTree = useMemo(() => buildFolderTree(workspace.folders), [workspace.folders]);
  const folderOptions = useMemo(
    () => [
      { label: '根目录（未分类）', value: 'root' },
      ...flattenFolderOptions(workspace.folders),
    ],
    [workspace.folders],
  );
  const selectedFolder =
    selectedLocation === 'all' || selectedLocation === 'root'
      ? null
      : workspace.folders.find((folder) => folder.id === selectedLocation) || null;
  const currentFolderId = selectedFolder?.id || null;
  const keyword = query.trim().toLocaleLowerCase();

  const visibleFolders = workspace.folders
    .filter((folder) => folder.parentId === currentFolderId)
    .filter((folder) => folder.name.toLocaleLowerCase().includes(keyword))
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'));
  const visibleDocuments = workspace.documents
    .filter((document) => selectedLocation === 'all' || document.folderId === currentFolderId)
    .filter((document) => kindFilter === 'all' || document.kind === kindFilter)
    .filter((document) =>
      `${document.name} ${getMarkdownDocumentKindLabel(document.kind)}`
        .toLocaleLowerCase()
        .includes(keyword),
    )
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));

  const openDocumentPreview = async (document: MarkdownDocumentRecord) => {
    setPreviewLoadingId(document.id);
    try {
      const storedDocument = await getStoredDocument(document.id);
      setPreviewDocument(storedDocument);
    } catch {
      messageApi.error('数据库读取失败，无法预览文件');
    } finally {
      setPreviewLoadingId(null);
    }
  };

  const createFolder = async () => {
    const latestWorkspace = loadMarkdownWorkspace();
    const parentId = selectedFolder?.id || null;
    const siblingNames = latestWorkspace.folders
      .filter((folder) => folder.parentId === parentId)
      .map((folder) => folder.name);
    const folder = createMarkdownFolder(
      createUniqueMarkdownFolderName(newFolderName, siblingNames),
      parentId,
    );
    const nextWorkspace = {
      ...latestWorkspace,
      folders: [...latestWorkspace.folders, folder],
    };
    try {
      await createStoredFolder(folder);
      saveMarkdownWorkspace(nextWorkspace);
      setWorkspace(nextWorkspace);
      setNewFolderOpen(false);
      setNewFolderName('新建文件夹');
      messageApi.success(`已创建文件夹 ${folder.name}`);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '创建文件夹失败');
    }
  };

  const moveDocument = async () => {
    if (!movingDocument) return;
    const latestWorkspace = loadMarkdownWorkspace();
    const targetFolderId = moveTarget === 'root' ? null : moveTarget;
    const nextWorkspace = moveMarkdownDocument(latestWorkspace, movingDocument.id, targetFolderId);
    try {
      await moveStoredDocument(movingDocument.id, targetFolderId);
      saveMarkdownWorkspace(nextWorkspace);
      setWorkspace(nextWorkspace);
      const targetName = getMarkdownFolderPath(targetFolderId, nextWorkspace.folders);
      messageApi.success(`已将 ${movingDocument.name} 移动到 ${targetName}`);
      setMovingDocument(null);
      setMoveTarget('root');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '移动文件失败');
    }
  };

  const openMoveDialog = (document: MarkdownDocumentRecord) => {
    setMovingDocument(document);
    setMoveTarget(document.folderId || 'root');
  };

  const currentTitle =
    selectedLocation === 'all'
      ? '所有文件'
      : selectedLocation === 'root'
        ? '根目录'
        : selectedFolder?.name || '我的文档';

  const openDocumentCreation = () => {
    requestMarkdownCreation();
    onCreateDocument();
  };

  const editPreviewDocument = () => {
    if (!previewDocument) return;
    requestMarkdownEdit(previewDocument.id);
    setPreviewDocument(null);
    onCreateDocument();
  };

  return (
    <div className="page-surface my-documents-page">
      {messageContextHolder}
      <div className="my-documents-shell">
        <aside className="my-documents-sidebar">
          <div className="my-documents-sidebar-title">
            <HardDrive size={19} />
            <span>我的文档</span>
          </div>
          <button
            type="button"
            className={`my-documents-location ${selectedLocation === 'all' ? 'is-active' : ''}`}
            onClick={() => setSelectedLocation('all')}
          >
            <Files size={17} />
            <span>所有文件</span>
            <span className="my-documents-location-count">{workspace.documents.length}</span>
          </button>
          <button
            type="button"
            className={`my-documents-location ${selectedLocation === 'root' ? 'is-active' : ''}`}
            onClick={() => setSelectedLocation('root')}
          >
            <Home size={17} />
            <span>根目录</span>
          </button>
          <div className="my-documents-folder-label">文件夹</div>
          {folderTree.length ? (
            <FolderNavigation
              nodes={folderTree}
              selectedLocation={selectedLocation}
              onSelect={setSelectedLocation}
            />
          ) : (
            <Typography.Text className="my-documents-no-folder" type="secondary">
              暂无文件夹
            </Typography.Text>
          )}
        </aside>

        <main className="my-documents-content">
          <div className="my-documents-heading">
            <div>
              <Typography.Title level={3}>{currentTitle}</Typography.Title>
              <div className="my-documents-breadcrumb">
                <span>我的文档</span>
                {selectedFolder && (
                  <>
                    <ChevronRight size={14} />
                    <span>{getMarkdownFolderPath(selectedFolder.id, workspace.folders)}</span>
                  </>
                )}
              </div>
            </div>
            <div className="my-documents-heading-actions">
              <Button icon={<FolderPlus size={17} />} onClick={() => setNewFolderOpen(true)}>
                新建子文件夹
              </Button>
              <Button type="primary" icon={<FilePlus2 size={17} />} onClick={openDocumentCreation}>
                新建
              </Button>
            </div>
          </div>

          <div className="my-documents-summary">
            <span>{workspace.documents.length} 个文件</span>
            <span>{workspace.folders.length} 个文件夹</span>
            <Typography.Text type="secondary">MySQL 持久化</Typography.Text>
          </div>

          <div className="my-documents-toolbar">
            <Input
              allowClear
              value={query}
              prefix={<Search size={16} />}
              placeholder={`在${currentTitle}中搜索`}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Select<KindFilter>
              value={kindFilter}
              aria-label="我的文档类型"
              options={[
                { label: '全部类型', value: 'all' },
                { label: '文档', value: 'document' },
                { label: '在线 Word', value: 'word' },
                { label: '多维表格', value: 'multidimensional-table' },
                { label: '在线表格', value: 'spreadsheet' },
              ]}
              onChange={setKindFilter}
            />
          </div>

          <div className="my-documents-list-head" aria-hidden="true">
            <span>名称</span>
            <span>类型</span>
            <span>位置</span>
            <span>大小</span>
            <span>最近修改</span>
            <span>操作</span>
          </div>

          {!workspaceReady ? (
            <div className="my-documents-empty" aria-label="正在从数据库加载文档">
              <Spin tip="正在从 MySQL 读取文档…" />
            </div>
          ) : visibleFolders.length || visibleDocuments.length ? (
            <div className="my-documents-list">
              {visibleFolders.map((folder) => {
                const itemCount =
                  workspace.folders.filter((item) => item.parentId === folder.id).length +
                  workspace.documents.filter((item) => item.folderId === folder.id).length;
                return (
                  <div key={folder.id} className="my-documents-row">
                    <button
                      type="button"
                      className="my-documents-name-button"
                      onClick={() => setSelectedLocation(folder.id)}
                    >
                      <span className="my-documents-folder-icon">
                        <FolderOpen size={21} />
                      </span>
                      <span title={folder.name}>{folder.name}</span>
                    </button>
                    <Tag>文件夹</Tag>
                    <Typography.Text type="secondary">
                      {getMarkdownFolderPath(folder.parentId, workspace.folders)}
                    </Typography.Text>
                    <Typography.Text type="secondary">{itemCount} 项</Typography.Text>
                    <Typography.Text type="secondary">
                      {formatDateTime(folder.createdAt)}
                    </Typography.Text>
                    <Button type="link" onClick={() => setSelectedLocation(folder.id)}>
                      打开
                    </Button>
                  </div>
                );
              })}

              {visibleDocuments.map((document) => (
                <div key={document.id} className="my-documents-row">
                  <button
                    type="button"
                    className="my-documents-name-button"
                    disabled={previewLoadingId === document.id}
                    onClick={() => void openDocumentPreview(document)}
                  >
                    <span className={`my-documents-file-icon is-${document.kind}`}>
                      {document.kind === 'multidimensional-table' ? (
                        <Database size={20} />
                      ) : document.kind === 'spreadsheet' ? (
                        <Sheet size={20} />
                      ) : (
                        <FileText size={20} />
                      )}
                    </span>
                    <span title={document.name}>{document.name}</span>
                  </button>
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
                  <Typography.Text type="secondary" ellipsis={{ tooltip: true }}>
                    {getMarkdownFolderPath(document.folderId, workspace.folders)}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {formatFileSize(document.size)}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {formatDateTime(document.updatedAt)}
                  </Typography.Text>
                  <span className="my-documents-actions">
                    <Tooltip title="移动到文件夹">
                      <Button
                        type="text"
                        aria-label={`移动 ${document.name}`}
                        icon={<MoveRight size={17} />}
                        onClick={() => openMoveDialog(document)}
                      />
                    </Tooltip>
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
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="my-documents-empty">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={query ? '没有匹配的文件或文件夹' : '这里还没有内容'}
              >
                {!query && (
                  <Button icon={<FolderPlus size={16} />} onClick={() => setNewFolderOpen(true)}>
                    创建第一个文件夹
                  </Button>
                )}
              </Empty>
            </div>
          )}
        </main>
      </div>

      <Modal
        title="新建子文件夹"
        open={newFolderOpen}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ disabled: !newFolderName.trim() }}
        onOk={() => void createFolder()}
        onCancel={() => setNewFolderOpen(false)}
      >
        <Typography.Paragraph type="secondary">
          创建位置：
          {selectedFolder ? getMarkdownFolderPath(selectedFolder.id, workspace.folders) : '根目录'}
        </Typography.Paragraph>
        <Input
          autoFocus
          maxLength={80}
          value={newFolderName}
          placeholder="例如：项目资料"
          onChange={(event) => setNewFolderName(event.target.value)}
          onPressEnter={() => newFolderName.trim() && void createFolder()}
        />
      </Modal>

      <Modal
        title={`移动 ${movingDocument?.name || ''}`}
        open={Boolean(movingDocument)}
        okText="移动"
        cancelText="取消"
        onOk={() => void moveDocument()}
        onCancel={() => setMovingDocument(null)}
      >
        <Typography.Paragraph type="secondary">请选择目标文件夹：</Typography.Paragraph>
        <Select
          className="my-documents-move-select"
          value={moveTarget}
          options={folderOptions}
          onChange={setMoveTarget}
        />
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
        <div className="my-documents-preview-meta">
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
            {previewDocument
              ? getMarkdownFolderPath(previewDocument.folderId, workspace.folders)
              : ''}
          </Typography.Text>
        </div>
        <MarkdownPreview
          key={`${previewDocument?.id}-${previewDocument?.updatedAt}-${previewDocument?.content.length}`}
          content={previewDocument?.content || ''}
          kind={previewDocument?.kind || 'document'}
        />
      </Modal>
    </div>
  );
}
