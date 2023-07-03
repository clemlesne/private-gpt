import "./conversation.scss";
import { useAuth } from "oidc-react";
import { useState, useEffect, useMemo } from "react";
import { v4 as uuidv4 } from "uuid";
import axios from "axios";
import Button from "./Button";
import Dropdown from "./Dropdown";
import Message from "./Message";
import PropTypes from "prop-types";

function Conversation({
  conversationId,
  refreshConversations,
  setConversationLoading,
}) {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [input, setInput] = useState(null);
  const [conversation, setConversation] = useState({ messages: [] });
  const [loading, setLoading] = useState(false);
  const [secret, setSecret] = useState(false);
  const [prompts, setPrompts] = useState({});
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [optionsPrompt, setOptionsPrompt] = useState([]);
  // Dynamic
  const auth = useAuth();

  useEffect(() => {
    const fetchPrompts = async () => {
      if (!auth.userData) return;
      if (conversationId) return;

      await axios
        .get(`${API_BASE_URL}/prompt`, {
          timeout: 30000,
          headers: {
            Authorization: `Bearer ${auth.userData.id_token}`,
          },
        })
        .then((res) => {
          if (!res.data) return;
          const localPrompts = res.data.prompts.reduce((map, obj) => {
            map[obj.id] = obj;
            return map;
          }, {});
          setPrompts(localPrompts);
        })
        .catch((error) => {
          console.error(error);
        });
    };

    fetchPrompts();
  }, [auth, conversationId]);

  useMemo(() => {
    if (conversationId) return;
    const options = [];
    for (const [id, prompt] of Object.entries(prompts)) {
      options.push({ label: prompt.name, group: prompt.group, id: id });
    }
    setOptionsPrompt(options);
  }, [prompts, conversationId]);

  useEffect(() => {
    const fetchConversation = async () => {
      if (!auth.userData) return;

      if (!conversationId) {
        setConversation({ messages: [] });
        return;
      }

      await axios
        .get(`${API_BASE_URL}/conversation/${conversationId}`, {
          timeout: 30000,
          headers: {
            Authorization: `Bearer ${auth.userData.id_token}`,
          },
        })
        .then((res) => {
          if (!res.data) return;
          setConversation(res.data);
        })
        .catch((error) => {
          console.error(error);
        });
    };

    setConversationLoading(true);
    fetchConversation().finally(() => {
      setConversationLoading(false);
    });
  }, [auth, conversationId]);

  const sendMessage = () => {
    let localMessages = [...conversation.messages];

    const addMessages = (newMessages) => {
      localMessages = [...localMessages, ...newMessages];
      setConversation({ ...conversation, messages: localMessages });
    };

    const replaceLastMessage = (newMessage) => {
      const tmp = [...localMessages];
      tmp[tmp.length - 1] = newMessage;
      localMessages = tmp;
      setConversation({ ...conversation, messages: localMessages });
    };

    const fetchMessage = async () => {
      if (!auth.userData) return;

      setLoading(true);

      // First, create the message
      await axios
        .post(`${API_BASE_URL}/message`, null, {
          params: {
            content: input,
            conversation_id: conversation ? conversation.id : null,
            prompt_id:
              !conversationId && selectedPrompt ? selectedPrompt.id : null,
            secret: secret,
          },
          timeout: 30000,
          headers: {
            Authorization: `Bearer ${auth.userData.id_token}`,
          },
        })
        .then((res) => {
          if (!res.data) return;

          const cleanup = () => {
            source.close();
            // Ask to refresh the conversation, if it is not loaded, or if the title is not either
            if (!conversationId || !conversation.title)
              refreshConversations(res.data.id);
            setLoading(false);
          };

          // Then, fetch the message
          const lastMessage = res.data.messages[res.data.messages.length - 1];
          let stream = "";
          const source = new EventSource(
            `${API_BASE_URL}/message/${lastMessage.id}?token=${lastMessage.token}`
          );
          source.onmessage = (e) => {
            if (e.data === "STOP") {
              cleanup();
              return;
            }

            // Update the last message
            stream += e.data;
            replaceLastMessage({
              content: stream,
              created_at: new Date().toISOString(),
              id: uuidv4(),
              role: "assistant",
              secret: secret,
            });
          };
          source.onerror = (e) => {
            if (e.eventPhase === EventSource.CLOSED) cleanup();
          };
        })
        .catch((error) => {
          console.error(error);
          setLoading(false);
        });
    };

    addMessages([
      {
        content: input,
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "user",
        secret: secret,
      },
      {
        content: "Loading…",
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "assistant",
        secret: secret,
      },
    ]);

    fetchMessage();

    // Reset the input
    setInput("");
  };

  useEffect(() => {
    window.scrollTo(0, document.body.scrollHeight);
  }, [conversation]);

  const inputKeyHandler = (e) => {
    // Ability to search with enter, and add a new line with shift+enter
    if (e.key === "Enter" && !e.shiftKey && input.length > 0) {
      sendMessage();
      e.preventDefault();
    }
  };

  return (
    <div className="conversation">
      <div className="conversation__container">
        <div className="conversation__messages">
          {conversation.messages.length == 0 && (
            <div className="conversation__messages__empty">
              <big>🔒 Private GPT</big>
              {!auth.userData && (
                <Button
                  onClick={() => auth.signIn()}
                  text="Signin"
                  active={true}
                  loading={auth.isLoading}
                />
              )}
            </div>
          )}
          {conversation.messages.map((message) => (
            <Message
              content={message.content}
              date={message.created_at}
              defaultDisplaySub={message.secret}
              key={message.id}
              role={message.role}
              secret={message.secret}
            />
          ))}
        </div>
        {auth.userData && (
          <form
            className="conversation__input"
            onSubmit={(e) => {
              sendMessage();
              e.preventDefault();
            }}
          >
            <div className="conversation__input__block">
              {!conversationId && (
                <Dropdown
                  defaultTitle="Default tone"
                  onChange={(id) => setSelectedPrompt(prompts[id])}
                  options={optionsPrompt}
                  selected={selectedPrompt ? selectedPrompt.id : null}
                  disabled={loading}
                />
              )}
              {conversation.prompt && (
                <p>Converse as {conversation.prompt.name.toLowerCase()}.</p>
              )}
              <Button
                active={secret}
                disabled={loading}
                emoji={secret ? "🙈" : "💾"}
                onClick={() => setSecret(!secret)}
                text={secret ? "Temporary" : "Stored"}
              />
            </div>
            <div className="conversation__input__block">
              <textarea
                placeholder="Message"
                value={input || ""}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={inputKeyHandler}
              />
            </div>
            <div className="conversation__input__block">
              <Button
                active={true}
                disabled={!(input && input.length > 0)}
                emoji="⬆️"
                loading={loading}
                text="Send"
                type="submit"
              />
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

Conversation.propTypes = {
  conversationId: PropTypes.string,
  refreshConversations: PropTypes.func.isRequired,
  setConversationLoading: PropTypes.func.isRequired,
};

export default Conversation;
