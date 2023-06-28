import "normalize.css/normalize.css";
import "./main.scss";
import { HelmetProvider } from 'react-helmet-async';
import App from "./App";
import React from "react";
import ReactDOM from "react-dom/client";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HelmetProvider>
      <App />
    </HelmetProvider>
  </React.StrictMode>
);
