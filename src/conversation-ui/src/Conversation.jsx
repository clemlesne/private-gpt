import "./conversation.scss";
import { client, getIdToken, login, userLang } from "./Utils";
import { ConversationContext } from "./App";
import { useMsal, useAccount, useIsAuthenticated } from "@azure/msal-react";
import { useParams } from "react-router-dom";
import { useState, useEffect, useMemo, useContext } from "react";
import { v4 as uuidv4 } from "uuid";
import * as XLSX from "xlsx";
import Button from "./Button";
import Message from "./Message";
import Select, { createFilter } from "react-select";
import {
  ArrowDownFilled,
  ArrowUpFilled,
  EyeLinesFilled,
  FlashFilled,
  KeyFilled,
  LightbulbFilled,
  SaveFilled,
  WarningFilled,
} from "@fluentui/react-icons";

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
  const { instance, accounts, inProgress } = useMsal();
  const account = useAccount(accounts[0] || null);
  const isAuthenticated = useIsAuthenticated();
  // React context
  const [, refreshConversations] = useContext(ConversationContext);

  useEffect(() => {
    if (!account) return;

    const controller = new AbortController();

    const fetchPrompts = async () => {
      if (conversationId) return;

      const idToken = await getIdToken(account, instance);
      if (!idToken) return;

      await client
        .get("/prompt", {
          signal: controller.signal,
          timeout: 10_000,
          headers: {
            Authorization: `Bearer ${idToken}`,
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

    return () => {
      if (controller) controller.abort();
    }
  }, [account, conversationId]);

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
    if (!account) return;

    const controller = new AbortController();

    const fetchConversation = async () => {
      if (!conversationId) {
        setConversation({ messages: [] });
        return;
      }

      const idToken = await getIdToken(account, instance);
      if (!idToken) return;

      await client
        .get(`/conversation/${conversationId}`, {
          signal: controller.signal,
          timeout: 10_000,
          headers: {
            Authorization: `Bearer ${idToken}`,
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

    return () => {
      if (controller) controller.abort();
    }
  }, [account, conversationId]);

  const sendMessage = () => {
    // Create a locache state cache, as state props wont't be updated until the next render
    let localMessages = [...conversation.messages];

    const controller = new AbortController();
    let source;

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
      if (!isAuthenticated) return;

      const idToken = await getIdToken(account, instance);
      if (!idToken) return;

      setLoading(true);


      // First, create the message
      await client
        .post("/message", null, {
          signal: controller.signal,
          timeout: 30_000,
          params: {
            content: input,
            conversation_id: conversation ? conversation.id : null,
            prompt_id:
              !conversationId && selectedPrompt ? selectedPrompt.id : null,
            secret: secret,
            language: userLang,
          },
          headers: {
            Authorization: `Bearer ${idToken}`,
          },
        })
        .then((res) => {
          if (!res.data) return;

          const cleanup = () => {
            // Free backend resources
            source.close();

            // Stop loading
            updateLastMessage({
              loading: false,
            });

            setLoading(false);
            // Ask to refresh the conversation, if it is not loaded, or if the title is not either
            if (!conversationId || !conversation.title)
              refreshConversations(res.data.id);
          };

          // Then, fetch the message
          const lastMessage = res.data.messages[res.data.messages.length - 1];
          let content = "";
          let actions = [];
          source = new EventSource(
            `${client.defaults.baseURL}/message/${lastMessage.token}`
          );
          source.onmessage = (e) => {
            if (e.data === "STOP") {
              cleanup();
              return;
            }

            const json = JSON.parse(e.data);
            if (json.content) content += json.content;
            if (json.action) actions.push(json.action);
            updateLastMessage({
              actions,
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
          content =
            content.charAt(0).toUpperCase() + content.slice(1).toLowerCase();

          // Stop loading
          updateLastMessage({
            content,
            error: true,
            loading: false,
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
        created_at: new Date().toISOString(),
        id: uuidv4(),
        loading: true,
        role: "assistant",
        secret,
      },
    ]);

    fetchMessage();

    // Reset the input
    setInput("");

    return () => {
      if (controller) controller.abort();
      if (source) source.close();
    }
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
      {conversation.messages.length > 0 && (
        <div className="conversation__header">
          <h2>{conversation.title ? conversation.title : "New chat"}</h2>
        </div>
      )}
      {conversation.messages.length == 0 && (
        <div className="conversation__empty">
          <div className="conversation__empty__header">
            <span>{import.meta.env.VITE_END_USER_APP_ICON}</span>
            <big>
              Welcome to{" "}
              {import.meta.env.VITE_END_USER_APP_NAME.replace("\\'", "'")}
            </big>
          </div>
          <div className="conversation__empty__doc">
            <div>
              <h2>
                <LightbulbFilled />
              </h2>
            </div>
            <div>
              <h2>Examples</h2>
              <p>
                Generating content that is tailored to specific audiences or
                personas.
              </p>
              <p>
                Help on technical language and jargon in specific industries
                (such as finance or healthcare).
              </p>
            </div>
            <div>
              <h2>
                <FlashFilled />
              </h2>
            </div>
            <div>
              <h2>Capabilities</h2>
              <p>
                Analyzing large amounts of qualitative data (such as news
                articles or earnings calls) to inform investment decisions.
              </p>
              <p>
                Generating summaries of court cases or contracts to save time on
                manual review.
              </p>
            </div>
            <div>
              <h2>
                <WarningFilled />
              </h2>
            </div>
            <div>
              <h2>Limitations</h2>
              <p>
                Ensuring that generated content adheres to applicable
                regulations in a given industry or region.
              </p>
              <p>
                Mitigating any risks associated with automated content creation
                (such as reputational harm or inadvertent bias).
              </p>
            </div>
          </div>
          {!isAuthenticated && (
            <Button
              active={true}
              emoji={KeyFilled}
              large={true}
              loading={inProgress === "login"}
              onClick={() => login(instance)}
              text="Signin"
            />
          )}
        </div>
      )}
      {conversation.messages.length > 0 && (
        <div className="conversation__messages">
          {conversation.messages.map((message) => (
            <Message
              actions={message?.actions}
              content={message?.content}
              date={message.created_at}
              defaultDisplaySub={message.secret}
              error={message?.error}
              key={message.id}
              loading={message?.loading}
              role={message.role}
              secret={message?.secret}
            />
          ))}
        </div>
      )}
      {isAuthenticated && (
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
            {conversationId && (
              <Button
                disabled={loading}
                emoji={ArrowDownFilled}
                onClick={() => downloadToExcel()}
                text="Download"
              />
            )}
            <Button
              active={secret}
              disabled={loading}
              emoji={secret ? SaveFilled : EyeLinesFilled}
              onClick={() => setSecret(!secret)}
              text={secret ? "Stored" : "Temporary"}
            />
          </div>
          <div className="conversation__input__block">
            <textarea
              autoFocus={true}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={inputKeyHandler}
              placeholder="Message"
              value={input || ""}
            />
          </div>
          <div className="conversation__input__block">
            <Button
              active={true}
              disabled={!(input && input.length > 0)}
              emoji={ArrowUpFilled}
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
