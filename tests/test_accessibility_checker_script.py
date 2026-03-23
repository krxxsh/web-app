import importlib.util
from pathlib import Path


def _load_checker_module():
    root = Path(__file__).resolve().parents[1]
    checker_path = root / ".agent" / "skills" / "frontend-design" / "scripts" / "accessibility_checker.py"
    spec = importlib.util.spec_from_file_location("accessibility_checker", checker_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_input_with_id_is_not_flagged(tmp_path):
    checker = _load_checker_module()
    html = tmp_path / "sample.html"
    html.write_text("<html><body><input id='email' type='email'></body></html>", encoding="utf-8")

    issues = checker.check_accessibility(html)

    assert "Input without label or aria-label" not in issues


def test_skip_link_prevents_skip_issue(tmp_path):
    checker = _load_checker_module()
    html = tmp_path / "sample.html"
    html.write_text(
        "<html><body><a href='#main-content'>Skip to main content</a><main id='main-content'></main></body></html>",
        encoding="utf-8",
    )

    issues = checker.check_accessibility(html)

    assert "Consider adding skip-to-main-content link" not in issues


def test_onclick_without_keyboard_handler_is_flagged(tmp_path):
    checker = _load_checker_module()
    html = tmp_path / "sample.html"
    html.write_text("<html><body><div onclick='doThing()'>Click</div></body></html>", encoding="utf-8")

    issues = checker.check_accessibility(html)

    assert "onClick without keyboard handler (onKeyDown)" in issues
