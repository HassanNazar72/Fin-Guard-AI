import { Dashboard } from "@/components/Dashboard";
import { Footer } from "@/components/Footer";
import { GithubIcon, ShieldIcon } from "@/components/icons";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
      <header className="mb-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-ink">
            <ShieldIcon width={20} height={20} />
          </span>
          <div>
            <h1 className="text-lg font-semibold leading-tight tracking-tight text-ink">FinGuard AI</h1>
            <p className="text-xs text-muted">Autonomous Financial Statement Analyst</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="https://github.com/HassanNazar72"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden h-9 items-center gap-1.5 rounded-full border border-line bg-card px-3 text-xs font-medium text-ink-2 hover:text-ink sm:inline-flex"
          >
            <GithubIcon /> HassanNazar72
          </a>
          <ThemeToggle />
        </div>
      </header>
      <Dashboard />
      <Footer />
    </main>
  );
}
