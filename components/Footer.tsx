import { GithubIcon } from "./icons";

export function Footer() {
  return (
    <footer className="mt-10 flex justify-center border-t border-line pt-6 pb-10">
      <a
        href="https://github.com/HassanNazar72"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-2 hover:text-ink hover:underline"
      >
        <GithubIcon /> HassanNazar72
      </a>
    </footer>
  );
}
