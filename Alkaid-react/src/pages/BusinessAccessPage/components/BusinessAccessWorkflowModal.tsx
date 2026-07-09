import { Modal, Progress, Space, Tag, Typography } from 'antd';
import type { BusinessAccessWorkflowActivity } from '../../../api/businessAccess';

interface BusinessAccessWorkflowModalProps {
  activity: BusinessAccessWorkflowActivity | null;
}

const statusLabels: Record<BusinessAccessWorkflowActivity['status'], string> = {
  submitting: '正在提交',
  pending: '等待执行',
  running: '执行中',
  retrying: '重试中',
  success: '已完成',
  failed: '执行失败',
  cancel_requested: '取消中',
  cancelled: '已取消',
  timed_out: '已超时',
};

function visibleProgress(activity: BusinessAccessWorkflowActivity) {
  if (activity.progress > 0) {
    return activity.progress;
  }
  if (activity.status === 'submitting') {
    return 5;
  }
  if (activity.status === 'pending') {
    return 10;
  }
  return 15;
}

export default function BusinessAccessWorkflowModal({ activity }: BusinessAccessWorkflowModalProps) {
  const percent = activity ? visibleProgress(activity) : 0;

  return (
    <Modal
      open={Boolean(activity)}
      title="业务准入任务处理中"
      centered
      closable={false}
      keyboard={false}
      maskClosable={false}
      footer={null}
      width={560}
      zIndex={1200}
    >
      {activity ? (
        <div className="business-access-workflow-modal-content" role="status" aria-live="polite">
          <div className="business-access-workflow-modal-heading">
            <Typography.Title level={5}>{activity.label}</Typography.Title>
            <Space size={8}>
              <Tag color="processing">{statusLabels[activity.status]}</Tag>
              <Typography.Text type="secondary">
                {activity.jobId ? `Workflow Job #${activity.jobId}` : '正在创建 Job'}
              </Typography.Text>
            </Space>
          </div>
          <Progress
            percent={percent}
            status="active"
            strokeWidth={14}
            strokeColor={{ from: '#1677ff', to: '#52c41a' }}
          />
          <Typography.Paragraph type="secondary" className="business-access-workflow-modal-tip">
            Workflow 完成后将自动关闭并展示处理结果，请勿重复操作。
          </Typography.Paragraph>
        </div>
      ) : null}
    </Modal>
  );
}
