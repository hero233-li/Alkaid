export const PAGE_MULTI_OPEN_EVENT = 'alioth:page-multi-open-change';

const PAGE_MULTI_OPEN_KEY = 'alioth_page_multi_open_by_menu';

export type PageMultiOpenPreferences = Record<string, boolean>;

export interface PageMultiOpenDetail {
  menuKey: string;
  enabled: boolean;
  preferences: PageMultiOpenPreferences;
}

export function readPageMultiOpenPreferences(): PageMultiOpenPreferences {
  const stored = localStorage.getItem(PAGE_MULTI_OPEN_KEY);
  if (!stored) {
    return {};
  }

  try {
    const parsed = JSON.parse(stored);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function savePageMultiOpen(menuKey: string, enabled: boolean) {
  const preferences = {
    ...readPageMultiOpenPreferences(),
    [menuKey]: enabled,
  };
  localStorage.setItem(PAGE_MULTI_OPEN_KEY, JSON.stringify(preferences));
  window.dispatchEvent(
    new CustomEvent<PageMultiOpenDetail>(PAGE_MULTI_OPEN_EVENT, {
      detail: { menuKey, enabled, preferences },
    }),
  );
}
