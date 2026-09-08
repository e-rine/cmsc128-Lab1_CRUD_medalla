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

// ---------- Delete confirmation modal ----------
function openDeleteModal(taskId, taskTitle) {
  closeAllMenus(null);
  const modal = document.getElementById("delete-modal");
  const text = document.getElementById("delete-modal-text");
  const form = document.getElementById("delete-form");

  text.textContent = `"${taskTitle}" will be permanently removed. This can't be undone.`;
  form.action = `/delete-task/${taskId}`;
  modal.classList.add("open");
}

function closeDeleteModal() {
  document.getElementById("delete-modal").classList.remove("open");
}

// Close modal if the overlay itself (not the box) is clicked
document.getElementById("delete-modal")?.addEventListener("click", (event) => {
  if (event.target.id === "delete-modal") closeDeleteModal();
});