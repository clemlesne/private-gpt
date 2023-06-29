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
  const groupedConversations = conversations.reduce((acc, conversation) => {
    const now = moment();
    const created_at = moment(conversation.created_at);
    const diff = now.diff(created_at, "days");

    if (diff === 0) {
      acc.today.push(conversation);
    } else if (diff <= 7) {
      acc.thisWeek.push(conversation);
    } else if (diff <= 30) {
      acc.thisMonth.push(conversation);
    } else if (diff <= 365) {
      acc.thisYear.push(conversation);
    } else {
      acc.older.push(conversation);
    }

    return acc;
  }, { today: [], thisWeek: [], thisMonth: [], thisYear: [], older: [] });

  // Sort conversations by date, from newest to oldest
  const sortedConversations = [
    ...groupedConversations.today,
    ...groupedConversations.thisWeek,
    ...groupedConversations.thisMonth,
    ...groupedConversations.thisYear,
    ...groupedConversations.older,
  ];

  const displayConversations = (title, arr) => {
    if (arr.length === 0) return;
    return (
      <>
        <h3>{title}</h3>
        {arr.map((conversation) => (
          <a
            key={conversation.id}
            onClick={() => setSelectedConversation(conversation.id)}
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
  }

  return (
    <div className="conversations">
      {/* This button is never disabled and this is on purpose.

      It is the central point of the application and should always be clickable. UX interviews with users showed that they were confused when the button was disabled. They thought that the application was broken. */}
      <Button
        onClick={() => setSelectedConversation(null)}
        text="New chat"
        emoji="+"
        active={true}
      />
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
