import "./conversation.scss"
import { useState, useMemo } from "react";
import { v4 as uuidv4 } from 'uuid';
import axios from "axios";
import Button from "./Button";
import Message from "./Message";
import PropTypes from "prop-types";

function Conversation({ conversation: initialConversation, F, fetchConversations }) {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState(null);
  const [conversation, setConversation] = useState(initialConversation);

  // Update the messages when the conversation changes
  useMemo(() => {
    setConversation(initialConversation);
    setMessages(initialConversation ? initialConversation.messages : []);
  }, [initialConversation]);

  const sendMessage = () => {
    let localMessages = [...messages];

    const addMessages = (newMessages) => {
      localMessages = [...localMessages, ...newMessages];
      setMessages(localMessages);
    };

    const replaceLastMessage = (newMessage) => {
      const tmp = [...localMessages];
      tmp[tmp.length - 1] = newMessage;
      localMessages = tmp;
      setMessages(localMessages);
    };

    const fetchMessage = async () => {
      // First, create the message
      await axios
        .post(`${API_BASE_URL}/message`, null, {
          params: {
            user: F,
            content: input,
            conversation_id: conversation ? conversation.id : null,
          },
          timeout: 30000,
        })
        .then((res) => {
          if (!res.data) return

          // Reload conversation list if the conversation is new
          if(!conversation) fetchConversations();

          // Save current context
          setConversation(res.data);

          // Then, fetch the message
          const lastMessage = res.data.messages[res.data.messages.length - 1];
          let stream = "";
          const source = new EventSource(`${API_BASE_URL}/message/${lastMessage.id}?user=${F}`);
          source.onopen = () => {
            if(!conversation) fetchConversations();
          };
          source.onmessage = (e) => {
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
          }
        })
        .catch((error) => {
          console.error(error);
        });
    };

    addMessages([{
      content: input,
      created_at: new Date().toISOString(),
      id: uuidv4(),
      role: "user",
    }, {
      content: "Loading…",
      created_at: new Date().toISOString(),
      id: uuidv4(),
      role: "system",
    }]);

    fetchMessage();

    // Reset the input
    setInput("");
  };

  return (
    <div className="conversation">
      <div className="conversation__container">
        <div className="conversation__messages">
          {messages.map((message) => (
            message.content ? <Message key={message.id} content={message.content} role={message.role} date={message.created_at} /> : null
          ))}
        </div>
        <form className="conversation__input" onSubmit={(e) => sendMessage(input) && e.preventDefault()}>
          <textarea placeholder="Message" value={input || ""} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => (e.key === "Enter" && !e.shiftKey) && sendMessage(input) && e.preventDefault()} />
          <Button text="Send" emoji="🧠" type="submit" />
        </form>
      </div>
    </div>
  )
}

Conversation.propTypes = {
  conversation: PropTypes.object,
  F: PropTypes.string,
  fetchConversations: PropTypes.func.isRequired,
  setSelectedConversation: PropTypes.func.isRequired,
}

export default Conversation
