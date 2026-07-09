import { useCallback, useEffect, useState } from 'react';
import { getProductApplicationConfigDto } from '../api/productApplicationApi';
import { adaptProductApplicationConfig } from '../model/configAdapter';
import type { ProductApplicationConfig } from '../model/types';

const CONFIG_CACHE_TTL_MS = 60_000;
let cachedConfig: ProductApplicationConfig | null = null;
let cachedAt = 0;
let pendingRequest: Promise<ProductApplicationConfig> | null = null;

function loadProductConfig(force: boolean) {
  if (!force && cachedConfig && Date.now() - cachedAt < CONFIG_CACHE_TTL_MS) {
    return Promise.resolve(cachedConfig);
  }
  if (!force && pendingRequest) {
    return pendingRequest;
  }
  pendingRequest = getProductApplicationConfigDto()
    .then(adaptProductApplicationConfig)
    .then((config) => {
      cachedConfig = config;
      cachedAt = Date.now();
      return config;
    })
    .finally(() => {
      pendingRequest = null;
    });
  return pendingRequest;
}

export function useProductConfig() {
  const [config, setConfig] = useState<ProductApplicationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [requestVersion, setRequestVersion] = useState(0);

  const retry = useCallback(() => setRequestVersion((version) => version + 1), []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    loadProductConfig(requestVersion > 0)
      .then((nextConfig) => {
        if (active) {
          setConfig(nextConfig);
        }
      })
      .catch((requestError) => {
        if (active) {
          setConfig(null);
          setError(requestError instanceof Error ? requestError.message : '获取产品申请配置失败');
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [requestVersion]);

  return { config, loading, error, retry };
}
