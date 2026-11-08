import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Fonts ship with the app (no font service): Inter for the interface, Inter Tight
// for headings and score numbers. The browser downloads only the subsets in use.
import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/inter-tight/wght.css";
import "./styles/tokens.css";
import "./styles/overlay-tokens.css";
import "./styles/base.css";
import "./ui/ui.css";
import "./styles/screens.css";
import "./styles/result.css";
import { App } from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("#root element missing");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
