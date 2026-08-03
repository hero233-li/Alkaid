import { useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Modal,
  Pagination,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { DynamicQueryResult, Risk050009Detail } from '../types';

type ResultRow = Record<string, unknown>;
const text = (value: unknown) =>
  value === null || value === undefined || value === '' ? '-' : String(value);
const resultTag = (value: unknown) => {
  const label = text(value);
  return <Tag color={label === '验证通过' ? 'success' : 'error'}>{label}</Tag>;
};

export default function Risk050009ResultList({
  result,
  busy,
}: {
  result: DynamicQueryResult | null;
  busy: boolean;
}) {
  const [details, setDetails] = useState<Risk050009Detail[]>([]);
  const [detailPage, setDetailPage] = useState(1);
  if (!result) return null;
  const rows: (ResultRow & { __rowKey: number })[] = (result?.body ?? []).map((row, index) => ({
    ...row,
    __rowKey: index,
  }));
  const total = rows.length;
  const passed = rows.filter((row) => row['verificationResult'] === '验证通过').length;
  const failed = rows.filter((row) => row['verificationResult'] === '验证不通过').length;
  const successRate = total ? Number(((passed / total) * 100).toFixed(2)) : 0;
  const columns = [
    { title: '环境', dataIndex: 'environment', key: 'environment', width: 100 },
    { title: '产品代码', dataIndex: 'productCode', key: 'productCode', width: 120 },
    { title: '产品名称', dataIndex: 'productName', key: 'productName', width: 150 },
    { title: '卡号', dataIndex: 'cardNo', key: 'cardNo', width: 210 },
    { title: '查询开始日期', dataIndex: 'queryStartDate', key: 'queryStartDate', width: 140 },
    { title: '截止日期', dataIndex: 'queryEndDate', key: 'queryEndDate', width: 140 },
    { title: '查询柜员号', dataIndex: 'tellerNo', key: 'tellerNo', width: 130 },
    { title: '查询柜员权限', dataIndex: 'tellerPermission', key: 'tellerPermission', width: 140 },
    {
      title: '该次验证结果',
      dataIndex: 'verificationResult',
      key: 'verificationResult',
      width: 140,
      render: resultTag,
    },
    {
      title: '操作',
      key: 'operation',
      width: 90,
      render: (_: unknown, row: ResultRow) => (
        <Button
          type="link"
          disabled={busy}
          onClick={() => {
            setDetails(Array.isArray(row.details) ? (row.details as Risk050009Detail[]) : []);
            setDetailPage(1);
          }}
        >
          详情
        </Button>
      ),
    },
  ];
  const currentDetail = details[detailPage - 1];
  const closeDetail = () => {
    setDetails([]);
    setDetailPage(1);
  };
  return (
    <>
      <Card
        title={
          <Space>
            <span>高频交易查询结果</span>
            <Tag color="blue">risk050009 · 高频交易</Tag>
          </Space>
        }
      >
        <div className="high-frequency-report">
          <Typography.Title level={5}>执行成功率报告</Typography.Title>
          <Row gutter={[16, 16]} align="middle">
            <Col xs={12} md={5}>
              <Statistic title="总数量" value={total} />
            </Col>
            <Col xs={12} md={5}>
              <Statistic title="验证通过" value={passed} valueStyle={{ color: '#389e0d' }} />
            </Col>
            <Col xs={12} md={5}>
              <Statistic title="验证不通过" value={failed} valueStyle={{ color: '#cf1322' }} />
            </Col>
            <Col xs={24} md={9}>
              <div className="high-frequency-success-rate">
                <Typography.Text type="secondary">成功率</Typography.Text>
                <Progress
                  type="circle"
                  percent={successRate}
                  strokeColor={failed ? '#ff4d4f' : '#52c41a'}
                  format={(percent) => `${percent ?? 0}%`}
                  width={112}
                />
              </div>
            </Col>
          </Row>
        </div>
        <Table
          rowKey="__rowKey"
          bordered
          loading={busy}
          pagination={false}
          dataSource={rows}
          columns={columns}
          scroll={{ x: 1200 }}
        />
      </Card>
      <Modal
        title="查询详细情况"
        open={details.length > 0}
        footer={null}
        width={860}
        onCancel={closeDetail}
        destroyOnClose
      >
        {currentDetail && (
          <>
            <Descriptions bordered column={2} size="middle">
              <Descriptions.Item label="卡号">{text(currentDetail.cardNo)}</Descriptions.Item>
              <Descriptions.Item label="交易方">
                {text(currentDetail.counterparty)}
              </Descriptions.Item>
              <Descriptions.Item label="交易卡号">
                {text(currentDetail.counterpartyCardNo)}
              </Descriptions.Item>
              <Descriptions.Item label="时间">
                {text(currentDetail.transactionTime)}
              </Descriptions.Item>
              <Descriptions.Item label="柜员名称">
                {text(currentDetail.tellerName)}
              </Descriptions.Item>
              <Descriptions.Item label="行内行外">
                {text(currentDetail.transferScope)}
              </Descriptions.Item>
              <Descriptions.Item label="机构号" span={2}>
                {text(currentDetail.organizationNo)}
              </Descriptions.Item>
            </Descriptions>
            <div className="high-frequency-detail-pagination">
              <Pagination
                current={detailPage}
                total={details.length}
                pageSize={1}
                showSizeChanger={false}
                showQuickJumper
                showTotal={(count) => `共 ${count} 笔`}
                onChange={setDetailPage}
              />
            </div>
          </>
        )}
      </Modal>
    </>
  );
}
