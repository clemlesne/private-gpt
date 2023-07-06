import "./search.scss";
import { client } from "./Utils";
import { useAuth } from "oidc-react";
import { useState, useMemo, useRef } from "react";
import Button from "./Button";
import Message from "./Message";

function Search() {
  // State
  const [input, setInput] = useState(null);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  // Ref
  const self = useRef(null);
  // Dynamic
  const auth = useAuth();

  const fetchSearch = async () => {
    if (!auth.userData) return;
    if (!input || input.length === 0) return;

    setLoading(true);

    await client
      .get("/message", {
        params: {
          q: input,
        },
        timeout: 10_000,
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

  // Hide search when clicking outside of the container
  useMemo(() => {
    const handleClickOutside = (e) => {
      if (self.current && !self.current.contains(e.target)) {
        setMessages([]);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [self]);

  const inputKeyHandler = (e) => {
    // Ability to search with enter, and add a new line with shift+enter
    if (e.key === "Enter" && !e.shiftKey && input.length > 0) {
      fetchSearch();
      e.preventDefault();
    }
  };

  return (
    <div ref={self} className="search">
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
            e.preventDefault();
          }
        }}
      >
        <input
          placeholder="Search messages across all conversations"
          value={input || ""}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={inputKeyHandler}
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
  );
}

export default Search;
