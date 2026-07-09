// sw.js — enables offline-first behaviour for the citizen submission forms.
// Strategy: this app is small enough that we don't cache pages aggressively;
// the real value here is catching failed POST requests (offline submissions)
// and letting the page's own IndexedDB queue + background sync handle retry.

const SYNC_TAG = "sync-queued-submissions";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// When the browser regains connectivity, it fires a sync event for any
// tag we registered while offline (see offline-sync.js on the page side).
self.addEventListener("sync", (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(flushQueueFromIndexedDB());
  }
});

async function flushQueueFromIndexedDB() {
  const clients = await self.clients.matchAll();
  // Delegate the actual flush to the page context, which already has the
  // IndexedDB helper loaded (avoids duplicating the DB logic in two places).
  clients.forEach((client) => client.postMessage({ type: "FLUSH_QUEUE" }));
}
