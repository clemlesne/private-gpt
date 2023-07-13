import "./conversation.scss";
import { client } from "./Utils";
import { ConversationContext } from "./App";
import { useAuth } from "oidc-react";
import { useParams } from "react-router-dom";
import { useState, useEffect, useMemo, useContext } from "react";
import { v4 as uuidv4 } from "uuid";
import * as XLSX from "xlsx";
import Button from "./Button";
import Message from "./Message";
import Select, { createFilter } from "react-select";

function Conversation() {
  // State
  const [conversation, setConversation] = useState({ messages: [] });
  const [input, setInput] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optionsPrompt, setOptionsPrompt] = useState([]);
  const [prompts, setPrompts] = useState({});
  const [secret, setSecret] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  // Browser context
  const { conversationId } = useParams();
  // Dynamic
  const auth = useAuth();
  // React context
  const [, refreshConversations] = useContext(ConversationContext);

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
        .catch((err) => {
          console.error(err);
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
        .catch((err) => {
          console.error(err);
        });
    };

    fetchConversation();
  }, [auth, conversationId]);

  const sendMessage = () => {
    // Create a locache state cache, as state props wont't be updated until the next render
    let localMessages = [...conversation.messages];

    // Append the message to the list
    const addMessages = (newMessages) => {
      // Update local state cache
      localMessages = [...localMessages, ...newMessages];
      // Update state
      setConversation({ ...conversation, messages: localMessages });
    };

    // Keep the same id, avoid React to re-render the whole list
    const updateLastMessage = (newMessage) => {
      const tmp = [...localMessages];
      // Update the last message with the new content
      tmp[tmp.length - 1] = Object.assign({}, tmp[tmp.length - 1], newMessage);
      // Update local state cache
      localMessages = tmp;
      // Update state
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
          let content = "";
          const source = new EventSource(
            `${client.defaults.baseURL}/message/${lastMessage.id}?token=${lastMessage.token}`
          );
          source.onmessage = (e) => {
            if (e.data === "STOP") {
              cleanup();
              return;
            }

            // Update the last message
            content += e.data;
            updateLastMessage({
              content,
            });
          };
          source.onerror = (e) => {
            if (e.eventPhase === EventSource.CLOSED) cleanup();
          };
        })
        .catch((err) => {
          let content;
          if (err.response?.status == 400) {
            content = err.response.data.detail;
          } else if (err.request?.statusText) {
            content = err.request.statusText;
            console.error(err);
          } else if (err.message) {
            content = err.message;
            console.error(err);
          }

          // Capitalize the first letter only
          content = content.charAt(0).toUpperCase() + content.slice(1).toLowerCase();

          updateLastMessage({
            content,
            error: true,
          });

          setLoading(false);
        });
    };

    addMessages([
      {
        content: input,
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "user",
        secret,
      },
      {
        content: "Loading…",
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "assistant",
        secret,
      },
    ]);

    fetchMessage();

    // Reset the input
    setInput("");
  };

  // Scroll to the bottom of the page when the conversation changes
  useEffect(() => {
    const main = document.getElementById("main");
    if (main) main.scrollTop = main.scrollHeight;
  }, [conversation]);

  // Handle the input, allow to send a message with enter
  const inputKeyHandler = (e) => {
    // Ability to search with enter, and add a new line with shift+enter
    if (e.key === "Enter" && !e.shiftKey && input.length > 0) {
      sendMessage();
      e.preventDefault();
    }
  };

  // Download the conversation to an Excel file
  const downloadToExcel = () => {
    // Convert the conversation to an array of objects
    const data = conversation.messages.map((message) => {
      return {
        content: message.content,
        date: message.created_at,
        role: message.role,
      };
    });
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Conversation");
    XLSX.writeFile(wb, `conversation-${conversation.id}.xlsx`);
  };

  return (
    <div className="conversation">
      <div className="conversation__header">
        {conversationId && <h2>{conversation.title ? conversation.title : "New chat"}</h2>}
      </div>
      {conversation.messages.length == 0 && (
        <div className="conversation__empty">
          <div className="conversation__empty__header">
            <span>🔒</span>
            <big>Welcome to Private GPT</big>
          </div>
          <div className="conversation__empty__doc">
            <div>
              <h2>💡</h2>
            </div>
            <div>
              <h2>Examples</h2>
              <p>Generating content that is tailored to specific audiences or personas.</p>
              <p>Help on technical language and jargon in specific industries (such as finance or healthcare).</p>
            </div>
            <div>
              <h2>⚡️</h2>
            </div>
            <div>
              <h2>Capabilities</h2>
              <p>Analyzing large amounts of qualitative data (such as news articles or earnings calls) to inform investment decisions.</p>
              <p>Generating summaries of court cases or contracts to save time on manual review.</p>
            </div>
            <div>
              <h2>⚠️</h2>
            </div>
            <div>
              <h2>Limitations</h2>
              <p>Ensuring that generated content adheres to applicable regulations in a given industry or region.</p>
              <p>Mitigating any risks associated with automated content creation (such as reputational harm or inadvertent bias).</p>
            </div>
          </div>
          {!auth.userData && (
            <Button
              active={true}
              emoji="🔑"
              large={true}
              loading={auth.isLoading}
              onClick={() => auth.signIn()}
              text="Signin"
            />
          )}
        </div>
      )}
      {conversation.messages.length > 0 && <div className="conversation__messages">
        {conversation.messages.map((message) => (
          <Message
            content={message.content}
            date={message.created_at}
            defaultDisplaySub={message.secret}
            error={message.error}
            key={message.id}
            role={message.role}
            secret={message.secret}
          />
        ))}
      </div>}
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
                filterOption={createFilter({
                  ignoreAccents: true,
                  ignoreCase: true,
                  matchFrom: "any",
                })}
              />
            )}
            {conversation.prompt && (
              <p>Converse as {conversation.prompt.name.toLowerCase()}.</p>
            )}
            {conversationId && <Button
              disabled={loading}
              emoji="⬇️"
              onClick={() => downloadToExcel()}
              text="Download"
            />}
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
  );
}

export default Conversation;
