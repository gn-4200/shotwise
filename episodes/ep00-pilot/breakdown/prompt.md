You are the storyboard supervisor of an animated series. Break the script below into scenes
and shots for production.

SERIES BIBLE
# The Lantern Line (sample bible, replace with your series)

World: Qamar, a desert city of sandstone rooftops where lanterns are the only light after dusk.
Tone: warm, quiet adventure. Short scenes, one clear want per episode, a cliffhanger line at the end.

## Characters (use these names exactly)
- Ayla: a 24-year-old mapmaker. Short black hair with a white streak, amber eyes, dusty blue field jacket, brass compass on a cord. Curious, quick, hides worry with jokes.
- Tariq: the 70-year-old lantern keeper. White beard, deep-set grey eyes, patched ochre robe, carries a lantern with cracked green glass. Slow to speak, never wrong about the wind.

## Locations (use these names exactly)
- Qamar Rooftops: flat sandstone rooftops at dusk, hanging lanterns, distant dunes.
- The Lantern Tower: a narrow spiral stair inside a stone tower lit by one green lantern.
- The Dry Canal: a cracked stone channel below the city, moonlit, echoing.

## Episode formula
Cold open in the middle of a problem, title card, three acts, a line that makes the viewer need the next episode.


VISUAL STYLE
motion_words: subtle natural motion, slow cinematic camera, consistent lighting
negative: text, watermark, logo, extra fingers, deformed face, blurry, low quality,
  photo-realistic
one_line: Painterly 2D animation style, soft edges, warm amber and teal palette, gentle
  film grain, cinematic lighting


SCRIPT FOR ep00-pilot
# Ep 00, Pilot: "The Last Green Lantern"

## Scene 1, Qamar Rooftops, dusk
Wide on the rooftops. Lanterns flicker on one by one. Ayla runs across a roof, a map tube on her back.
AYLA: Tariq! The west line went dark. Three towers, all at once.
Tariq is already on the ledge, holding his green lantern up to the wind.
TARIQ: Not dark. Hidden. Someone is drawing the lamps down into the canal.
AYLA: Nobody goes into the canal. There is nothing down there but echoes.
TARIQ: Then we will go and ask the echoes.

## Scene 2, The Lantern Tower, night
Close on Tariq's hands lighting a second lantern from the first. The green glass hums.
TARIQ: My grandfather lit this one the night the river left. It has never gone out.
AYLA: And if it does?
TARIQ: Then the city forgets where it is.
Ayla unrolls her map on the stair. A line of lanterns is drawn across it, three of them crossed out.

## Scene 3, The Dry Canal, night
Establishing shot of the canal from above, moonlight on puddles. Two small figures climb down.
Ayla's compass needle spins, then points down the tunnel.
AYLA: It is pointing at something that is not north.
A faint green glow far down the canal. Tariq raises his lantern. The glow answers, blinking twice.
TARIQ: That is not a lamp. That is a signal.
Hard cut. Title: The Lantern Line.


Rules:
- Shots run 4 to 8 seconds, target 6. Every line of dialogue belongs to exactly one shot.
- Use shot_type closeup_dialogue for any line longer than six words, so it can be lip-synced.
- Set needs_video to false for reaction shots, establishing shots and inserts that a slow camera move
  can carry. Aim for about 60 percent of shots with needs_video false.
- Use only character and location names that appear in the bible, spelled exactly as there.
- camera is a short phrase a cinematographer would say. action describes what the viewer sees, not feelings.
- Give every scene a mood word usable as a music prompt. Shot ids look like s01_01 (scene, shot).
Return JSON that matches the provided schema and nothing else.