import "./app.scss";
import { client } from "./Utils";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { Outlet } from "react-router-dom";
import { useAuth } from "oidc-react";
import { useNavigate } from "react-router-dom";
import { useState, useEffect, createContext } from "react";
import Header from "./Header";
import useLocalStorageState from "use-local-storage-state";

export const ConversationContext = createContext(null);
export const ThemeContext = createContext(null);

function App() {
  // Browser context
  const getPreferredScheme = () =>
    window?.matchMedia?.("(prefers-color-scheme:dark)")?.matches
      ? "dark"
      : "light";
  // State
  const [conversations, setConversations] = useState([]);
  // Persistance
  const [darkTheme, setDarkTheme] = useLocalStorageState("darkTheme", {
    defaultValue: () => getPreferredScheme() == "dark",
  });
  // Dynamic
  const auth = useAuth();
  const navigate = useNavigate();

  const fetchConversations = async (idToSelect = null) => {
    if (!auth.userData) return;

    await client
      .get("/conversation", {
        timeout: 10_000,
        headers: {
          Authorization: `Bearer ${auth.userData.id_token}`,
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
      .catch((error) => {
        console.error(error);
      });
  };

  const refreshConversations = async (id) => {
    fetchConversations(id);
  };

  useEffect(() => {
    fetchConversations();
  }, [auth]);

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
              "https://github.com/clemlesne/private-gpt/blob/main/LICENCE",
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
        htmlAttributes={{ class: darkTheme ? "theme--dark" : "theme--light" }}
      />
      <ThemeContext.Provider value={[ darkTheme, setDarkTheme ]}>
        <ConversationContext.Provider value={[ conversations, refreshConversations ]}>
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
