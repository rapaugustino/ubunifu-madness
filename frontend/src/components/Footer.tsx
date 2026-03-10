import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-card-border py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-muted">
          <div className="w-6 h-6 rounded bg-accent flex items-center justify-center text-xs font-bold text-white">
            UM
          </div>
          Ubunifu Madness &copy; 2026
        </div>
        <div className="flex items-center gap-3 text-xs text-muted flex-wrap justify-center">
          <Link href="/about" className="hover:text-foreground transition-colors">
            How It Works
          </Link>
          <span>&middot;</span>
          <Link href="/terms" className="hover:text-foreground transition-colors">
            Terms &amp; Disclaimers
          </Link>
          <span>&middot;</span>
          <a
            href="https://github.com/rapaugustino"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            GitHub
          </a>
          <span>&middot;</span>
          <span>
            Data:{" "}
            <a
              href="https://www.kaggle.com/competitions/march-machine-learning-mania-2026/overview"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent/70 hover:text-accent transition-colors"
            >
              Kaggle
            </a>
            {" "}(CC BY 4.0) &middot; ESPN
          </span>
        </div>
      </div>
    </footer>
  );
}
