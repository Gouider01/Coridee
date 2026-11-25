/* Presentation-only helpers for the conversation page.
 * - day separators ("Today", "Yesterday", "Mon 3 Nov") between messages
 * - message time shown as HH:MM only (the separator carries the date)
 * - "Pins" button hidden while nothing is pinned
 * Works on server-rendered messages and on ones added later by polling or by
 * "load older messages". It never changes message data or ids. */
(function () {
    "use strict";
    const list = document.getElementById("messages");
    if (!list) return;

    const dayKey = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

    function dayLabel(d) {
        const now = new Date();
        const yesterday = new Date(now);
        yesterday.setDate(now.getDate() - 1);
        if (dayKey(d) === dayKey(now)) return "Today";
        if (dayKey(d) === dayKey(yesterday)) return "Yesterday";
        const opts = { weekday: "short", day: "numeric", month: "short" };
        if (d.getFullYear() !== now.getFullYear()) opts.year = "numeric";
        return d.toLocaleDateString(undefined, opts);
    }

    function previousMessage(node) {
        let p = node.previousElementSibling;
        while (p && !p.classList.contains("message")) p = p.previousElementSibling;
        return p;
    }

    function polish() {
        observer.disconnect();
        list.querySelectorAll(".message").forEach((article) => {
            const sent = new Date(article.dataset.sentAt);
            if (Number.isNaN(sent.getTime())) return;

            const time = article.querySelector(".message-meta time");
            if (time) {
                const hhmm = sent.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
                if (time.textContent !== hhmm) time.textContent = hhmm;
            }

            const prev = previousMessage(article);
            const prevSent = prev ? new Date(prev.dataset.sentAt) : null;
            const needsSeparator = !prevSent || dayKey(prevSent) !== dayKey(sent);
            const before = article.previousElementSibling;
            const hasSeparator = before && before.classList.contains("day-separator");

            if (needsSeparator && !hasSeparator) {
                const sep = document.createElement("div");
                sep.className = "day-separator";
                sep.setAttribute("role", "separator");
                const span = document.createElement("span");
                span.textContent = dayLabel(sent);
                sep.append(span);
                article.before(sep);
            } else if (!needsSeparator && hasSeparator) {
                before.remove();
            } else if (needsSeparator && hasSeparator) {
                const span = before.firstElementChild;
                const label = dayLabel(sent);
                if (span && span.textContent !== label) span.textContent = label;
            }
        });
        observer.observe(list, { childList: true });
    }

    const observer = new MutationObserver((mutations) => {
        const relevant = mutations.some((m) =>
            [...m.addedNodes].some((n) => n.nodeType === 1 && n.classList.contains("message"))
        );
        if (relevant) polish();
    });
    polish();

    const pinButton = document.getElementById("pinned-toggle");
    const pinCount = document.getElementById("pinned-count");
    if (pinButton && pinCount) {
        const syncPins = () => {
            pinButton.hidden = Number(pinCount.textContent) === 0;
        };
        new MutationObserver(syncPins).observe(pinCount, {
            childList: true, characterData: true, subtree: true,
        });
        syncPins();
    }
})();
