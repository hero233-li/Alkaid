import { Modal, Progress, Space, Tag, Typography } from 'antd';
import type { ApplicationDataActivity } from '../types';
export default function ApplicationDataWorkflowModal({
  activity,
}: {
  activity: ApplicationDataActivity | null;
}) {
  return (
    <Modal
      title="申请数据生成"
      open={Boolean(activity)}
      centered
      closable={false}
      keyboard={false}
      maskClosable={false}
      footer={null}
    >
      {activity && (
        <>
          <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 18 }}>
            <Typography.Text strong>{activity.label}</Typography.Text>
            <Tag color="processing">{activity.status}</Tag>
          </Space>
          <Progress percent={activity.progress || 5} status="active" strokeWidth={13} />
        </>
      )}
    </Modal>
  );
}
