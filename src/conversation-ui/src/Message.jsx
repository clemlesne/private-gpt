import "./message.scss";
import { useState, useRef } from "react";
import moment from "moment";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGemoji from "remark-gemoji";
import remarkGfm from "remark-gfm";
import remarkImages from "remark-images";
import remarkMath from "remark-math";
import remarkNormalizeHeadings from "remark-normalize-headings";

function Message({ content, role, date, secret, defaultDisplaySub = false }) {
  // State
  const [displaySub, setDisplaySub] = useState(defaultDisplaySub);
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
          remarkPlugins={[remarkGfm, remarkBreaks, remarkMath, remarkGemoji, remarkNormalizeHeadings, remarkImages]}
          children={content}
        />
      </div>
      {displaySub && (
        <small className="message__sub">
          {secret && <span>Temporary, </span>}
          <span>{moment(date).fromNow()}</span>
        </small>
      )}
    </div>
  );
}

Message.propTypes = {
  content: PropTypes.string.isRequired,
  date: PropTypes.string.isRequired,
  defaultDisplaySub: PropTypes.bool,
  role: PropTypes.string.isRequired,
  secret: PropTypes.bool.isRequired,
};

export default Message;
