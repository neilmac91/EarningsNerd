# Admit a todo row only if a reader hit it, it blocks testers, payment or the launch, it is an exposure today, or it is one of five chosen bets; name every other finding as a limit in its pull request

Date: 2026-11-11 · Area: ops / planning

**Context.** One year after the first commit the product was still pre-launch: registration by invitation, collection
closed, and `is_checkout_available()` returning False. `tasks/todo.md` held 102 open rows inside its 120-line cap, and
weighed 173 KB: one row ran to 2,614 words and one status bullet to 2,058 words of deploy history. Of the 102:
- none cited a reader, a tester or a customer who had asked for the work;
- at least 33 said they were left or found by the review of another pull request, since `AGENTS.md` §5 sent every
  review finding outside a fix's diff to a follow-up row;
- 36 waited on the founder, one of them since mid-October;
- none was about admitting testers in number, opening checkout or getting the site indexed.

The founder, 2026-11-11: "my todo list is almost at capacity ... be ruthless and always think about what can make
EarningsNerd commercially successful", then "please update the todo file as you see fit". The triage meant to keep
42 rows, parked 16 and closed 44. Checking each of the 42 against the code found five already done on main and never
closed (the privacy page's corrections, two billing fixes, a CI change), so the page had been stale as well as long.
It kept 33 as 17 rows, built two, closed one that no pull request carried, parked one more, and added six rows the
launch needed and no row covered. The page went from 25,600 words to under 1,800.

The triage's own review then found that the first version of this rule named three grounds while the page kept rows on
two more (the public launch, and product work nobody had asked for), and that a per-line word cap is met by wrapping
a row, as the line cap had been met by longer lines. The rule below names the grounds the page uses, and the gate
bounds the whole page.

**Rule.**
1. A row enters `tasks/todo.md` only on one of four grounds: a reader, tester or customer hit it; it blocks
   admitting testers, taking payment or the public launch; it is a security, legal or availability exposure today; or
   it is a product bet chosen on purpose, its owner opening `(bet; …)`, at most five at a time. "A review found it"
   is not a ground.
2. A finding that meets none of them is a limit the pull request's body names. It gets no row and no parking line.
3. A row that waits on an event, not on work, is parked: one line under "Parked" naming the event that revives it.
4. The page has budgets: 30 open rows (any checkbox bullet, at any indent), 70 words on any line, 80 lines, 2,400
   words in all and five bets. At a cap, close, merge or park a row before adding one. A line cap alone is met by
   longer lines, and a per-line cap by wrapping, so the page's words are counted whole.
5. A row is a pointer. Deploy history, production state and a review's evidence stay out of it: read production live,
   and keep evidence in the pull request that produced it.
6. The page opens with four reader numbers (testers admitted, conversations held, testers back for a second filing,
   people asked to pay). When none moves in a week, question the rows before adding more.
7. Check a row against main before you keep it, act on it or put it to the founder: read the file it names. A row
   whose work has merged is closed, not carried (`ops-re-read-main-before-you-ask-the-founder-about-an-open-item.md`).

**Evidence.**
- `backend/tests/unit/test_agent_workflow_rules.py::test_todo_is_one_page_of_open_items`: the budgets (rule 4) and
  the cap on bets (rule 1). Which ground a row claims, and rules 2, 3 and 5 to 7, are review-checked.
- `AGENTS.md` §7 (admission and format), §5 (a round-2 finding outside the diff) and §3 (who may add a row).
- `tasks/archive/todo-ledger-2026-10-08-through-2026-11-11.md`: the page as it stood, and what the triage did with
  each row.
- `docs/RESEARCH_SYNTHESIS.md`, "The decision filter": the same test, written in June 2026 ("Did a real retail
  investor ask for this?").
