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
    for node in cdp("Accessibility.getFullAXTree")["nodes"]:
        role = node.get("role", {}).get("value", "")
        name = node.get("name", {}).get("value", "")
        node_id = node.get("backendDOMNodeId")
        if role not in INTERACTIVE_ROLES or not name or not node_id:
            continue
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
        controls.append(
            {
                "node_id": node_id,
                "role": role,
                "name": name,
                "visible": visible,
                "disabled": bool(property_value(node, "disabled", False)),
                "href": link_target(node_id) if role == "link" else None,
            }
        )
    return {
        "url": page["url"],
        "title": page["title"],
        "controls": controls,
    }


request = json.loads(
    base64.b64decode(os.environ["WALT_BROWSER_REQUEST"]).decode("utf-8")
)
ensure_real_tab()
action = request["action"]

if action == "click":
    click_node(request["node_id"])
elif action == "fill":
    click_node(request["node_id"])
    press_key("a", modifiers=2)
    press_key("Backspace")
    type_text(request["value"])
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
