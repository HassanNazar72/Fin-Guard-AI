"use client";

import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "./icons";

type Theme = "light" | "dark";
const STORAGE_KEY = "finguard-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setTheme(current === "dark" ? "dark" : "light");
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage blocked (private mode): the toggle still works for this visit */
    }
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line bg-card text-ink-2 transition hover:text-ink"
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      title="Toggle theme"
    >
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
