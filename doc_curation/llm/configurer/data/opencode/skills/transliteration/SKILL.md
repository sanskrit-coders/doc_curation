---
name: transliteration
description: Transliterates Sanskrit across scripts with indic_transliteration (aksharamukha_helper for Tamil, sanscript otherwise). Use when text must be converted between scripts. For Vedic accent marks, use the accenting skill.
---

Transliterate Sanskrit with `indic_transliteration` (venv: `~/gitland/python_venv`).

- Tamil: `aksharamukha_helper.transliterate_tamil`
- Everything else: `sanscript.transliterate`

```python
from indic_transliteration import sanscript

slp1 = sanscript.transliterate(devanagari_text, sanscript.DEVANAGARI, sanscript.SLP1)
```

Always specify source and target schemes explicitly (`sanscript.DEVANAGARI`, `sanscript.SLP1`, `sanscript.IAST`, etc.).

Do not add or drop accent marks here — see the `accenting` skill.
