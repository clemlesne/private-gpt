import axios from "axios";
import axiosRetry from "axios-retry";

const headerOpenClass = "header--open";

const client = axios.create({
  baseURL: 'http://127.0.0.1:8081',
});
axiosRetry(client, {
  retries: 11, // 11 retries + 1 attempt = 12 requests
  retryDelay: (retryCount, err) => axiosRetry.exponentialDelay(retryCount, err, 250),
  shouldResetTimeout: true,
  retryCondition: (err) => {
    return axiosRetry.isNetworkOrIdempotentRequestError(err) || (err.response?.status == 429);
  }
});

const header = (enabled) => {
  if (enabled == undefined) {
    document.documentElement.classList.toggle(headerOpenClass);
  } else if (enabled) {
    document.documentElement.classList.add(headerOpenClass);
  } else {
    document.documentElement.classList.remove(headerOpenClass);
  }
};

export { client, header };
