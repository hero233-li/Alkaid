import { Modal, Progress, Space, Tag, Typography } from 'antd';
import type { ApplicationLinkActivity } from '../model/types';

export default function ApplicationLinkWorkflowModal({
  activity,
}: {
  activity: ApplicationLinkActivity | null;
}) {
  return (
    <Modal
      title="申请链接生成"
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
