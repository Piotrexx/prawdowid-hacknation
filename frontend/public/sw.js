/* Service worker dla powiadomień Web Push panelu moderatora. */

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    if (event.data) payload = event.data.json();
  } catch {
    // Puste powiadomienie ma znaczenie samo w sobie: nowy komentarz w panelu.
  }
  const title = payload.title || "Prawdowid – nowy komentarz";
  const options = {
    body:
      payload.body ||
      "W panelu moderatora pojawił się nowy komentarz. Otwórz panel, aby zobaczyć szczegóły.",
    icon: "/logo-avatar-1280.png",
    badge: "/logo-avatar-1280.png",
    tag: "prawdowid-comment",
    renotify: true,
    data: { url: payload.url || "/moderator" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/moderator", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          await client.focus();
          if ("navigate" in client) await client.navigate(target);
          return;
        }
      }
      if (self.clients.openWindow) await self.clients.openWindow(target);
    })(),
  );
});
