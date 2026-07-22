import { useEffect, useMemo, useState } from 'react';
import { Button, Drawer, Layout, Menu, Tabs, Typography, message } from 'antd';
import { Menu as MenuIcon } from 'lucide-react';

import { getDeploymentCapabilities } from '../api/meta';
import { getHiddenMenuKeys } from '../api/portal';
import aliothLogo from '../assets/alioth-logo.svg';
import {
  DEFAULT_MENU_KEY,
  getVisibleMenuItems,
  getMenuClosable,
  getMenuLabel,
  renderMenuPage,
} from '../config/menuConfig';
import {
  MENU_VISIBILITY_CHANGED_EVENT,
  type MenuVisibilityChangedDetail,
} from '../config/menuVisibility';
import { useOpenTabs } from './appShell/useOpenTabs';

const { Sider, Content } = Layout;

export default function AppShell() {
  const [hiddenMenuKeys, setHiddenMenuKeys] = useState<string[]>([]);
  const [unavailableMenuKeys, setUnavailableMenuKeys] = useState<string[]>([]);
  const [menuReady, setMenuReady] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const {
    activeTabKey,
    openTabs,
    expandedMenuKeys,
    setExpandedMenuKeys,
    activateTab,
    openMenu,
    closeTab,
  } = useOpenTabs();
  const activeMenuKey =
    openTabs.find((tab) => tab.key === activeTabKey)?.menuKey || DEFAULT_MENU_KEY;
  const menuItems = useMemo(
    () => getVisibleMenuItems(hiddenMenuKeys, unavailableMenuKeys),
    [hiddenMenuKeys, unavailableMenuKeys],
  );
  const tabItems = openTabs.map((tab) => ({
    key: tab.key,
    label: getMenuLabel(tab.menuKey),
    closable: getMenuClosable(tab.menuKey),
    children: renderMenuPage(tab.menuKey, {
      onNavigate: (menuKey) => openMenu(menuKey, true),
      tabKey: tab.key,
      unavailableMenuKeys,
    }),
  }));

  useEffect(() => {
    Promise.all([getHiddenMenuKeys(), getDeploymentCapabilities()])
      .then(([hiddenKeys, capabilities]) => {
        setHiddenMenuKeys(hiddenKeys);
        setUnavailableMenuKeys(
          Object.entries(capabilities.features)
            .filter(([, capability]) => !capability.enabled)
            .map(([key]) => key),
        );
      })
      .catch((error) =>
        message.error(error instanceof Error ? error.message : '获取菜单显示设置失败'),
      )
      .finally(() => setMenuReady(true));
    const handleChange = (event: Event) => {
      setHiddenMenuKeys((event as CustomEvent<MenuVisibilityChangedDetail>).detail.hiddenMenuKeys);
    };
    window.addEventListener(MENU_VISIBILITY_CHANGED_EVENT, handleChange);
    return () => window.removeEventListener(MENU_VISIBILITY_CHANGED_EVENT, handleChange);
  }, []);

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" width={224}>
        <div className="brand">
          <img className="brand-logo" src={aliothLogo} alt="" aria-hidden="true" />
          <Typography.Text className="brand-title">Alioth</Typography.Text>
        </div>
        {menuReady && (
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[activeMenuKey]}
            openKeys={expandedMenuKeys}
            items={menuItems}
            onOpenChange={setExpandedMenuKeys}
            onClick={(event) => openMenu(event.key, true)}
          />
        )}
      </Sider>
      <Layout>
        <Content className="app-content">
          <Button
            className="mobile-menu-button"
            aria-label="打开导航菜单"
            disabled={!menuReady}
            icon={<MenuIcon size={18} />}
            onClick={() => setMobileMenuOpen(true)}
          >
            菜单
          </Button>
          <Tabs
            type="editable-card"
            hideAdd
            activeKey={activeTabKey}
            onChange={activateTab}
            onEdit={(targetKey, action) => {
              if (action === 'remove') closeTab(String(targetKey));
            }}
            items={tabItems}
          />
        </Content>
      </Layout>
      <Drawer
        className="mobile-menu-drawer"
        title="Alioth 导航"
        placement="left"
        width={280}
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      >
        {menuReady && (
          <Menu
            mode="inline"
            selectedKeys={[activeMenuKey]}
            openKeys={expandedMenuKeys}
            items={menuItems}
            onOpenChange={setExpandedMenuKeys}
            onClick={(event) => {
              openMenu(event.key, true);
              setMobileMenuOpen(false);
            }}
          />
        )}
      </Drawer>
    </Layout>
  );
}
