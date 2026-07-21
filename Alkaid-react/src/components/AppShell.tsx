import { Layout, Menu, Tabs, Typography } from 'antd';

import aliothLogo from '../assets/alioth-logo.svg';
import {
  DEFAULT_MENU_KEY,
  appMenuItems,
  getMenuClosable,
  getMenuLabel,
  renderMenuPage,
} from '../config/menuConfig';
import { useOpenTabs } from './appShell/useOpenTabs';

const { Sider, Content } = Layout;

export default function AppShell() {
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
  const tabItems = openTabs.map((tab) => ({
    key: tab.key,
    label: tab.instanceNo
      ? `${getMenuLabel(tab.menuKey)}-${tab.instanceNo}`
      : getMenuLabel(tab.menuKey),
    closable: getMenuClosable(tab.menuKey),
    children: renderMenuPage(tab.menuKey, {
      onNavigate: (menuKey) => openMenu(menuKey, true),
      tabKey: tab.key,
    }),
  }));

  return (
    <Layout className="app-shell">
      <Sider className="app-sider" width={224}>
        <div className="brand">
          <img className="brand-logo" src={aliothLogo} alt="" aria-hidden="true" />
          <Typography.Text className="brand-title">Alioth</Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[activeMenuKey]}
          openKeys={expandedMenuKeys}
          items={appMenuItems}
          onOpenChange={setExpandedMenuKeys}
          onClick={(event) => openMenu(event.key, true)}
        />
      </Sider>
      <Layout>
        <Content className="app-content">
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
    </Layout>
  );
}
