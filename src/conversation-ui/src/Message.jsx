import "./message.scss";
import moment from "moment";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState, useRef } from "react";

function Message({ content, role, date }) {
  // State
  const [displaySub, setDisplaySub] = useState(false);
  // Refs
  const httpContent = useRef(null);

  const copyToClipboard = (e) => {
    e.preventDefault();
    // Copy to clipboard
    navigator.clipboard.writeText(content);
    // Animation feedback
    const opacity = window.getComputedStyle(httpContent.current).opacity;
    httpContent.current.style.opacity = opacity / 2;
    setTimeout(() => {
      httpContent.current.style.opacity = opacity;
    }, 250);
  };

  return (
    <div className={`message message--${role}`}>
      <div
        ref={httpContent}
        className="message__content"
        onClick={() => setDisplaySub(!displaySub)}
        onDoubleClick={copyToClipboard}
      >
        {/* eslint-disable-next-line react/no-children-prop */}
        <ReactMarkdown
          linkTarget="_blank"
          remarkPlugins={[remarkGfm]}
          children={content}
        />
      </div>
      {displaySub && (
        <small className="message__sub">
          <span>{moment(date).fromNow()}</span>
        </small>
      )}
    </div>
  );
}

Message.propTypes = {
  content: PropTypes.string.isRequired,
  role: PropTypes.string.isRequired,
  date: PropTypes.string.isRequired,
};

export default Message;
