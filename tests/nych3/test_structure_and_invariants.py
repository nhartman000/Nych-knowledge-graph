from nych3.llm.gestalt_call import build_request, prompt_text


def test_form_feed_pages(encode):
    st = encode("Peter ran.\fHe stopped.", expected_pages=3)[0]["structure"]
    assert st["page_marker_kind"] == "form_feed"
    assert st["run_counts"] == {"expected_pages": 3, "completed_pages": 2, "complete": False}


def test_line_marker_pages(encode):
    st = encode("--- page 1 ---\nPeter ran.\n--- page 2 ---\nHe stopped.")[0]["structure"]
    assert st["page_marker_kind"] == "line_marker" and st["completed_pages"] == 2
    assert [p["sentences"][0]["text"] for p in st["pages"]] == ["Peter ran.", "He stopped."]


def test_questions_and_dialogue_flagged_never_answered(encode):
    story = 'Peter looked up. Would the wolf come back? "Who is there?" he whispered.'
    state, gst, *_ = encode(story)
    assert state["manifest"]["invariant_story_content_flags"]["contains_question_mark"] is True
    inv = state["structure"]["invariant_content"]
    assert {i["kind"] for i in inv} == {"question", "dialogue"}
    assert all(i.get("answer") is None for i in inv if i["kind"] == "question")
    req = build_request(gst)
    assert "never answer" in req["directive"]
    assert "never answer" in prompt_text(req)
    assert gst["nych3"]["source"]["story"] == story


def test_spatial_and_user_label(encode):
    st = encode(prompt="Narrated in first person.")[0]
    assert st["scope"]["narrator"]["narrative_person"] == "third"
    assert st["scope"]["narrator"]["user_label"] == "first" and st["scope"]["narrator"]["user_label_differs"] is True
