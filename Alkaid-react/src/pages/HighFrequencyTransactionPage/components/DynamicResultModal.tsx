import {useState} from 'react';
import {Button, Descriptions, Modal, Space, Table, Tag} from 'antd';
import type {DynamicQueryResult} from '../types';

const display = (value: unknown) => {
    if (value === null || value === undefined || value === '') return '-';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value)
};

export default function DynamicResultModal({result, onClose}: {
    result: DynamicQueryResult | null;
    onClose: () => void
}) {
    const [detailRow, setDetailRow] = useState<Record<string, unknown> | null>(null);
    const columns = result?.head.map(column => ({
        title: column.title,
        dataIndex: column.key,
        key: column.key,
        minWidth: 130,
        render: (value: unknown, row: Record<string, unknown>) => {
            const text = display(value);
            if (column.type === 'action') {
                return <Button type="link" onClick={() => setDetailRow(row)}>{column.actionLabel || text || '详情'}</Button>
            }
            if (column.type === 'tag') {
                return <Tag color={column.tagColors?.[text] || 'processing'}>{text}</Tag>
            }
            return text
        }
    })) ?? [];
    const data = result?.body.map((row, index) => ({...row, __rowKey: index})) ?? [];
    const title = result ? <Space><span>{result.title}</span><Tag color="blue">{result.functionCode} · {result.functionName}</Tag></Space> : '查询结果';
    const close = () => {
        setDetailRow(null);
        onClose()
    };
    return <>
        <Modal title={title} open={Boolean(result)} width="90vw" footer={null} onCancel={close} destroyOnClose>
            {result && <Table rowKey="__rowKey" bordered pagination={false} columns={columns} dataSource={data} scroll={{x: 'max-content'}}/>}
        </Modal>
        <Modal title="交易详情" open={Boolean(detailRow)} width={720} footer={null} onCancel={() => setDetailRow(null)} destroyOnClose>
            {result && detailRow && <Descriptions bordered column={1} size="small">
                {result.head.filter(column => column.type !== 'action').map(column => {
                    const text = display(detailRow[column.key]);
                    return <Descriptions.Item key={column.key} label={column.title}>
                        {column.type === 'tag' ? <Tag color={column.tagColors?.[text] || 'processing'}>{text}</Tag> : text}
                    </Descriptions.Item>
                })}
            </Descriptions>}
        </Modal>
    </>
}
