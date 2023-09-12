import { InteractionRequiredAuthError } from "@azure/msal-browser";
import axios from "axios";
import axiosRetry from "axios-retry";

const userLang = navigator.language || navigator.userLanguage;

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

const login = async (instance) => {
  // Browsers are increasingly blocking third party cookies by default. Detect that option is combersome. Thus, we always use redirect instead of popup.
  // See: https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/3118#issuecomment-1655932572
  await instance.loginRedirect();
};

const logout = async (account, instance) => {
  if (!account) return null;
  const opt = { account };
  // Browsers are increasingly blocking third party cookies by default. Detect that option is combersome. Thus, we always use redirect instead of popup.
  // See: https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/3118#issuecomment-1655932572
  await instance.logoutRedirect(opt);
};

const getIdToken = async (account, instance) => {
  if (!account) return null;

  const req = {
    account: account,
    loginHint: account.username,
    scopes: ["openid", "profile", "email", "User.Read", "Calendars.ReadWrite", "Mail.ReadWrite"],
  };

  // Try silent first
  const idToken = await instance
    .acquireTokenSilent(req)
    .then((res) => {
      return res.idToken;
    })
    .catch((error) => {
      const onSuccess = (res) => {
        return res.idToken;
      };

      const onError = (error) => {
        console.error(error);
        return null;
      };

      if (!(error instanceof InteractionRequiredAuthError)) {
        return onError(error);
      }

      // Browsers are increasingly blocking third party cookies by default. Detect that option is combersome. Thus, we always use redirect instead of popup.
      // See: https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/3118#issuecomment-1655932572
      return instance.acquireTokenRedirect(req).then(onSuccess).catch(onError);
    });

  return idToken;
};

export {
  client,
  getIdToken,
  login,
  logout,
  userLang,
};
