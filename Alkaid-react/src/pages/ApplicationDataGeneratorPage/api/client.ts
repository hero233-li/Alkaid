import axios from'axios';
export const applicationDataClient=axios.create({baseURL:'/api',timeout:15000});
applicationDataClient.interceptors.response.use(response=>response,error=>Promise.reject(new Error(error.response?.data?.message||error.message||'请求失败')));
