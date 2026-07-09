// dashboard.js — live updates, filters, map, and the dispatch modal for the
// coordinator dispatch board.

let leafletMap = null;
let mapMarkersLayer = null;

document.addEventListener("DOMContentLoaded", () => {
    if (!document.body.dataset.role || document.body.dataset.role !== "coordinator") return;

    const socket = io();

    socket.on("connect", () => {
        socket.emit("join_coordinator_room");
    });

    socket.on("new_request", (data) => {
        showLiveToast(`New request: ${data.category} (${data.urgency})`);
        setTimeout(() => window.location.reload(), 1200);
    });

    socket.on("new_offer", (data) => {
        showLiveToast(`New offer: ${data.resource_type}`);
        setTimeout(() => window.location.reload(), 1200);
    });

    socket.on("status_update", (data) => {
        showLiveToast(`Status changed: ${data.entity_type} #${data.entity_id} → ${data.new_status}`);
        setTimeout(() => window.location.reload(), 1200);
    });

    socket.on("matches_computed", (data) => {
        showLiveToast(`Matches computed for request #${data.request_id}`);
    });

    socket.on("dispatch_created", (data) => {
        showLiveToast(`Dispatched request #${data.request_id} ↔ offer #${data.offer_id}`);
        setTimeout(() => window.location.reload(), 1200);
    });

    initFilters();
});

function showLiveToast(message) {
    let toast = document.getElementById("live-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "live-toast";
        toast.className = "live-toast";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.display = "block";
}

function toggleAuditLog(entityType, entityId, btn) {
    const container = document.getElementById(`audit-${entityType}-${entityId}`);
    if (container.classList.contains("show")) {
        container.classList.remove("show");
        return;
    }
    if (!container.dataset.loaded) {
        fetch(`/coordinator/audit/${entityType}/${entityId}`)
            .then((r) => r.text())
            .then((html) => {
                container.innerHTML = html;
                container.dataset.loaded = "true";
            });
    }
    container.classList.add("show");
}

/* ---------- dispatch modal ---------- */

function openDispatchModal(requestId, offerId, needCategory, offerType, maxNeeded, maxOffer) {
    document.getElementById("dispatch-request-id").value = requestId;
    document.getElementById("dispatch-offer-id").value = offerId;
    const suggested = Math.max(0.1, Math.min(maxNeeded || 1, maxOffer || 1));
    const qtyInput = document.getElementById("dispatch-quantity");
    qtyInput.value = suggested;
    qtyInput.max = maxOffer || "";
    document.getElementById("dispatch-modal-sub").textContent =
        `Request #${requestId} (${needCategory}) ↔ Offer #${offerId} (${offerType})`;
    document.getElementById("dispatch-modal").classList.add("show");
}

function closeDispatchModal() {
    document.getElementById("dispatch-modal").classList.remove("show");
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDispatchModal();
});

/* ---------- list / map toggle ---------- */

function setBoardView(view) {
    const listBtn = document.getElementById("view-list-btn");
    const mapBtn = document.getElementById("view-map-btn");
    const listView = document.getElementById("board-list-view");
    const mapView = document.getElementById("dispatch-map");

    if (view === "map") {
        listView.style.display = "none";
        mapView.classList.add("show");
        listBtn.classList.remove("active");
        mapBtn.classList.add("active");
        initMap();
        setTimeout(() => { if (leafletMap) leafletMap.invalidateSize(); }, 50);
    } else {
        listView.style.display = "";
        mapView.classList.remove("show");
        mapBtn.classList.remove("active");
        listBtn.classList.add("active");
    }
}

function initMap() {
    if (leafletMap || typeof L === "undefined") return;
    const dataEl = document.getElementById("map-markers-data");
    let markers = [];
    try { markers = JSON.parse(dataEl.textContent); } catch (e) { markers = []; }

    if (markers.length === 0) {
        document.getElementById("dispatch-map").innerHTML =
            '<div class="empty-state">No locations to show yet — pending needs and available offers with coordinates will appear here.</div>';
        return;
    }

    const avgLat = markers.reduce((s, m) => s + m.lat, 0) / markers.length;
    const avgLng = markers.reduce((s, m) => s + m.lng, 0) / markers.length;

    leafletMap = L.map("dispatch-map").setView([avgLat, avgLng], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 18,
    }).addTo(leafletMap);

    const urgencyColor = { critical: "#dc2626", high: "#f59e0b", medium: "#64718a", low: "#64718a" };

    markers.forEach((m) => {
        const color = m.kind === "request" ? (urgencyColor[m.urgency] || "#dc2626") : "#0d9488";
        const marker = L.circleMarker([m.lat, m.lng], {
            radius: 8,
            color: color,
            fillColor: color,
            fillOpacity: 0.75,
            weight: 2,
        }).addTo(leafletMap);
        const kindLabel = m.kind === "request" ? "Need" : "Offer";
        marker.bindPopup(`<strong>${kindLabel}</strong><br>${m.label}`);
    });
}

/* ---------- filters & sort ---------- */

function initFilters() {
    const categorySel = document.getElementById("filter-category");
    const urgencySel = document.getElementById("filter-urgency");
    const sortSel = document.getElementById("sort-requests");
    const unmatchedChk = document.getElementById("filter-unmatched");
    if (!categorySel) return;

    [categorySel, urgencySel, unmatchedChk].forEach((el) => el.addEventListener("change", applyFilters));
    sortSel.addEventListener("change", applySort);

    applyFilters();
}

function applyFilters() {
    const category = document.getElementById("filter-category").value;
    const urgency = document.getElementById("filter-urgency").value;
    const unmatchedOnly = document.getElementById("filter-unmatched").checked;

    let visibleRequests = 0;
    document.querySelectorAll("#requests-list > .entry").forEach((el) => {
        const matchesCategory = !category || el.dataset.category === category;
        const matchesUrgency = !urgency || el.dataset.urgency === urgency;
        const matchesUnmatched = !unmatchedOnly || el.dataset.unmatched === "true";
        const visible = matchesCategory && matchesUrgency && matchesUnmatched;
        el.style.display = visible ? "" : "none";
        if (visible) visibleRequests += 1;
    });

    let visibleOffers = 0;
    document.querySelectorAll("#offers-list > .entry").forEach((el) => {
        const matchesCategory = !category || el.dataset.category === category;
        const visible = matchesCategory;
        el.style.display = visible ? "" : "none";
        if (visible) visibleOffers += 1;
    });

    document.getElementById("filter-count").textContent =
        `${visibleRequests} need${visibleRequests === 1 ? "" : "s"} · ${visibleOffers} offer${visibleOffers === 1 ? "" : "s"} shown`;
}

function applySort() {
    const sortBy = document.getElementById("sort-requests").value;
    const list = document.getElementById("requests-list");
    const items = Array.from(list.querySelectorAll(".entry"));
    const urgencyRank = { critical: 0, high: 1, medium: 2, low: 3 };

    items.sort((a, b) => {
        if (sortBy === "urgency") {
            return (urgencyRank[a.dataset.urgency] ?? 4) - (urgencyRank[b.dataset.urgency] ?? 4);
        }
        if (sortBy === "score") {
            return parseFloat(b.dataset.score || 0) - parseFloat(a.dataset.score || 0);
        }
        // newest first (default) — created_at is an ISO string, sorts fine lexicographically
        return (b.dataset.created || "").localeCompare(a.dataset.created || "");
    });

    items.forEach((el) => list.appendChild(el));
}
