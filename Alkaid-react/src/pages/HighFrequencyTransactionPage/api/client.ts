import axios from 'axios';
export const highFrequencyClient = axios.create({ baseURL: '/api', timeout: 15000 });
highFrequencyClient.interceptors.response.use(
  (response) => response,
  (error) =>
    Promise.reject(new Error(error.response?.data?.message || error.message || '请求失败')),
);
