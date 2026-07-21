import { useCallback, useEffect, useRef, useState } from 'react';

import {
  PAGE_MULTI_OPEN_EVENT,
  readPageMultiOpenPreferences,
  type PageMultiOpenDetail,
  type PageMultiOpenPreferences,
} from '../../config/appPreferences';
import {
  DEFAULT_MENU_KEY,
  DEFAULT_OPEN_MENU_KEYS,
  getMenuClosable,
  getMenuParentKey,
  isMenuLeaf,
} from '../../config/menuConfig';
import { clearTabSessionCache, migrateTabSessionCache } from './tabSessionCache';
import { menuKeyFromLocation, updateMenuRoute, type RouteHistoryMode } from './tabRoute';

export interface OpenTab {
  key: string;
  menuKey: string;
  instanceNo?: number;
}

function initialOpenTabs(menuKey: string): OpenTab[] {
  const homeTab = { key: DEFAULT_MENU_KEY, menuKey: DEFAULT_MENU_KEY };
  return menuKey === DEFAULT_MENU_KEY ? [homeTab] : [homeTab, { key: menuKey, menuKey }];
}

export function useOpenTabs() {
  const [initialMenuKey] = useState(menuKeyFromLocation);
  const tabSequence = useRef(0);
  const [activeTabKey, setActiveTabKey] = useState(initialMenuKey);
  const [openTabs, setOpenTabs] = useState<OpenTab[]>(() => initialOpenTabs(initialMenuKey));
  const [expandedMenuKeys, setExpandedMenuKeys] = useState<string[]>(DEFAULT_OPEN_MENU_KEYS);
  const [pageMultiOpenPreferences, setPageMultiOpenPreferences] =
    useState<PageMultiOpenPreferences>(readPageMultiOpenPreferences);

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
    (menuKey: string, allowNewInstance: boolean, historyMode: RouteHistoryMode = 'push') => {
      if (!isMenuLeaf(menuKey)) return;
      if (allowNewInstance && pageMultiOpenPreferences[menuKey] && getMenuClosable(menuKey)) {
        const menuTabs = openTabs.filter((tab) => tab.menuKey === menuKey);
        const maxInstanceNo = menuTabs.reduce((max, tab) => Math.max(max, tab.instanceNo || 0), 0);
        const normalizedTabs =
          menuTabs.length > 0 && maxInstanceNo === 0
            ? openTabs.map((tab) => (tab.menuKey === menuKey ? { ...tab, instanceNo: 1 } : tab))
            : openTabs;
        tabSequence.current += 1;
        const nextTab: OpenTab = {
          key: `${menuKey}::${Date.now()}::${tabSequence.current}`,
          menuKey,
          instanceNo: (maxInstanceNo || menuTabs.length) + 1,
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
    },
    [activateTab, openTabs, pageMultiOpenPreferences],
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

  useEffect(() => {
    const handlePreferenceChange = (event: Event) => {
      const detail = (event as CustomEvent<PageMultiOpenDetail>).detail;
      setPageMultiOpenPreferences(detail.preferences);
      if (detail.enabled) return;
      const targetTabs = openTabs.filter((tab) => tab.menuKey === detail.menuKey);
      if (!targetTabs.length) return;
      const activeTarget = targetTabs.find((tab) => tab.key === activeTabKey);
      const keepTarget = activeTarget || targetTabs[targetTabs.length - 1];
      targetTabs.forEach((tab) => {
        if (tab.key === keepTarget.key) migrateTabSessionCache(tab.key, detail.menuKey);
        else clearTabSessionCache(tab.key);
      });
      setOpenTabs((tabs) => {
        let inserted = false;
        return tabs.reduce<OpenTab[]>((nextTabs, tab) => {
          if (tab.menuKey !== detail.menuKey) nextTabs.push(tab);
          else if (!inserted && tab.key === keepTarget.key) {
            nextTabs.push({ key: detail.menuKey, menuKey: detail.menuKey });
            inserted = true;
          }
          return nextTabs;
        }, []);
      });
      if (activeTarget) setActiveTabKey(detail.menuKey);
    };
    window.addEventListener(PAGE_MULTI_OPEN_EVENT, handlePreferenceChange);
    return () => window.removeEventListener(PAGE_MULTI_OPEN_EVENT, handlePreferenceChange);
  }, [activeTabKey, openTabs]);

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
