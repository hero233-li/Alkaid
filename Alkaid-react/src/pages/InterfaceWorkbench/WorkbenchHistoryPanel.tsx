import { useEffect, useRef, useState } from 'react';
import { Button, Empty, Input, Modal, Popconfirm, Spin, Tag, Tooltip, Typography } from 'antd';
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  FolderArchive,
  FolderOpen,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from 'lucide-react';

import type { WorkbenchHistoryItem, WorkbenchPackage } from '../../types';
import { displayRequestName, methodClassName, statusColor } from './presentation';

interface WorkbenchHistoryPanelProps {
  items: WorkbenchHistoryItem[];
  visibleItems: WorkbenchHistoryItem[];
  selectedId: number | null;
  loading: boolean;
  search: string;
  onSearchChange: (value: string) => void;
  onNew: () => void;
  onImport: () => void;
  packages: WorkbenchPackage[];
  visiblePackages: WorkbenchPackage[];
  selectedPackageRequestId: number | null;
  packagesLoading: boolean;
  sazImporting: boolean;
  onImportSaz: (file: File) => void;
  onOpenPackageRequest: (packageId: number, requestId: number) => void;
  onDeletePackage: (packageId: number) => void;
  onRefresh: () => void;
  onClear: () => void;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
  onStartRename: (item: WorkbenchHistoryItem) => void;
  renameOpen: boolean;
  renameName: string;
  renameSaving: boolean;
  onRenameNameChange: (value: string) => void;
  onRenameCancel: () => void;
  onRenameSubmit: () => void;
}

