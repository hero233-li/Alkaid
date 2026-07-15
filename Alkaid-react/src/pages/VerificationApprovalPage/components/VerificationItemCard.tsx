import { Button, Card, Space, Tag } from 'antd';
import { Check, RotateCcw } from 'lucide-react';
import type { VerificationItem } from '../types';

interface VerificationItemCardProps {
  item: VerificationItem;
  disabled: boolean;
  onComplete: () => void;
  onCancel: () => void;
}

export default function VerificationItemCard({
  item,
  disabled,
  onComplete,
  onCancel,
}: VerificationItemCardProps) {
  const completed = item.status === 'completed';

  return (
    <Card
      size="small"
      className={`verification-item-card${completed ? ' verification-item-card--completed' : ''}`}
      title={(
        <span className="verification-item-heading">
          <span>{item.title}</span>
          <Tag color={completed ? 'blue' : 'default'}>{completed ? '已完成' : '未完成'}</Tag>
        </span>
      )}
    >
      <Space className="verification-item-actions">
        <Button type="primary" icon={<Check size={14} />} disabled={disabled} onClick={onComplete}>
          完成
        </Button>
        <Button icon={<RotateCcw size={14} />} disabled={disabled} onClick={onCancel}>
          取消
        </Button>
      </Space>
    </Card>
  );
}
