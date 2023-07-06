import "./message.scss";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { PrismAsync as SyntaxHighlighter } from "react-syntax-highlighter";
import { ThemeContext } from "./App";
import { useState, useRef, useContext } from "react";
import moment from "moment";
import PropTypes from "prop-types";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGemoji from "remark-gemoji";
import remarkGfm from "remark-gfm";
import remarkImages from "remark-images";
import remarkMath from "remark-math";
import remarkNormalizeHeadings from "remark-normalize-headings";

function Message({
  content,
  date,
  role,
  defaultDisplaySub = false,
  error = false,
  secret = false,
}) {
  // State
  const [displaySub, setDisplaySub] = useState(defaultDisplaySub);
  // Refs
  const httpContent = useRef(null);
  // React context
  const [darkTheme,] = useContext(ThemeContext);

  const clipboardHandler = (e) => {
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
    <div className={`message message--${role} ${error ? "message--error" : ""}`}>
      <div
        ref={httpContent}
        className="message__content"
        onClick={() => setDisplaySub(!displaySub)}
        onDoubleClick={clipboardHandler}
      >
        { }
        <ReactMarkdown
          linkTarget="_blank"
          remarkPlugins={[
            remarkGfm,
            remarkBreaks,
            remarkMath,
            remarkGemoji,
            remarkNormalizeHeadings,
            remarkImages,
          ]}
          children={content}
          components={{
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || "");
              return !inline && match ? (
                <SyntaxHighlighter
                  {...props}
                  children={String(children).replace(/\n$/, "")}
                  customStyle={{
                    borderRadius: "var(--radius)",
                  }}
                  language={match[1]}
                  PreTag="div"
                  showLineNumbers={true}
                  style={darkTheme ? oneDark : oneLight}
                />
              ) : (
                <code {...props} className={className}>
                  {children}
                </code>
              );
            },
          }}
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
  role: PropTypes.string.isRequired,
  defaultDisplaySub: PropTypes.bool,
  error: PropTypes.bool,
  secret: PropTypes.bool,
};

export default Message;
