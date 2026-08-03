import { Button, Space, type TableProps } from 'antd';
import { History, Send } from 'lucide-react';
import { ActionTable, DetailOverlay } from '../../../components/common';
import type {
  BusinessAccessNotification,
  BusinessAccessRecord,
  NotificationVersionType,
} from '../types';

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

interface NotificationPushOverlayProps {
  record: BusinessAccessRecord | null;
  notifications: BusinessAccessNotification[];
  loading: boolean;
  busy: boolean;
  pushingKey: string | null;
  onClose: () => void;
  onPush: (notification: BusinessAccessNotification, versionType: NotificationVersionType) => void;
}

export default function NotificationPushOverlay({
  record,
  notifications,
  loading,
  busy,
  pushingKey,
  onClose,
  onPush,
}: NotificationPushOverlayProps) {
  const columns: NonNullable<TableProps<BusinessAccessNotification>['columns']> = [
    { title: '通知编号', dataIndex: 'notificationNo', width: 150 },
    { title: '通知类型', dataIndex: 'notificationType', width: 150 },
    { title: '目标系统', dataIndex: 'targetSystem', width: 120 },
    { title: '新版本', dataIndex: 'latestVersion', width: 100 },
    { title: '旧版本', dataIndex: 'previousVersion', width: 100 },
    { title: '更新时间', dataIndex: 'updatedAt', width: 180, render: formatDate },
  ];

  return (
    <DetailOverlay
      presentation="modal"
      title={record ? `通知推送 - ${record.businessNo}` : '通知推送'}
      width={1080}
      open={Boolean(record)}
      onClose={onClose}
      modalProps={{ closable: !busy, keyboard: !busy, maskClosable: !busy }}
    >
      <ActionTable<BusinessAccessNotification>
        contained={false}
        rowKey="id"
        dataSource={notifications}
        columns={columns}
        actionColumn={{ width: 190, fixed: 'right' }}
        renderActions={(notification) => (
          <Space size={6}>
            <Button
              size="small"
              type="primary"
              icon={<Send size={14} />}
              loading={pushingKey === `${notification.id}:latest`}
              disabled={busy}
              onClick={() => onPush(notification, 'latest')}
            >
              推送新
            </Button>
            <Button
              size="small"
              icon={<History size={14} />}
              loading={pushingKey === `${notification.id}:previous`}
              disabled={busy}
              onClick={() => onPush(notification, 'previous')}
            >
              推送旧
            </Button>
          </Space>
        )}
        tableProps={{
          loading,
          pagination: false,
          locale: {
            emptyText: loading ? 'Workflow 正在加载通知记录...' : '暂无通知记录',
          },
          scroll: { x: 990 },
          size: 'small',
        }}
      />
    </DetailOverlay>
  );
}
