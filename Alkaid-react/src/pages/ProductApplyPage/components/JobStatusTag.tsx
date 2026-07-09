import { Space, Tag } from 'antd';
import type { JobStatus } from '../../../types/jobs';
import { statusMeta } from '../model/jobModel';

interface JobStatusTagProps {
  status: JobStatus;
  attemptCount?: number;
}

export default function JobStatusTag({ status, attemptCount = 1 }: JobStatusTagProps) {
  const meta = statusMeta[status];
  return (
    <Space size={4}>
      <Tag color={meta?.color || 'default'}>{meta?.label || status}</Tag>
      {attemptCount > 1 && <Tag>第 {attemptCount} 次</Tag>}
    </Space>
  );
}
