import { useEffect, useState } from 'react';
import { Switch, Tabs, Typography, message } from 'antd';
import {
  PAGE_MULTI_OPEN_EVENT,
  readPageMultiOpenPreferences,
  savePageMultiOpen,
  type PageMultiOpenDetail,
  type PageMultiOpenPreferences,
} from '../config/appPreferences';

interface ConfigurablePage {
  key: string;
  label: string;
  configurable: boolean;
}

interface SystemSettingsPageProps {
  pages: ConfigurablePage[];
}

export default function SystemSettingsPage({ pages }: SystemSettingsPageProps) {
  const [preferences, setPreferences] = useState<PageMultiOpenPreferences>(
    readPageMultiOpenPreferences,
  );

  useEffect(() => {
    const handleChange = (event: Event) => {
      setPreferences((event as CustomEvent<PageMultiOpenDetail>).detail.preferences);
    };

    window.addEventListener(PAGE_MULTI_OPEN_EVENT, handleChange);
    return () => window.removeEventListener(PAGE_MULTI_OPEN_EVENT, handleChange);
  }, []);

  const changePageMultiOpen = (page: ConfigurablePage, enabled: boolean) => {
    savePageMultiOpen(page.key, enabled);
    message.success(`${page.label}已切换为${enabled ? '多开' : '复用'}`);
  };

  const multiOpenPanel = (
    <section className="settings-panel compact">
      <div className="settings-table-head">
        <span>菜单</span>
        <span>是否多开</span>
      </div>
      {pages.map((page) => {
        const enabled = preferences[page.key] === true;
        return (
          <div className="settings-row compact" key={page.key}>
            <Typography.Text>{page.label}</Typography.Text>
            {page.configurable ? (
              <Switch
                checked={enabled}
                checkedChildren="多开"
                unCheckedChildren="复用"
                onChange={(checked) => changePageMultiOpen(page, checked)}
              />
            ) : (
              <Typography.Text type="secondary">固定单页</Typography.Text>
            )}
          </div>
        );
      })}
    </section>
  );

  return (
    <div className="page-surface">
      <div className="page-title-row">
        <div>
          <Typography.Title level={3}>系统设置</Typography.Title>
          <Typography.Text type="secondary">系统页面行为设置</Typography.Text>
        </div>
      </div>

      <Tabs
        className="settings-tabs"
        type="card"
        items={[{ key: 'page-multi-open', label: '页面多开管理', children: multiOpenPanel }]}
      />
    </div>
  );
}
