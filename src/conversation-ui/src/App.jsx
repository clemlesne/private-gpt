import "./app.scss";
import { client, getIdToken, IS_TAURI } from "./Utils";
import { getCurrent } from "@tauri-apps/api/window";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { isPermissionGranted, requestPermission } from '@tauri-apps/api/notification';
import { Outlet, useNavigate } from "react-router-dom";
import { platform } from "@tauri-apps/api/os";
import { useMsal, useAccount } from "@azure/msal-react";
import { useState, useEffect, createContext, useMemo } from "react";
import Header from "./Header";
import Titlebar from "./Titlebar";
import useLocalStorageState from "use-local-storage-state";

export const ConversationContext = createContext(null);
export const ThemeContext = createContext(null);

function App() {
  console.debug(IS_TAURI ? "Running in Tauri" : "Running in browser");

  // Browser context
  const getPreferredScheme = async () => {
    if (IS_TAURI) {
      const theme = await getCurrent().theme();
      return theme == "dark" ? "dark" : "light";
    }
    return window?.matchMedia?.("(prefers-color-scheme:dark)")?.matches
      ? "dark"
      : "light";
  };
  // State
  const [conversations, setConversations] = useState([]);
  const [isVisible, setIsVisible] = useState(true);
  // Persistance
  let darkTheme, setDarkTheme;
  if (IS_TAURI) {
    // Tauri does not support dynamic theme change
    // See: https://github.com/tauri-apps/tauri/issues/4316
    darkTheme = async () => (await getPreferredScheme()) == "dark";
    setDarkTheme = () => {};
  } else {
    // In a browser, we persist the theme in local storage
    const [localDarkTheme, localSetDarkTheme] = useLocalStorageState(
      "darkTheme",
      {
        defaultValue: async () => (await getPreferredScheme()) == "dark",
      }
    );
    darkTheme = localDarkTheme;
    setDarkTheme = localSetDarkTheme;
  }
  // Dynamic
  const navigate = useNavigate();
  // Refresh account
  const { accounts, instance } = useMsal();
  const account = useAccount(accounts[0] || null);

  // Watch for window focus
  useEffect(() => {
    const handleBlur = () => {
      setIsVisible(false);
    };
    const handleFocus = () => {
      setIsVisible(true);
    };
    window.addEventListener("blur", handleBlur);
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("focus", handleFocus);
    };
  }, []);

  // Init notifications
  useMemo(() => {
    if (!IS_TAURI) return;

    const grantPermission = async () => {
      let permissionGranted = await isPermissionGranted();
      if (!permissionGranted) {
        const permission = await requestPermission();
        permissionGranted = permission === 'granted';
      }

      if (permissionGranted) {
        console.debug("Permission granted");
      } else {
        console.debug("Permission denied");
      }
    };

    grantPermission();
  }, []);

  const fetchConversations = async (idToSelect = null) => {
    if (!account) return;

    const idToken = await getIdToken(account, instance);

    await client
      .get("/conversation", {
        timeout: 10_000,
        headers: {
          Authorization: `Bearer ${idToken}`,
        },
      })
      .then((res) => {
        if (!res.data) return;

        const localConversations = res.data.conversations;
        setConversations(localConversations);

        if (idToSelect) {
          let found = null;
          // Search for the conversation ID
          for (const conversation of localConversations) {
            if (conversation.id == idToSelect) {
              found = conversation.id;
              break;
            }
          }
          // If ID not found, select the first one
          if (!found) {
            found = localConversations[0].id;
          }
          navigate(`/conversation/${found}`);
        }
      })
      .catch((err) => {
        console.error(err);
      });
  };

  useEffect(() => {
    fetchConversations();
  }, [account]);

  const themeContextProps = useMemo(
    () => [darkTheme, setDarkTheme],
    [darkTheme, setDarkTheme]
  );

  const conversationContextProps = useMemo(() => {
    const refreshConversations = async (id) => {
      fetchConversations(id);
    };
    return [conversations, refreshConversations];
  }, [conversations]);

  return (
    <>
      <Helmet
        script={[
          helmetJsonLdProp({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            alternateName: "Private ChatGPT",
            applicationCategory: "Communication",
            applicationSubCategory: "Chat",
            browserRequirements: "Requires JavaScript, HTML5, CSS3.",
            countryOfOrigin: "France",
            description:
              "Private GPT is a local version of Chat GPT, using Azure OpenAI",
            image: "/assets/fluentui-emoji-cat.svg",
            inLanguage: "en-US",
            isAccessibleForFree: true,
            learningResourceType: "workshop",
            license:
              "https://github.com/clemlesne/private-gpt/blob/main/LICENSE",
            name: "Private GPT",
            releaseNotes: "https://github.com/clemlesne/private-gpt/releases",
            typicalAgeRange: "12-",
            version: import.meta.env.VITE_VERSION,
            sourceOrganization: {
              "@type": "Organization",
              name: "Microsoft",
              url: "https://microsoft.com",
            },
            maintainer: {
              "@type": "Person",
              email: "clemence@lesne.pro",
              name: "Clémence Lesne",
            },
          }),
        ]}
        htmlAttributes={{
          class: `
            ${darkTheme ? "theme--dark" : "theme--light"}
            ${IS_TAURI ? "tauri" : ""}
            ${IS_TAURI && platform == "Windows_NT" ? "tauri--win" : ""}
            ${isVisible ? "visibility--visible" : "visibility--hidden"}
          `,
        }}
      />
      <ThemeContext.Provider value={themeContextProps}>
        <ConversationContext.Provider value={conversationContextProps}>
          {IS_TAURI && <Titlebar />}
          <Header />
          <div id="main" className="main">
            <div className="main__container">
              <Outlet />
            </div>
          </div>
        </ConversationContext.Provider>
      </ThemeContext.Provider>
    </>
  );
}

export default App;
