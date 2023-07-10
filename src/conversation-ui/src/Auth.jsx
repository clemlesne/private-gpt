import "./auth.scss";
import Loader from "./Loader";

function Auth() {
  return (
    <div className="auth">
      <h2>Authenticating</h2>
      <Loader />
    </div>
  );
}

export default Auth;
