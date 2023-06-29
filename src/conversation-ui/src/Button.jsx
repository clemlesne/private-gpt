import "./button.scss";
import Loader from "./Loader";
import PropTypes from "prop-types"

function Button({ disabled, onClick, text, loading, emoji, type, active }) {
  return (
    <button className={`button ${active ? "button--active" : undefined}`} disabled={disabled} onClick={onClick} type={type ? type : "button"}>
      {(loading && <Loader />) || emoji && <span>{emoji}</span>}
      <span>{text}</span>
    </button>
  );
}

Button.propTypes = {
  active: PropTypes.bool,
  disabled: PropTypes.bool,
  emoji: PropTypes.string,
  loading: PropTypes.bool,
  onClick: PropTypes.func,
  text: PropTypes.string.isRequired,
  type: PropTypes.string,
}

export default Button;