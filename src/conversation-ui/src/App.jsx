import "./app.scss";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { useAuth } from "oidc-react";
import { useState, useEffect } from "react";
import axios from "axios";
import Button from "./Button";
import Conversation from "./Conversation";
import Conversations from "./Conversations";
import Search from "./Search";
import useLocalStorageState from "use-local-storage-state";

function App() {
  // Browser context
  const getPreferredScheme = () =>
    window?.matchMedia?.("(prefers-color-scheme:dark)")?.matches
      ? "dark"
      : "light";
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [hideConversation, setHideConversation] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  // Persistance
  const [darkTheme, setDarkTheme] = useLocalStorageState("darkTheme", {
    defaultValue: () => getPreferredScheme() == "dark",
  });
  // Dynamic
  const auth = useAuth();

  const fetchConversations = async (idToSelect = null) => {
    if (!auth.userData) return;

    await axios
      .get(`${API_BASE_URL}/conversation`, {
        timeout: 30000,
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
          setSelectedConversation(found);
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
      <div className="header">
        <div className="header__top">
          <h1>🔒 Private GPT</h1>
          <Button
            className="header__top__toggle"
            emoji="="
            text="Menu"
            onClick={() =>
              document.documentElement.classList.toggle("header--open")
            }
          />
        </div>
        <div className="header__content">
          {auth.userData && (
            <Conversations
              conversationLoading={conversationLoading}
              conversations={conversations}
              selectedConversation={selectedConversation}
              setSelectedConversation={setSelectedConversation}
            />
          )}
        </div>
        <small className="header__bottom">
          <div className="header__bottom__block">
            {auth.userData && (
              <p>
                Logged as {auth.userData.profile.name ? auth.userData.profile.name : "unknown name"} (
                {auth.userData.profile.email ? auth.userData.profile.email : "unknown email"}).
              </p>
            )}
            {auth.isLoading && <p>Connecting...</p>}
          </div>
          <div className="header__bottom__block">
            <Button
              onClick={() => (auth.userData ? auth.signOut() : auth.signIn())}
              text={auth.userData ? "Signout" : "Signin"}
              loading={auth.isLoading}
            />
            <Button
              emoji={darkTheme ? "🌕" : "☀️"}
              onClick={() => setDarkTheme(!darkTheme)}
              text={darkTheme ? "Dark" : "Light"}
            />
          </div>
        </small>
      </div>
      <div className="main">
        {auth.userData && <Search setHideConversation={setHideConversation} />}
        {!hideConversation && (
          <Conversation
            conversationId={selectedConversation}
            refreshConversations={refreshConversations}
            setConversationLoading={setConversationLoading}
          />
        )}
      </div>
    </>
  );
}

export default App;
