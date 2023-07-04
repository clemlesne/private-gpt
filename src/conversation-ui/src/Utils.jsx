import axios from "axios";
import axiosRetry from "axios-retry";

const client = axios.create({
  baseURL: 'http://127.0.0.1:8081',
});
axiosRetry(client, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  shouldResetTimeout: true,
});

export { client };
