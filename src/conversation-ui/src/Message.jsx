import "./message.scss";
import moment from "moment";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";

function Message({ content, role, date }) {
  // State
  const [displaySub, setDisplaySub] = useState(false);

  return (
    <div className={`message ${role == "system" ? "message--system" : ""}`}>
      <div className="message__content" onClick={() => setDisplaySub(!displaySub)}>
        { /* eslint-disable-next-line react/no-children-prop */ }
        <ReactMarkdown linkTarget="_blank" remarkPlugins={[remarkGfm]} children={content} />
      </div>
      {displaySub && <div className="message__sub">
        <span>{moment(date).format("lll")}</span>
      </div>}
    </div>
  )
}

Message.propTypes = {
  content: PropTypes.string.isRequired,
  role: PropTypes.string.isRequired,
  date: PropTypes.string.isRequired,
}

export default Message
