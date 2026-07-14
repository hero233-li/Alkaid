import { Button, Card, Space, Table } from 'antd';
import { Copy, Download, QrCode } from 'lucide-react';
import type { ApplicationDataRecord } from '../types';

const fields: (keyof ApplicationDataRecord)[] = [
  'environment', 'customerNo', 'customerName', 'certificateType', 'certificateNo',
  'cardNo', 'phone', 'tellerNo', 'companyName', 'companyCreditCode', 'organizationCode',
];
const labels = [
  '环境', '客户号', '客户名称', '客户证件类型', '客户证件号', '客户卡号', '客户手机号',
  '开卡柜员', '客户公司名称', '客户公司信用代码', '客户公司组织机构代码',
];

function download(records: ApplicationDataRecord[]) {
  const quote = (value: unknown) => `"${String(value ?? '').split('"').join('""')}"`;
  const csv = [labels, ...records.map((row) => fields.map((field) => row[field]))]
    .map((row) => row.map(quote).join(','))
    .join('\n');
  const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = '申请数据.csv';
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatRecord(record: ApplicationDataRecord) {
  return fields.map((field, index) => `${labels[index]}：${record[field] ?? ''}`).join('\n');
}

export default function ApplicationDataResultList({ records, onQr }: { records: ApplicationDataRecord[]; onQr: (value: string) => void }) {
  return <Card title="生成结果" extra={records.length ? <Button icon={<Download size={15} />} onClick={() => download(records)}>下载 CSV</Button> : null}>
    <Table rowKey="id" dataSource={records} pagination={false} scroll={{ x: 2100 }} columns={[
      ...fields.map((dataIndex, index) => ({ title: labels[index], dataIndex, width: dataIndex === 'companyName' ? 190 : 150 })),
      { title: '操作', fixed: 'right' as const, width: 180, render: (_: unknown, row: ApplicationDataRecord) => <Space><Button size="small" icon={<Copy size={14} />} onClick={() => void navigator.clipboard.writeText(formatRecord(row))}>复制</Button><Button size="small" icon={<QrCode size={14} />} onClick={() => onQr(formatRecord(row))}>二维码</Button></Space> },
    ]} />
  </Card>;
}
