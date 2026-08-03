import { DEFAULT_MENU_KEY, getMenuKeyByRoute, getMenuRoute } from '../../config/menuConfig';

export type RouteHistoryMode = 'push' | 'replace';

export function menuKeyFromLocation() {
  try {
    const route = decodeURIComponent(window.location.hash.replace(/^#/, '') || '/');
    return getMenuKeyByRoute(route) || DEFAULT_MENU_KEY;
  } catch {
    return DEFAULT_MENU_KEY;
  }
}

export function updateMenuRoute(menuKey: string, mode: RouteHistoryMode = 'push') {
  const nextHash = `#${getMenuRoute(menuKey)}`;
  if (window.location.hash === nextHash) return;
  const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
  const state = { ...window.history.state, menuKey };
  if (mode === 'replace') window.history.replaceState(state, '', nextUrl);
  else window.history.pushState(state, '', nextUrl);
}
