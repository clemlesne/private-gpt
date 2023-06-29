import "./search.scss";
import { useAuth } from "oidc-react";
import { useState, useMemo, useRef } from "react";
import axios from "axios";
import Button from "./Button";
import Message from "./Message";
import PropTypes from "prop-types";

function Search({ setHideConversation }) {
  // Constants
  const API_BASE_URL = "http://127.0.0.1:8081";
  // State
  const [input, setInput] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  // Ref
  const self = useRef(null);
  // Dynamic
  const auth = useAuth();

  const fetchSearch = async () => {
    if (!auth.userData) return;
    if (!input || input.length === 0) return;

    setLoading(true);

    await axios
      .get(`${API_BASE_URL}/message`, {
        params: {
          q: input,
        },
        timeout: 30000,
        headers: {
          Authorization: `Bearer ${auth.userData.id_token}`,
        },
      })
      .then((res) => {
        if (!res.data) return;
        setMessages(res.data.answers);
      })
      .catch((error) => {
        console.error(error);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useMemo(() => {
    fetchSearch();
  }, [auth]);

  useMemo(() => {
    setHideConversation(messages.length > 0);
  }, [messages]);

  // Hide search when clicking outside of the container
  useMemo(() => {
    const handleClickOutside = (e) => {
      if (self.current &&
      !self.current.contains(e.target)) {
        setMessages([]);
        setHideConversation(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [self]);

  return (
    <div className="search">
      <div ref={self} className="search__container">
        <form
          className="search__input"
          onSubmit={(e) => {
            fetchSearch();
            e.preventDefault();
          }}
          onKeyDown={(e) => {
            // Ability to close search with escape
            if (e.key === "Escape") {
              setMessages([]);
              setHideConversation(false);
              e.preventDefault();
            }
          }}
        >
          <input
            placeholder="Search messages across all conversations"
            value={input || ""}
            onChange={(e) => {
              setInput(e.target.value);
            }}
            onKeyDown={(e) => {
              // Ability to insert new line with shift + enter
              if (e.key === "Enter" && !e.shiftKey && input.length > 0) {
                fetchSearch();
                e.preventDefault();
              }
            }}
          />
          <Button
            disabled={!(input && input.length > 0)}
            emoji="🔍"
            loading={loading}
            text="Search"
            type="submit"
          />
        </form>
        {messages.length > 0 && (
          <div className="search__messages">
            <h2 className="search__title">Search results</h2>
            {messages.map((message) => (
              <Message
                content={message.data.content}
                date={message.data.created_at}
                defaultDisplaySub={true}
                key={message.data.id}
                role={message.data.role}
                secret={message.secret}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

Search.propTypes = {
  setHideConversation: PropTypes.func.isRequired,
};

export default Search;
