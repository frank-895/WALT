"""Fixed Browser Use program executed inside each Atomic sandbox."""

BROWSER_ACTION_COMMAND = r"""BU_CDP_URL="$CHROMIUM_CDP_URL" browser-use <<'PY'
import base64
import json
import os
import time

INTERACTIVE_ROLES = {
    "button",
    "checkbox",
    "combobox",
    "link",
    "listbox",
    "menuitem",
    "option",
    "radio",
    "searchbox",
    "slider",
    "spinbutton",
    "switch",
    "tab",
    "textbox",
}
EXCLUDED_HIGHLIGHT_ROLES = {
    "InlineTextBox",
    "RootWebArea",
    "WebArea",
    "generic",
    "none",
    "presentation",
}


def property_value(node, name, default=None):
    for item in node.get("properties", []):
        if item.get("name") == name:
            return item.get("value", {}).get("value", default)
    return default


def box_for(node_id):
    model = cdp("DOM.getBoxModel", backendNodeId=node_id)["model"]
    quad = model["border"]
    return {
        "left": min(quad[0::2]),
        "right": max(quad[0::2]),
        "top": min(quad[1::2]),
        "bottom": max(quad[1::2]),
    }


def scroll_to_node(node_id):
    try:
        cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=node_id)
    except Exception:
        pass


def click_node(node_id):
    scroll_to_node(node_id)
    box = box_for(node_id)
    click_at_xy(
        (box["left"] + box["right"]) / 2,
        (box["top"] + box["bottom"]) / 2,
    )


def clear_highlight():
    try:
        js("document.getElementById('walt-browser-highlight')?.remove()")
    except Exception:
        pass


def highlight_node(node_id):
    scroll_to_node(node_id)
    resolved = cdp("DOM.resolveNode", backendNodeId=node_id)
    object_id = resolved["object"]["objectId"]
    cdp(
        "Runtime.callFunctionOn",
        objectId=object_id,
        functionDeclaration='''function() {
            document.getElementById('walt-browser-highlight')?.remove();
            const rect = this.nodeType === Node.TEXT_NODE
                ? (() => {
                    const range = document.createRange();
                    range.selectNodeContents(this);
                    return range.getBoundingClientRect();
                })()
                : this.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            const marker = document.createElement('div');
            marker.id = 'walt-browser-highlight';
            marker.setAttribute('aria-hidden', 'true');
            Object.assign(marker.style, {
                position: 'fixed',
                left: `${Math.max(0, rect.left - 4)}px`,
                top: `${Math.max(0, rect.top - 4)}px`,
                width: `${Math.max(8, rect.width + 8)}px`,
                height: `${Math.max(8, rect.height + 8)}px`,
                border: '3px solid #d7ef78',
                borderRadius: '8px',
                boxShadow: '0 0 0 3px rgba(215, 239, 120, 0.22), 0 0 18px rgba(215, 239, 120, 0.55)',
                boxSizing: 'border-box',
                pointerEvents: 'none',
                zIndex: '2147483647',
            });
            document.body.appendChild(marker);
            if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
                marker.animate(
                    [
                        { opacity: 0.55, transform: 'scale(0.98)' },
                        { opacity: 1, transform: 'scale(1)' },
                    ],
                    { duration: 420, iterations: 2, direction: 'alternate', easing: 'ease-out' },
                );
            }
        }''',
    )


def link_target(node_id):
    try:
        resolved = cdp("DOM.resolveNode", backendNodeId=node_id)
        object_id = resolved["object"]["objectId"]
        result = cdp(
            "Runtime.callFunctionOn",
            objectId=object_id,
            functionDeclaration="function(){return this.href || null}",
            returnByValue=True,
        )
        return result.get("result", {}).get("value")
    except Exception:
        return None


def observe():
    page = page_info()
    controls = []
    highlight_targets = []
    seen = set()
    for node in cdp("Accessibility.getFullAXTree")["nodes"]:
        if node.get("ignored"):
            continue
        role = node.get("role", {}).get("value", "")
        name = node.get("name", {}).get("value", "").strip()
        node_id = node.get("backendDOMNodeId")
        if not name or not node_id or (node_id, role, name) in seen:
            continue
        seen.add((node_id, role, name))
        try:
            box = box_for(node_id)
        except Exception:
            continue
        visible = (
            box["right"] > 0
            and box["bottom"] > 0
            and box["left"] < page["w"]
            and box["top"] < page["h"]
            and box["right"] > box["left"]
            and box["bottom"] > box["top"]
        )
        if not visible:
            continue
        target = {
            "node_id": node_id,
            "role": role,
            "name": name,
            "visible": True,
        }
        if role in INTERACTIVE_ROLES:
            controls.append(
                {
                    **target,
                    "disabled": bool(property_value(node, "disabled", False)),
                    "href": link_target(node_id) if role == "link" else None,
                }
            )
        elif role not in EXCLUDED_HIGHLIGHT_ROLES:
            highlight_targets.append(target)
    return {
        "url": page["url"],
        "title": page["title"],
        "controls": controls,
        "highlight_targets": highlight_targets,
    }


request = json.loads(
    base64.b64decode(os.environ["WALT_BROWSER_REQUEST"]).decode("utf-8")
)
ensure_real_tab()
action = request["action"]

if action != "highlight":
    clear_highlight()

if action == "click":
    click_node(request["node_id"])
elif action == "fill":
    click_node(request["node_id"])
    press_key("a", modifiers=2)
    press_key("Backspace")
    type_text(request["value"])
elif action == "highlight":
    highlight_node(request["node_id"])
elif action == "key":
    press_key(request["key"])
elif action == "scroll":
    scroll(0, 0, dy=request["delta_y"])
elif action == "wait":
    time.sleep(request["milliseconds"] / 1000)

if action not in {"observe", "wait"}:
    time.sleep(0.15)

print(json.dumps(observe(), separators=(",", ":")))
PY"""

RELOAD_DEMO_COMMAND = r"""BU_CDP_URL="$CHROMIUM_CDP_URL" browser-use <<'PY'
import os
import time

ensure_real_tab()
goto_url(os.environ["ATOMIC_URL"])

deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    try:
        ensure_real_tab()
        error = js("document.documentElement.dataset.waltError")
        if error:
            raise RuntimeError(f"Atomic failed to prepare: {error}")
        if (
            js("document.documentElement.dataset.waltReady") == "true"
            and "Atomic CRM" in page_info()["title"]
        ):
            break
    except RuntimeError:
        raise
    except Exception:
        pass
    time.sleep(0.1)
else:
    raise RuntimeError("Atomic did not load the tailored demo data")
PY"""
