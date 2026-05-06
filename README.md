# molloy-detector
*(this readme is completely handwritten. the software was 99% vibe-coded in ~20 min with claude code)*

Runs a local facial and audio recognition monitoring suite that can be configured on specific facial / audio triggers and plays a soundbite upon detection. 

<img width="1909" height="907" alt="Screenshot 2026-05-05 at 5 34 17 PM" src="https://github.com/user-attachments/assets/8d133671-70ff-4e07-9603-2bed573cd958" />


## context 
inspired by [@jencgeo](https://github.com/jencgeo): 
<img width="442" height="68" alt="Screenshot 2026-05-05 at 5 35 49 PM" src="https://github.com/user-attachments/assets/09661fd0-8049-4030-95cf-c05fb3df5801" />

- "Iwtv": [interview with the vampire](https://www.imdb.com/title/tt3960394/), emmy-nominated tv series on amc based on Anne Rice books 
- "sexy back": 2006 hit [SexyBack by Justin Timberlake feat. Timbaland](https://www.youtube.com/watch?v=3gOHvDP_vCs)
- "Daniel": Daniel Molloy played by Eric Bogosian

## quickstart 
- with github cli: `gh repo clone valstechblog/molloy-detector` 
- `cd` into your local `molloy-detector` clone 
- run `python3 main.py` to open UI
- starter assets provided in `assets` folder. user can replace with audio and reference image of your choice (must use exact match filename `sexyback.mp3` for audio playback, *todo update this to be configurable*)
- on mac, terminal will require screen monitoring permissions

## UI workflow 
- Recommend running in free local face recognition mode. Also provided an option to use Claude Vision (added API cost estimate) which is untested
- Upload reference image for facial recognition via `Load Reference Photo` (example provided `assets/reference.molloy.png`
- Click `start monitoring`, which will monitor your entire screen for reference face / audio trigger 
- Modify audio play time and detection cooldown via UI `Play for` and `Cooldown` 
- Modify audio detection triggers, currently hardcoded to not particularly useful strings, in `detector.py:AudioDetector` 
