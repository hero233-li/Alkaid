import type { ReactNode } from 'react';
import { Button, Progress, Space, type TableProps } from 'antd';
import { RefreshCw, Square } from 'lucide-react';
import { ActionTable } from '../../../components/common';
import type { ProductApplicationResult } from '../model/types';
import { activeStatuses, formatDate } from '../model/jobModel';
import JobStatusTag from './JobStatusTag';

interface JobResultListProps {
  results: ProductApplicationResult[];
  onDetail: (result: ProductApplicationResult) => void;
  onRetry: (result: ProductApplicationResult) => void;
  onCancel: (result: ProductApplicationResult) => void;
  renderActions?: (result: ProductApplicationResult) => ReactNode;
}

export default function JobResultList({
  results,
  onDetail,
  onRetry,
  onCancel,
  renderActions,
}: JobResultListProps) {
  const columns: NonNullable<TableProps<ProductApplicationResult>['columns']> = [
    { title: '申请项目', dataIndex: 'name', width: 220 },
    { title: '产品', dataIndex: 'product', width: 160 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 150,
      render: (_, record) => <JobStatusTag status={record.status} attemptCount={record.attemptCount} />,
    },
    {
      title: '进度',
      dataIndex: 'progress',
      width: 220,
      render: (value: number, record) => (
        <Progress
          percent={value}
          size="small"
          status={
            record.status === 'success'
              ? 'success'
              : record.status === 'failed' || record.status === 'timed_out'
                ? 'exception'
                : activeStatuses.has(record.status)
                  ? 'active'
                  : 'normal'
          }
        />
      ),
    },
    { title: '创建时间', dataIndex: 'createdAt', width: 190, render: (value: string) => formatDate(value) },
  ];

  const defaultActions = (record: ProductApplicationResult) => (
    <Space size={6}>
      <Button size="small" onClick={() => onDetail(record)}>详情</Button>
      {(record.status === 'failed' || record.status === 'timed_out') && (
        <Button
          size="small"
          type="primary"
          icon={<RefreshCw size={14} />}
          onClick={() => onRetry(record)}
        >
          重试
        </Button>
      )}
      {activeStatuses.has(record.status) && (
        <Button size="small" danger icon={<Square size={13} />} onClick={() => onCancel(record)}>
          取消
        </Button>
      )}
    </Space>
  );

  return (
    <ActionTable<ProductApplicationResult>
      title="执行结果"
      rowKey="id"
      dataSource={results}
      columns={columns}
      renderActions={renderActions ?? defaultActions}
      actionColumn={{ width: 220 }}
      tableProps={{
        locale: { emptyText: '暂无执行结果' },
        pagination: { pageSize: 6, hideOnSinglePage: true },
      }}
    />
  );
}
