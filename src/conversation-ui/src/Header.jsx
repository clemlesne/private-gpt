import "./header.scss";
import { header } from "./Utils";
import { ThemeContext, ConversationContext } from "./App";
import { useAuth } from "oidc-react";
import { useContext } from "react";
import { useNavigate, Link } from "react-router-dom";
import Button from "./Button";
import Conversations from "./Conversations";

function Header() {
  // Dynamic
  const auth = useAuth();
  const navigate = useNavigate();
  // React context
  const [conversations] = useContext(ConversationContext);
  const [darkTheme, setDarkTheme] = useContext(ThemeContext);

  return (
    <div className="header">
      <div className="header__top">
        <Link to="/" className="a--unstyled">
          <h1>🔒 Private GPT</h1>
        </Link>
        <Button
          className="header__top__toggle"
          emoji="="
          text="Menu"
          onClick={() => header() }
        />
      </div>
      {auth.userData && <div className="header__actions">
        {/* This button is never disabled and this is on purpose.

        It is the central point of the application and should always be clickable. UX interviews with users showed that they were confused when the button was disabled. They thought that the application was broken. */}
        <Button
          onClick={() => {
            header(false);
            navigate("/");
          }}
          text="New chat"
          emoji="+"
          active={true}
        />
        <Button
          onClick={() => {
            header(false);
            navigate("/search");
          }}
          text="Search"
          emoji="🔍"
        />
      </div>}
      <div className="header__content">
        {auth.userData && (
          <Conversations
            conversations={conversations}
          />
        )}
      </div>
      <small className="header__bottom">
        <div className="header__bottom__block">
          {auth.userData && (
            <p>
              Logged as{" "}
              {auth.userData.profile.name
                ? auth.userData.profile.name
                : "unknown name"}{" "}
              (
              {auth.userData.profile.email
                ? auth.userData.profile.email
                : "unknown email"}
              ).
            </p>
          )}
          {auth.isLoading && <p>Connecting...</p>}
        </div>
        <div className="header__bottom__block">
          <span>
            {import.meta.env.VITE_VERSION} ({import.meta.env.MODE})
          </span>
        </div>
        <div className="header__bottom__block">
          <Button
            onClick={() => {
              header(false);
              auth.userData ? auth.signOut() : auth.signIn()
            }}
            emoji={auth.userData ? "🚪" : "🔑"}
            loading={auth.isLoading}
            text={auth.userData ? "Signout" : "Signin"}
          />
          <Button
            onClick={() => {
              header(false);
              setDarkTheme(!darkTheme);
            }}
            emoji={darkTheme ? "☀️" : "🌕"}
            text={darkTheme ? "Light" : "Dark"}
          />
        </div>
      </small>
    </div>
  );
}

export default Header;
