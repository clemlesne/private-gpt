import "./header.scss";
import { AddFilled, DoorFilled, EqualOffFilled, KeyFilled, Person12Filled, SearchFilled, WeatherMoonFilled, WeatherSunnyFilled } from "@fluentui/react-icons";
import { header, login, logout } from "./Utils";
import { ThemeContext, ConversationContext } from "./App";
import { useContext } from "react";
import { useMsal, useAccount, useIsAuthenticated } from "@azure/msal-react";
import { useNavigate } from "react-router-dom";
import Button from "./Button";
import Conversations from "./Conversations";

function Header() {
  // Dynamic
  const { instance, accounts, inProgress } = useMsal();
  const account = useAccount(accounts[0] || null);
  const isAuthenticated = useIsAuthenticated();
  const navigate = useNavigate();
  // React context
  const [conversations] = useContext(ConversationContext);
  const [darkTheme, setDarkTheme] = useContext(ThemeContext);

  return (
    <div className="header">
      <div className="header__actions">
        {/* This button is never disabled and this is on purpose.

        It is the central point of the application and should always be clickable. UX interviews with users showed that they were confused when the button was disabled. They thought that the application was broken. */}
        {isAuthenticated && <>
          <Button
            onClick={() => {
              header(false);
              navigate("/");
            }}
            text="New chat"
            emoji={AddFilled}
            active={true}
          />
          <Button
            onClick={() => {
              header(false);
              navigate("/search");
            }}
            text="Search"
            emoji={SearchFilled}
          />
        </>}
        <Button
          className="header__actions__toggle"
          emoji={EqualOffFilled}
          text="Menu"
          onClick={() => header() }
        />
      </div>
      <div className="header__content">
        {isAuthenticated && (
          <Conversations
            conversations={conversations}
          />
        )}
      </div>
      <small className="header__bottom">
        <div className="header__bottom__block">
          {isAuthenticated && (
            <p>
              <Person12Filled />
              {" "}Logged as{" "}
              {account.name
                ? account.name
                : "unknown name"}{" "}
              (
              {account.username
                ? account.username
                : "unknown username"}
              ).
            </p>
          )}
          {inProgress === "login" && <p>Connecting...</p>}
        </div>
        <div className="header__bottom__block">
          <span>
            App v{import.meta.env.VITE_VERSION} ({import.meta.env.MODE})
          </span>
        </div>
        <div className="header__bottom__block">
          <Button
            onClick={() => {
              header(false);
              isAuthenticated ? logout(account, instance) : login(instance);
            }}
            emoji={isAuthenticated ? DoorFilled : KeyFilled}
            loading={inProgress === "login"}
            text={isAuthenticated ? "Signout" : "Signin"}
          />
          <Button
            onClick={() => {
              header(false);
              setDarkTheme(!darkTheme);
            }}
            emoji={darkTheme ? WeatherSunnyFilled : WeatherMoonFilled}
            text={darkTheme ? "Light" : "Dark"}
          />
        </div>
      </small>
    </div>
  );
}

export default Header;
