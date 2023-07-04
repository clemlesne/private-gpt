import "./conversation.scss";
import { client } from "./Utils";
import { useAuth } from "oidc-react";
import { useState, useEffect, useMemo } from "react";
import { v4 as uuidv4 } from "uuid";
import Button from "./Button";
import Message from "./Message";
import PropTypes from "prop-types";
import Select from "react-select";

function Conversation({
  conversationId,
  darkTheme,
  refreshConversations,
  setLoadingConversation,
}) {
  // State
  const [conversation, setConversation] = useState({ messages: [] });
  const [input, setInput] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optionsPrompt, setOptionsPrompt] = useState([]);
  const [prompts, setPrompts] = useState({});
  const [secret, setSecret] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  // Dynamic
  const auth = useAuth();

  useEffect(() => {
    const fetchPrompts = async () => {
      if (!auth.userData) return;
      if (conversationId) return;

      await client
        .get("/prompt", {
          timeout: 10_000,
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
    // Group prompts by group
    const groups = {};
    for (const prompt of Object.values(prompts)) {
      if (!groups[prompt.group]) groups[prompt.group] = [];
      groups[prompt.group].push(prompt);
    }
    // Convert to options
    const options = Object.entries(groups).map(([group, prompts]) => {
      return {
        label: group,
        options: prompts.map((prompt) => {
          return {
            label: prompt.name,
            value: prompt.id,
          };
        }),
      };
    });
    setOptionsPrompt(options);
  }, [prompts, conversationId]);

  useEffect(() => {
    const fetchConversation = async () => {
      if (!auth.userData) return;

      if (!conversationId) {
        setConversation({ messages: [] });
        return;
      }

      await client
        .get(`/conversation/${conversationId}`, {
          timeout: 10_000,
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

    setLoadingConversation(true);
    fetchConversation().finally(() => {
      setLoadingConversation(false);
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
      await client
        .post("/message", null, {
          params: {
            content: input,
            conversation_id: conversation ? conversation.id : null,
            prompt_id:
              !conversationId && selectedPrompt ? selectedPrompt.id : null,
            secret: secret,
          },
          timeout: 10_000,
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
            `${client.defaults.baseURL}/message/${lastMessage.id}?token=${lastMessage.token}`
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
              darkTheme={darkTheme}
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
                <Select
                  className="react-select"
                  classNamePrefix="react-select"
                  defultValue={selectedPrompt ? selectedPrompt.id : null}
                  isDisabled={loading}
                  menuPlacement="auto"
                  minMenuHeight={384}
                  onChange={(e) => setSelectedPrompt(prompts[e.value])}
                  options={optionsPrompt}
                  placeholder="Default tone"
                  unstyled={true}
                />
              )}
              {conversation.prompt && (
                <p>Converse as {conversation.prompt.name.toLowerCase()}.</p>
              )}
              <Button
                active={secret}
                disabled={loading}
                emoji={secret ? "💾" : "🙈"}
                onClick={() => setSecret(!secret)}
                text={secret ? "Stored" : "Temporary"}
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
  darkTheme: PropTypes.bool,
  refreshConversations: PropTypes.func.isRequired,
  setLoadingConversation: PropTypes.func.isRequired,
};

export default Conversation;
