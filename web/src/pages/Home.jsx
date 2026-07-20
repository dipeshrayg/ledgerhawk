import { Link } from "react-router-dom";

const STEPS = [
  {
    n: "01",
    title: "Compile the contract",
    body: "Feed it the MSA, the amendments, even that one email where someone extended a discount. It builds a typed model of every pricing clause: rates, tiers, caps, expiry dates, who said what and when.",
  },
  {
    n: "02",
    title: "Run the invoice like a test",
    body: "A separate, deterministic engine replays each billing period against the compiled rules and works out exactly what should have been charged, to the cent.",
  },
  {
    n: "03",
    title: "Read the diff",
    body: "Any gap between what should have been billed and what actually was becomes a finding: the clause, the arithmetic, the dollar amount, all in one place.",
  },
  {
    n: "04",
    title: "Get the paperwork",
    body: "One click turns a finding into a dispute letter that quotes the actual contract language, not a summary of it.",
  },
];

const FEATURES = [
  { title: "Reconciliation", body: "PASS/FAIL on every invoice, with the receipts to prove it." },
  { title: "Leakage forecast", body: "See next year's rate hikes and renewal traps before they ever reach an invoice." },
  { title: "Contract unit tests", body: "Legal writes an assertion once. It gets checked forever, on every new bill." },
  { title: "Version diff", body: "What actually changed between contract v1 and v2, and what it costs you." },
  { title: "Pre-sign review", body: "Catch a bad clause before you sign it, not two years into the term." },
  { title: "Audit copilot", body: "Ask it why a vendor's bill jumped in March. Get an answer with a receipt attached." },
];

const AUDIENCE = [
  "Accounts payable teams currently trusting vendor math on faith",
  "Procurement, before they sign the next multi-year deal",
  "Legal and contracts teams who want their terms enforced by something other than memory",
  "Anyone who's stared at an invoice sure something was off, with no way to prove it",
];

function Stat({ value, label, accent }) {
  return (
    <div className="border-l border-ink/10 pl-4 first:border-l-0 first:pl-0 dark:border-ink-dark/10 sm:pl-6">
      <div className={`font-display text-2xl font-bold sm:text-4xl ${accent ? "text-accent dark:text-accent-dark" : ""}`}>{value}</div>
      <div className="mt-1 text-[11px] uppercase tracking-wide text-ink/50 dark:text-ink-dark/50 sm:text-xs">{label}</div>
    </div>
  );
}

