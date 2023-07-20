import "./message.scss";
import { notification } from "./Utils";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/esm/styles/prism";
import { PrismAsync as SyntaxHighlighter } from "react-syntax-highlighter";
import { ThemeContext } from "./App";
import { useState, useRef, useContext } from "react";
import Button from "./Button";
import moment from "moment";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGemoji from "remark-gemoji";
import remarkGfm from "remark-gfm";
import remarkImages from "remark-images";
import remarkMath from "remark-math";
import remarkNormalizeHeadings from "remark-normalize-headings";
import { AddFilled, ClipboardRegular } from "@fluentui/react-icons";

function Message({
  content,
  date,
  defaultDisplaySub = false,
  error = false,
  role,
  secret = false,
}) {
  // State
  const [displaySub, setDisplaySub] = useState(defaultDisplaySub);
  const [displayActions, setDisplayActions] = useState(false);
  const [mouseIn, setMouseIn] = useState(false);
  // Refs
  const httpContent = useRef(null);
  // React context
  const [darkTheme] = useContext(ThemeContext);

  const clipboardHandler = () => {
    // Copy to clipboard
    navigator.clipboard.writeText(content);
    // Notification
    notification("Copied to clipboard");
    // Animation feedback
    const opacity = window.getComputedStyle(httpContent.current).opacity;
    httpContent.current.style.opacity = opacity / 2;
    setTimeout(() => {
      httpContent.current.style.opacity = opacity;
    }, 250);
  };

  return (
    <div
      className={`message message--${role} ${error ? "message--error" : ""}`}
      onMouseEnter={() => {
        setMouseIn(true);
        setDisplayActions(true);
      }}
      onMouseLeave={() => {
        setMouseIn(false);
        setDisplayActions(false);
      }}
    >
      <div
        className="message__content"
        onClick={() => {
          if (!mouseIn) setDisplayActions(!displayActions);
        }}
        ref={httpContent}
      >
        <ReactMarkdown
          linkTarget="_blank"
          remarkPlugins={[
            remarkBreaks,
            remarkGemoji,
            remarkGfm,
            remarkImages,
            remarkMath,
            remarkNormalizeHeadings,
          ]}
          children={content}
          components={{
            code({ node, inline, className, children, ...props }) {
              if (!inline) {
                const match = /language-(\w+)/.exec(className || "");
                const language = match ? match[1] : null;
                return (
                  <SyntaxHighlighter
                    {...props}
                    children={String(children).replace(/\n$/, "")}
                    customStyle={{
                      borderRadius: "var(--radius)",
                      margin: "none",
                      padding: "var(--message-padding-v) var(--message-padding-h)",
                    }}
                    language={language}
                    PreTag="div"
                    showLineNumbers={true}
                    style={darkTheme ? oneDark : oneLight}
                  />
                );
              } else {
                return (
                  <code {...props} className={className}>
                    {children}
                  </code>
                );
              }
            },
          }}
        />
      </div>
      {displaySub && (
        <small className="message__sub">
          {secret && <span>Temporary, </span>}
          <span>{moment.utc(date).fromNow()}</span>
        </small>
      )}
      {displayActions && (
        <small className="message__actions">
          <Button emoji={ClipboardRegular} onClick={clipboardHandler} text="Copy" />
          <Button
            emoji={AddFilled}
            onClick={() => setDisplaySub(!displaySub)}
            text="Details"
          />
        </small>
      )}
    </div>
  );
}

Message.propTypes = {
  content: PropTypes.string.isRequired,
  date: PropTypes.string.isRequired,
  defaultDisplaySub: PropTypes.bool,
  error: PropTypes.bool,
  role: PropTypes.string.isRequired,
  secret: PropTypes.bool,
};

export default Message;
