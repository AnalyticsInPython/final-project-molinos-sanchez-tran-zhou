# Lowlights

Rafael Sanchez — ENGI 4503, Analytics in Python

Some context first. Our group built In League, a web app that compares colleges side
by side on federal IPEDS data (admissions, financial aid, graduation rates, athletics,
outcomes) and can tailor the numbers to who you are. I did almost all of my work with
Claude Code. These are the five moments during the week where something went wrong in
a way that changed how I worked afterwards.

## 1. It explained the data confidently, and it was wrong

**How I noticed.** Our cards show things like "2021 graduation rate," which is
ambiguous, so I asked Claude to add a line under each card explaining what the year
actually means. It wrote that the 2021 graduation figures follow students who started
college in fall 2014. Something felt off. That's a seven-year gap for what is
supposed to be a four-year graduation rate.

**What went wrong.** The sentence read like documentation, but Claude had guessed the
most plausible explanation and written it as fact without looking at the table. The
uncomfortable part is that when I pushed back, my version was wrong too. I assumed the
four-year rate must track a later class, the one that started in 2016. When Claude
finally checked the actual data, it turned out IPEDS follows a single entering class
and counts it once at four years and again at six. Both of us had it wrong.

**What I did.** Had it verify against the real tables before rewording anything, and
write a test so the mapping can't quietly drift. The bigger lesson was that any
sentence our app tells a user about what a number means has to trace back to a real
column, not to whatever sounds right.

## 2. Every test passed and the app was broken

**How I noticed.** By using the app. I clicked an older year in the year selector and
every more recent year vanished from my selection and stayed disabled until I
refreshed.

**What went wrong.** During a refactor Claude had renamed a field from `unitid` to
`id` and missed a few places that still used the old name. Our test suite, over two
hundred tests, stayed green the whole time, because the breakage was in the browser
and we had no tests there. When I reported the bug, Claude's fix missed another spot.
Then another. By the third time I came back with the same symptom it admitted it
hadn't searched the code properly. The fix was as incomplete as the change that
caused it.

**What I did.** Stopped treating a passing test suite as proof that anything a user
touches works. From then on I clicked through every UI change myself before merging.

## 3. It answered the easy version of my question

**How I noticed.** The night before the demo, walking through our run sheet signed in
as our demo profile. I had asked for a quick way to compare the schools a user had
saved to their profile. What Claude built was a link that jumped straight to a
comparison of every area we had, at the latest year, all at once. It looked terrible
on screen, and it wasn't a comparison anyone would actually want.

**What went wrong.** When my instructions are vague, Claude doesn't ask what I mean.
It picks the most literal interpretation and executes it well, which is almost worse,
because the output looks finished. I had said "compare their saved schools" and it
took that to mean compare everything. Which areas and which years were the whole
point, and it made those decisions for the user instead of leaving them to the user.

**What I did.** Had it replaced with a button that fills in the saved schools and
then leaves areas and years to the person using it. More generally, I started writing
down the actual question, and what decision it feeds, before handing over a task. A
vague prompt is now my mistake, not Claude's.

## 4. The UI was correct but not how a person would want it

**How I noticed.** Again by using it. Year selection came back as a dropdown, when a
user needs buttons for the common ranges and greyed-out years showing where data is
missing. Picking a filter on a card scrolled the page back to the top. And a chart
legend that said "women / other groups / everyone" was coloured by school, so it
didn't mean what it said.

**What went wrong.** Left alone, Claude builds interfaces that are consistent and
easy to implement, not ones that match what a person expects. The legend wasn't a
matter of taste. It was misleading.

**What I did.** Stopped asking for screens and started describing what the user
should be able to do and see, and planned on correcting the first version.

## 5. Staying token-efficient was a real challenge

**How I noticed.** Usage was tight all week. The extra usage we were supposed to get
through CBS hadn't come through yet, so I was on my own plan and watching it closely.
The newer Fable model was noticeably better on hard problems, but it's much hungrier,
and a couple of long sessions on it ate most of a day's budget.

**What went wrong.** This one is on me more than the model. Being short pushed me
toward running several agents in parallel and letting things run overnight to
stretch what I had. That's exactly the mode where I was reading the least, and item 2
is what comes out of it.

**What I did.** Kept every parallel agent on its own branch opening a draft PR
instead of merging on its own, and reviewed each branch myself before anything went
into main.
