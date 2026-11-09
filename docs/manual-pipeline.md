# The Salt Brothers, Part 1: manual pipeline

Target: 28-minute film, realistic dark fantasy, about 300 shots, 5 voices. One pass by hand. Each step names the
Shotwise stage it maps to, so the automation later follows this exact order.

Folder: shotwise/bible/ (series bible, sheets) and shotwise/episodes/part1/ (this film: idea.md, script.md, breakdown.json, shots/sXX_YY/, music/, marketing/, log/).

| # | Step (Shotwise stage) | Do | Tools | Output | Done when | Time |
|---|---|---|---|---|---|---|
| 0 | Setup | Student plan, YouTube channel and handles on TikTok/IG/FB with the same name, folder tree, a log sheet (step, hours, cost, keeper rate) | Google AI Plus, DaVinci Resolve (free), CapCut | folders, log.xlsx | every account exists, same handle everywhere | 1 day |
| 1 | Bible (bible/) | Characters with fixed look strings, 3-view sheets each, locations, the one world rule, style guide with 10 reference frames, voice casting notes | Nano Banana Pro | bible.md, sheets/*.png | 5 characters hold across 3 test generations | 2–3 days |
| 2 | Script (script) | Outline to full script, ~3,200 words, scene headings and NAME: lines, read aloud | any chat model + you | script.md | read-aloud runs 26–30 min | 3–5 days |
| 3 | Shot list (breakdown) | One row per shot: id, scene, duration, type, cast, location, camera, action, lines, still-or-video, hero | spreadsheet or breakdown.json | breakdown.json | durations sum to 28 min, every line assigned, ~30 hero shots marked | 1–2 days |
| 4 | Keyframes (keyframes) | 2 candidates for hero shots, 1 for stills, references = character sheets + look strings; pick, save approved.png, log the prompt | Nano Banana Pro (50/day), Nano Banana free (100/day) for stills | shots/*/keyframes/approved.png | all 300 approved, contact sheet looks like one film | 1–2 weeks |
| 5 | Voices (voice) | Cast 5 voices, generate every line, line_n.wav per shot, normalise to -16 LUFS | ElevenLabs Creator, or Kokoro/Chatterbox on Kaggle | shots/*/voice/line_n.wav | all lines exported | 2–3 days |
| 6 | Clips (video, lipsync) | Hero shots: image-to-video from approved.png with a motion prompt, 3–4 attempts, pick. Dialogue close-ups: lip-sync with the voice line. Stills: nothing, the edit moves them | Kling Pro, or Veo in Flow | shots/*/video/approved.mp4, lipsync/approved.mp4 | every hero shot and close-up has an approved clip | 1–2 weeks |
| 7 | Music and sound (music) | One cue per scene, ambient beds, SFX | YouTube Audio Library, Lyria 3, Freesound, Pixabay | music/*.wav, sfx/ | cue list matches the scene list | 2 days |
| 8 | Edit (assemble) | Timeline in shot order, Ken Burns on stills, dialogue track, ducked music, SFX, subtitles, title and end card, colour pass, 4K export | DaVinci Resolve, free upscaler on Kaggle | export/part1.mp4, part1.srt | full watch-through with notes fixed, -16 LUFS, no shot under 4 s | 1 week |
| 9 | Packaging (publish) | Title formula, 3 thumbnails, description (logline, chapters, AI disclosure, original story, credits, the debate question), tags, end screen, SRT, synthetic-media checkbox, scheduled premiere, pinned question | YouTube Studio | scheduled premiere | premiere date set, 10 days out | 1 day |
| 10 | Teasers (cutdowns) | 3 verticals 20–45 s (wonder, betrayal, rule) + 3 cutdowns 60–90 s, captions burned, scheduled over 10 days on TikTok, Reels, FB Reels, Shorts; $20–50 ad test per teaser | CapCut, Meta Ads | marketing/*.mp4, calendar | calendar filled, winner identified | 2 days |
| 11 | Launch week | Premiere live, reply to comments, pin the question, watch retention, claim copies, post the Part 2 teaser at the peak | YouTube Studio | metrics sheet | week logged | 1 week |
| 12 | Retro (log/) | Hours, costs, keeper rates, the three steps that hurt most. This list is the automation backlog | log.xlsx | retro.md | written within 2 days of launch | half day |

Total: about 6–8 weeks part time, $120–330 in tools, plus $150–350 optional ad tests.

Rules that keep the film monetisable: paid or commercial-licensed tools only (no Kling free, Suno free, ElevenLabs free), AI disclosure on upload, keep every prompt and pick in the shot folder.
