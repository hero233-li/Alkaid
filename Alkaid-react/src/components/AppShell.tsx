import { useEffect, useRef, useState } from 'react';
import { Layout, Menu, Tabs, Typography } from 'antd';
import aliothLogo from '../assets/alioth-logo.svg';
import {
  PAGE_MULTI_OPEN_EVENT,
  readPageMultiOpenPreferences,
  type PageMultiOpenDetail,
  type PageMultiOpenPreferences,
} from '../config/appPreferences';
import {
  DEFAULT_MENU_KEY,
  DEFAULT_OPEN_MENU_KEYS,
  appMenuItems,
  getMenuClosable,
  getMenuKeyByRoute,
  getMenuLabel,
  getMenuParentKey,
  getMenuRoute,
  isMenuLeaf,
  renderMenuPage,
} from '../config/menuConfig';

const { Sider, Content } = Layout;

interface OpenTab {
  key: string;
  menuKey: string;
  instanceNo?: number;
}

type RouteHistoryMode = 'push' | 'replace';

function menuKeyFromLocation() {
  try {
    const route = decodeURIComponent(window.location.hash.replace(/^#/, '') || '/');
    return getMenuKeyByRoute(route) || DEFAULT_MENU_KEY;
  } catch {
    return DEFAULT_MENU_KEY;
  }
}

function updateMenuRoute(menuKey: string, mode: RouteHistoryMode = 'push') {
  const nextHash = `#${getMenuRoute(menuKey)}`;
  if (window.location.hash === nextHash) {
    return;
  }
  const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
  const state = { ...window.history.state, menuKey };
  if (mode === 'replace') {
    window.history.replaceState(state, '', nextUrl);
  } else {
    window.history.pushState(state, '', nextUrl);
  }
}

function initialOpenTabs(menuKey: string): OpenTab[] {
  const homeTab = { key: DEFAULT_MENU_KEY, menuKey: DEFAULT_MENU_KEY };
  return menuKey === DEFAULT_MENU_KEY ? [homeTab] : [homeTab, { key: menuKey, menuKey }];
}

function matchingTabCacheKeys(tabKey: string) {
  const suffix = `:${tabKey}`;
  return Object.keys(sessionStorage).filter(
    (key) => key.startsWith('alioth:') && key.endsWith(suffix),
  );
}

function clearTabSessionCache(tabKey: string) {
  matchingTabCacheKeys(tabKey).forEach((key) => sessionStorage.removeItem(key));
}

function migrateTabSessionCache(fromTabKey: string, toTabKey: string) {
  matchingTabCacheKeys(fromTabKey).forEach((key) => {
    const nextKey = `${key.slice(0, -fromTabKey.length)}${toTabKey}`;
    const value = sessionStorage.getItem(key);
    if (value !== null) {
      sessionStorage.setItem(nextKey, value);
    }
    sessionStorage.removeItem(key);
  });
}

export default function AppShell() {
  const initialMenuKey = useRef(menuKeyFromLocation()).current;
  const tabSequence = useRef(0);
  const [activeTabKey, setActiveTabKey] = useState(initialMenuKey);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>(() => initialOpenTabs(initialMenuKey));
  const [expandedMenuKeys, setExpandedMenuKeys] = useState<string[]>(DEFAULT_OPEN_MENU_KEYS);
  const [pageMultiOpenPreferences, setPageMultiOpenPreferences] =
    useState<PageMultiOpenPreferences>(readPageMultiOpenPreferences);

  useEffect(() => {
    const handlePageMultiOpenChange = (event: Event) => {
      const detail = (event as CustomEvent<PageMultiOpenDetail>).detail;
      setPageMultiOpenPreferences(detail.preferences);

      if (detail.enabled) {
        return;
      }

      const targetTabs = openTabs.filter((tab) => tab.menuKey === detail.menuKey);
      if (!targetTabs.length) {
        return;
      }

      const activeTarget = targetTabs.find((tab) => tab.key === activeTabKey);
      const keepTarget = activeTarget || targetTabs[targetTabs.length - 1];
      const normalizedTarget: OpenTab = { key: detail.menuKey, menuKey: detail.menuKey };
      targetTabs.forEach((tab) => {
        if (tab.key === keepTarget.key) {
          migrateTabSessionCache(tab.key, detail.menuKey);
        } else {
          clearTabSessionCache(tab.key);
        }
      });
      setOpenTabs((tabs) => {
        let inserted = false;
        return tabs.reduce<OpenTab[]>((nextTabs, tab) => {
          if (tab.menuKey !== detail.menuKey) {
            nextTabs.push(tab);
          } else if (!inserted && tab.key === keepTarget.key) {
            nextTabs.push(normalizedTarget);
            inserted = true;
          }
          return nextTabs;
        }, []);
      });
      if (activeTarget) {
        setActiveTabKey(detail.menuKey);
      }
    };

    window.addEventListener(PAGE_MULTI_OPEN_EVENT, handlePageMultiOpenChange);
    return () => window.removeEventListener(PAGE_MULTI_OPEN_EVENT, handlePageMultiOpenChange);
  }, [activeTabKey, openTabs]);

  useEffect(() => {
    updateMenuRoute(initialMenuKey, 'replace');
  }, [initialMenuKey]);

  const activeMenuKey =
    openTabs.find((tab) => tab.key === activeTabKey)?.menuKey || DEFAULT_MENU_KEY;

  const tabItems = openTabs.map((tab) => {
    return {
      key: tab.key,
      label: tab.instanceNo
        ? `${getMenuLabel(tab.menuKey)}-${tab.instanceNo}`
        : getMenuLabel(tab.menuKey),
      closable: getMenuClosable(tab.menuKey),
      children: renderMenuPage(tab.menuKey, { onNavigate: selectMenu, tabKey: tab.key }),
    };
  });

  const activateTab = (
    tabKey: string,
    menuKey?: string,
    historyMode: RouteHistoryMode = 'push',
  ) => {
    const targetMenuKey =
      menuKey || openTabs.find((tab) => tab.key === tabKey)?.menuKey || DEFAULT_MENU_KEY;
    setActiveTabKey(tabKey);
    updateMenuRoute(targetMenuKey, historyMode);
    const parentKey = getMenuParentKey(targetMenuKey);
    if (parentKey) {
      setExpandedMenuKeys((keys) => (keys.includes(parentKey) ? keys : [...keys, parentKey]));
    }
  };

  function openMenu(
    menuKey: string,
    allowNewInstance: boolean,
    historyMode: RouteHistoryMode = 'push',
  ) {
    if (!isMenuLeaf(menuKey)) {
      return;
    }

    if (allowNewInstance && pageMultiOpenPreferences[menuKey] && getMenuClosable(menuKey)) {
      const menuTabs = openTabs.filter((tab) => tab.menuKey === menuKey);
      const maxInstanceNo = menuTabs.reduce((max, tab) => Math.max(max, tab.instanceNo || 0), 0);
      const normalizedTabs =
        menuTabs.length > 0 && maxInstanceNo === 0
          ? openTabs.map((tab) => (tab.menuKey === menuKey ? { ...tab, instanceNo: 1 } : tab))
          : openTabs;
      const instanceNo = (maxInstanceNo || menuTabs.length) + 1;
      tabSequence.current += 1;
      const nextTab: OpenTab = {
        key: `${menuKey}::${Date.now()}::${tabSequence.current}`,
        menuKey,
        instanceNo,
      };
      setOpenTabs([...normalizedTabs, nextTab]);
      activateTab(nextTab.key, menuKey, historyMode);
      return;
    }

    const existingTab = [...openTabs].reverse().find((tab) => tab.menuKey === menuKey);
    if (existingTab) {
      activateTab(existingTab.key, menuKey, historyMode);
      return;
    }

    const nextTab: OpenTab = { key: menuKey, menuKey };
    setOpenTabs((tabs) => [...tabs, nextTab]);
    activateTab(nextTab.key, menuKey, historyMode);
  }

  function selectMenu(menuKey: string) {
    openMenu(menuKey, true);
  }

  const closeTab = (targetTabKey: string) => {
    const targetTab = openTabs.find((tab) => tab.key === targetTabKey);
    if (!targetTab || !getMenuClosable(targetTab.menuKey)) {
      return;
    }

    clearTabSessionCache(targetTabKey);
    const nextTabs = openTabs.filter((tab) => tab.key !== targetTabKey);
    setOpenTabs(nextTabs);
    if (activeTabKey === targetTabKey) {
      const nextTab = nextTabs[nextTabs.length - 1] || {
        key: DEFAULT_MENU_KEY,
        menuKey: DEFAULT_MENU_KEY,
      };
      activateTab(nextTab.key, nextTab.menuKey);
    }
  };

  useEffect(() => {
    const handleRouteChange = () => {
      openMenu(menuKeyFromLocation(), false, 'replace');
    };
    window.addEventListener('popstate', handleRouteChange);
    window.addEventListener('hashchange', handleRouteChange);
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
      window.removeEventListener('hashchange', handleRouteChange);
    };
  }, [openTabs, pageMultiOpenPreferences]);

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
          onOpenChange={(keys) => setExpandedMenuKeys(keys)}
          onClick={(event) => selectMenu(event.key)}
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
              if (action === 'remove') {
                closeTab(String(targetKey));
              }
            }}
            items={tabItems}
          />
        </Content>
      </Layout>
    </Layout>
  );
}
