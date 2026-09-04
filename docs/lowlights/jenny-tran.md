# Lowlights — Jenny Tran

**1. It redesigned the one thing I asked it not to touch.**
I asked Claude to make the landing page prettier — nicer visuals, better
buttons, that's it. What came back had also swapped out the school picker for
a new browse-grid I never asked for. Nothing was technically broken; it just
wasn't what I said. I think what happened is that "make it nicer" and "make
it better" quietly became the same instruction to it, and the picker looked
like a place it could improve. I made it revert the picker outright and told
it, plainly, to leave selection alone. The annoying part is what came after:
I didn't trust that boundary anymore, so I found myself repeating "don't
touch the picker" on almost every request for the rest of the project, even
when there was no reason to think it would wander again. One overreach and I
was doing the fencing myself from then on.

**2. A button nobody could read, and the tests said everything was fine.**
Days after Claude added a green gradient "Compare" button, I looked at the
page with nothing selected yet and the button text was just... grey on
bright green. Barely legible. I hadn't asked for anything fancy there, and I
couldn't tell you why it looked wrong — I just knew it did, and said so. Turns
out a CSS id rule was overriding the background but not the text color on the
disabled state, so it kept the vivid button look with unreadable text. 344
tests were green, lint was clean, none of it noticed, because none of it
looks at a screen. Claude had only ever screenshotted the button while it was
clickable. That was the moment it clicked for me that "the tests pass" and
"it works" aren't the same sentence — somebody still has to look at the ugly
states, not just the good ones.

**3. The link kept going dead between turns.**
More than once I came back to check something and the local site just... wasn't
there anymore. Not broken — just gone, connection refused. Each time it turned
out Claude had killed its own background server while tidying up at the end of
a turn, without mentioning it or starting it back up. From where I sat, a
feature that worked five minutes ago had quietly stopped existing, and I had
no way to know that without asking. It took me noticing the pattern out loud —
"this keeps happening" — before it stopped happening.

What ties these together: I never caught any of them by reading code or
watching it work through a task. I caught them by actually using the thing —
looking at the screen, clicking around, coming back later and finding it
gone. The tools it uses to check its own work don't look at the product the
way I do, so that part's still on me.
