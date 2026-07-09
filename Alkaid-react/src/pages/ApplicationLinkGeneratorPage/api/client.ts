import axios from 'axios';

export const applicationLinkClient = axios.create({
  baseURL: '/api',
  timeout: 15_000,
});

applicationLinkClient.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(new Error(error.response?.data?.message || error.message || '请求失败'));
  },
);
