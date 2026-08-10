import { Modal, Progress, Space, Spin, Tag, Typography } from 'antd';

interface VerificationWorkflowModalProps {
  active: boolean;
  label: string;
  progress: number;
}

export default function VerificationWorkflowModal({
  active,
  label,
  progress,
}: VerificationWorkflowModalProps) {
  return (
    <Modal
      title="核实审批处理中"
      open={active}
      centered
      closable={false}
      keyboard={false}
      maskClosable={false}
      footer={null}
      zIndex={1300}
    >
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 18 }}>
        <Space>
          <Spin size="small" />
          <Typography.Text strong>{label}</Typography.Text>
        </Space>
        <Tag color="processing">处理中</Tag>
      </Space>
      <Progress percent={Math.max(5, progress)} status="active" strokeWidth={13} />
      <Typography.Text type="secondary">
        任务已提交到 Celery，正在等待执行结果，请不要重复操作
      </Typography.Text>
    </Modal>
  );
}
