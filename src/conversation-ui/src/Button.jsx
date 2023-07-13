import "./button.scss";
import Loader from "./Loader";
import PropTypes from "prop-types";

function Button({
  active,
  className,
  disabled,
  emoji,
  large,
  loading,
  onClick,
  text,
  type,
}) {
  return (
    <button
      aria-valuetext={text}
      className={`button ${active ? "button--active" : ""} ${
        large ? "button--large" : ""
      } ${className ? className : ""}`}
      disabled={disabled}
      onClick={onClick}
      type={type ? type : "button"}
    >
      {(loading && <Loader />) || <span>{emoji}</span>}
      {text && <span className="button__text">{text}</span>}
    </button>
  );
}

Button.propTypes = {
  active: PropTypes.bool,
  className: PropTypes.string,
  disabled: PropTypes.bool,
  emoji: PropTypes.string.isRequired,
  large: PropTypes.bool,
  loading: PropTypes.bool,
  onClick: PropTypes.func,
  text: PropTypes.string,
  type: PropTypes.string,
};

export default Button;
