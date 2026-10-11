// Service worker di GestiPC: riceve le notifiche push e gestisce i loro pulsanti.
// Non intercetta le richieste di rete: l'app funziona solo online.
const ICON = "{{ icon }}";
const BADGE = "{{ badge }}";
const ACTION_URL = "{% url 'webapp:push_action' %}";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

function show(data) {
  return self.registration.showNotification(data.title || "GestiPC", {
    body: data.body || "",
    tag: data.tag,
    renotify: !!(data.renotify && data.tag),
    silent: !!data.silent,
    requireInteraction: !!data.requireInteraction,
    icon: ICON,
    badge: BADGE,
    actions: (data.actions || []).map((a) => ({ action: a.action, title: a.title })),
    data: { url: data.url || "/app/", actions: data.actions || [] },
  });
}

async function closeTags(tags) {
  for (const tag of tags || []) {
    const open = await self.registration.getNotifications({ tag: tag });
    open.forEach((n) => n.close());
  }
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(closeTags(data.close_tags).then(() => show(data)));
});

async function runAction(action) {
  try {
    const response = await fetch(ACTION_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: action.token }),
    });
    const result = await response.json();
    await closeTags(result.close_tags);
    await show(result);
  } catch (e) {
    await show({ title: "Errore di connessione", body: "Apri l'app per timbrare.", url: "/app/" });
  }
  await refreshClients();
}

async function refreshClients() {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  windows.forEach((w) => w.postMessage({ type: "gestipc:refresh" }));
}

async function openApp(url) {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const w of windows) {
    if (new URL(w.url).pathname.startsWith("/app/") && "focus" in w) {
      await w.focus();
      if ("navigate" in w) await w.navigate(url);
      return;
    }
  }
  await self.clients.openWindow(url);
}

self.addEventListener("notificationclick", (event) => {
  const notification = event.notification;
  const action = (notification.data.actions || []).find((a) => a.action === event.action);
  notification.close();
  event.waitUntil(action ? runAction(action) : openApp(notification.data.url || "/app/"));
});
