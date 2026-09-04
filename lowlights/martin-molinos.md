# Lowlights

Martin Molinos — In League (Molinos, Sanchez, Tran, Zhou)

Six things I watched go wrong while working with Claude this week.

## 1. The chart that wasn't there, twice

Claude built a page for my group and told me it was finished. The main chart on
it was blank.

**How I noticed.** I opened it and looked at it.

**What went wrong.** The bars used the wrong kind of HTML tag — one the browser
won't let you set a height on, because it's meant to sit inside a line of text.
They were in the code and came out with no height. Nothing crashed and nothing
warned me: the HTML was technically correct.

**What I did.** It fixed the CSS. An hour later the colour squares next to each
school didn't show either — same wrong tag, in a table. It had explained the
mistake to me an hour earlier and then made it again. Now I don't assume a bug it
just explained is one it won't repeat.

## 2. Colours picked by taste

Two of the five lines on our chart looked like the same colour to me.

**How I noticed.** I told it the chart was hard for me to read.

**What went wrong.** It picked the colours by eye. There's an actual measurement
for how far apart two colours look, and when it finally ran it, my blue and
purple came out at 7.3 where 15 is the minimum — 3.4 for someone colourblind.

**What I did.** Made it run the check instead of eyeballing it. I was right that
something was off; I couldn't have told you why. The number did that part.

## 3. Questions that changed nothing

The sign-up tells you your answers change what you see. Two of the three changed
nothing.

**How I noticed.** I filled in the questionnaire and went looking for what my
answers had done to the page.

**What went wrong.** They were saved and never read back. Saving is the part you
can watch working, so it looked finished. The page promised in writing that your
stage "decides what leads the comparison", and nothing decided anything.

**What I did.** Home state now sets the in-state or out-of-state price, and stage
picks which area leads. GPA still changes nothing, so we say so in the demo
instead of pretending.

## 4. The warning label named the wrong source

A notice on each card says how old the numbers are and who published them. It
credited IPEDS for figures that came from the College Scorecard.

**How I noticed.** I read it.

**What went wrong.** Every other area is IPEDS, so "IPEDS" was written straight
into the notice. After graduation is the one card pulling from a different
agency, and the notice said IPEDS anyway.

**What I did.** The card now tells the notice which agency it's using. Blaming
the wrong agency isn't a vague error, it's a wrong fact printed on the page.

## 5. Five schools blamed for one survey ending

I asked the financial aid card for every year it has. It came back saying all
five of my schools were missing years.

**How I noticed.** I read the notice above the chart and it didn't match what I
knew: none of these five had stopped reporting anything.

**What went wrong.** Net price stops in 2021 and I'd asked through 2024, so the
last three years are empty for everybody. Each card worked that out separately
and phrased it as a fact about the schools rather than about the survey. Not
vague, but pointed the wrong way: a reader would sensibly prefer whichever school
we happened not to name.

**What I did.** That arithmetic lives in one place now, and cuts the window to
the years the survey covers before naming anybody. The half that was true
survived — two schools really are missing a year the others report, and those two
are still named.

## 6. Validation that was silently switched off

The sign-in box has a rule saying which characters a username may contain. Chrome
had been throwing it away and checking nothing.

**How I noticed.** A red line in the browser console during a run-through, on the
screen we're presenting from.

**What went wrong.** The rule is valid in Python and valid in JavaScript, and
Chrome rejects it: a hyphen means something different under a newer setting
Chrome applies to that attribute. When it can't read the rule it discards it
silently. Signing in still worked, because the server checks too; what was dead
was the half that warns you as you type.

**What I did.** Escaped the hyphen, and added a check over every rule of this
kind in the project. The reason this shipped is that the rule is surprising, so
we didn't reason about it — we ran 22 patterns through the browser's own engine
and checked the answers.

## The pattern

Anything Claude could check by itself, it checked, and got right. Anything that
needed a person to actually look, it got wrong and then told me it was done. Five
of these six I found by opening a page and reading it. The suite is 431 tests and
green; not one of these came out of it.
