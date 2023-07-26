import "./main.scss";
import "normalize.css/normalize.css";
import {
  AppInsightsContext,
  ReactPlugin,
} from "@microsoft/applicationinsights-react-js";
import { ApplicationInsights } from "@microsoft/applicationinsights-web";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { CustomNavigationClient } from "./utils/NavigationClient";
import { HelmetProvider } from "react-helmet-async";
import { LogLevel } from "@azure/msal-common";
import { MsalProvider } from "@azure/msal-react";
import { PublicClientApplication } from "@azure/msal-browser";
import App from "./App";
import Conversation from "./Conversation";
import React from "react";
import ReactDOM from "react-dom/client";
import Search from "./Search";

const reactPlugin = new ReactPlugin();
const appInsights = new ApplicationInsights({
  config: {
    connectionString: import.meta.env.VITE_APP_INSIGHTS_CONNECTION_STR,
    extensions: [reactPlugin],
    enableAutoRouteTracking: true,
  },
});
appInsights.loadAppInsights();

const router = createBrowserRouter([
  {
    element: <App />,
    path: "/",
    children: [
      {
        path: "",
        element: <Conversation />,
      },
      {
        path: "conversation/:conversationId",
        element: <Conversation />,
      },
      {
        path: "search",
        element: <Search />,
      }
    ],
  },
]);

const pcaConfig = {
  auth: {
    clientId: import.meta.env.VITE_OIDC_CLIENT_ID,
    navigateToLoginRequestUrl: true, // Go back to the original page after login
    postLogoutRedirectUri: "/", // Go back to the app root after logout
    redirectUri: "/", // Go back to the app root after login
  },
  cache: {
    cacheLocation: "localStorage",
    temporaryCacheLocation: "sessionStorage",
  },
  system: {
    navigationClient: new CustomNavigationClient(router.navigate),
    loggerOptions: {
      logLevel: import.meta.env.DEV ? LogLevel.Verbose : LogLevel.Warning,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Info:
            console.info(message);
            return;
          case LogLevel.Verbose:
            console.debug(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
        }
      },
      piiLoggingEnabled: false,
    },
  },
};
const pca = new PublicClientApplication(pcaConfig);

// Set the default account
pca.addEventCallback((event) => {
  if (event.eventType === "msal:loginSuccess") {
    pca.setActiveAccount(event.payload.account);
  }
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppInsightsContext.Provider value={reactPlugin}>
      <HelmetProvider>
        <MsalProvider instance={pca}>
          <RouterProvider router={router} />
        </MsalProvider>
      </HelmetProvider>
    </AppInsightsContext.Provider>
  </React.StrictMode>
);
