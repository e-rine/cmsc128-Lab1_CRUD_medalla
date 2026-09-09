// ---------- Three-dot dropdown menu ----------
function closeAllMenus(exceptId) {
  document.querySelectorAll(".menu-dropdown.open").forEach((menu) => {
    if (menu.id !== `menu-${exceptId}`) menu.classList.remove("open");
  });
}

function toggleMenu(taskId) {
  const menu = document.getElementById(`menu-${taskId}`);
  closeAllMenus(taskId);
  menu.classList.toggle("open");
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
let pendingDeletes = {};        
let currentToastTaskId = null;  // which task the visible toast's Undo button applies to

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

// closes if anywhere is clicked
document.getElementById("delete-modal")?.addEventListener("click", (event) => {
  if (event.target.id === "delete-modal") closeDeleteModal();
});

// what happens when u delete
document.getElementById("delete-form")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const taskId = event.target.dataset.taskId;
  closeDeleteModal();
  if (taskId) startPendingDelete(taskId);
});

// starts the undo timer
function startPendingDelete(taskId) {
  const row = document.getElementById(`task-${taskId}`);
  if (!row) return;

  if (pendingDeletes[taskId]) {
    clearTimeout(pendingDeletes[taskId].timeoutId);
  }

  row.classList.add("pending-delete");
  showUndoToast(taskId);

  const timeoutId = setTimeout(() => finalizePendingDelete(taskId), UNDO_WINDOW_MS);
  pendingDeletes[taskId] = { timeoutId, row };
}

// actually deletes from the database
function finalizePendingDelete(taskId) {
  const pending = pendingDeletes[taskId];
  if (!pending) return;
  delete pendingDeletes[taskId];

  if (currentToastTaskId === taskId) hideUndoToast();

  fetch(`/delete-task/${taskId}`, { method: "POST" })
    .then(() => pending.row.remove())
    .catch(() => {
      pending.row.classList.remove("pending-delete");
    });
}

// when u click undo, cancels the timer and returns visible
function undoDelete() {
  const taskId = currentToastTaskId;
  if (taskId == null || !pendingDeletes[taskId]) return;

  clearTimeout(pendingDeletes[taskId].timeoutId);
  pendingDeletes[taskId].row.classList.remove("pending-delete");
  delete pendingDeletes[taskId];
  hideUndoToast();
}

// help function to show the undo banner
function showUndoToast(taskId) {
  currentToastTaskId = taskId;
  const toast = document.getElementById("undo-toast");
  const bar = document.getElementById("undo-toast-bar");

  toast.classList.add("open");

  // Restart the progress-bar animation every time a new delete is pending
  bar.classList.remove("animate");
  void bar.offsetWidth; 
  bar.classList.add("animate");
}

// hides the previous undo banner when another one is beingdeleted
function hideUndoToast() {
  currentToastTaskId = null;
  const toast = document.getElementById("undo-toast");
  const bar = document.getElementById("undo-toast-bar");
  toast.classList.remove("open");
  bar.classList.remove("animate");
}

// auto delete if u refresh or exit
window.addEventListener("beforeunload", () => {
  Object.keys(pendingDeletes).forEach((taskId) => {
    navigator.sendBeacon(`/delete-task/${taskId}`);
  });
});