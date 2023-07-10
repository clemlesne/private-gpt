import "./main.scss";
import "normalize.css/normalize.css";
import { AppInsightsContext, ReactPlugin } from "@microsoft/applicationinsights-react-js";
import { ApplicationInsights } from "@microsoft/applicationinsights-web";
import { AuthProvider } from "oidc-react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";
import App from "./App";
import Auth from "./Auth";
import Conversation from "./Conversation";
import React from "react";
import ReactDOM from "react-dom/client";
import Search from "./Search";

const reactPlugin = new ReactPlugin();
const appInsights = new ApplicationInsights({
  config: {
    connectionString: "InstrumentationKey=0b860d29-2a55-4d29-ab57-88cdd85a8da0;IngestionEndpoint=https://westeurope-5.in.applicationinsights.azure.com/;LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com",
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
      },
      {
        path: "auth",
        element: <Auth />,
      },
    ],
  },
]);

const oidcConfig = {
  onSignIn: () => {
    router.navigate("/");
  },
  authority: "https://login.microsoftonline.com/common/v2.0",
  clientId: "e9d5f20f-7f14-4204-a9a2-0d91d6af5c82",
  redirectUri: "https://127.0.0.1:8080/auth",
  scope: "openid profile email",
  silentRedirectUri: "https://127.0.0.1:8080/auth",
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppInsightsContext.Provider value={reactPlugin}>
      <HelmetProvider>
        <AuthProvider {...oidcConfig}>
          <RouterProvider router={router} />
        </AuthProvider>
      </HelmetProvider>
    </AppInsightsContext.Provider>
  </React.StrictMode>
);
