import "./conversations.scss"
import Button from "./Button";
import PropTypes from "prop-types";

function Conversations({ conversations, selectedConversation, setSelectedConversation, conversationLoading }) {
  return (
    <div className="conversations">
      <Button onClick={() => setSelectedConversation(null)} text="New chat" emoji="+" disabled={selectedConversation == null} active={true} />
      <p>Conversation history:</p>
      {conversations.map((conversation) => (
        <Button key={conversation.id} onClick={() => setSelectedConversation(conversation.id)} text={conversation.title ? conversation.title : "New chat"} disabled={conversation.id == selectedConversation} loading={conversation.id == selectedConversation && conversationLoading} />
      ))}
    </div>
  )
}

Conversations.propTypes = {
  conversationLoading: PropTypes.bool.isRequired,
  conversations: PropTypes.array.isRequired,
  selectedConversation: PropTypes.string,
  setSelectedConversation: PropTypes.func.isRequired,
}

export default Conversations
