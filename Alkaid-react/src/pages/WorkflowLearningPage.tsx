import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import { Play, RefreshCw, Square } from 'lucide-react';
import { cancelJob, getJobDetail, retryJob, streamJobLogs } from '../api/jobs';
import type { JobDetail, JobLog, JobStatus } from '../types/jobs';
import {
  getWorkflowLabGuide,
  getWorkflowRuntime,
  submitWorkflowLab,
  type WorkflowGuideItem,
  type WorkflowLabGuide,
  type WorkflowLabJob,
  type WorkflowRuntimeSnapshot,
} from '../api/workflowLab';

interface LabFormValues {
  name: string;
  durationMs: number;
  simulateFailure: boolean;
}

interface LabExecution extends WorkflowLabJob {
  logs: JobLog[];
  errorMessage?: string;
}

const activeStatuses = new Set<JobStatus>(['pending', 'running', 'retrying', 'cancel_requested']);
const retryableStatuses = new Set<JobStatus>(['failed', 'timed_out']);
const statusMeta: Record<JobStatus, { label: string; color: string }> = {
  pending: { label: '等待 Worker', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  retrying: { label: '等待重试', color: 'warning' },
  success: { label: '成功', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancel_requested: { label: '取消中', color: 'warning' },
  cancelled: { label: '已取消', color: 'default' },
  timed_out: { label: '已超时', color: 'error' },
};

function mergeDetail(current: LabExecution, detail: JobDetail): LabExecution {
  return {
    ...current,
    status: detail.status,
    stage: detail.stage,
    progress: detail.progress,
    traceId: detail.traceId,
    idempotencyKey: detail.idempotencyKey,
    attemptCount: detail.attemptCount,
    deadlineAt: detail.deadlineAt,
    errorMessage: detail.errorMessage,
  };
}

function guideTable(items: WorkflowGuideItem[]) {
  return (
    <Table<WorkflowGuideItem>
      rowKey="title"
      dataSource={items}
      pagination={false}
      size="small"
      columns={[
        { title: '位置/步骤', dataIndex: 'title', width: 170 },
        { title: '说明', dataIndex: 'description' },
        {
          title: '代码或路径',
          dataIndex: 'code',
          render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
        },
      ]}
    />
  );
}

export default function WorkflowLearningPage() {
  const [form] = Form.useForm<LabFormValues>();
  const [guide, setGuide] = useState<WorkflowLabGuide | null>(null);
  const [runtime, setRuntime] = useState<WorkflowRuntimeSnapshot | null>(null);
  const [job, setJob] = useState<LabExecution | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [guideError, setGuideError] = useState('');

  useEffect(() => {
    getWorkflowLabGuide()
      .then(setGuide)
      .catch((error) => setGuideError(error instanceof Error ? error.message : '指南加载失败'));
  }, []);

  useEffect(() => {
    let active = true;
    const refresh = () =>
      getWorkflowRuntime()
        .then((value) => active && setRuntime(value))
        .catch(() => undefined);
    void refresh();
    const timer = window.setInterval(refresh, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!job || !activeStatuses.has(job.status)) {
      return;
    }
    let active = true;
    const refresh = () =>
      getJobDetail(job.id)
        .then((detail) => {
          if (active) {
            setJob((current) =>
              current?.id === detail.id ? mergeDetail(current, detail) : current,
            );
          }
        })
        .catch(() => undefined);
    void refresh();
    const timer = window.setInterval(refresh, 700);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (!job) {
      return;
    }
    const controller = new AbortController();
    const afterId = Math.max(0, ...job.logs.map((log) => log.id || 0));
    void streamJobLogs(
      job.id,
      afterId,
      {
        onLog: (log) =>
          setJob((current) => {
            if (
              !current ||
              current.id !== job.id ||
              (log.id && current.logs.some((item) => item.id === log.id))
            ) {
              return current;
            }
            return { ...current, logs: [...current.logs, log] };
          }),
        onStatus: (status) =>
          setJob((current) =>
            current?.id === job.id
              ? { ...current, status: status.status, progress: status.progress }
              : current,
          ),
      },
      controller.signal,
    ).catch(() => undefined);
    return () => controller.abort();
  }, [job?.id]);

  const submit = async (values: LabFormValues) => {
    setSubmitting(true);
    try {
      const result = await submitWorkflowLab(values);
      setJob({ ...result, logs: [] });
      message.success('实验 Job 已进入共享队列');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '实验提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const retry = async () => {
    if (!job) return;
    try {
      const detail = await retryJob(job.id);
      setJob((current) => (current ? mergeDetail(current, detail) : current));
      message.success(`已提交第 ${detail.attemptCount} 次执行`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '重试失败');
    }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      const detail = await cancelJob(job.id);
      setJob((current) => (current ? mergeDetail(current, detail) : current));
      message.success('实验 Job 已取消');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '取消失败');
    }
  };

  const guideTabs = useMemo(
    () =>
      guide
        ? [
            {
              key: 'change',
              label: '如何修改',
              children: (
                <Timeline
                  items={guide.changeSteps.map((item) => ({
                    children: (
                      <div>
                        <Typography.Text strong>{item.title}</Typography.Text>
                        <div>{item.description}</div>
                        <Typography.Text code>{item.code}</Typography.Text>
                      </div>
                    ),
                  }))}
                />
              ),
            },
            { key: 'files', label: '关键文件', children: guideTable(guide.keyFiles) },
            { key: 'apis', label: '接口清单', children: guideTable(guide.apis) },
            {
              key: 'yaml',
              label: 'YAML 示例',
              children: <pre className="workflow-learning-code">{guide.definitionExample}</pre>,
            },
          ]
        : [],
    [guide],
  );

  if (!guide) {
    return (
      <div className="page-surface">
        <Card>
          {guideError ? (
            <Alert type="error" message={guideError} />
          ) : (
            <Spin tip="正在加载 Workflow 指南..." />
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="page-surface workflow-learning-page">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message={guide.title}
          description={
            <span>
              {guide.summary} 详细文档：
              <Typography.Text code>{guide.documentPath}</Typography.Text>
            </span>
          }
        />

        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="Worker 数" value={runtime?.workerThreads ?? '-'} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="正在执行" value={runtime?.activeWorkers ?? '-'} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="队列等待" value={runtime?.queuedTasks ?? '-'} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="已完成任务" value={runtime?.completedTasks ?? '-'} />
            </Card>
          </Col>
        </Row>

        <Card title="整体执行链路" size="small">
          <Row gutter={[12, 12]}>
            {guide.architecture.map((item, index) => (
              <Col
                xs={24}
                md={12}
                xl={index === guide.architecture.length - 1 ? 24 : 8}
                key={item.title}
              >
                <Card size="small" className="workflow-learning-node">
                  <Tag color="blue">{index + 1}</Tag>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <div>{item.description}</div>
                  <Typography.Text code>{item.code}</Typography.Text>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={9}>
            <Card title="动手实验" extra="仅使用 workflow_lab，不影响产品申请">
              <Form<LabFormValues>
                form={form}
                layout="vertical"
                initialValues={{
                  name: '我的第一个 Workflow',
                  durationMs: 3000,
                  simulateFailure: false,
                }}
                onFinish={submit}
              >
                <Form.Item
                  name="name"
                  label="实验名称"
                  rules={[{ required: true, message: '请输入实验名称' }]}
                >
                  <Input maxLength={100} />
                </Form.Item>
                <Form.Item
                  name="durationMs"
                  label="模拟业务处理时长（毫秒）"
                  rules={[{ required: true }]}
                >
                  <InputNumber min={100} max={10000} step={500} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item name="simulateFailure" label="模拟执行失败" valuePropName="checked">
                  <Switch checkedChildren="失败" unCheckedChildren="成功" />
                </Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={submitting}
                  icon={<Play size={15} />}
                >
                  提交到共享队列
                </Button>
              </Form>
              <Alert
                className="workflow-learning-tip"
                type="warning"
                showIcon
                message="学习提示"
                description="失败 Job 重试时仍使用原 Payload，所以会再次失败。关闭模拟失败并重新提交，才会创建一个新的成功实验。"
              />
            </Card>
          </Col>

          <Col xs={24} xl={15}>
            <Card
              title="当前实验 Job"
              extra={
                job && (
                  <Space>
                    {retryableStatuses.has(job.status) && (
                      <Button
                        size="small"
                        type="primary"
                        icon={<RefreshCw size={14} />}
                        onClick={() => void retry()}
                      >
                        重试
                      </Button>
                    )}
                    {activeStatuses.has(job.status) && (
                      <Button
                        size="small"
                        danger
                        icon={<Square size={13} />}
                        onClick={() => void cancel()}
                      >
                        取消
                      </Button>
                    )}
                  </Space>
                )
              }
            >
              {!job ? (
                <Typography.Text type="secondary">
                  提交一次实验后，这里会显示状态、Trace、进度和实时日志。
                </Typography.Text>
              ) : (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color={statusMeta[job.status].color}>{statusMeta[job.status].label}</Tag>
                    <span>Job #{job.id}</span>
                    <span>第 {job.attemptCount} 次执行</span>
                    <Typography.Text code>{job.traceId}</Typography.Text>
                  </Space>
                  <Progress
                    percent={job.progress}
                    status={
                      job.status === 'success'
                        ? 'success'
                        : retryableStatuses.has(job.status)
                          ? 'exception'
                          : activeStatuses.has(job.status)
                            ? 'active'
                            : 'normal'
                    }
                  />
                  {job.errorMessage && <Alert type="error" showIcon message={job.errorMessage} />}
                  <div className="product-backend-logs workflow-learning-logs">
                    {job.logs.map((log, index) => (
                      <div
                        className="product-backend-log-line"
                        key={log.id || `${log.createdAt}-${index}`}
                      >
                        <span className="product-backend-log-time">
                          {new Date(log.createdAt).toLocaleTimeString('zh-CN')}
                        </span>
                        <Tag
                          color={
                            log.level === 'ERROR'
                              ? 'error'
                              : log.level === 'WARN'
                                ? 'warning'
                                : 'blue'
                          }
                        >
                          {log.level}
                        </Tag>
                        <span>{log.message}</span>
                      </div>
                    ))}
                    {!job.logs.length && (
                      <span className="product-backend-log-empty">等待 Worker 日志...</span>
                    )}
                  </div>
                </Space>
              )}
            </Card>
          </Col>
        </Row>

        <Card title="状态机速查" size="small">
          <Row gutter={[12, 12]}>
            {guide.statuses.map((item) => (
              <Col xs={24} md={12} xl={8} key={item.title}>
                <Card size="small">
                  <Tag color={statusMeta[item.title as JobStatus]?.color || 'blue'}>
                    {item.title}
                  </Tag>
                  <span>{item.description}</span>
                  <div>
                    <Typography.Text code>{item.code}</Typography.Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card title="自己修改时怎么走" size="small">
          <Tabs items={guideTabs} />
        </Card>
      </Space>
    </div>
  );
}
