import "./conversation.scss";
import { useAuth } from "oidc-react";
import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import axios from "axios";
import Button from "./Button";
import Message from "./Message";
import PropTypes from "prop-types";

function Conversation({ conversationId, refreshConversations }) {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [input, setInput] = useState(null);
  const [conversation, setConversation] = useState({ messages: [] });
  // Dynamic
  const auth = useAuth();

  useEffect(() => {
    const fetchConversation = async () => {
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

          // Save current context
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
      // First, create the message
      await axios
        .post(`${API_BASE_URL}/message`, null, {
          params: {
            content: input,
            conversation_id: conversation ? conversation.id : null,
          },
          timeout: 30000,
          headers: {
            Authorization: `Bearer ${auth.userData.id_token}`,
          },
        })
        .then((res) => {
          if (!res.data) return;

          // Then, fetch the message
          const lastMessage = res.data.messages[res.data.messages.length - 1];
          let stream = "";
          const source = new EventSource(
            `${API_BASE_URL}/message/${lastMessage.id}?token=${lastMessage.token}`
          );
          source.onmessage = (e) => {
            if (e.data === "STOP") {
              source.close();
              if (!conversation.id) refreshConversations();
              return;
            }

            // Update the last message
            stream += e.data;
            replaceLastMessage({
              content: stream,
              created_at: new Date().toISOString(),
              id: uuidv4(),
              role: "system",
            });
          };
          source.onerror = (e) => {
            if (e.eventPhase === EventSource.CLOSED) {
              source.close();
            }
          };
        })
        .catch((error) => {
          console.error(error);
        });
    };

    addMessages([
      {
        content: input,
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "user",
      },
      {
        content: "Loading…",
        created_at: new Date().toISOString(),
        id: uuidv4(),
        role: "system",
      },
    ]);

    fetchMessage();

    // Reset the input
    setInput("");
  };

  return (
    <div className="conversation">
      <div className="conversation__container">
        <div className="conversation__messages">
          {conversation.messages.length == 0 && <p className="conversation__messages__empty">🔒 Private GPT</p>}
          {conversation.messages.map((message) =>
            message.content ? (
              <Message
                key={message.id}
                content={message.content}
                role={message.role}
                date={message.created_at}
              />
            ) : null
          )}
        </div>
        <form
          className="conversation__input"
          onSubmit={(e) => {
            sendMessage();
            e.preventDefault();
          }}
        >
          <textarea
            placeholder="Message"
            value={input || ""}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && input.length > 0) {
                sendMessage();
                e.preventDefault();
              }
            }}
          />
          <Button
            text="Send"
            emoji="⬆️"
            type="submit"
            disabled={!(input && input.length > 0)}
          />
        </form>
      </div>
    </div>
  );
}

Conversation.propTypes = {
  conversationId: PropTypes.string,
  refreshConversations: PropTypes.func.isRequired,
};

export default Conversation;