export function WorkbenchHistoryPanel(props: WorkbenchHistoryPanelProps) {
  const sazInputRef = useRef<HTMLInputElement>(null);
  const [expandedPackageIds, setExpandedPackageIds] = useState<Set<number>>(new Set());
  useEffect(() => {
    setExpandedPackageIds((current) => {
      const next = new Set(current);
      props.packages.forEach((item) => next.add(item.id));
      return next;
    });
  }, [props.packages]);
  const togglePackage = (packageId: number) => {
    setExpandedPackageIds((current) => {
      const next = new Set(current);
      if (next.has(packageId)) next.delete(packageId);
      else next.add(packageId);
      return next;
    });
  };
  return (
    <>
      <aside className="workbench-library">
        <div className="workbench-library-title">
          <div>
            <Typography.Title level={4}>接口管理</Typography.Title>
            <Typography.Text type="secondary">快速请求</Typography.Text>
          </div>
          <Tooltip title="新建请求">
            <Button type="primary" icon={<Plus size={16} />} onClick={props.onNew} />
          </Tooltip>
        </div>
        <Input
          prefix={<Search size={16} />}
          value={props.search}
          placeholder="搜索接口包或请求历史"
          onChange={(event) => props.onSearchChange(event.target.value)}
        />
        <div className="workbench-library-actions">
          <Button icon={<Upload size={16} />} onClick={props.onImport}>
            导入 cURL
          </Button>
          <Button
            icon={<FolderArchive size={16} />}
            loading={props.sazImporting}
            onClick={() => sazInputRef.current?.click()}
          >
            导入 SAZ
          </Button>
          <input
            ref={sazInputRef}
            className="workbench-saz-input"
            type="file"
            accept=".saz,application/octet-stream"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) props.onImportSaz(file);
              event.currentTarget.value = '';
            }}
          />
        </div>
        <div className="workbench-library-secondary-actions">
          <Button icon={<RefreshCw size={16} />} onClick={props.onRefresh} />
          <Popconfirm
            title="清空请求历史？"
            okText="清空"
            cancelText="取消"
            onConfirm={props.onClear}
          >
            <Button icon={<Trash2 size={16} />} />
          </Popconfirm>
        </div>
        <div className="history-group-label">
          <FolderArchive size={16} />
          <span>接口包</span>
          <Tag>{props.packages.length}</Tag>
        </div>
        <div className="workbench-packages-pane">
          <Spin spinning={props.packagesLoading || props.sazImporting}>
            <div className="workbench-package-list">
              {props.visiblePackages.map((item) => (
                <div className="workbench-package-folder" key={item.id}>
                  <div className="workbench-package-folder-header">
                    <button
                      className="workbench-package-summary"
                      onClick={() => togglePackage(item.id)}
                    >
                      {expandedPackageIds.has(item.id) ? (
                        <ChevronDown size={14} />
                      ) : (
                        <ChevronRight size={14} />
                      )}
                      <FolderOpen size={15} />
                      <span title={item.sourceFilename}>{item.name}</span>
                      <Tag>{item.requestCount}</Tag>
                    </button>
                    <Popconfirm
                      title="删除这个接口包？"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => props.onDeletePackage(item.id)}
                    >
                      <Button
                        size="small"
                        type="text"
                        danger
                        icon={<Trash2 size={13} />}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </Popconfirm>
                  </div>
                  {expandedPackageIds.has(item.id) && (
                    <div className="workbench-package-requests">
                      {item.requests.map((request) => (
                        <button
                          className={`workbench-package-request ${
                            props.selectedPackageRequestId === request.id ? 'active' : ''
                          }`}
                          key={request.id}
                          onClick={() => props.onOpenPackageRequest(item.id, request.id)}
                        >
                          <FileCode2 size={14} />
                          <span className={`history-method ${methodClassName(request.method)}`}>
                            {request.method}
                          </span>
                          <span title={request.url}>{request.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {!props.visiblePackages.length && (
                <Typography.Text className="workbench-package-empty" type="secondary">
                  暂无接口包，可导入 Fiddler SAZ
                </Typography.Text>
              )}
            </div>
          </Spin>
        </div>
        <div className="history-group-label">
          <FolderOpen size={16} />
          <span>请求历史</span>
          <Tag>{props.items.length}</Tag>
        </div>
        <Spin spinning={props.loading}>
          <div className="history-list">
            {props.visibleItems.length ? (
              props.visibleItems.map((item) => (
                <div
                  className={`history-item ${props.selectedId === item.id ? 'active' : ''}`}
                  key={item.id}
                >
                  <button className="history-item-main" onClick={() => props.onOpen(item.id)}>
                    <span className={`history-method ${methodClassName(item.method)}`}>
                      {item.method}
                    </span>
                    <span className="history-content">
                      <span className="history-name">{displayRequestName(item)}</span>
                      <span className="history-url">{item.url}</span>
                    </span>
                    <span className="history-meta">
                      <Tag color={item.success ? statusColor(item.responseStatus) : 'error'}>
                        {item.responseStatus || 'ERR'}
                      </Tag>
                      <span>{item.durationMs ?? '-'}ms</span>
                    </span>
                  </button>
                  <span className="history-item-actions">
                    <Tooltip title="修改名称">
                      <Button
                        size="small"
                        type="text"
                        icon={<Pencil size={14} />}
                        onClick={() => props.onStartRename(item)}
                      />
                    </Tooltip>
                    <Popconfirm
                      title="删除这条请求？"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => props.onDelete(item.id)}
                    >
                      <Button size="small" type="text" danger icon={<Trash2 size={14} />} />
                    </Popconfirm>
                  </span>
                </div>
              ))
            ) : (
              <Empty
                className="history-empty"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无请求记录"
              />
            )}
          </div>
        </Spin>
      </aside>
      <Modal
        title="修改请求名称"
        open={props.renameOpen}
        confirmLoading={props.renameSaving}
        onCancel={props.onRenameCancel}
        onOk={props.onRenameSubmit}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={props.renameName}
          placeholder="请输入请求名称"
          maxLength={200}
          onChange={(event) => props.onRenameNameChange(event.target.value)}
          onPressEnter={props.onRenameSubmit}
        />
      </Modal>
    </>
  );
}
