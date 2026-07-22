import { useCallback, useEffect, useState } from 'react';
import {
  DEFAULT_MENU_KEY,
  DEFAULT_OPEN_MENU_KEYS,
  getMenuClosable,
  getMenuParentKey,
  isMenuLeaf,
} from '../../config/menuConfig';
import { clearTabSessionCache } from './tabSessionCache';
import { menuKeyFromLocation, updateMenuRoute, type RouteHistoryMode } from './tabRoute';

export interface OpenTab {
  key: string;
  menuKey: string;
}

function initialOpenTabs(menuKey: string): OpenTab[] {
  const homeTab = { key: DEFAULT_MENU_KEY, menuKey: DEFAULT_MENU_KEY };
  return menuKey === DEFAULT_MENU_KEY ? [homeTab] : [homeTab, { key: menuKey, menuKey }];
}

export function useOpenTabs() {
  const [initialMenuKey] = useState(menuKeyFromLocation);
  const [activeTabKey, setActiveTabKey] = useState(initialMenuKey);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>(() => initialOpenTabs(initialMenuKey));
  const [expandedMenuKeys, setExpandedMenuKeys] = useState<string[]>(DEFAULT_OPEN_MENU_KEYS);

  const activateTab = useCallback(
    (tabKey: string, menuKey?: string, historyMode: RouteHistoryMode = 'push') => {
      const targetMenuKey =
        menuKey || openTabs.find((tab) => tab.key === tabKey)?.menuKey || DEFAULT_MENU_KEY;
      setActiveTabKey(tabKey);
      updateMenuRoute(targetMenuKey, historyMode);
      const parentKey = getMenuParentKey(targetMenuKey);
      if (parentKey) {
        setExpandedMenuKeys((keys) => (keys.includes(parentKey) ? keys : [...keys, parentKey]));
      }
    },
    [openTabs],
  );

  const openMenu = useCallback(
    (menuKey: string, _allowNewInstance: boolean, historyMode: RouteHistoryMode = 'push') => {
      if (!isMenuLeaf(menuKey)) return;
      const existingTab = [...openTabs].reverse().find((tab) => tab.menuKey === menuKey);
      if (existingTab) {
        activateTab(existingTab.key, menuKey, historyMode);
        return;
      }
      const nextTab: OpenTab = { key: menuKey, menuKey };
      setOpenTabs((tabs) => [...tabs, nextTab]);
      activateTab(nextTab.key, menuKey, historyMode);
    },
    [activateTab, openTabs],
  );

  const closeTab = useCallback(
    (targetTabKey: string) => {
      const targetTab = openTabs.find((tab) => tab.key === targetTabKey);
      if (!targetTab || !getMenuClosable(targetTab.menuKey)) return;
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
    },
    [activateTab, activeTabKey, openTabs],
  );

  useEffect(() => {
    updateMenuRoute(initialMenuKey, 'replace');
  }, [initialMenuKey]);

  useEffect(() => {
    const handleRouteChange = () => openMenu(menuKeyFromLocation(), false, 'replace');
    window.addEventListener('popstate', handleRouteChange);
    window.addEventListener('hashchange', handleRouteChange);
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
      window.removeEventListener('hashchange', handleRouteChange);
    };
  }, [openMenu]);

  return {
    activeTabKey,
    openTabs,
    expandedMenuKeys,
    setExpandedMenuKeys,
    activateTab,
    openMenu,
    closeTab,
  };
}
