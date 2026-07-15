import { Modal, Progress, Space, Spin, Tag, Typography } from 'antd';

interface ProductApplicationWorkflowModalProps {
  active: boolean;
}

export default function ProductApplicationWorkflowModal({
  active,
}: ProductApplicationWorkflowModalProps) {
  return (
    <Modal
      title="产品申请处理中"
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
          <Typography.Text strong>正在提交产品申请</Typography.Text>
        </Space>
        <Tag color="processing">处理中</Tag>
      </Space>
      <Progress percent={8} status="active" strokeWidth={13} showInfo={false} />
      <Typography.Text type="secondary">正在等待后端返回，请不要重复操作</Typography.Text>
    </Modal>
  );
}
