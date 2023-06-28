import "./app.scss";
import { Helmet } from "react-helmet-async";
import { helmetJsonLdProp } from "react-schemaorg";
import { useState, useMemo } from "react";
import axios from "axios";
import Conversation from "./Conversation";
import Conversations from "./Conversations";
import FingerprintJS from "@fingerprintjs/fingerprintjs";
import useLocalStorageState from "use-local-storage-state";

function App() {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  // Persistance
  const [F, setF] = useLocalStorageState("F", { defaultValue: null });
  // Dynamic
  const conversation = conversations.find((c) => c.id === selectedConversation);

  const fetchConversations = async () => {
    await axios
      .get(`${API_BASE_URL}/conversation`, {
        params: {
          user: F,
        },
        timeout: 30000,
      })
      .then((res) => {
        if (!res.data) return
        setConversations(res.data.conversations);
      })
      .catch((error) => {
        console.error(error);
      });
  };

  // Init the FingerPrintJS from the browser
  useMemo(() => {
    FingerprintJS.load()
      .then((fp) => fp.get())
      .then((res) => setF(res.visitorId));
  }, []);

  useMemo(() => {
    fetchConversations();
  }, []);

  return (
    <>
      <Helmet script={[
        helmetJsonLdProp({
          "@context": "https://schema.org",
          "@type": "WebApplication",
          alternateName: "Private ChatGPT",
          applicationCategory: "Communication",
          applicationSubCategory: "Chat",
          browserRequirements: "Requires JavaScript, HTML5, CSS3.",
          countryOfOrigin: "France",
          description: "Private GPT is a local version of Chat GPT, using Azure OpenAI",
          image: "/assets/fluentui-emoji-cat.svg",
          inLanguage: "en-US",
          isAccessibleForFree: true,
          learningResourceType: "workshop",
          license: "https://github.com/clemlesne/private-gpt/blob/main/LICENCE",
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
      ]} />
      <div className="header">
        <h1>🧠 Private GPT</h1>
        <p>Private GPT is a local version of Chat GPT, using Azure OpenAI.</p>
        <Conversations conversations={conversations} selectedConversation={selectedConversation} setSelectedConversation={setSelectedConversation} F={F} />
      </div>
      <Conversation conversation={conversation} fetchConversations={fetchConversations} />
    </>
  );
}

export default App;