export function Home() {
  return (
    <div className="min-h-screen bg-paper font-sans text-ink dark:bg-paper-dark dark:text-ink-dark">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-ink focus:px-4 focus:py-2 focus:text-paper dark:focus:bg-ink-dark dark:focus:text-paper-dark"
      >
        Skip to main content
      </a>
      <header className="border-b border-ink/10 dark:border-ink-dark/10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <span className="font-display text-lg font-bold tracking-tight">LedgerHawk</span>
          <nav className="hidden items-center gap-7 text-xs font-medium uppercase tracking-widest text-ink/60 dark:text-ink-dark/60 md:flex">
            <a href="#how-it-works" className="hover:text-ink dark:hover:text-ink-dark">How it works</a>
            <a href="#features" className="hover:text-ink dark:hover:text-ink-dark">Features</a>
            <a href="https://github.com/dipeshrayg/ledgerhawk" className="hover:text-ink dark:hover:text-ink-dark">GitHub</a>
          </nav>
          <Link
            to="/app"
            className="border border-ink px-4 py-2 text-xs font-semibold uppercase tracking-widest transition hover:bg-ink hover:text-paper dark:border-ink-dark dark:hover:bg-ink-dark dark:hover:text-paper-dark"
          >
            Open dashboard
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section id="main-content" className="mx-auto max-w-6xl px-5 pb-16 pt-16 sm:px-8 sm:pt-24">
        <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-accent dark:text-accent-dark">
          CI/CD for enterprise contracts
        </p>
        <h1 className="max-w-4xl font-display text-[clamp(2.1rem,7.5vw,5.5rem)] font-bold leading-[1.05] tracking-tight">
          Your vendor invoices have bugs. Nobody's running the tests.
        </h1>
        <p className="mt-8 max-w-xl text-lg leading-relaxed text-ink/70 dark:text-ink-dark/70">
          LedgerHawk compiles a contract into a set of executable pricing rules, then replays every
          invoice against them. When a vendor overcharges you, it doesn't show up as a vague anomaly:
          it shows up as a failing test, with the clause, the math, and a dispute letter attached.
        </p>
        <div className="mt-9 flex flex-wrap items-center gap-4">
          <Link
            to="/app"
            className="bg-ink px-6 py-3 text-xs font-semibold uppercase tracking-widest text-paper transition hover:opacity-80 dark:bg-ink-dark dark:text-paper-dark"
          >
            Open the live dashboard
          </Link>
          <a
            href="https://github.com/dipeshrayg/ledgerhawk"
            className="border border-ink/30 px-6 py-3 text-xs font-semibold uppercase tracking-widest transition hover:border-ink dark:border-ink-dark/30 dark:hover:border-ink-dark"
          >
            Read the source
          </a>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-ink/10 py-10 dark:border-ink-dark/10">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <p className="mb-8 text-xs font-semibold uppercase tracking-widest text-ink/50 dark:text-ink-dark/50">
            From the seeded demo portfolio: five vendors, twelve months of invoices each
          </p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-4 sm:gap-x-8">
            <Stat value="$86,420.40" label="Recovered" accent />
            <Stat value="14 / 14" label="Planted errors caught" />
            <Stat value="0 / 46" label="False positives" />
            <Stat value="60" label="Invoices reconciled" />
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
        <h2 className="font-display text-2xl font-bold uppercase tracking-tight sm:text-3xl">
          The leak nobody's watching
        </h2>
        <p className="mt-6 text-lg leading-relaxed text-ink/75 dark:text-ink-dark/75">
          Every enterprise contract has exact pricing terms: a per-seat rate, an escalation cap, a
          discount that expires on a specific date. Almost nobody re-checks those terms against what
          actually gets billed. AP pays what's on the invoice. The vendor's billing system makes a
          small arithmetic mistake, or "forgets" a discount, or bumps a rate two months early, and the
          number on the page still looks completely normal.
        </p>
        <p className="mt-5 text-lg leading-relaxed text-ink/75 dark:text-ink-dark/75">
          There's no red flag. It's just wrong, quietly, every month, until someone happens to reread
          a 40-page MSA and three amendments and catches it by hand.
        </p>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t border-ink/10 py-16 dark:border-ink-dark/10 sm:py-24">
        <div className="mx-auto max-w-4xl px-5 sm:px-8">
          <h2 className="font-display mb-10 text-2xl font-bold uppercase tracking-tight sm:text-3xl">
            How it actually works
          </h2>
          <div className="divide-y divide-ink/10 dark:divide-ink-dark/10">
            {STEPS.map((s) => (
              <div key={s.n} className="grid gap-2 py-7 sm:grid-cols-[90px_1fr] sm:gap-6">
                <span className="font-display text-2xl font-bold text-accent dark:text-accent-dark">{s.n}</span>
                <div>
                  <h3 className="font-semibold">{s.title}</h3>
                  <p className="mt-2 leading-relaxed text-ink/70 dark:text-ink-dark/70">{s.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Design law */}
      <section className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
        <h2 className="font-display text-2xl font-bold uppercase tracking-tight sm:text-3xl">
          The one rule that matters
        </h2>
        <p className="mt-6 text-lg leading-relaxed text-ink/75 dark:text-ink-dark/75">
          An LLM reads your contract and drafts your dispute email. It never touches the money. Every
          dollar figure in this system comes out of a plain, unit-tested Python function that
          multiplies a rate by a quantity: the same kind of code you'd trust to run payroll.
        </p>
        <p className="mt-5 text-lg leading-relaxed text-ink/75 dark:text-ink-dark/75">
          If you're going to bet money on a piece of software, that's the part worth checking. So go
          check it:{" "}
          <a
            href="https://github.com/dipeshrayg/ledgerhawk/blob/main/api/app/pipeline/billing_engine.py"
            className="font-medium text-accent dark:text-accent-dark underline"
          >
            api/app/pipeline/billing_engine.py
          </a>
          , no LLM calls anywhere in it.
        </p>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-ink/10 py-16 dark:border-ink-dark/10 sm:py-24">
        <div className="mx-auto max-w-4xl px-5 sm:px-8">
          <h2 className="font-display mb-10 text-2xl font-bold uppercase tracking-tight sm:text-3xl">
            What's actually in here
          </h2>
          <div className="divide-y divide-ink/10 dark:divide-ink-dark/10">
            {FEATURES.map((f) => (
              <div key={f.title} className="grid gap-1 py-6 sm:grid-cols-[220px_1fr] sm:gap-8">
                <h3 className="font-semibold">{f.title}</h3>
                <p className="leading-relaxed text-ink/70 dark:text-ink-dark/70">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Audience */}
      <section className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
        <h2 className="font-display text-2xl font-bold uppercase tracking-tight sm:text-3xl">
          Who actually needs this
        </h2>
        <div className="mt-6 divide-y divide-ink/10 dark:divide-ink-dark/10">
          {AUDIENCE.map((a) => (
            <p key={a} className="py-4 text-lg leading-relaxed text-ink/75 dark:text-ink-dark/75">
              {a}
            </p>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-ink/10 py-20 text-center dark:border-ink-dark/10 sm:py-28">
        <h2 className="font-display text-3xl font-bold uppercase tracking-tight sm:text-4xl">
          It's running right now.
        </h2>
        <p className="mx-auto mt-4 max-w-lg text-ink/70 dark:text-ink-dark/70">
          Seeded with five fictional vendors and fourteen real mistakes, hiding in plain sight on
          normal-looking invoices. Go find them.
        </p>
        <Link
          to="/app"
          className="mt-8 inline-block bg-ink px-8 py-4 text-xs font-semibold uppercase tracking-widest text-paper transition hover:opacity-80 dark:bg-ink-dark dark:text-paper-dark"
        >
          Open the live dashboard
        </Link>
      </section>

      <footer className="border-t border-ink/10 px-5 py-10 dark:border-ink-dark/10 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 text-xs uppercase tracking-widest text-ink/50 dark:text-ink-dark/50 sm:flex-row sm:justify-between">
          <span>© 2026 Dipesh Ray. MIT licensed.</span>
          <div className="flex flex-wrap items-center justify-center gap-5">
            <Link to="/terms" className="hover:text-ink dark:hover:text-ink-dark">Terms</Link>
            <Link to="/privacy" className="hover:text-ink dark:hover:text-ink-dark">Privacy</Link>
            <Link to="/cookies" className="hover:text-ink dark:hover:text-ink-dark">Cookies</Link>
            <a
              href="https://github.com/dipeshrayg/ledgerhawk/blob/main/docs/PROVENANCE.md"
              className="hover:text-ink dark:hover:text-ink-dark"
            >
              Provenance
            </a>
            <a href="https://github.com/dipeshrayg/ledgerhawk" className="hover:text-ink dark:hover:text-ink-dark">
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
