# 02_structure -- S2 Freeze document structure

**Reads:** 01_boot/output/state.json

**Writes:** pages -> sentences -> tokens with char spans; expected_pages vs completed_pages; per-sentence is_question and dialogue spans; invariant_content list

**Musts:**
- Page marking is an OPEN CHOICE: form-feed, a line '--- page N ---', else single page.
- Never merge sentences (regression: old encoder merged the Peter text into one record).

**Run:** `python 02_structure/run.py`
