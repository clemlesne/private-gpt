import "./dropdown.scss";
import PropTypes from "prop-types";

function Dropdown({ options, disabled, onChange, selected, defaultTitle }) {
  const defaultTitleKey = "title";

  const onChangeHandler = (e) => {
    const value = e.target.value;
    if (value === defaultTitleKey) return;
    onChange(value);
  };

  return (
    <select
      className="dropdown"
      disabled={disabled}
      onChange={onChangeHandler}
      defaultValue={selected ? selected : defaultTitleKey}
    >
      {!options && (
        <option selected disabled={true}>
          No options
        </option>
      )}
      {options && <option key={defaultTitleKey}>{defaultTitle}</option>}
      {options &&
        options.map((option) => (
          <option key={option.id} value={option.id} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
    </select>
  );
}

Dropdown.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.shape({
      disabled: PropTypes.bool,
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    })
  ),
  defaultTitle: PropTypes.string.isRequired,
  disabled: PropTypes.bool,
  onChange: PropTypes.func.isRequired,
  selected: PropTypes.string,
};

export default Dropdown;
