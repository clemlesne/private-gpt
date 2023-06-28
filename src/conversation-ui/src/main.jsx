import "./main.scss";
import "normalize.css/normalize.css";
import { AuthProvider } from 'oidc-react';
import { HelmetProvider } from 'react-helmet-async';
import App from "./App";
import React from "react";
import ReactDOM from "react-dom/client";
import {
  createBrowserRouter,
  RouterProvider,
} from "react-router-dom";


const router = createBrowserRouter([
  {
    element: <App />,
    path: "/",
  },
  {
    element: null,
    path: "/auth",
  },
]);

const oidcConfig = {
  onSignIn: () => {
    router.navigate('/');
  },
  authority: 'https://login.microsoftonline.com/common/v2.0',
  clientId: 'e9d5f20f-7f14-4204-a9a2-0d91d6af5c82',
  redirectUri: 'https://127.0.0.1:8080/auth',
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
