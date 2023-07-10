import "./button.scss";
import Loader from "./Loader";
import PropTypes from "prop-types";

function Button({ disabled, onClick, text, loading, emoji, type, active, className, large }) {
  return (
    <button className={`button ${active ? "button--active" : ""} ${large ? "button--large" : ""} ${className}`} disabled={disabled} onClick={onClick} type={type ? type : "button"} aria-valuetext={text}>
      {(loading && <Loader />) || <span>{emoji}</span>}
      <span className="button__text">{text}</span>
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
  text: PropTypes.string.isRequired,
  type: PropTypes.string,
}

export default Button;
