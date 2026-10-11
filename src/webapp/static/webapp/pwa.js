// PWA: service worker, iscrizione alle notifiche push, installazione.
(function () {
  const script = document.currentScript;
  const inTelegram = window.GestiPC && window.GestiPC.inTelegram;
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const pushSupported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  // Il service worker serve solo per le notifiche: non lo registriamo dentro Telegram.
  const swReady = !inTelegram && "serviceWorker" in navigator
    ? navigator.serviceWorker.register(script.dataset.sw, { scope: "/" }).then(() => navigator.serviceWorker.ready)
    : Promise.resolve(null);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", (e) => {
      if (e.data && e.data.type === "gestipc:refresh") window.location.reload();
    });
  }

  // --- Installazione (Chrome/Android) ---
  const installCard = document.getElementById("installa");
  let installEvent = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    installEvent = e;
    if (installCard && !inTelegram) installCard.hidden = false;
  });
  if (installCard) {
    installCard.querySelector("[data-do=install]").addEventListener("click", async () => {
      if (!installEvent) return;
      installEvent.prompt();
      await installEvent.userChoice;
      installEvent = null;
      installCard.hidden = true;
    });
  }
  window.addEventListener("appinstalled", () => { if (installCard) installCard.hidden = true; });

  // --- Notifiche ---
  const card = document.getElementById("notifiche");
  if (!card) return;

  const errorEl = card.querySelector("[data-error]");
  const setState = (state) => {
    card.querySelectorAll("[data-state]").forEach((el) => { el.hidden = el.dataset.state !== state; });
    errorEl.hidden = true;
  };
  const showError = (msg) => { errorEl.textContent = msg; errorEl.hidden = false; };

  const post = (url, body) => fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": card.dataset.csrf },
    body: JSON.stringify(body || {}),
  }).then((r) => r.json());

  function urlBase64ToUint8Array(base64) {
    const padding = "=".repeat((4 - (base64.length % 4)) % 4);
    const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }

  async function refresh() {
    if (inTelegram) return setState("telegram");
    if (!pushSupported) return setState(isIOS && !standalone ? "ios-install" : "unsupported");
    if (Notification.permission === "denied") return setState("denied");
    const reg = await swReady;
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      // Ri-invia l'iscrizione: la associa all'utente corrente e la ripristina se il server l'ha rimossa.
      post(card.dataset.subscribe, sub.toJSON());
      return setState("on");
    }
    setState("off");
  }

  async function enable() {
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return refresh();
      const reg = await swReady;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(card.dataset.key),
      });
      const res = await post(card.dataset.subscribe, sub.toJSON());
      if (!res.ok) throw new Error(res.error || "Iscrizione non riuscita.");
      await refresh();
    } catch (e) {
      showError(e.message || "Impossibile attivare le notifiche.");
    }
  }

  async function disable() {
    const reg = await swReady;
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      await post(card.dataset.unsubscribe, { endpoint: sub.endpoint });
      await sub.unsubscribe();
    }
    refresh();
  }

  async function test() {
    const res = await post(card.dataset.test);
    if (!res.ok) showError("Invio non riuscito. Prova a disattivare e riattivare le notifiche.");
  }

  card.addEventListener("click", (e) => {
    const action = e.target.closest("[data-do]");
    if (!action) return;
    ({
      enable: enable,
      disable: disable,
      test: test,
      "open-browser": () => window.GestiPC.tg.openLink(card.dataset.site),
    })[action.dataset.do]();
  });

  refresh().catch(() => setState("unsupported"));
})();
