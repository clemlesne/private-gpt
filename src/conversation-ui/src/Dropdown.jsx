import "./dropdown.scss";
import PropTypes from "prop-types";

function Dropdown({ options, disabled, onChange, selected, defaultTitle }) {
  const defaultTitleKey = "title";

  // Group options by group field
  const groupedOptions = options
    ? options.reduce((acc, option) => {
        if (!acc[option.group]) {
          acc[option.group] = [];
        }
        acc[option.group].push(option);
        return acc;
      }, {})
    : null;

  // Sort groups alphabetically
  if (groupedOptions) {
    Object.keys(groupedOptions)
      .sort()
      .forEach((key) => {
        var value = groupedOptions[key];
        delete groupedOptions[key];
        groupedOptions[key] = value;
      });
  }

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
      {!groupedOptions && (
        <option selected disabled={true}>
          No options
        </option>
      )}
      {groupedOptions && <option key={defaultTitleKey}>{defaultTitle}</option>}
      {groupedOptions &&
        Object.keys(groupedOptions).map((group) => (
          <optgroup key={group} label={group}>
            {groupedOptions[group].map((option) => (
              <option
                disabled={option.disabled}
                key={option.id}
                value={option.id}
              >
                {option.label}
              </option>
            ))}
          </optgroup>
        ))}
    </select>
  );
}

Dropdown.propTypes = {
  options: PropTypes.arrayOf(
    PropTypes.shape({
      disabled: PropTypes.bool,
      group: PropTypes.string.isRequired,
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
