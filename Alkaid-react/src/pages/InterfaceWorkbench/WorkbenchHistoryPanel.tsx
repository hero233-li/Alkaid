import { Button, Empty, Input, Modal, Popconfirm, Spin, Tag, Tooltip, Typography } from 'antd';
import { FolderOpen, Pencil, Plus, RefreshCw, Search, Trash2, Upload } from 'lucide-react';

import type { WorkbenchHistoryItem } from '../../types';
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
          placeholder="搜索请求历史"
          onChange={(event) => props.onSearchChange(event.target.value)}
        />
        <div className="workbench-library-actions">
          <Button icon={<Upload size={16} />} onClick={props.onImport}>
            导入 cURL
          </Button>
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
