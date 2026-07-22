import { useCallback, useEffect, useState } from 'react';
import { Button, Input, Select, Space, Table, Tag, Typography, message } from 'antd';
import { RefreshCw, Search } from 'lucide-react';
import { getJobDetail, listJobs } from '../api/jobs';
import type { JobDetail, JobStatus } from '../types/jobs';
import TaskCenterJobDetail from './TaskCenterJobDetail';

const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '等待中', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '重试中', value: 'retrying' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '取消中', value: 'cancel_requested' },
  { label: '已取消', value: 'cancelled' },
  { label: '已超时', value: 'timed_out' },
];

const statusLabels: Record<JobStatus, string> = {
  pending: '等待中',
  running: '执行中',
  retrying: '重试中',
  success: '成功',
  failed: '失败',
  cancel_requested: '取消中',
  cancelled: '已取消',
  timed_out: '已超时',
};

const statusColors: Record<JobStatus, string> = {
  pending: 'default',
  running: 'processing',
  retrying: 'warning',
  success: 'success',
  failed: 'error',
  cancel_requested: 'warning',
  cancelled: 'default',
  timed_out: 'error',
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

export default function TaskCenterPage() {
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [draftStatus, setDraftStatus] = useState('');
  const [draftQuery, setDraftQuery] = useState('');
  const [appliedFilters, setAppliedFilters] = useState({ limit: 5 });
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);

  const loadJobs = useCallback(
    async (filters: { status?: string; query?: string; limit: number }) => {
      setLoading(true);
      try {
        setJobs(await listJobs(filters));
      } catch (error) {
        message.error(error instanceof Error ? error.message : '获取任务列表失败');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadJobs({ limit: 5 });
  }, [loadJobs]);

  const searchJobs = () => {
    const nextFilters = {
      status: draftStatus || undefined,
      query: draftQuery.trim() || undefined,
      limit: draftStatus || draftQuery.trim() ? 100 : 5,
    };
    setAppliedFilters(nextFilters);
    void loadJobs(nextFilters);
  };

  const openDetail = async (job: JobDetail) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setSelectedJob(null);
    try {
      setSelectedJob(await getJobDetail(job.id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '获取任务详情失败');
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="page-surface task-center-page">
      <div className="page-title-row">
        <div>
          <Typography.Title level={3}>任务中心</Typography.Title>
          <Typography.Text type="secondary">查询最近任务、执行状态和失败原因</Typography.Text>
        </div>
        <Button
          icon={<RefreshCw size={16} />}
          loading={loading}
          onClick={() => void loadJobs(appliedFilters)}
        >
          刷新
        </Button>
      </div>

      <Space className="task-center-filters" wrap>
        <Input
          allowClear
          value={draftQuery}
          prefix={<Search size={15} />}
          placeholder="搜索 Job、日志或内部调用记录"
          onChange={(event) => setDraftQuery(event.target.value)}
          onPressEnter={searchJobs}
        />
        <Select value={draftStatus} options={statusOptions} onChange={setDraftStatus} />
        <Button type="primary" onClick={searchJobs}>
          查询
        </Button>
      </Space>

      <Table<JobDetail>
        rowKey="id"
        loading={loading}
        dataSource={jobs}
        pagination={{ pageSize: 20, hideOnSinglePage: true }}
        scroll={{ x: 900 }}
        columns={[
          { title: 'Job ID', dataIndex: 'id', width: 90 },
          { title: '任务名称', dataIndex: 'name', width: 220, ellipsis: true },
          { title: '产品', dataIndex: 'product', width: 140, ellipsis: true },
          {
            title: '状态',
            dataIndex: 'status',
            width: 110,
            render: (value: JobStatus) => (
              <Tag color={statusColors[value]}>{statusLabels[value]}</Tag>
            ),
          },
          { title: '阶段', dataIndex: 'stage', width: 150, ellipsis: true },
          { title: '进度', dataIndex: 'progress', width: 90, render: (value) => `${value}%` },
          {
            title: '失败原因',
            dataIndex: 'errorMessage',
            ellipsis: true,
            render: (value?: string) => value || '-',
          },
          {
            title: '创建时间',
            dataIndex: 'createdAt',
            width: 190,
            render: formatTime,
          },
          {
            title: '操作',
            key: 'actions',
            width: 90,
            fixed: 'right',
            render: (_, job) =>
              job.apiCallCount > 0 ? (
                <Button type="link" onClick={() => void openDetail(job)}>
                  详情
                </Button>
              ) : (
                '-'
              ),
          },
        ]}
      />
      <TaskCenterJobDetail
        detail={selectedJob}
        loading={detailLoading}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />
    </div>
  );
}
