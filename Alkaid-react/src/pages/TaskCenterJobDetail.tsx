import { Card, Collapse, Descriptions, Empty, Space, Spin, Tag, Typography } from 'antd';
import { DetailOverlay } from '../components/common';
import type { JobApiCall, JobDetail, JobLog } from '../types/jobs';

interface TaskCenterJobDetailProps {
  detail: JobDetail | null;
  loading: boolean;
  open: boolean;
  onClose: () => void;
}

function formatTime(value?: string) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function JsonContent({ value }: { value: unknown }) {
  return <pre className="task-center-detail-code">{JSON.stringify(value ?? null, null, 2)}</pre>;
}

function ApiCallContent({ call }: { call: JobApiCall }) {
  return (
    <div className="task-center-call-content">
      <Descriptions size="small" column={2} bordered>
        <Descriptions.Item label="执行步骤">{call.step || '-'}</Descriptions.Item>
        <Descriptions.Item label="执行次数">{call.attempt}</Descriptions.Item>
        <Descriptions.Item label="响应状态">{call.responseStatus ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="耗时">
          {call.durationMs === undefined ? '-' : `${call.durationMs} ms`}
        </Descriptions.Item>
        <Descriptions.Item label="开始时间">{formatTime(call.startedAt)}</Descriptions.Item>
        <Descriptions.Item label="完成时间">{formatTime(call.finishedAt)}</Descriptions.Item>
      </Descriptions>
      {call.errorMessage && <Typography.Text type="danger">{call.errorMessage}</Typography.Text>}
      <Card size="small" title="请求内容">
        <JsonContent value={{ headers: call.requestHeaders, body: call.requestBody }} />
      </Card>
      <Card size="small" title={call.responseTruncated ? '响应内容（已截断）' : '响应内容'}>
        <JsonContent value={{ headers: call.responseHeaders, body: call.responseBody }} />
      </Card>
    </div>
  );
}

function callStatus(call: JobApiCall) {
  if (call.status === 'success') return <Tag color="success">成功</Tag>;
  if (call.status === 'failed') return <Tag color="error">失败</Tag>;
  return <Tag color="processing">执行中</Tag>;
}

function LogList({ logs }: { logs: JobLog[] }) {
  if (!logs.length)
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行日志" />;
  return (
    <div className="task-center-log-list">
      {logs.map((log, index) => (
        <div className="task-center-log-line" key={log.id ?? `${log.createdAt}-${index}`}>
          <Typography.Text type="secondary">{formatTime(log.createdAt)}</Typography.Text>
          <Tag color={log.level === 'ERROR' ? 'error' : log.level === 'WARN' ? 'warning' : 'blue'}>
            {log.level}
          </Tag>
          <span>{log.message}</span>
        </div>
      ))}
    </div>
  );
}

export default function TaskCenterJobDetail({
  detail,
  loading,
  open,
  onClose,
}: TaskCenterJobDetailProps) {
  const calls = detail?.apiCalls ?? [];
  return (
    <DetailOverlay
      presentation="drawer"
      title="任务执行详情"
      open={open}
      onClose={onClose}
      width={860}
    >
      <Spin spinning={loading}>
        {detail ? (
          <Space direction="vertical" size={16} className="task-center-detail-stack">
            <Card size="small" title="任务信息">
              <Descriptions size="small" column={2} bordered>
                <Descriptions.Item label="Job ID">{detail.id}</Descriptions.Item>
                <Descriptions.Item label="任务名称">{detail.name}</Descriptions.Item>
                <Descriptions.Item label="产品">{detail.product || '-'}</Descriptions.Item>
                <Descriptions.Item label="阶段">{detail.stage}</Descriptions.Item>
                <Descriptions.Item label="Trace ID">{detail.traceId}</Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {formatTime(detail.createdAt)}
                </Descriptions.Item>
              </Descriptions>
            </Card>
            <Card size="small" title={`内部调用记录（${calls.length}）`}>
              {calls.length ? (
                <Collapse
                  items={calls.map((call) => ({
                    key: call.id,
                    label: (
                      <Space wrap>
                        {callStatus(call)}
                        <Typography.Text code>{call.method}</Typography.Text>
                        <span>{call.url}</span>
                        {call.durationMs !== undefined && (
                          <Typography.Text type="secondary">{call.durationMs} ms</Typography.Text>
                        )}
                      </Space>
                    ),
                    children: <ApiCallContent call={call} />,
                  }))}
                />
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内部调用记录" />
              )}
            </Card>
            <Card size="small" title="后端运行日志">
              <LogList logs={detail.logs ?? []} />
            </Card>
            <Card size="small" title="执行结果">
              <JsonContent value={detail.result} />
            </Card>
          </Space>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无任务详情" />
        )}
      </Spin>
    </DetailOverlay>
  );
}
