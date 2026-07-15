import { Button, Card, Empty, Space, Tag } from 'antd';
import {
  CheckCheck,
  ClipboardCheck,
  CornerDownLeft,
  FileUp,
  PackageCheck,
  RefreshCw,
  Send,
  UserCheck,
} from 'lucide-react';
import type {
  VerificationQuickAction,
  VerificationTask,
} from '../types';
import VerificationItemCard from './VerificationItemCard';

interface VerificationTaskPanelProps {
  task: VerificationTask | null;
  hasSearched: boolean;
  allCompleted: boolean;
  busy: boolean;
  onClaim: () => void;
  onReturn: () => void;
  onRefresh: () => void;
  onItemChange: (itemId: string, completed: boolean) => void;
  onAction: (action: VerificationQuickAction) => void;
}

export default function VerificationTaskPanel({
  task,
  hasSearched,
  allCompleted,
  busy,
  onClaim,
  onReturn,
  onRefresh,
  onItemChange,
  onAction,
}: VerificationTaskPanelProps) {
  if (!task) {
    return (
      <Card title="核实审批结果">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={hasSearched ? '未查询到核实内容' : '请先输入搜索条件查询核实任务'}
        />
      </Card>
    );
  }

  const claimed = task.ownershipStatus === 'claimed';

  return (
    <div className="verification-task-stack">
      <Card
        title={<span className="verification-task-title"><ClipboardCheck size={18} />合同号：{task.contractNo}</span>}
        extra={(
          <Space>
            <Button icon={<RefreshCw size={15} />} disabled={busy} onClick={onRefresh}>
              刷新
            </Button>
            {claimed ? (
              <Button danger icon={<CornerDownLeft size={15} />} loading={busy} onClick={onReturn}>退回任务池</Button>
            ) : (
              <Button type="primary" icon={<UserCheck size={15} />} loading={busy} onClick={onClaim}>领取</Button>
            )}
          </Space>
        )}
      >
        <div className="verification-task-toolbar">
          <div className="verification-task-tags">
            <Tag color={claimed ? 'processing' : 'default'}>领取状态：{claimed ? '已领取' : '未领取'}</Tag>
            <Tag color="blue">任务状态：{task.taskStatus}</Tag>
            <Tag>节点：{task.node}</Tag>
            <Tag>柜员号：{task.tellerNo}</Tag>
            <Tag>机构号：{task.organizationNo}</Tag>
            <Tag color="geekblue">产品名称：{task.productName}</Tag>
          </div>
          <Space wrap className="verification-quick-actions">
            <Button
              icon={<CheckCheck size={15} />}
              disabled={!claimed || busy}
              onClick={() => onAction('complete')}
            >
              一键完成
            </Button>
            <Button
              icon={<FileUp size={15} />}
              disabled={!claimed || busy}
              onClick={() => onAction('supplement')}
            >
              一键补件
            </Button>
            <Button
              type="primary"
              ghost
              icon={<Send size={15} />}
              disabled={!allCompleted || busy}
              onClick={() => onAction('submit')}
            >
              一键提交
            </Button>
            <Button
              type="primary"
              icon={<PackageCheck size={15} />}
              disabled={!claimed || busy}
              onClick={() => onAction('approval-submit')}
            >
              一键审批提交
            </Button>
          </Space>
        </div>
      </Card>

      {claimed && (
        <Card className="verification-content-card">
          <div className="verification-item-grid">
            {task.items.map((item) => (
              <VerificationItemCard
                key={item.id}
                item={item}
                disabled={busy}
                onComplete={() => onItemChange(item.id, true)}
                onCancel={() => onItemChange(item.id, false)}
              />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
