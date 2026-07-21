import { Button, Card, message, Space, Table, Typography } from 'antd';
import { Copy, QrCode } from 'lucide-react';
import type { ApplicationLinkResult } from '../model/types';

interface ApplicationLinkResultRow {
  key: 'internal' | 'external';
  type: string;
  url: string;
}

async function copyLink(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // 非 HTTPS 或非 localhost 的页面无法使用 Clipboard API，继续使用兼容方案。
    }
  }

  const textArea = document.createElement('textarea');
  textArea.value = value;
  textArea.setAttribute('readonly', '');
  textArea.style.position = 'fixed';
  textArea.style.top = '0';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.select();
  textArea.setSelectionRange(0, textArea.value.length);

  try {
    if (!document.execCommand('copy')) {
      throw new Error('浏览器不支持复制');
    }
  } finally {
    document.body.removeChild(textArea);
  }
}

export default function ApplicationLinkResultList({
  result,
  onQr,
}: {
  result: ApplicationLinkResult | null;
  onQr: (value: string) => void;
}) {
  const handleCopy = async (url: string) => {
    try {
      await copyLink(url);
      message.success('链接已复制');
    } catch {
      message.error('复制失败，请手动复制链接');
    }
  };

  const rows: ApplicationLinkResultRow[] = result
    ? [
        { key: 'internal', type: '内网链接', url: result.internalUrl },
        { key: 'external', type: '外网链接', url: result.externalUrl },
      ]
    : [];

  return (
    <Card title="生成结果">
      <Table<ApplicationLinkResultRow>
        rowKey="key"
        dataSource={rows}
        pagination={false}
        columns={[
          { title: '链接类型', dataIndex: 'type', width: 120 },
          {
            title: '链接地址',
            dataIndex: 'url',
            render: (value: string, record) => (
              <Typography.Text
                className={`application-link-value application-link-value--${record.key}`}
              >
                {value}
              </Typography.Text>
            ),
          },
          {
            title: '操作',
            width: 230,
            render: (_, record) => (
              <Space>
                <Button icon={<Copy size={15} />} onClick={() => void handleCopy(record.url)}>
                  复制
                </Button>
                {record.key === 'external' && (
                  <Button icon={<QrCode size={15} />} onClick={() => onQr(record.url)}>
                    申请二维码
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}
