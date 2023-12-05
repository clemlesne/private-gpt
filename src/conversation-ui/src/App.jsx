import "./app.scss";
import { client, getIdToken } from "./Utils";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { Outlet, useNavigate } from "react-router-dom";
import { useMsal, useAccount } from "@azure/msal-react";
import { useState, useEffect, createContext, useMemo } from "react";
import Header from "./Header";
import useLocalStorageState from "use-local-storage-state";

export const ConversationContext = createContext(null);
export const HeaderOpenContext = createContext(null);
export const ThemeContext = createContext(null);

function App() {
  // Browser context
  const getPreferredScheme = async () => {
    return window?.matchMedia?.("(prefers-color-scheme:dark)")?.matches
      ? "dark"
      : "light";
  };
  // State
  const [conversations, setConversations] = useState([]);
  const [isVisible, setIsVisible] = useState(true);
  const [headerOpen, setHeaderOpen] = useState(false);
  // Persistance
  let darkTheme, setDarkTheme;
  // In a browser, we persist the theme in local storage
  const [localDarkTheme, localSetDarkTheme] = useLocalStorageState(
    "darkTheme",
    {
      defaultValue: async () => (await getPreferredScheme()) == "dark",
    }
  );
  darkTheme = localDarkTheme;
  setDarkTheme = localSetDarkTheme;
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

  const fetchConversations = async (idToSelect = null) => {
    if (!account) return;

    const idToken = await getIdToken(account, instance);
    if (!idToken) return;

    const controller = new AbortController();

    await client
      .get("/conversation", {
        signal: controller.signal,
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

    return () => {
      if (controller) controller.abort();
    }
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

  const headerOpenContextProps = useMemo(
    () => [headerOpen, setHeaderOpen],
    [headerOpen, setHeaderOpen]
  );

  const endUserAppName = import.meta.env.VITE_END_USER_APP_NAME.replace(
    "\\'",
    "'"
  );
  const version = import.meta.env.VITE_VERSION || "0.0.0-unknown";
  const description = `${endUserAppName} is a personal assitant using your enterprise data.`;

  return (
    <>
      <Helmet
        title={endUserAppName}
        meta={[
          {
            name: "description",
            content: description,
          },
        ]}
        script={[
          helmetJsonLdProp({
            "@context": "https://schema.org",
            "@type": "WebApplication",
            alternateName: "Private AI Assistant",
            applicationCategory: "Communication",
            applicationSubCategory: "Chat",
            browserRequirements: "Requires JavaScript, HTML5, CSS3.",
            countryOfOrigin: "France",
            description: description,
            image: "/assets/fluentui-emoji-cat.svg",
            inLanguage: "en-US",
            isAccessibleForFree: true,
            learningResourceType: "workshop",
            license:
              "https://github.com/clemlesne/private-gpt/blob/main/LICENSE",
            name: endUserAppName,
            releaseNotes: "https://github.com/clemlesne/private-gpt/releases",
            typicalAgeRange: "12-",
            version: version,
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
            ${headerOpen ? "header--open" : ""}
            ${isVisible ? "visibility--visible" : "visibility--hidden"}
          `,
        }}
      />
      <HeaderOpenContext.Provider value={headerOpenContextProps}>
        <ThemeContext.Provider value={themeContextProps}>
          <ConversationContext.Provider value={conversationContextProps}>
            <Header />
            <div id="main" className="main">
              <div className="main__container">
                <Outlet />
              </div>
            </div>
          </ConversationContext.Provider>
        </ThemeContext.Provider>
      </HeaderOpenContext.Provider>
    </>
  );
}

export default App;
