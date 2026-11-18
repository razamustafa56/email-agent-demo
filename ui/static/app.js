/* Client-side behaviour: tabs, account filter, counts, deep links, actions, idle pause.
   Switching tabs or filters never talks to the server; only real actions do. */
(function () {
  var view = { f: "all", t: "summary" };
  var IDLE_MS = 15 * 60 * 1000;
  var lastActive = Date.now();
  var handledDeepLink = false;
  var toastTimer = null;

  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function app() { return document.getElementById("app"); }
  function send(payload) {
    if (window.Shiny && Shiny.setInputValue) {
      payload.nonce = Date.now() + Math.random();
      Shiny.setInputValue("act", payload, { priority: "event" });
    }
  }

  function apply() {
    var a = app();
    if (!a) return;
    a.className = "f-" + view.f + " t-" + view.t;
    $all("[data-filter]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.filter === view.f ? "true" : "false"); });
    $all("[data-tab-btn]").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tabBtn === view.t ? "true" : "false"); });
    recount();
    try { localStorage.setItem("dash-view", JSON.stringify(view)); } catch (e) {}
  }

  function visible(el) {
    return !el.classList.contains("gone") && (view.f === "all" || el.dataset.acc === view.f);
  }

  function recount() {
    var counts = { summary: 0, reply: 0, todo: 0, opp: 0, waiting: 0, fyi: 0 };
    $all("#p-summary li[data-id]").forEach(function (li) { if (visible(li)) counts.summary++; });
    $all(".card[data-tab]").forEach(function (c) { if (visible(c)) counts[c.dataset.tab] = (counts[c.dataset.tab] || 0) + 1; });
    Object.keys(counts).forEach(function (k) {
      $all('[data-count="' + k + '"]').forEach(function (s) { s.textContent = counts[k]; });
      $all('.empty[data-for="' + k + '"]').forEach(function (e) { e.classList.toggle("show", counts[k] === 0); });
    });
  }

  function hideItem(id, hide) {
    $all('[data-id="' + CSS.escape(id) + '"]').forEach(function (el) { el.classList.toggle("gone", hide); });
    recount();
  }

  function openItem(id, flash) {
    var c = document.querySelector('.card[data-id="' + CSS.escape(id) + '"]');
    if (!c) return false;
    if (view.f !== "all" && c.dataset.acc !== view.f) view.f = "all";
    view.t = c.dataset.tab;
    apply();
    c.open = true;
    c.scrollIntoView({ behavior: "smooth", block: "start" });
    if (flash) { c.classList.add("flash"); setTimeout(function () { c.classList.remove("flash"); }, 2200); }
    return true;
  }

  function init() {
    if (!app()) return;
    try { var saved = JSON.parse(localStorage.getItem("dash-view") || "null"); if (saved) view = saved; } catch (e) {}
    apply();
    if (!handledDeepLink) {
      handledDeepLink = true;
      var id = new URLSearchParams(location.search).get("item");
      if (id) openItem(id, true);
    }
  }

  function showToast(text, undoId) {
    var t = document.getElementById("toast");
    if (!t) return;
    t.innerHTML = "";
    var span = document.createElement("span");
    span.textContent = text;
    t.appendChild(span);
    if (undoId) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = "Undo";
      b.onclick = function () { hideItem(undoId, false); send({ op: "undo", id: undoId }); t.classList.remove("show"); };
      t.appendChild(b);
    }
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 5000);
  }

  function login() {
    var pw = document.getElementById("pw");
    if (pw && window.Shiny && Shiny.setInputValue) {
      Shiny.setInputValue("login", { pw: pw.value, nonce: Date.now() }, { priority: "event" });
    }
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("#unlock")) { login(); return; }
    var el = e.target.closest("[data-filter],[data-tab-btn],[data-goto],[data-op]");
    if (!el) return;
    if (el.dataset.filter) { view.f = el.dataset.filter; apply(); return; }
    if (el.dataset.tabBtn) { view.t = el.dataset.tabBtn; apply(); return; }
    if (el.dataset.goto) { openItem(el.dataset.goto, true); return; }
    var op = el.dataset.op, id = el.dataset.id;
    if (op === "save") {
      var ta = document.querySelector('textarea[data-draft="' + CSS.escape(id) + '"]');
      send({ op: "save", id: id, text: ta ? ta.value : "" });
      return;
    }
    if (op === "done" || op === "snooze" || op === "mute") hideItem(id, true);
    send({ op: op, id: id, sender: el.dataset.sender || "" });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target && e.target.id === "pw") { e.preventDefault(); login(); }
  });

  ["click", "keydown", "scroll", "touchstart", "mousemove"].forEach(function (ev) {
    document.addEventListener(ev, function () { lastActive = Date.now(); }, { passive: true });
  });
  setInterval(function () {
    if (Date.now() - lastActive > IDLE_MS && window.Shiny && Shiny.setInputValue) {
      var idle = document.getElementById("idle");
      if (idle && idle.hidden) {
        idle.hidden = false;
        Shiny.setInputValue("idle", Date.now(), { priority: "event" });
      }
    }
  }, 30000);

  /* ---------------- sending: confirm dialog + undo countdown ---------------- */
  var PLACEHOLDER = /\[[^\[\]\n]{1,120}\]/g;
  var countdown = null;

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function draftText(id) {
    var ta = document.querySelector('textarea[data-draft="' + CSS.escape(id) + '"]');
    return ta ? ta.value : "";
  }

  function closeCompose() {
    var c = document.getElementById("compose");
    if (c) c.remove();
  }

  function openCompose(m) {
    closeCompose();
    var text = draftText(m.id);
    var wrap = el("div", { id: "compose", role: "dialog", "aria-modal": "true", "aria-labelledby": "compose-title" });
    var box = el("div", { class: "compose-box" });
    wrap.appendChild(box);
    box.appendChild(el("h2", { id: "compose-title" }, "Send reply"));

    var fromRow = el("p", { class: "compose-from" });
    fromRow.appendChild(el("span", { class: "label" }, "From "));
    fromRow.appendChild(document.createTextNode(m.from));
    box.appendChild(fromRow);
    if (m.warning) box.appendChild(el("p", { class: "compose-warn" }, m.warning));

    box.appendChild(el("label", { for: "c-to", class: "label" }, "To"));
    var to = el("input", { id: "c-to", type: "text", autocomplete: "off" });
    to.value = (m.to || []).join(", ");
    box.appendChild(to);

    var others = m.others || [];
    var all = null;
    if (others.length) {
      var row = el("label", { class: "compose-all" });
      all = el("input", { type: "checkbox", id: "c-all" });
      row.appendChild(all);
      row.appendChild(document.createTextNode(" Reply all (also " + others.join(", ") + ")"));
      box.appendChild(row);
    }
    box.appendChild(el("label", { for: "c-cc", class: "label" }, "Cc"));
    var cc = el("input", { id: "c-cc", type: "text", autocomplete: "off", placeholder: "optional" });
    box.appendChild(cc);
    if (all) all.addEventListener("change", function () {
      var current = cc.value.split(/[,;]+/).map(function (s) { return s.trim(); }).filter(Boolean);
      if (all.checked) {
        others.forEach(function (o) { if (current.indexOf(o) < 0) current.push(o); });
      } else {
        current = current.filter(function (c) { return others.indexOf(c) < 0; });
      }
      cc.value = current.join(", ");
    });

    var subj = el("p", { class: "compose-subject" });
    subj.appendChild(el("span", { class: "label" }, "Subject "));
    subj.appendChild(document.createTextNode(m.subject));
    box.appendChild(subj);
    box.appendChild(el("pre", { class: "compose-body" }, text || "(empty)"));

    var problems = [];
    if (!m.allowed) problems.push(m.why);
    var ph = (text.match(PLACEHOLDER) || []);
    if (ph.length) problems.push("Fill in the bracketed parts in the draft first: " + ph.slice(0, 3).join(", "));
    if (!text.trim()) problems.push("The draft is empty.");
    problems.forEach(function (p) { box.appendChild(el("p", { class: "compose-problem" }, p)); });

    box.appendChild(el("p", { class: "hint" },
      "To change the text, close this and edit the draft. After you press Send you have " + m.undo +
      " seconds to undo; keep this page open (closing it cancels the send)."));

    var actions = el("div", { class: "actions" });
    var cancel = el("button", { type: "button", class: "btn" }, "Cancel");
    var go = el("button", { type: "button", class: "btn primary" }, "Send");
    if (problems.length) go.disabled = true;
    cancel.onclick = closeCompose;
    go.onclick = function () {
      var payload = { op: "send", id: m.id, to: to.value, cc: cc.value, text: draftText(m.id) };
      if (!payload.to.trim()) { to.focus(); return; }
      closeCompose();
      startCountdown(payload, m.undo, to.value);
    };
    actions.appendChild(go);
    actions.appendChild(cancel);
    box.appendChild(actions);
    wrap.addEventListener("click", function (e) { if (e.target === wrap) closeCompose(); });
    document.body.appendChild(wrap);
    to.focus();
  }

  function stopCountdown() {
    if (countdown) { clearInterval(countdown.timer); countdown = null; }
  }

  function startCountdown(payload, seconds, toText) {
    stopCountdown();
    var t = document.getElementById("toast");
    var left = seconds;
    var span = el("span");
    var undo = el("button", { type: "button" }, "Undo");
    t.innerHTML = "";
    t.appendChild(span);
    t.appendChild(undo);
    t.classList.add("show");
    clearTimeout(toastTimer);
    function paint() { span.textContent = "Sending to " + toText + " in " + left + "s"; }
    paint();
    countdown = { timer: setInterval(function () {
      lastActive = Date.now();
      left -= 1;
      if (left <= 0) {
        stopCountdown();
        span.textContent = "Sending…";
        undo.remove();
        send(payload);
        return;
      }
      paint();
    }, 1000) };
    undo.onclick = function () { stopCountdown(); showToast("Not sent."); };
  }

  if (window.jQuery) {
    jQuery(document).on("shiny:value", function (e) { if (e.name === "root") setTimeout(init, 0); });
    jQuery(document).on("shiny:connected", function () {
      Shiny.addCustomMessageHandler("toast", function (m) { showToast(m.text, m.undo); });
      Shiny.addCustomMessageHandler("compose", openCompose);
      Shiny.addCustomMessageHandler("sent", function (m) { hideItem(m.id, true); });
      Shiny.addCustomMessageHandler("send_failed", function (m) { stopCountdown(); });
    });
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeCompose(); });
})();
