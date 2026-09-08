// ---------- Three-dot dropdown menu ----------
function closeAllMenus(exceptId) {
  document.querySelectorAll(".menu-dropdown.open").forEach((menu) => {
    if (menu.id !== `menu-${exceptId}`) menu.classList.remove("open");
  });
}

function toggleMenu(taskId) {
  const menu = document.getElementById(`menu-${taskId}`);
  const wasOpen = menu.classList.contains("open");
  closeAllMenus(null);
  if (wasOpen) return;

  const trigger = document.querySelector(`#task-${taskId} .menu-trigger`);
  const rect = trigger.getBoundingClientRect();
  const menuHeight = 90; // approx height of the 2-item dropdown

  // Open above the button instead of below if there isn't room underneath
  const openUpward = window.innerHeight - rect.bottom < menuHeight;

  menu.style.left = `${rect.right - 120}px`; // right-align to the trigger (min-width: 120px)
  menu.style.top = openUpward
    ? `${rect.top - menuHeight}px`
    : `${rect.bottom + 4}px`;

  menu.classList.add("open");
}

// Close dropdown when clicking anywhere outside it
document.addEventListener("click", (event) => {
  if (!event.target.closest(".task-menu")) {
    closeAllMenus(null);
  }
});

// ---------- Inline edit form ----------
function toggleEditForm(taskId) {
  closeAllMenus(null);
  const form = document.getElementById(`edit-form-${taskId}`);
  form.classList.toggle("open");
}

// ---------- Delete confirmation modal + undo ----------
const UNDO_WINDOW_MS = 5000;
let pendingDelete = null;

function openDeleteModal(taskId, taskTitle) {
  closeAllMenus(null);
  const modal = document.getElementById("delete-modal");
  const text = document.getElementById("delete-modal-text");
  const form = document.getElementById("delete-form");

  text.textContent = `"${taskTitle}" will be removed.`;
  form.dataset.taskId = taskId;
  modal.classList.add("open");
}

function closeDeleteModal() {
  document.getElementById("delete-modal").classList.remove("open");
}

// Close modal if the overlay itself (not the box) is clicked
document.getElementById("delete-modal")?.addEventListener("click", (event) => {
  if (event.target.id === "delete-modal") closeDeleteModal();
});

// Starts the undo window
document.getElementById("delete-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const taskId = event.target.dataset.taskId;
  closeDeleteModal();
  if (taskId) startPendingDelete(taskId);
});

function startPendingDelete(taskId) {
  const row = document.getElementById(`task-${taskId}`);
  if (!row) return;

  // Only one undo-able delete at a time
  if (pendingDelete) finalizePendingDelete();

  row.classList.add("pending-delete");
  showUndoToast();

  const timeoutId = setTimeout(finalizePendingDelete, UNDO_WINDOW_MS);
  pendingDelete = { taskId, timeoutId, row };
}

function finalizePendingDelete() {
  if (!pendingDelete) return;
  const { taskId, row } = pendingDelete;
  pendingDelete = null;
  hideUndoToast();

  fetch(`/delete-task/${taskId}`, { method: "POST" })
    .then(() => row.remove())
    .catch(() => {
      // Request failed
      row.classList.remove("pending-delete");
    });
}

function undoDelete() {
  if (!pendingDelete) return;
  clearTimeout(pendingDelete.timeoutId);
  pendingDelete.row.classList.remove("pending-delete");
  pendingDelete = null;
  hideUndoToast();
}

function showUndoToast() {
  const toast = document.getElementById("undo-toast");
  const bar = document.getElementById("undo-toast-bar");

  toast.classList.add("open");

  // Restart the progress-bar animation every time a new delete is pending
  bar.classList.remove("animate");
  void bar.offsetWidth; // force reflow so the class removal registers
  bar.classList.add("animate");
}

function hideUndoToast() {
  const toast = document.getElementById("undo-toast");
  const bar = document.getElementById("undo-toast-bar");
  toast.classList.remove("open");
  bar.classList.remove("animate");
}

// Finalize deletion even if the page is closed mid-undo-window
window.addEventListener("beforeunload", () => {
  if (pendingDelete) {
    navigator.sendBeacon(`/delete-task/${pendingDelete.taskId}`);
  }
});