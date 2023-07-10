import "./main.scss";
import "normalize.css/normalize.css";
import { AuthProvider } from "oidc-react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";
import App from "./App";
import Conversation from "./Conversation";
import React from "react";
import ReactDOM from "react-dom/client";
import Search from "./Search";
import Auth from "./Auth";

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
  }
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
    <HelmetProvider>
      <AuthProvider {...oidcConfig}>
        <RouterProvider router={router} />
      </AuthProvider>
    </HelmetProvider>
  </React.StrictMode>
);
