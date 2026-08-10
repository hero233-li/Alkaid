import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Button, Spin, Switch, Tabs, Typography, message } from 'antd';
import { Save } from 'lucide-react';
import {
  getAutoExpandedMenuKeys,
  getHiddenMenuKeys,
  getHomeShortcutKeys,
  saveAutoExpandedMenuKeys,
  saveHiddenMenuKeys,
  saveHomeShortcutKeys,
} from '../api/portal';
import { emitMenuVisibilityChanged } from '../config/menuVisibility';
import ReleaseManagementPage from './ReleaseManagementPage';
import { PORTAL_CONTENT_CHANGED_EVENT } from './WelcomePage';

interface ConfigurablePage {
  key: string;
  label: string;
  icon?: ReactNode;
  configurable: boolean;
  homeShortcutConfigurable: boolean;
}

interface ExpandableMenu {
  key: string;
  label: string;
  icon?: ReactNode;
}

interface SystemSettingsPageProps {
  pages: ConfigurablePage[];
  expandableMenus: ExpandableMenu[];
}

export default function SystemSettingsPage({ pages, expandableMenus }: SystemSettingsPageProps) {
  const [messageApi, messageContextHolder] = message.useMessage();
  const [hiddenMenuKeys, setHiddenMenuKeys] = useState<string[]>([]);
  const [homeShortcutKeys, setHomeShortcutKeys] = useState<string[]>([]);
  const [autoExpandedMenuKeys, setAutoExpandedMenuKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingAutoExpand, setSavingAutoExpand] = useState(false);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const [hiddenKeys, shortcutKeys, expandedKeys] = await Promise.all([
        getHiddenMenuKeys(),
        getHomeShortcutKeys(),
        getAutoExpandedMenuKeys(),
      ]);
      setHiddenMenuKeys(hiddenKeys);
      setHomeShortcutKeys(shortcutKeys);
      setAutoExpandedMenuKeys(expandedKeys);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '获取系统设置失败');
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const changeMenuVisibility = (page: ConfigurablePage, visible: boolean) => {
    setHiddenMenuKeys((keys) =>
      visible ? keys.filter((key) => key !== page.key) : [...new Set([...keys, page.key])],
    );
  };

  const changeHomeShortcut = (page: ConfigurablePage, enabled: boolean) => {
    setHomeShortcutKeys((keys) =>
      enabled ? [...new Set([...keys, page.key])] : keys.filter((key) => key !== page.key),
    );
  };

  const changeAutoExpand = (menu: ExpandableMenu, enabled: boolean) => {
    setAutoExpandedMenuKeys((keys) =>
      enabled ? [...new Set([...keys, menu.key])] : keys.filter((key) => key !== menu.key),
    );
  };

  const saveMenuAndHome = async () => {
    setSaving(true);
    try {
      const orderedShortcutKeys = pages
        .filter((page) => page.homeShortcutConfigurable && homeShortcutKeys.includes(page.key))
        .map((page) => page.key);
      const [savedHiddenKeys, savedShortcutKeys] = await Promise.all([
        saveHiddenMenuKeys(hiddenMenuKeys),
        saveHomeShortcutKeys(orderedShortcutKeys),
      ]);
      setHiddenMenuKeys(savedHiddenKeys);
      setHomeShortcutKeys(savedShortcutKeys);
      emitMenuVisibilityChanged(savedHiddenKeys);
      window.dispatchEvent(new Event(PORTAL_CONTENT_CHANGED_EVENT));
      messageApi.success('菜单与首页入口设置已更新');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '保存菜单与首页入口设置失败');
    } finally {
      setSaving(false);
    }
  };

  const saveAutoExpand = async () => {
    setSavingAutoExpand(true);
    try {
      const orderedKeys = expandableMenus
        .filter((menu) => autoExpandedMenuKeys.includes(menu.key))
        .map((menu) => menu.key);
      const savedKeys = await saveAutoExpandedMenuKeys(orderedKeys);
      setAutoExpandedMenuKeys(savedKeys);
      messageApi.success('自动展开设置已保存，将在下次刷新或重新打开页面时生效');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '保存自动展开设置失败');
    } finally {
      setSavingAutoExpand(false);
    }
  };

  const menuAndHomePanel = (
    <div className="settings-embedded-page">
      <div className="page-title-row">
        <div>
          <Typography.Title level={5}>菜单与首页入口</Typography.Title>
          <Typography.Text type="secondary">
            在一个页面中控制左侧导航和首页“快速入口”的显示
          </Typography.Text>
        </div>
        <Button
          type="primary"
          loading={saving}
          icon={<Save size={16} />}
          onClick={() => void saveMenuAndHome()}
        >
          保存
        </Button>
      </div>

      <Spin spinning={loading}>
        <section className="shortcut-manage-list combined-settings-list">
          <div className="combined-settings-header" aria-hidden="true">
            <span />
            <span>页面</span>
            <span>侧边栏显示</span>
            <span>首页快速入口</span>
          </div>
          {pages.map((page) => {
            const visible = !hiddenMenuKeys.includes(page.key);
            return (
              <div className="shortcut-manage-row combined-settings-row" key={page.key}>
                <span className="shortcut-manage-icon">{page.icon}</span>
                <Typography.Text>{page.label}</Typography.Text>
                <span className="combined-settings-control" data-label="侧边栏显示">
                  {page.configurable ? (
                    <Switch
                      aria-label={`${page.label}侧边栏显示`}
                      checked={visible}
                      onChange={(checked) => changeMenuVisibility(page, checked)}
                    />
                  ) : (
                    <Typography.Text type="secondary">固定显示</Typography.Text>
                  )}
                </span>
                <span className="combined-settings-control" data-label="首页快速入口">
                  {page.homeShortcutConfigurable ? (
                    <Switch
                      aria-label={`${page.label}首页快速入口`}
                      checked={homeShortcutKeys.includes(page.key)}
                      onChange={(checked) => changeHomeShortcut(page, checked)}
                    />
                  ) : (
                    <Typography.Text type="secondary">不支持</Typography.Text>
                  )}
                </span>
              </div>
            );
          })}
        </section>
      </Spin>
    </div>
  );

  const autoExpandPanel = (
    <div className="settings-embedded-page">
      <div className="page-title-row">
        <div>
          <Typography.Title level={5}>菜单自动展开</Typography.Title>
          <Typography.Text type="secondary">
            控制首次打开或刷新页面时自动展开的一级菜单；之后仍可手动展开或收起
          </Typography.Text>
        </div>
        <Button
          type="primary"
          loading={savingAutoExpand}
          icon={<Save size={16} />}
          onClick={() => void saveAutoExpand()}
        >
          保存
        </Button>
      </div>

      <Spin spinning={loading}>
        <section className="shortcut-manage-list auto-expand-settings-list">
          <div className="auto-expand-settings-header" aria-hidden="true">
            <span />
            <span>一级菜单</span>
            <span>自动展开</span>
          </div>
          {expandableMenus.map((menu) => (
            <div className="shortcut-manage-row auto-expand-settings-row" key={menu.key}>
              <span className="shortcut-manage-icon">{menu.icon}</span>
              <Typography.Text>{menu.label}</Typography.Text>
              <span className="auto-expand-settings-control" data-label="自动展开">
                <Switch
                  aria-label={`${menu.label}自动展开`}
                  checked={autoExpandedMenuKeys.includes(menu.key)}
                  onChange={(checked) => changeAutoExpand(menu, checked)}
                />
              </span>
            </div>
          ))}
        </section>
      </Spin>
    </div>
  );

  return (
    <div className="page-surface">
      {messageContextHolder}
      <div className="page-title-row">
        <div>
          <Typography.Title level={3}>系统设置</Typography.Title>
          <Typography.Text type="secondary">
            集中管理菜单、首页入口、自动展开和版本信息
          </Typography.Text>
        </div>
      </div>

      <Tabs
        className="settings-tabs"
        size="small"
        type="card"
        items={[
          { key: 'menu-and-home', label: '菜单与首页入口', children: menuAndHomePanel },
          { key: 'auto-expand', label: '自动展开', children: autoExpandPanel },
          {
            key: 'releases',
            label: '版本管理',
            children: <ReleaseManagementPage embedded />,
          },
        ]}
      />
    </div>
  );
}
