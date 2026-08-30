from api.demo.browser_harness import BROWSER_ACTION_COMMAND


def test_browser_actions_wait_for_stable_accessibility_state() -> None:
    harness_source = BROWSER_ACTION_COMMAND.partition("<<'PY'\n")[2].rpartition("\nPY")[
        0
    ]

    compile(harness_source, "browser_harness.py", "exec")
    assert "def observe_settled(minimum_milliseconds):" in BROWSER_ACTION_COMMAND
    assert 'state["state_stable"] = True' in BROWSER_ACTION_COMMAND
    assert 'state["state_stable"] = False' in BROWSER_ACTION_COMMAND
    assert "time.sleep(0.15)" not in BROWSER_ACTION_COMMAND
