import "./conversations.scss";
import Button from "./Button";
import Loader from "./Loader";
import moment from "moment";
import PropTypes from "prop-types";

function Conversations({
  conversations,
  selectedConversation,
  setSelectedConversation,
  conversationLoading,
}) {
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
              // Close the header on mobile, if any
              document.documentElement.classList.remove("header--open");
              // Set the conversation
              setSelectedConversation(conversation.id);
            }}
            disabled={conversation.id == selectedConversation}
          >
            {conversation.id == selectedConversation && conversationLoading && (
              <Loader />
            )}{" "}
            {conversation.title ? conversation.title : "New chat"}{" "}
          </a>
        ))}
      </>
    );
  };

  return (
    <div className="conversations">
      <div className="conversations__actions">
        {/* This button is never disabled and this is on purpose.

        It is the central point of the application and should always be clickable. UX interviews with users showed that they were confused when the button was disabled. They thought that the application was broken. */}
        <Button
          onClick={() => setSelectedConversation(null)}
          text="New chat"
          emoji="+"
          active={true}
        />
      </div>
      <h2>Your conversations</h2>
      {displayConversations("Today", groupedConversations.today)}
      {displayConversations("This week", groupedConversations.thisWeek)}
      {displayConversations("This month", groupedConversations.thisMonth)}
      {displayConversations("This year", groupedConversations.thisYear)}
      {displayConversations("Older", groupedConversations.older)}
    </div>
  );
}

Conversations.propTypes = {
  conversationLoading: PropTypes.bool.isRequired,
  conversations: PropTypes.array.isRequired,
  selectedConversation: PropTypes.string,
  setSelectedConversation: PropTypes.func.isRequired,
};

export default Conversations;
