import "./conversations.scss"
import PropTypes from "prop-types";
import Button from "./Button";

function Conversations({ conversations, selectedConversation, setSelectedConversation }) {
  return (
    <div className="conversations">
      <Button onClick={() => setSelectedConversation(null)} text="New conversation" emoji="+" disabled={selectedConversation == null} />
      <p>Conversation history:</p>
      {conversations.map((conversation) => (
        <Button key={conversation.id} onClick={() => setSelectedConversation(conversation.id)} text={conversation.title ? conversation.title : "No title yet"} disabled={conversation.id == selectedConversation} />
      ))}
    </div>
  )
}

Conversations.propTypes = {
  conversations: PropTypes.array.isRequired,
  selectedConversation: PropTypes.string,
  setSelectedConversation: PropTypes.func.isRequired,
}

export default Conversations
