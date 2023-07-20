import { InteractionRequiredAuthError } from "@azure/msal-browser";
import axios from "axios";
import axiosRetry from "axios-retry";

const headerOpenClass = "header--open";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});
axiosRetry(client, {
  retries: 11, // 11 retries + 1 attempt = 12 requests
  retryDelay: (retryCount, err) =>
    axiosRetry.exponentialDelay(retryCount, err, 250),
  shouldResetTimeout: true,
  retryCondition: (err) => {
    return (
      axiosRetry.isNetworkOrIdempotentRequestError(err) ||
      err.response?.status == 429
    );
  },
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

const login = async (instance) => {
  await instance.loginPopup();
};

const logout = async (account, instance) => {
  if (!account) return null;
  const opt = { account };
  await instance.logoutPopup(opt);
};

const getIdToken = async (account, instance) => {
  if (!account) return null;

  const req = {
    account: account,
    loginHint: account.username,
    scopes: ["openid", "profile", "email", "User.Read"],
  };

  // Try silent first
  const idToken = await instance
    .acquireTokenSilent(req)
    .then((res) => {
      return res.idToken;
    })
    .catch((error) => {
      if (!(error instanceof InteractionRequiredAuthError)) {
        console.error(error);
        return null;
      }

      const onSuccess = (res) => {
        return res.idToken;
      };

      const onError = (error) => {
        console.error(error);
        return null;
      };

      // Failback to popup
      return instance.acquireTokenPopup(req).then(onSuccess).catch(onError);
    });

  return idToken;
};

export {
  client,
  getIdToken,
  header,
  login,
  logout,
};
