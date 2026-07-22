import { describe, expect, it } from 'vitest';
import { getVisibleMenuItems } from './menuConfig';

interface MenuItemShape {
  key?: string | number;
  children?: MenuItemShape[];
}

function flattenKeys(items: MenuItemShape[] = []): Array<string | number> {
  return items.flatMap((item) => [
    ...(item.key === undefined ? [] : [item.key]),
    ...flattenKeys(item.children),
  ]);
}

describe('getVisibleMenuItems', () => {
  it('removes hidden leaves while keeping protected settings available', () => {
    const keys = flattenKeys(
      getVisibleMenuItems(['product-application', 'workbench']) as MenuItemShape[],
    );

    expect(keys).not.toContain('product-application');
    expect(keys).not.toContain('workbench');
    expect(keys).toContain('settings');
    expect(keys).toContain('home');
    expect(keys).not.toContain('release-management');
    expect(keys).not.toContain('home-shortcut-management');
  });

  it('removes capabilities that are unavailable in the current deployment', () => {
    const keys = flattenKeys(
      getVisibleMenuItems([], ['workflow-learning', 'card-status-processing']) as MenuItemShape[],
    );

    expect(keys).not.toContain('workflow-learning');
    expect(keys).not.toContain('card-status-processing');
    expect(keys).toContain('jobs');
    expect(keys).toContain('settings');
  });
});
