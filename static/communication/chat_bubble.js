/* Floating messages bubble: unread badge + recent chats popover. Presentation only. */
(function () {
    "use strict";
    const root = document.getElementById("chat-bubble");
    if (!root) return;
    const toggle = document.getElementById("cb-toggle");
    const panel = document.getElementById("cb-panel");
    const list = document.getElementById("cb-list");
    const badge = document.getElementById("cb-badge");
    const allLink = document.getElementById("cb-all");
    let busy = false;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function render(data) {
        const total = Number(data.unread_total) || 0;
        badge.hidden = total === 0;
        badge.textContent = total > 99 ? "99+" : String(total);
        toggle.setAttribute("aria-label", total ? `Messages, ${total} unread` : "Messages");
        if (data.list_url) allLink.href = data.list_url;
        list.replaceChildren();
        if (!data.chats.length) {
            list.append(el("li", "cb-empty", "No conversations yet."));
            return;
        }
        data.chats.forEach((chat) => {
            const li = el("li");
            const a = el("a", "cb-item" + (chat.unread ? " is-unread" : ""));
            a.href = chat.url;
            const text = el("span", "cb-text");
            text.append(el("span", "cb-name", chat.title), el("span", "cb-preview", chat.preview));
            const side = el("span", "cb-side");
            side.append(el("span", "", chat.time));
            if (chat.unread) side.append(el("span", "cb-dot"));
            a.append(el("span", "cb-avatar", chat.group ? "\u25CF\u25CF" : chat.initial), text, side);
            li.append(a);
            list.append(li);
        });
    }

    async function refresh() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            const response = await fetch(root.dataset.stateUrl, { headers: { Accept: "application/json" }, credentials: "same-origin" });
            if (!response.ok) return;
            render(await response.json());
            root.hidden = false;
        } catch (e) { /* offline: keep the last state */ } finally { busy = false; }
    }

    function setOpen(open) {
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        if (open) refresh();
    }

    toggle.addEventListener("click", () => setOpen(panel.hidden));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { setOpen(false); toggle.focus(); } });
    document.addEventListener("click", (e) => { if (!panel.hidden && !root.contains(e.target)) setOpen(false); });
    document.addEventListener("visibilitychange", refresh);
    refresh();
    setInterval(refresh, 30000);
})();
