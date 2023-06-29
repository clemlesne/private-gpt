import "./app.scss";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { useAuth } from "oidc-react";
import { useState, useEffect } from "react";
import axios from "axios";
import Conversation from "./Conversation";
import Conversations from "./Conversations";
import Search from "./Search";

function App() {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [hideConversation, setHideConversation] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  // Dynamic
  const auth = useAuth();

  const fetchConversations = async (refresh = false) => {
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
        if (refresh) setSelectedConversation(localConversations[0].id);
      })
      .catch((error) => {
        console.error(error);
      });
  };

  const refreshConversations = async () => {
    fetchConversations(true);
  };

  // Fetch the conversations
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
      />
      <div className="header">
        <div className="header__top">
          <h1>🔒 Private GPT</h1>
          <Conversations
            conversations={conversations}
            selectedConversation={selectedConversation}
            setSelectedConversation={setSelectedConversation}
            conversationLoading={conversationLoading}
          />
        </div>
        <div className="header__bottom">
          {auth.userData && (
            <small>
              Logged as {auth.userData.profile.name} (
              {auth.userData.profile.email}).
            </small>
          )}
        </div>
      </div>
      <div className="main">
        <Search setHideConversation={setHideConversation} />
        {!hideConversation && <Conversation
          conversationId={selectedConversation}
          refreshConversations={refreshConversations}
          setConversationLoading={setConversationLoading}
        />}
      </div>
    </>
  );
}

export default App;
