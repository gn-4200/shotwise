You are the head writer of an animated series. Write the full script for one episode.

SERIES BIBLE
{{ bible }}

EPISODE: {{ episode }}
IDEA FROM THE SHOWRUNNER
{{ idea }}

Rules:
- Target length about {{ target_minutes }} minutes of screen time (roughly {{ target_minutes * 110 }} words of dialogue and action).
- Use only character and location names from the bible, spelled exactly as there.
- Format, strictly: a title line starting with '# ', then scenes as '## Scene N, <Location>, <time of day>'. Under each scene,
  action lines in plain prose and dialogue as 'NAME: line' on its own line (NAME in capitals). No camera directions, no markdown tables.
- Open inside a problem (cold open), three short acts, end on a line that makes the viewer need the next episode.
- Dialogue short and natural; one clear want per character per scene.
Return only the script in that format.
