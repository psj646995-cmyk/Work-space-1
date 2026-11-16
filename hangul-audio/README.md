# hangul-audio

Pre-made Korean recordings shared by `hangul-learning` (한글 탐험대) and `hangul-classroom` (Hangeul Classroom).

- `lex.json`: letter names, words, phrases and the lines in the conversation quiz.
- `syl-00.json` … `syl-18.json`: single syllables, one pack per initial consonant (ㄱ ㄲ ㄴ … ㅎ).
  Syllables with a final consonant are stored by the sound of the final (ㄱ ㄴ ㄷ ㄹ ㅁ ㅂ ㅇ), so 갓, 갖 and 같 share the recording of 갇.

Each pack maps the text to a base64 MP3 (mono, 40 kbps). Every clip is levelled to the same loudness (-14 dBFS RMS over the voiced part), so syllables and phrases play equally loud. The voice is the open-source
[Supertonic 3](https://huggingface.co/Supertone/supertonic-3) model by Supertone (voice style F1, OpenRAIL-M licence),
generated offline. Words and phrases were checked with Whisper speech recognition and re-made when it misheard them.
Text with no recording is spoken by the device's own voice.
