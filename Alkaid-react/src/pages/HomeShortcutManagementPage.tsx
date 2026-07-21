import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Button, Switch, Typography, message } from 'antd';
import { Save } from 'lucide-react';
import { getHomeShortcutKeys, saveHomeShortcutKeys } from '../api/portal';
import { PORTAL_CONTENT_CHANGED_EVENT } from './WelcomePage';

export interface ShortcutManageOption {
  key: string;
  label: string;
  icon?: ReactNode;
}

interface HomeShortcutManagementPageProps {
  pages: ShortcutManageOption[];
}

export default function HomeShortcutManagementPage({ pages }: HomeShortcutManagementPageProps) {
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      setSelectedKeys(await getHomeShortcutKeys());
    } catch (error) {
      message.error(error instanceof Error ? error.message : '获取首页入口失败');
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const togglePage = (key: string, enabled: boolean) => {
    setSelectedKeys((keys) => (enabled ? [...keys, key] : keys.filter((item) => item !== key)));
  };

  const save = async () => {
    setLoading(true);
    try {
      const orderedKeys = pages
        .filter((page) => selectedKeys.includes(page.key))
        .map((page) => page.key);
      setSelectedKeys(await saveHomeShortcutKeys(orderedKeys));
      window.dispatchEvent(new Event(PORTAL_CONTENT_CHANGED_EVENT));
      message.success('首页快速入口已更新');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存首页入口失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-surface">
      <div className="page-title-row">
        <div>
          <Typography.Title level={3}>首页入口管理</Typography.Title>
          <Typography.Text type="secondary">选择需要显示在首页“快速入口”中的页面</Typography.Text>
        </div>
        <Button type="primary" loading={loading} icon={<Save size={16} />} onClick={save}>
          保存
        </Button>
      </div>

      <section className="shortcut-manage-list">
        {pages.map((page) => (
          <div className="shortcut-manage-row" key={page.key}>
            <span className="shortcut-manage-icon">{page.icon}</span>
            <Typography.Text>{page.label}</Typography.Text>
            <Switch
              checked={selectedKeys.includes(page.key)}
              onChange={(checked) => togglePage(page.key, checked)}
            />
          </div>
        ))}
      </section>
    </div>
  );
}
