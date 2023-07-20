import { NavigationClient } from "@azure/msal-browser";

export class CustomNavigationClient extends NavigationClient {
  constructor(navigate) {
    super();
    this.navigate = navigate;
  }

  async navigateInternal(url, options) {
    const relativePath = url.replace(window.location.origin, "");
    if (options.noHistory) {
      this.navigate(relativePath, { replace: true });
    } else {
      this.navigate(relativePath);
    }

    return false;
  }
}
