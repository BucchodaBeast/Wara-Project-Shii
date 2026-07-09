// offline-sync.js
// Handles: registering the service worker, queuing submissions in IndexedDB
// when offline, flushing the queue when connectivity returns, and updating
// the beacon/queue indicators in the nav bar.

const DB_NAME = "dispatcher-offline-db";
const STORE_NAME = "queued-submissions";
const SYNC_TAG = "sync-queued-submissions";

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: "localId", autoIncrement: true });
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function queueSubmission(endpoint, payload) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        tx.objectStore(STORE_NAME).add({ endpoint, payload, queuedAt: Date.now() });
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

async function getQueuedCount() {
    const db = await openDB();
    return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const req = tx.objectStore(STORE_NAME).count();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(0);
    });
}

async function flushQueue() {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, "readonly");
    const all = await new Promise((resolve) => {
        const req = tx.objectStore(STORE_NAME).getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve([]);
    });

    for (const item of all) {
        try {
            const res = await fetch(item.endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(item.payload),
            });
            if (res.ok) {
                const delTx = db.transaction(STORE_NAME, "readwrite");
                delTx.objectStore(STORE_NAME).delete(item.localId);
            }
        } catch (e) {
            // still offline / server unreachable — leave it queued, try again later
            break;
        }
    }
    updateQueueIndicator();
}

async function updateQueueIndicator() {
    const count = await getQueuedCount();
    const el = document.getElementById("queue-indicator");
    if (!el) return;
    if (count > 0) {
        el.classList.add("show");
        el.textContent = `⏳ ${count} queued, will sync`;
    } else {
        el.classList.remove("show");
    }
}

function updateConnectivityUI() {
    const beacon = document.getElementById("connectivity-beacon");
    const banner = document.getElementById("offline-banner");
    const online = navigator.onLine;
    if (beacon) {
        beacon.classList.toggle("online", online);
        beacon.classList.toggle("offline", !online);
    }
    if (banner) {
        banner.classList.toggle("show", !online);
    }
}

async function registerBackgroundSync() {
    if ("serviceWorker" in navigator) {
        const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        if ("SyncManager" in window) {
            try {
                await reg.sync.register(SYNC_TAG);
            } catch (e) {
                // background sync unsupported on this browser — fall back to online event below
            }
        }
        navigator.serviceWorker.addEventListener("message", (event) => {
            if (event.data && event.data.type === "FLUSH_QUEUE") {
                flushQueue();
            }
        });
    }
}

// Intercepts a form submission: tries the network first, falls back to
// queuing in IndexedDB if the request fails (offline).
async function submitWithOfflineFallback(form, endpoint) {
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    if (!navigator.onLine) {
        await queueSubmission(endpoint, payload);
        await updateQueueIndicator();
        return { queued: true };
    }

    try {
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error("Server rejected the submission");
        return { queued: false, ok: true };
    } catch (e) {
        await queueSubmission(endpoint, payload);
        await updateQueueIndicator();
        return { queued: true };
    }
}

window.addEventListener("online", () => {
    updateConnectivityUI();
    flushQueue();
});
window.addEventListener("offline", updateConnectivityUI);

document.addEventListener("DOMContentLoaded", () => {
    updateConnectivityUI();
    updateQueueIndicator();
    registerBackgroundSync();
});
