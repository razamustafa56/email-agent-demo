/* Stands in for the dashboard's server in the public demo. The real app.js talks to
   "Shiny"; here a tiny fake Shiny answers every button locally, so nothing is saved
   or sent anywhere. */
(function () {
  var handlers = {};
  var info = {};
  try { info = JSON.parse(document.getElementById("demo-data").textContent); } catch (e) {}

  function emit(name, msg) { if (handlers[name]) handlers[name](msg); }
  function toast(text, undo) { emit("toast", { text: text, undo: undo || null }); }

  function act(a) {
    var op = a.op, id = a.id, sender = a.sender || "this sender";
    switch (op) {
      case "refresh": toast("Up to date. (The real app re-reads the latest mail here.)"); break;
      case "done": toast("Marked done. It won't appear in the next digest.", id); break;
      case "snooze": toast("Snoozed until tomorrow 9:00 AM.", id); break;
      case "undo": toast("Undone."); break;
      case "mute": toast("Got it: " + sender + " won't show up again."); break;
      case "calm": toast("Got it: " + sender + " will never trigger urgent alerts."); break;
      case "always": toast("Got it: " + sender + " will always show up."); break;
      case "save": toast("Draft saved. (In the real app it's updated in Gmail.)"); break;
      case "compose":
        var c = (info.compose || {})[id];
        if (!c) { toast("This email has no draft."); break; }
        emit("compose", { id: id, from: c.from, warning: "", to: c.to, others: c.others,
                          subject: c.subject, allowed: true, why: "", undo: info.undo || 10 });
        break;
      case "send":
        emit("sent", { id: id });
        var from = ((info.compose || {})[id] || {}).from || "your address";
        toast("Demo only: nothing was sent. In the real app this reply goes out from " + from +
              " and lands in the same thread.");
        break;
    }
  }

  window.Shiny = {
    addCustomMessageHandler: function (name, fn) { handlers[name] = fn; },
    setInputValue: function (name, value) {
      if (name === "act") setTimeout(function () { act(value || {}); }, 150);
    }
  };

  // "Open in Gmail" can't open a made-up email
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="mail.google.com"]');
    if (a) { e.preventDefault(); toast("In the real app this opens the email in Gmail."); }
  }, true);

  // Hide the intro for clean screenshots: index.html?clean
  if (/[?&]clean\b/.test(location.search)) document.documentElement.classList.add("clean");

  // app.js listens for two Shiny events through jQuery; a tiny stand-in is enough here
  var listeners = {};
  if (!window.jQuery) {
    window.jQuery = function () {
      return { on: function (type, fn) { (listeners[type] = listeners[type] || []).push(fn); return this; } };
    };
  }
  function fire(type, extra) {
    (listeners[type] || []).forEach(function (fn) { fn(Object.assign({ type: type }, extra || {})); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fire("shiny:connected");
    fire("shiny:value", { name: "root" });
  });
})();
