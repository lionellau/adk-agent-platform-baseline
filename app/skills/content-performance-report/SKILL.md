---
name: content-performance-report
description: Writes a business-unit content performance brief from viewership figures the agent already retrieved. Covers structure, how to state numbers and date ranges, ranking, trends and a short recommendation.
---

# Content performance brief

Use this when asked for a report, brief, summary or weekly update on content performance.

## Step 1: Check you have the numbers
You need figures that came from a tool in this conversation (views per title, per week or per
business unit, with the date range). If you don't have them, say which figures are missing.
Never estimate.

## Step 2: Read the house style
Use `load_skill_resource` to read `references/report-style.md` and follow it.

## Step 3: Write the brief
1. **Headline**: one sentence with the single most important number.
2. **Top titles**: a ranked list (title, views, change vs the previous week if known).
3. **Trend**: one or two sentences on direction, with the numbers behind it.
4. **Watch-outs**: anything that dropped more than 5 % week on week.
5. **Recommendation**: one action for the business unit.

## Step 4: Respect the reader's preferences
If the user has a saved preference (for example "at most 3 bullet points"), it overrides the
length of steps 3.2 to 3.5.
