Postmortem Generator

 What is this?

If a website goes down, an API fails, etc., after it has happened, engineers need to write up a report, explaining what happened, why it happened, and then what they're going to do to prevent it from happening again. They are known as Postmortems. They take hours to write correctly, and are often rushed or never written.

We're creating a tool that could take the 'fuzzy' notes made during an incident (the alerts, the time, what the engineers are noticing at the time) and use AI to produce a well-structured post mortem automatically. The concept is that it's still being read by a human before it is published, but it's still written in a first draft by the AI, so nobody's writing a report at 2am after a power outage, having fixed it in the first draft.

 How all this will be tested for its effectiveness.

Rather than trying to build this and hope it's good, we're taking advantage of a public dataset of 227 actual postmortems from companies such as Amazon, GitHub, Cloudflare, and Google after their own outages. 

We took the final report of each incident and used AI algorithms to reconstruct the likely original notes from the incident, which are what we called the “raw” notes (as we did not have the messy write-up during the incident). Next, we processed those raw notes with our own AI system and compared the results it produced with the notes that the company released.

In short: when our AI can write something that resembles what real companies do, it's an idea that works.

 Tech we used

For the backend, we will be using Python + Flask.The backend will be Flask + Python.
- The actual AI generation and scoring will be performed using Google's Gemini API.
- For the backend, it is a simple PHP/MySQL database application that has been written using plain HTML, CSS, and JS (no framework).
- JSON result files for storing the results

 What is working, right now?

- Cleaned and scraped 227 real post mortems from danluu's GitHub repo [post-mortems](https://github.com/danluu/post-mortems)
Created feasible “raw incident notes” for all 227 of them, which was done through AI.
- Raw Notes to Structured Post Mortem (Summary, Root Cause, Impact, Timeline, Action Items)
Evaluated 30 of these, with an average score of 3.5/5 (compared with the real postmortems judged by AI – the AI will give each a score).
Copying and pasting 227 actual incidents from a dropdown, or adding your own notes, to create a postmortem, then viewing it next to the real postmortem and a score.

 What if we continue on?

- Connect it to real tools such as Slack/PagerDuty to get incident data automatically rather than hand entered
Allow humans to edit generated draft before finalizing.
- Only calculate the 227 entries, not 30 entries
- Automatically create tickets for the action items, they become tracked.

 Team
Gurnoor Kaur 
Srishti Pilania 
Ananya Sharma 
Kanakpreet Kaur
