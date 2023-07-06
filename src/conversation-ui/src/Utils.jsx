import axios from "axios";
import axiosRetry from "axios-retry";

const headerOpenClass = "header--open";

const client = axios.create({
  baseURL: 'http://127.0.0.1:8081',
});
axiosRetry(client, {
  retries: 12,
  retryDelay: axiosRetry.exponentialDelay,
  shouldResetTimeout: true,
  retryCondition: (error) => {
    return axiosRetry.isNetworkOrIdempotentRequestError(error) || error.response.status == 429;
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
