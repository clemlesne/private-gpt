import "./header.scss";
import { AddFilled, ArrowDownFilled, ArrowUpFilled, DoorFilled, KeyFilled, SearchFilled, WeatherMoonFilled, WeatherSunnyFilled } from "@fluentui/react-icons";
import { login, logout } from "./Utils";
import { ThemeContext, ConversationContext, HeaderOpenContext } from "./App";
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
  const [headerOpen, setHeaderOpen] = useContext(HeaderOpenContext);

  return (
    <div className="header">
      <div className="header__actions">
        {/* This button is never disabled and this is on purpose.

        It is the central point of the application and should always be clickable. UX interviews with users showed that they were confused when the button was disabled. They thought that the application was broken. */}
        {isAuthenticated && <>
          <Button
            onClick={() => {
              setHeaderOpen(false);
              navigate("/");
            }}
            text="New chat"
            emoji={AddFilled}
            active={true}
          />
          <Button
            onClick={() => {
              setHeaderOpen(false);
              navigate("/search");
            }}
            text="Search"
            emoji={SearchFilled}
          />
        </>}
        <Button
          className="header__actions__toggle"
          emoji={headerOpen ? ArrowUpFilled : ArrowDownFilled}
          text="Menu"
          onClick={() => setHeaderOpen(!headerOpen) }
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
          <Button
            onClick={() => {
              setHeaderOpen(false);
              isAuthenticated ? logout(account, instance) : login(instance);
            }}
            emoji={isAuthenticated ? DoorFilled : KeyFilled}
            loading={inProgress === "login"}
            text={isAuthenticated ? "Signout" : "Signin"}
          />
          <Button
            onClick={() => {
              setHeaderOpen(false);
              setDarkTheme(!darkTheme);
            }}
            emoji={darkTheme ? WeatherSunnyFilled : WeatherMoonFilled}
            text={darkTheme ? "Light" : "Dark"}
          />
        </div>
        <div className="header__bottom__block">
          {isAuthenticated && (
            <p>
              Logged as{" "}
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
            App v{import.meta.env.VITE_VERSION || "0.0.0-unknown"} ({import.meta.env.MODE})
          </span>
        </div>
      </small>
    </div>
  );
}

export default Header;
