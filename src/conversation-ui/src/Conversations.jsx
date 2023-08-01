import "./conversations.scss";
import { ConversationContext, HeaderOpenContext } from "./App";
import { useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import moment from "moment";

function Conversations() {
  // Browser context
  const { conversationId } = useParams();
  // Dynamic
  const navigate = useNavigate();
  // React context
  const [, setHeaderOpen] = useContext(HeaderOpenContext);
  const [conversations] = useContext(ConversationContext);

  const groupedConversations = conversations.reduce(
    (acc, conversation) => {
      const now = moment();
      const created_at = moment(conversation.created_at);

      if (now.isSame(created_at, "day")) {
        acc.today.push(conversation);
      } else if (now.diff(created_at, "week") == 0) {
        acc.weekAgo.push(conversation);
      } else if (now.diff(created_at, "month") == 0) {
        acc.monthAgo.push(conversation);
      } else if (now.diff(created_at, "year") == 0) {
        acc.yearAgo.push(conversation);
      } else {
        acc.older.push(conversation);
      }

      return acc;
    },
    { today: [], weekAgo: [], monthAgo: [], yearAgo: [], older: [] }
  );

  const displayConversations = (title, arr) => {
    if (arr.length === 0) return;
    return (
      <>
        <h3>{title}</h3>
        {arr.map((conversation) => (
          <a
            key={conversation.id}
            onClick={() => {
              setHeaderOpen(false);
              navigate(`/conversation/${conversation.id}`);
            }}
            disabled={conversation.id == conversationId}
          >
            {conversation.title ? conversation.title : "New chat"}{" "}
          </a>
        ))}
      </>
    );
  };

  return (
    <div className="conversations">
      <h2>Your conversations</h2>
      { conversations.length === 0 && <p>No conversations yet.</p>}
      {displayConversations("Today", groupedConversations.today)}
      {displayConversations("A week ago", groupedConversations.weekAgo)}
      {displayConversations("A month ago", groupedConversations.monthAgo)}
      {displayConversations("A year ago", groupedConversations.yearAgo)}
      {displayConversations("Older", groupedConversations.older)}
    </div>
  );
}

export default Conversations;
