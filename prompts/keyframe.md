{{ style.one_line }}
{{ shot.shot_type }} shot. {{ shot.action }}
{% for c in characters %}{{ c.name }}: {{ c.look }}. {% endfor %}
Location: {{ location.look }}. {{ scene.time_of_day }}, mood {{ scene.mood }}.
Camera: {{ shot.camera }}. 16:9, clean composition, no text, no watermark.
{% if note %}Correction from the previous attempt: {{ note }}{% endif %}
