import "./titlebar.scss";
import { IS_TAURI } from "./Utils";

function Titlebar() {
  if (!IS_TAURI) {
    return null;
  }

  // Get the title of the current window in HTML
  const title = document.querySelector("title").innerHTML;

  return (
    <div data-tauri-drag-region className="titlebar">
      {title}
    </div>
  );
}

export default Titlebar;
