# Provenance & Authorship

**Author:** Dipesh Ray ([@dipeshrayg](https://github.com/dipeshrayg))
**Project:** LedgerHawk - CI/CD for Enterprise Contracts
**First published:** July 2026, at [github.com/dipeshrayg/ledgerhawk](https://github.com/dipeshrayg/ledgerhawk)

This isn't legal advice - it's a plain record of who built this and when,
plus what that record actually gets you if someone else tries to claim it.

## The evidence

Every commit in this repository is signed with the author's name and email
and carries a SHA hash that GitHub timestamps the moment it's pushed. Change
one byte of a commit's content and its hash changes with it - you can't
edit history quietly and keep the same hash. That gives you two things for
free, with no paperwork: a public record of *who* wrote this, and a public
record of *when*. Anyone can check both by cloning the repo and running
`git log`.

Copyright itself doesn't need registration to exist. Under the Berne
Convention (which the US, UK, and most countries follow), the moment you
write original code, you own the copyright on it. The [LICENSE](../LICENSE)
file in this repo just makes that ownership explicit in writing.

## What the MIT license actually protects - and what it doesn't

This project is MIT-licensed, on purpose. That means:

- **Anyone can legally use, copy, modify, or sell software built on this
  code.** That's the point of open source, and it's why this was built
  as MIT instead of something locked-down.
- **Nobody can strip the copyright notice and claim they wrote it.** The
  license's one real condition is that the original copyright notice stays
  attached. Remove it and claim authorship, and that's not a gray area -
  it's a license violation, and the git history above is the evidence that
  proves it.

So MIT doesn't stop someone from forking this and building a product on
top of it - it was never meant to. What it stops is someone erasing your
name from it and calling it theirs. If you ever see that happen - a repo,
a product, a portfolio site presenting this work (or a close copy of it)
as someone else's - the commit history here, timestamped and signed under
your name, is what you'd point to first.

## If you want more than that

None of the above requires you to do anything else. If you want a stronger
paper trail beyond what git already gives you for free:

- **Register the copyright** with the U.S. Copyright Office (or your
  country's equivalent). It's inexpensive and gives you access to
  statutory damages in the US if you ever need to sue over infringement -
  git history alone doesn't get you that.
- **Sign your commits with GPG.** GitHub will mark them "Verified," which
  cryptographically ties a commit to your identity in a way a plain name
  and email can't.
- **Snapshot the public repo and live site** with a third-party timestamp
  you don't control yourself - the Internet Archive's Wayback Machine
  works, and so does a service like OpenTimestamps. The point is a
  timestamp nobody, including you, could quietly backdate.
- **If any specific technical method here is genuinely novel** - the
  precedence-resolution algorithm, say, or the DSL's structure - and you
  want to explore patenting it, that requires a patent attorney and an
  actual filing. Most software patents are narrow and hard to get, and
  nothing here does that for you automatically.

None of this is legal advice, and none of it substitutes for talking to an
actual IP lawyer if real money or a real dispute is on the table. What's
above is just what's already true the moment code lands in a public git
repository with your name on it - and what's left to do if that's not
enough for you.
