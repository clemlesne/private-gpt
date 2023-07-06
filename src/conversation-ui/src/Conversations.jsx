import "./conversations.scss";
import { ConversationContext } from "./App";
import { header } from "./Utils";
import { useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import moment from "moment";

function Conversations() {
  // Browser context
  const { conversationId } = useParams();
  // Dynamic
  const navigate = useNavigate();
  // React context
  const [conversations] = useContext(ConversationContext);

  const groupedConversations = conversations.reduce(
    (acc, conversation) => {
      const now = moment();
      const created_at = moment(conversation.created_at);

      if (now.isSame(created_at, "day")) {
        acc.today.push(conversation);
      } else if (now.isSame(created_at, "week")) {
        acc.thisWeek.push(conversation);
      } else if (now.isSame(created_at, "month")) {
        acc.thisMonth.push(conversation);
      } else if (now.isSame(created_at, "year")) {
        acc.thisYear.push(conversation);
      } else {
        acc.older.push(conversation);
      }

      return acc;
    },
    { today: [], thisWeek: [], thisMonth: [], thisYear: [], older: [] }
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
              header(false);
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
      {displayConversations("This week", groupedConversations.thisWeek)}
      {displayConversations("This month", groupedConversations.thisMonth)}
      {displayConversations("This year", groupedConversations.thisYear)}
      {displayConversations("Older", groupedConversations.older)}
    </div>
  );
}

export default Conversations;
