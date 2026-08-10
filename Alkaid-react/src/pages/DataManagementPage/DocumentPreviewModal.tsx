import { Button, Modal, Tag, Typography } from 'antd';
import { Lock, LockOpen, Pencil } from 'lucide-react';
import { formatFileSize, getMarkdownDocumentKindLabel, type MarkdownDocumentRecord } from './model';
import MarkdownPreview from './MarkdownPreview';
import './styles.css';

interface DocumentPreviewModalProps {
  document: MarkdownDocumentRecord | null;
  locationLabel?: string;
  onClose: () => void;
  onDownload: (document: MarkdownDocumentRecord) => void;
  onEdit: (document: MarkdownDocumentRecord) => void;
  onToggleLock: (document: MarkdownDocumentRecord) => void;
}

export default function DocumentPreviewModal({
  document,
  locationLabel,
  onClose,
  onDownload,
  onEdit,
  onToggleLock,
}: DocumentPreviewModalProps) {
  return (
    <Modal
      className={`data-management-document-preview-modal ${document?.kind === 'word' ? 'is-word' : ''}`}
      title={document?.name}
      open={Boolean(document)}
      width="min(1000px, calc(100vw - 48px))"
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        <Button key="download" onClick={() => document && onDownload(document)}>
          下载文件
        </Button>,
        <Button
          key="lock"
          icon={document?.locked ? <LockOpen size={16} /> : <Lock size={16} />}
          onClick={() => document && onToggleLock(document)}
        >
          {document?.locked ? '解锁' : '锁定'}
        </Button>,
        <Button
          key="edit"
          type="primary"
          disabled={document?.locked}
          icon={<Pencil size={16} />}
          onClick={() => document && onEdit(document)}
        >
          {document?.locked ? '已锁定' : '编辑'}
        </Button>,
      ]}
      onCancel={onClose}
    >
      <div className="data-management-preview-meta">
        <Tag
          color={
            document?.kind === 'multidimensional-table'
              ? 'cyan'
              : document?.kind === 'spreadsheet'
                ? 'lime'
                : 'blue'
          }
        >
          {document ? getMarkdownDocumentKindLabel(document.kind) : ''}
        </Tag>
        <Tag>
          {document?.kind === 'spreadsheet'
            ? 'JSON 工作簿'
            : document?.kind === 'word'
              ? 'Word 富文本'
              : 'Markdown'}
        </Tag>
        {locationLabel && <Typography.Text type="secondary">{locationLabel}</Typography.Text>}
        <Typography.Text type="secondary">
          {document ? formatFileSize(document.size) : ''}
        </Typography.Text>
      </div>
      <MarkdownPreview
        key={`${document?.id}-${document?.updatedAt}-${document?.content.length}`}
        content={document?.content || ''}
        kind={document?.kind || 'document'}
      />
    </Modal>
  );
}
