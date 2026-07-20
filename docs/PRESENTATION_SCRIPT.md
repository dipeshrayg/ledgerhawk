# LedgerHawk - Video Script (~4:15, fits a 3-5 minute slot)

Written against three specific criteria: a problem statement that makes
someone care in the first 45 seconds, a demo that shows the range of the
product across several features rather than one screen, and a technical
explanation detailed enough that a technical judge learns *why* it's built
this way, not just *that* it works. Bracketed notes are stage directions,
not narration.

Word count below is ~660 narration words. At a normal, unhurried 150 wpm
that's about 4:20; even at a slower 130 wpm it's under five minutes. Read
it aloud once before recording to check your own pace.

---

## [0:00] Problem statement

Quick question: when's the last time anyone at your company actually
checked that a vendor invoice matched the contract - recalculated it, line
by line, against the terms you signed, not just glanced at the total?

If the answer is "never," you're not alone. Every contract has exact
terms: a per-seat rate, an escalation cap, a discount with an expiry date.
Nobody re-derives those terms against what actually gets billed. A
vendor's billing system drops a discount, or applies an escalation two
months early, and the invoice still looks completely normal. There's no
red flag. It's just wrong, quietly, every month, until someone rereads a
forty-page contract by hand.

That's the gap. This closes it.

## [0:40] The pitch

This is LedgerHawk - CI/CD for enterprise contracts. Contracts get
compiled into executable pricing rules. Invoices get run against those
rules like test cases. An overcharge shows up exactly the way a failing
test does: the clause, the math, and proof.

## [1:00] Demo: the dashboard and a failing invoice

**[screen: open the live dashboard]**

Five vendors, sixty invoices reconciled. Right now it's caught fourteen
real discrepancies worth $86,420 - and zero false alarms on the other
forty-six clean invoices, which matters as much as the catches: a tool
that flags everything is as useless as one that flags nothing.

**[click into MegaCloud, a failing invoice, then "View evidence"]**

Click into a failing invoice: the clause it's based on, quoted verbatim
from the actual contract - not a summary - the math that produced the
expected number, and the dollar delta. One more click drafts a dispute
letter citing that same clause and math. Nothing here is a black box.

## [1:40] Demo: precedence, forecasting, the copilot

**[click Rule Inspector for MegaCloud]**

This contract is the hard case on purpose: an MSA, three amendments, and
an executed email extending a discount. Ask what the rate is right now,
and the system resolves which document wins - and shows its work: "from
Email Agreement, November 15th," not just a number.

**[click Forecast tab]**

Same contract, replayed thirty-six months forward. A 15% auto-renewal
uplift hits in five months - surfaced now, months before an invoice would
ever show it.

**[open the Audit Copilot, ask a question]**

And a natural-language question - "why did MegaCloud's cost jump?" -
answered by querying the same underlying findings, never by generating a
plausible-sounding number.

## [2:25] The technical explanation

Here's the one decision that matters most: this is a pipeline, not a
prompt. A Contract Agent turns raw text into a typed structure - parties,
term, every pricing clause, tagged with its source document. A Pricing
Agent lowers that into an executable rule set: rates, tiers, escalation
caps, proration. A Validator lints it for risk - uncapped escalation, a
missing proration rule. A Precedence Resolver decides, for any date,
which document's version of a rule wins - what just let the email
amendment win correctly.

Then - separately, deliberately - a deterministic Billing Engine replays
every invoice against those resolved rules in plain Python `Decimal`
arithmetic. No LLM anywhere near that function. An LLM reads contracts and
drafts emails; it never touches a dollar figure. Every number here traces
to a unit-tested function multiplying a rate by a quantity - the kind of
code you'd trust to run payroll, not a model's guess. That's
`billing_engine.py`, and it's five minutes of reading if you want to
verify the claim yourself.

It also runs two ways with identical output: a live backend, or - what
you're watching now - a static build with no server, where every screen
is pre-computed from that same pipeline. Same engine, two targets.

## [3:45] Close

I built a benchmark to hold this to: five contracts, sixty invoices,
fourteen deliberately planted billing errors, hidden the way real ones
hide. LedgerHawk catches all fourteen, flags nothing that isn't wrong, and
reconciles all sixty invoices in under five milliseconds.

Contracts compiled into rules. Invoices run like tests. Overcharges caught
with proof instead of a hunch. That's LedgerHawk. Thanks.

---

**Delivery notes:** the demo beats at 1:00 and 1:40 are the only places you
need the live site up. If you're still over five minutes at your own
pace, cut the static-vs-live paragraph at the end of the technical
section first - it's the one part not load-bearing for any of the three
scored criteria.
