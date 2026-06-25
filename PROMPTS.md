# Prompts Used in Building This Project

A chronological log of every prompt used during development, grouped by phase. (Some are missing because the conversation was compacted)

---

## Phase 0 — Initial Setup & API Failures

1. Assume you are an AI Architect and you need to design a rag model according to the requirements...Initially generate a plan on how to proceed. Below is the problem statement:

   > The Problem: Build an agent that answers questions about a small corpus of documents and cites its sources. We've attached a folder of 6 PDF documents (a mix of reports, a policy document, and some FAQs). Your agent should:
   > 1. Accept a natural-language question from the user.
   > 2. Search the document corpus and find the relevant content.
   > 3. Answer the question in plain language.
   > 4. Cite which document(s) and which section(s) the answer is drawn from.
   > 5. Refuse to answer (gracefully) when the corpus doesn't contain the information — saying "I don't know" is a feature, not a failure.
   > 6. Use Python fast api for backend, chroma db for vector db and react for frontend

2. `Implement it phase wise and ask me if you have any doubts.`

3. `Give me a detailed way to run the whole code`

4. `Failed to send telemetry event ClientStartEvent...` / Google API 404 error on `text-embedding-004`

5. `are there any free api keys...that will easily manage a 100-150 page pdf {detail: Error embedding...} without giving this error`
     `how about groq`

 `yes` *(confirming switch to Groq + sentence-transformers)*

---

## Phase 1 — Core Features

6. `can we do it only for 1 pdf....and I want to have the option to upload the file so that it can be embedded`

7. `what are the keys needed here`

8. `[DuplicateIDError: Expected IDs to be unique] what does this mean`

9. `Are you sure there will be no errors now?`

---

## Phase 2 — Chunking Strategy

10. `what's the chunking strategy being used?`

11. `is the chunking strategy effective here?`

12. `Generate a plan first to fix all the issues....Use the effective chunking strategy`

13. `Yes, Start one by one...ask me if you have any doubts`

14. `The chunk size is 400+` *(confirming Phase 1 sentence-aware chunking worked)*

15. `proceed with next phase` *(Phase 2 — section header detection)*

16. `All are annual reports`

17. `All reports are not related` *(6 independent annual reports from different companies)*

18. `[sections output with false positives shown]` *(debugging section header detection)*

19. `proceed with next phase` *(Phase 4 — vision/chart extraction)*

20. *(Answered AskUserQuestion)* Doc types: `Yes, I know all of them`

21. *(Answered AskUserQuestion)* Sentence split: `Keep it simple, no new deps`

22. *(Answered AskUserQuestion)* Image density: `Moderate — charts on maybe 20-40% of pages`

---

## Phase 3 — Retrieval Optimization

23. `generate a plan first to optimize this chunking process`

24. `implement only re ranking suggest which one is better first`


---

## Phase 4 — Documentation & Git

26. `generate a good readme file with the architecture design and why it's chosen....also tell why gemini flash 2.5 was not used...because the free tier was hitting limits...and also tell graphs etc...are also retrieved and chunked properly`

27. `Is there a git ignore file and is it updated correctly now`

28. `I want to push frontend folder now`

29. `Give me the commands...I'll only push it`

30. `In backend what are the files included in gitignore?`

31. `my env is the venv folder`

32. *(screenshot of backend folder)* — identified venv folder named `myenv`

---

## Phase 5 — Technical Discussion

33. `what is the search...is it hybrid search which we are using?`

34. `Is it needed to add sparse search as well here?`

---

## Phase 6 — Submission


35. `A short NOTES.md (half a page max) covering your overall approach, what you'd do differently if this were going to production, and any tradeoffs you made because of the 2-hour budget`
