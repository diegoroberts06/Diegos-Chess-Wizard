# Diegos-Chess-Wizard

A desktop app I built to run my chess classes. It tracks every student's Elo rating, game results, and skill mastery in one place, so I can see who is improving, who is stuck, and what to teach next.

I coach chess classes in San Antonio, and paper records were not cutting it. This is the tool I actually use.

## Features

- **Elo ratings.** Every student starts at 500 and ratings update after each recorded game using the standard Elo formula (K = 32, tuned so beginner ratings move at a sensible pace).
- **Standings view.** The whole class ranked by rating, with games played and win/loss records.
- **Game recording and log.** Record results as White or Black with wins, losses, and draws. Every game is kept in a full history log.
- **Skill tracking.** 15 core skills, from piece movement and castling to forks, pins, and pawn endgames. Each student is rated per skill on a 0 to 4 mastery scale (Not introduced, Learning, Developing, Proficient, Mastered).
- **Skill gap report.** A class-wide view shows which skills the group has mastered and which ones need teaching time, so lesson planning is based on data instead of guessing.
- **Player management.** Add and remove students as classes change.
- **Automatic saving.** All data persists to a local JSON file (`chess_wizard_data.json`) next to the script. It also reads the older `chess_class_data.json` format so records from earlier versions carry over.

## Getting started

You need Python 3 and one package:

pip install customtkinter

Then run:

python chess_wizard__1.py

## How it is built

- Python with a customtkinter GUI
- Ratings engine based on the standard Elo expected-score formula
- Data stored locally as JSON, no account or internet connection needed
- Some AI development assistance

## Why I built it

Chess coaching runs on feel unless you measure it. Two students can both "seem fine" while one has quietly stalled for a month. The tracker makes progress visible: rating trends show who is actually improving, and the skill grid shows exactly which concepts a class is missing. It is the same idea I keep coming back to in my business analytics studies: collect clean data, then let it tell you what to do next.

## License

MIT License. See `LICENSE` for details.
