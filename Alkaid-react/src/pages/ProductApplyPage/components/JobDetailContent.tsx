import { Fragment } from 'react';
import { Alert, Card, Space, Steps, Tag } from 'antd';
import type { ProductApplicationResult } from '../model/types';
import { formatDate, statusMeta, terminalStatuses } from '../model/jobModel';

interface JobDetailContentProps {
  result: ProductApplicationResult;
}

export default function JobDetailContent({ result }: JobDetailContentProps) {
  return (
    <div className="product-application-stack">
      <Card title="执行过程" size="small">
        <Steps
          current={result.stage === 'completed' ? 2 : result.stage === 'validate' ? 1 : 0}
          status={result.status === 'success' ? 'finish' : terminalStatuses.has(result.status) ? 'error' : 'process'}
          items={[
            { title: '参数提交' },
            { title: '规则验证' },
            { title: '完成' },
          ]}
        />
      </Card>
      <Card title="运行信息" size="small">
        <Space wrap>
          <Tag color={statusMeta[result.status]?.color}>{statusMeta[result.status]?.label}</Tag>
          <span>执行次数：{result.attemptCount || 1}</span>
          <span>Trace ID：{result.traceId || '-'}</span>
          {result.deadlineAt && <span>超时时间：{formatDate(result.deadlineAt)}</span>}
        </Space>
        {result.errorMessage && (
          <Alert type="error" showIcon message={result.errorMessage} className="product-job-error" />
        )}
      </Card>
      <Card title="提交参数" size="small">
        <pre className="product-result-code">{JSON.stringify(result.payload, null, 2)}</pre>
      </Card>
      <Card title="后端运行日志" size="small">
        <div className="product-backend-logs">
          {result.logs.map((log, index) => {
            const previousLog = result.logs[index - 1];
            const startsNewAttempt = Boolean(log.attempt || log.taskId) && (
              !previousLog
              || previousLog.attempt !== log.attempt
              || previousLog.taskId !== log.taskId
            );
            return (
              <Fragment key={log.id || `${log.createdAt}-${index}`}>
                {startsNewAttempt && (
                  <div className="product-backend-log-batch">
                    {log.attempt && <Tag color="purple">第 {log.attempt} 次执行</Tag>}
                    {log.taskId && <span title={log.taskId}>Celery Task：{log.taskId}</span>}
                  </div>
                )}
                <div className="product-backend-log-line">
                  <span className="product-backend-log-time">{formatDate(log.createdAt)}</span>
                  <Tag color={log.level === 'ERROR' ? 'error' : log.level === 'WARN' ? 'warning' : 'blue'}>
                    {log.level}
                  </Tag>
                  <span>{log.message}</span>
                </div>
              </Fragment>
            );
          })}
          {!result.logs.length && <span className="product-backend-log-empty">暂无后端运行日志</span>}
        </div>
      </Card>
    </div>
  );
}
