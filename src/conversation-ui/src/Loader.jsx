import "./loader.scss";
import {
  ArrowSyncCircleFilled
} from "@fluentui/react-icons";
import PropTypes from "prop-types";

function Loader({ className }) {
  return <ArrowSyncCircleFilled className={`loader ${className}`} />;
}

Loader.propTypes = {
  className: PropTypes.string,
};

export default Loader;
