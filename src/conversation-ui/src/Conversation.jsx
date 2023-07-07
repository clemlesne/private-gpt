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

    fetchConversation();
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
          // Catch 400 errors
          if (error.response && error.response.status == 400) {
            replaceLastMessage({
              content: error.response.data.detail,
              created_at: new Date().toISOString(),
              error: true,
              id: uuidv4(),
              role: "assistant",
              secret: secret,
            });
          } else { // Catch other errors
            console.error(error);
          }
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
      <div className="conversation__messages">
        {conversation.messages.length == 0 && (
          <div className="conversation__messages__empty">
            <big>🔒 Private GPT</big>
            <div className="conversation__messages__empty__doc">
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
                onClick={() => auth.signIn()}
                active={true}
                emoji="🔑"
                loading={auth.isLoading}
                text="Signin"
              />
            )}
          </div>
        )}
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
