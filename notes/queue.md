# Work queue (for Claude's off-computer runs)
Delo edits this list. Claude does the top unchecked item each run, ticks it, and logs in notes/work-log.md.
Delo can add, remove or reorder items any time. Items marked (Delo) are his: Claude never does them.

- [x] 1. Paper guide: a 1-page plain-words guide to Burnett et al. 2022 (arXiv 2203.10174): what they did, the map + storm drives, how they got 2.3 cm, what we reproduce, 5 terms to know. Write to notes/paper-burnett.md. (done Nov 20)
- [x] 2. Clear control: find a Boreas drive on the same route with no snow falling and a dry road (candidate 2020-12-18). Check its weather from the Boreas paper/site and any public preview. Write findings + the exact download command for Delo (do not download) to notes/control-drive.md. (done Nov 20; needs Delo to watch 2 previews + OK a script change)
- [x] 3. Blind budget design: write notes/blind-budget.md: the question, the method in steps (60 s stretch first), what "recovered" means, the numbers it produces, the null-result story, hours. Plain words. (done Nov 20)
- [x] 4. Step 2 script draft: scripts/score_60s.py (scan-to-map ICP on a 60 s storm stretch vs the Nov 26 map, using src/snowbound/loader.py). Test it on the data. Mark it "Written with Claude" at the top and in the README "Who built what". (done Nov 20; README line is in notes/readme-additions.md for Delo to apply)
- [ ] 5. Video captions: when new voice memos from Friday appear in ~/snowbound-data/video-editor/Raw Footage, transcribe them and write the exact spoken words per line to ~/snowbound-data/video-editor/captions_from_memos.md for the video edit. Do not edit the video project itself.
- [x] 6. (added by Claude, Nov 20) Run scripts/score_60s.py on the full 60 s storm stretch (start at truth, and 1 m off) and write the numbers to notes/results-60s-storm.md. (done Nov 20)
- [x] 7. (added by Claude, Nov 20) Blind budget sweep prototype: scripts/sweep_basin.py (test points every ~20 m, translation offsets on their own axis, heading offsets on their own axis, first match radius bigger than the offset). Test on 2 to 3 points of the storm stretch; the full run happens on the Mac. (done Nov 20, prototype tested on 2 points)
- [ ] (Delo) Write the 3 tests in tests/test_loader.py
- [ ] (Delo) Pivot rule in README
