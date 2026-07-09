// dashboard.js — live updates for the coordinator dispatch board.

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
