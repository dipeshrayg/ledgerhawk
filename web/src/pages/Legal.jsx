import { Link } from "react-router-dom";

function LegalPage({ title, updated, children }) {
  return (
    <div className="min-h-screen bg-paper font-sans text-ink dark:bg-paper-dark dark:text-ink-dark">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-ink focus:px-4 focus:py-2 focus:text-paper dark:focus:bg-ink-dark dark:focus:text-paper-dark"
      >
        Skip to main content
      </a>
      <header className="border-b border-ink/10 dark:border-ink-dark/10">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4 sm:px-8">
          <Link to="/" className="font-display text-lg font-bold tracking-tight">LedgerHawk</Link>
          <Link
            to="/"
            className="text-xs font-semibold uppercase tracking-widest text-ink/60 hover:text-ink dark:text-ink-dark/60 dark:hover:text-ink-dark"
          >
            Back home
          </Link>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
        <h1 className="font-display text-3xl font-bold uppercase tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-3 text-xs uppercase tracking-widest text-ink/50 dark:text-ink-dark/50">
          Last updated {updated}
        </p>
        <div className="prose-legal mt-10 space-y-6 text-base leading-relaxed text-ink/80 dark:text-ink-dark/80">
          {children}
        </div>
      </main>

      <footer className="border-t border-ink/10 px-5 py-10 text-center text-xs uppercase tracking-widest text-ink/50 dark:border-ink-dark/10 dark:text-ink-dark/50 sm:px-8">
        © 2026 Dipesh Ray. MIT licensed.
      </footer>
    </div>
  );
}

export function Terms() {
  return (
    <LegalPage title="Terms of use" updated="July 2026">
      <p>
        LedgerHawk is an open-source demo project. There's no account to create, nothing to buy, and
        no service-level agreement, because there's no paid service here: just a public GitHub
        repository and a static demo site built from it.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">What you're looking at</h2>
      <p>
        The live site at ledgerhawk's GitHub Pages address is a static build reconciling a seeded,
        entirely fictional dataset: five made-up vendors, synthetic contracts, and invented invoices.
        No real company, contract, or invoice is represented anywhere on this site. Any resemblance to
        a real vendor is coincidental.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">Using the code</h2>
      <p>
        The source is MIT-licensed. You can run it, fork it, modify it, and build on it, provided you
        keep the copyright notice attached, per the license terms in the repository's{" "}
        <a href="https://github.com/dipeshrayg/ledgerhawk/blob/main/LICENSE" className="text-accent dark:text-accent-dark underline">
          LICENSE
        </a>{" "}
        file.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">No warranty</h2>
      <p>
        This is demo software provided as-is, with no warranty of any kind, and none of its output
        (findings, dispute letters, forecasts, negotiation emails) should be treated as legal or
        financial advice. If you run this against your own real contracts and invoices, you're
        responsible for verifying the results yourself before acting on them.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">Contact</h2>
      <p>
        Questions go to{" "}
        <a href="https://github.com/dipeshrayg" className="text-accent dark:text-accent-dark underline">
          github.com/dipeshrayg
        </a>{" "}
        or the repository's issue tracker.
      </p>
    </LegalPage>
  );
}

export function Privacy() {
  return (
    <LegalPage title="Privacy policy" updated="July 2026">
      <p>
        The short version: this site doesn't collect anything from you, because there's nothing here
        for it to collect. There's no sign-up, no account, no form that sends your information
        anywhere.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">The live demo site</h2>
      <p>
        The deployed site is a static build with no backend server. Every screen, including the Audit
        Copilot chat, runs entirely in your browser against a pre-rendered, fictional dataset bundled
        into the site itself. Anything you type into the copilot's chat box is processed by JavaScript
        running on your own device and is never sent to a server, logged, or stored anywhere; it
        disappears the moment you close or refresh the tab.
      </p>
      <p>
        The site is hosted on GitHub Pages. GitHub, as the hosting provider, may log standard web
        server access data (like any host does) under its own privacy practices, which are outside
        this project's control. This project itself adds no analytics, tracking pixels, or third-party
        scripts of its own.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">Running it yourself</h2>
      <p>
        If you clone the repository and run the real backend locally (<code>./run.sh</code>), any
        contract or invoice data you feed it stays on your own machine, in a local SQLite file. Nothing
        is sent to a remote server unless you configure your own LLM API key, in which case whatever
        text you send to that provider is subject to that provider's own privacy policy, not this
        project's.
      </p>
      <h2 className="font-display pt-4 text-xl font-bold uppercase tracking-tight">Changes</h2>
      <p>
        If this policy ever needs to change (for example, if a future version of the demo adds real
        data storage), this page will be updated and the date at the top will reflect it.
      </p>
    </LegalPage>
  );
}

export function Cookies() {
  return (
    <LegalPage title="Cookie policy" updated="July 2026">
      <p>
        This site does not set any cookies of its own. No tracking cookies, no analytics cookies, no
        preference cookies: nothing.
      </p>
      <p>
        The only client-side storage this site's own code uses is ordinary in-memory browser state
        (React component state) for things like which tab you're viewing or what you've typed into the
        Audit Copilot chat box. That state lives only for the current page load and is cleared the
        moment you refresh or close the tab; none of it is written to cookies, local storage, or any
        server.
      </p>
      <p>
        GitHub Pages, as the hosting provider for the live demo, may use minimal technical
        infrastructure of its own to serve the site; see{" "}
        <a href="https://docs.github.com/en/site-policy" className="text-accent dark:text-accent-dark underline">
          GitHub's site policies
        </a>{" "}
        for what that covers. This project doesn't add anything on top of it.
      </p>
    </LegalPage>
  );
}
