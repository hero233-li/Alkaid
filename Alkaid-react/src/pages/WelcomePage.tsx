import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Button, Card, Empty, List, Modal, Spin, Typography } from 'antd';
import { ArrowRight, History, Rocket } from 'lucide-react';
import { getHomeShortcutKeys, listReleaseNotes } from '../api/portal';
import type { ReleaseNote } from '../types';

export const PORTAL_CONTENT_CHANGED_EVENT = 'alioth:portal-content-changed';

export interface HomeShortcutOption {
  key: string;
  label: string;
  icon?: ReactNode;
}

interface WelcomePageProps {
  shortcuts: HomeShortcutOption[];
  onNavigate: (menuKey: string) => void;
}

function formatDate(value: string) {
  if (!value) {
    return '';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export default function WelcomePage({ shortcuts, onNavigate }: WelcomePageProps) {
  const [releaseNotes, setReleaseNotes] = useState<ReleaseNote[]>([]);
  const [shortcutKeys, setShortcutKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);

  const loadPortalContent = useCallback(async () => {
    setLoading(true);
    try {
      const [notes, keys] = await Promise.all([listReleaseNotes(), getHomeShortcutKeys()]);
      setReleaseNotes(notes);
      setShortcutKeys(keys);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPortalContent().catch(() => undefined);
    window.addEventListener(PORTAL_CONTENT_CHANGED_EVENT, loadPortalContent);
    return () => window.removeEventListener(PORTAL_CONTENT_CHANGED_EVENT, loadPortalContent);
  }, [loadPortalContent]);

  const latestRelease = releaseNotes[0];
  const enabledShortcuts = shortcutKeys
    .map((key) => shortcuts.find((shortcut) => shortcut.key === key))
    .filter((shortcut): shortcut is HomeShortcutOption => Boolean(shortcut));

  return (
    <div className="page-surface welcome-page">
      <Spin spinning={loading}>
        <div className="welcome-grid">
          <Card
            className="welcome-card release-card"
            title={
              <span className="welcome-card-title">
                <Rocket size={18} />
                版本更新
              </span>
            }
            extra={
              <Button type="link" icon={<History size={16} />} onClick={() => setHistoryOpen(true)}>
                历史版本
              </Button>
            }
          >
            {latestRelease ? (
              <button className="latest-release" type="button" onClick={() => setHistoryOpen(true)}>
                <div className="latest-release-heading">
                  <Typography.Title level={4}>{latestRelease.version}</Typography.Title>
                  <Typography.Text type="secondary">{formatDate(latestRelease.createdAt)}</Typography.Text>
                </div>
                <Typography.Paragraph ellipsis={{ rows: 4 }}>{latestRelease.content}</Typography.Paragraph>
                <span className="latest-release-more">
                  查看全部历史版本 <ArrowRight size={15} />
                </span>
              </button>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无版本记录" />
            )}
          </Card>

          <Card
            className="welcome-card shortcuts-card"
            title={
              <span className="welcome-card-title">
                <ArrowRight size={18} />
                快速入口
              </span>
            }
          >
            {enabledShortcuts.length ? (
              <div className="shortcut-grid">
                {enabledShortcuts.map((shortcut) => (
                  <button key={shortcut.key} type="button" className="shortcut-item" onClick={() => onNavigate(shortcut.key)}>
                    <span className="shortcut-icon">{shortcut.icon}</span>
                    <span>{shortcut.label}</span>
                    <ArrowRight className="shortcut-arrow" size={16} />
                  </button>
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请在系统管理中配置首页入口" />
            )}
          </Card>
        </div>
      </Spin>

      <Modal title="历史版本" open={historyOpen} onCancel={() => setHistoryOpen(false)} footer={null} width={720}>
        <List
          className="release-history-list"
          dataSource={releaseNotes}
          locale={{ emptyText: '暂无版本记录' }}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <div className="release-history-title">
                    <Typography.Text strong>{item.version}</Typography.Text>
                    <Typography.Text type="secondary">{formatDate(item.createdAt)}</Typography.Text>
                  </div>
                }
                description={<Typography.Paragraph className="release-history-content">{item.content}</Typography.Paragraph>}
              />
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
}
