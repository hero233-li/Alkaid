function matchingTabCacheKeys(tabKey: string) {
  const suffix = `:${tabKey}`;
  return Object.keys(sessionStorage).filter(
    (key) => key.startsWith('alioth:') && key.endsWith(suffix),
  );
}

export function clearTabSessionCache(tabKey: string) {
  matchingTabCacheKeys(tabKey).forEach((key) => sessionStorage.removeItem(key));
}

export function migrateTabSessionCache(fromTabKey: string, toTabKey: string) {
  matchingTabCacheKeys(fromTabKey).forEach((key) => {
    const nextKey = `${key.slice(0, -fromTabKey.length)}${toTabKey}`;
    const value = sessionStorage.getItem(key);
    if (value !== null) sessionStorage.setItem(nextKey, value);
    sessionStorage.removeItem(key);
  });
}
