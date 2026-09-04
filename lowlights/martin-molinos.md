# Lowlights

Martin Molinos — In League (Molinos, Sanchez, Tran, Zhou)

Five things I watched go wrong while working with Claude this week. Other things
went wrong on this project that my teammates caught; these are the ones I was in
the loop for.

## 1. A plan for the four of us, written without reading the brief

Claude gave me a detailed plan for splitting the work between my groupmates and
me, with an argument for each piece.

**How I noticed.** Nothing in it was wrong exactly. It just didn't sound like it
came from anywhere. I said I wasn't convinced, that there was no rubric behind
it, and to go read the syllabus — which was on GitHub the whole time.

**What went wrong.** It had written the plan without it. Once it read the
syllabus, the work split turned out not to be the problem: the brief requires a
data-analysis component, and we had cut both analytical pieces an hour earlier.

**What I did.** Made it read the syllabus before advising me again, and put the
analysis back. It's the centre of our demo now.

## 2. "Finished" was a page with a blank centre

Claude built me a page summarising our scope to send to my teammates, and told me
it was done.

**How I noticed.** I read it and it was a mess. I said so, and told it to open it
in Chrome and see it the way I see it.

**What went wrong.** Made to look, it found something I hadn't: the bars in the
main chart were inline elements, which a browser won't apply a height to. Six
empty grey tracks where the centrepiece was. Nothing crashed — the HTML was valid.

**What I did.** I didn't diagnose this one. I refused the result and made it go
check, and it admitted it had never seen the page, only its own CSS. "Finished"
now means finished and looked at.

## 3. Colours picked by taste

Two of the five lines on our chart looked like the same colour to me.

**How I noticed.** I told it the chart was hard to read as a human, and that I
shouldn't have to match a line to a legend to know which school I'm looking at.

**What went wrong.** It had picked the colours by eye. There's an actual
measurement for how far apart two look, and when it finally ran it, my blue and
violet came out 7.3 apart against a floor of 15 — 3.4 for someone colourblind.

**What I did.** Made it measure instead of eyeballing, and swap in colours that
pass. I was right that something was off; I couldn't have told you why. The
number did that part.

## 4. Sent to sign up for something we already had

The map needed a MapTiler key, and Claude walked me through creating an account
to get one.

**How I noticed.** I asked why I had to log in at all, and whether users would
too. It said you sign in once, as the developer, to obtain a key. So I asked the
obvious next thing: doesn't that mean my groupmate already got one?

**What went wrong.** It did. The map already worked in the repo, so the key
existed in the team. Claude answered every question I asked accurately and never
raised the one that made the task unnecessary.

**What I did.** Asked Rafael for the key. Now I ask what a task is for before I
start it, not halfway through.

## 5. The exercise that turned into a testing tutorial

In the buggy-reports exercise we were meant to find the bugs planted in the code,
and the teacher had said to find them without the agent's help.

**How I noticed.** I'd fixed two and asked what testing a programmer would do
next. It came back with six techniques and commands to generate adversarial
filenames. I said I didn't think I was supposed to be doing all this — the point
was the problems already in the code — and that we should stick to the sample
data.

**What went wrong.** It answered my question well and lost the assignment doing
it. Its reply was "You're right, and I overshot."

**What I did.** Pulled it back and finished the bugs. It follows the question you
asked, not the task you're on, and I'm the only one holding the task.

## The pattern

None of these came from a test, and none from an error message. All five came
from being unconvinced by a confident answer. In three of them I couldn't say
what was wrong — only that something was, and that I wasn't accepting it yet.
Claude found the cause each time, but only once I made it go and look.
