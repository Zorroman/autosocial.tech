def test_create_ui_contains_preview_controls():
    js = open("frontend/app.js", "r", encoding="utf-8").read()
    assert "renderSocialPreview(" in js
    assert "data-cw-preview-tab" in js
    assert "cwAutoFixShorten" in js
    assert "cwAutoFixTags" in js
    assert "cwAutoFixCta" in js


def test_create_styles_contains_social_preview_blocks():
    css = open("frontend/styles.css", "r", encoding="utf-8").read()
    assert ".social-preview-card" in css
    assert ".social-preview-media" in css
    assert ".social-actions" in css
