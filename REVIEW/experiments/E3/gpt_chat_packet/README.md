# E3 GPT chat grading packet (32 items, 2 chunks)
1. Open a new GPT chat for each chunk. Paste the whole `chunk_N.md` (rubric included).
2. Save GPT's JSON array reply as `responses/chunk_N.json` (pasting as-is is fine; the script extracts the array).
3. Run `PYTHONPATH=shared /workspace/kgenv/bin/python tools/e3/gpt_packet.py ingest`.
Items are blinded and shuffled. The key is in `../gpt_chat_key_SECRET.json`; don't paste it into GPT.
