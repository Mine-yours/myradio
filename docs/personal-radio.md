# Personal daily dialogue radio

This is an initial automation scaffold. The original player is single-character and **does not yet switch between two character images**. The generated dialogue includes speaker IDs, and audio uses two voices, but visual speaker switching requires a separate player change.

## Configure
1. Edit `radio_config.json`: add HTTPS RSS URLs and topics, then set `enabled` to true.
2. Add `OPENAI_API_KEY` as a repository Actions secret.
3. Review TTS voice licenses and costs. The workflow runs at 07:00 JST (GitHub schedule may be delayed).
4. Set GitHub Pages source to `gh-pages` branch after the first successful publication.
5. Replace the original station name/logo/credits, sample episodes and giscus configuration before public launch.

The workflow uses the RSS title and description as source material; these are not full-article fact checks. Review the output before treating it as verified reporting. Do not put personal or confidential content in public episodes.

## Test
Run `python3 -m py_compile tools/daily_dialogue.py`. With `enabled=false`, running the generator exits without generating an episode. To test generation, enable it and use workflow_dispatch; this consumes API credits.

## Known limitations
- The current player is designed around one on-screen character. Speaker metadata is saved for future visual switching.
- RSS source content is untrusted; generated facts need editorial review.
- Audio is kept out of main and published by `tools/publish.sh` to gh-pages.
- Do not enable unattended publication until source selection and generated content have been reviewed.
