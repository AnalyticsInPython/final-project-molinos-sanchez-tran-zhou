# Lowlight One-Pager: Communications among agents

Rebecca (Taiyangzhi) Zhou — ENGI 4503, Analytics in Python

**What happened.** Our group project is to make a website that helps people
to compare universities. Early on, I asked my agent to change how the
"Areas" selection worked on our comparison tool from a dropdown to a plain,
always-visible checklist. It built the change, I liked it, and I had the
agent merge it to a new branch so it would ship alongside a profile feature
I also built earlier.

However, not long after, a teammate's agent reverted that exact commit.

**How I noticed.** I found out the next day, when I asked my agent something
unrelated: "is everything I built actually live on GitHub?" My Claude Code
walked the commit history across every branch, and made me realize that my
change had been merged and then quietly undone.

**What I think actually went wrong.** The root cause is pretty mundane: two
of us had agents editing the same page within the same stretch of time,
building toward two different designs, and neither agent had any way of
knowing the other existed. That's a coordination gap that comes with working
in parallel branches. It's not necessarily an agent mistake.

What I'd actually call the lowlight is what happened after the collision:
the revert didn't say why. Whoever reverted it could have written one
sentence, something like "reverting this because the new picker component
needs a different layout here". Without the note, a revert just looks like
an accident or a mistake that I would've not noticed if I didn't
proactively ask my Claude Code to check. An agent reverting code isn't the
problem; an agent reverting code and leaving no trace of the reasoning is
what turns a normal design disagreement into something that looks, from the
outside, like it was overwritten without a word.

**What I did.** I didn't push back on the revert. Once I saw what had
replaced it, it seemed like the right call, even though nobody had actually
told me that. I left my original pull request open rather than trying to
force my version back in, since the team had already solved the same
problem a different way by then.

**The takeaway.** The agent didn't cause this problem, but it did change how
I experienced it. Instead of watching the change happen and understanding it
in real time, I found out after the fact by asking my own agent to tell me
what state my project was in. The actual fix isn't a smarter agent; it's a
habit the team needs regardless of who's typing the commit: when you revert
someone else's work, possibly always add a note and quickly articulate why.
