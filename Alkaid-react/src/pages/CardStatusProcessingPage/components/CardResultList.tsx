import { Button, Card, Checkbox, Space, Table, Tag, Typography } from 'antd';
import { cardStatusConfig } from '../config/cardStatusConfig';
import type { CardAction, CardRecord } from '../types';

interface CardResultListProps {
  records: CardRecord[];
  selectedCardNo: string | null;
  busy: boolean;
  onSelect: (record: CardRecord | null) => void;
  onAction: (action: CardAction) => void;
}

export default function CardResultList({
  records,
  selectedCardNo,
  busy,
  onSelect,
  onAction,
}: CardResultListProps) {
  const selected = records.find((record) => record.cardNo === selectedCardNo) ?? null;

  return (
    <Card title="客户卡片">
      {records.length > 0 && (
        <div className="card-status-toolbar">
          <div className="card-status-toolbar__heading">
            <Typography.Text strong>卡片操作</Typography.Text>
            <Typography.Text type="secondary">
              {selected ? `已选择卡号：${selected.cardNo}` : '请先勾选一张卡片'}
            </Typography.Text>
          </div>
          <Space wrap>
            {cardStatusConfig.actions.map((item) => (
              <Button
                key={item.value}
                disabled={
                  busy
                  || !selected
                }
                onClick={() => onAction(item.value)}
              >
                {item.label}
              </Button>
            ))}
          </Space>
        </div>
      )}
      <Table<CardRecord>
        rowKey="cardNo"
        dataSource={records}
        pagination={false}
        scroll={{ x: 1300 }}
        columns={[
          {
            title: '选择',
            key: 'selection',
            width: 70,
            fixed: 'left',
            render: (_, record) => (
              <Checkbox
                checked={record.cardNo === selectedCardNo}
                disabled={busy}
                onChange={(event) => onSelect(event.target.checked ? record : null)}
              />
            ),
          },
          { title: '环境', dataIndex: 'environment', width: 90 },
          { title: '客户号', dataIndex: 'customerNo', width: 140 },
          { title: '证件号', dataIndex: 'certificateNo', width: 190 },
          { title: '卡号', dataIndex: 'cardNo', width: 190 },
          { title: '卡余额', dataIndex: 'balance', width: 110, render: (value) => `¥${Number(value).toFixed(2)}` },
          { title: '卡状态', dataIndex: 'status', width: 100, render: (value) => <Tag color={value === '正常' ? 'success' : 'warning'}>{value}</Tag> },
        ]}
      />
    </Card>
  );
}
