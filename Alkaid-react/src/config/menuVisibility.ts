export const MENU_VISIBILITY_CHANGED_EVENT = 'alioth:menu-visibility-changed';

export interface MenuVisibilityChangedDetail {
  hiddenMenuKeys: string[];
}

export function emitMenuVisibilityChanged(hiddenMenuKeys: string[]) {
  window.dispatchEvent(
    new CustomEvent<MenuVisibilityChangedDetail>(MENU_VISIBILITY_CHANGED_EVENT, {
      detail: { hiddenMenuKeys },
    }),
  );
}
