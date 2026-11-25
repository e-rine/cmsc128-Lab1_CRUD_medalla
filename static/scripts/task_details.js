/* Task details + edit pop-up on My Tasks.
 *
 * Click (or press Enter on) a task's title/description to open a window with everything about
 * it. Press "Edit" there (or the Edit button on the row) to change the task in the same
 * window; "Save changes" posts to /edit-task/<id>, the same route the old inline form used.
 *
 * The information comes from data-* attributes on each task row in my_tasks.html, so no extra
 * request is needed. Close with the button, the Esc key, or by clicking outside (outside-click
 * is ignored while editing so a slip doesn't throw away your changes).
 */
(function () {
  var modal = document.getElementById('details-modal');
  if (!modal) return;

  var el = {
    view: document.getElementById('details-view'),
    form: document.getElementById('details-form'),
    title: document.getElementById('details-title'),
    status: document.getElementById('details-status'),
    description: document.getElementById('details-description'),
    deadline: document.getElementById('details-deadline'),
    time: document.getElementById('details-time'),
    priority: document.getElementById('details-priority'),
    category: document.getElementById('details-category'),
    addedLabel: document.getElementById('details-added-label'),
    added: document.getElementById('details-added'),
    editButton: document.getElementById('details-edit'),
    cancelButton: document.getElementById('details-cancel'),
    fTitle: document.getElementById('ed-title'),
    fDescription: document.getElementById('ed-description'),
    fDate: document.getElementById('ed-date'),
    fTime: document.getElementById('ed-time'),
    fPriority: document.getElementById('ed-priority'),
    fCategory: document.getElementById('ed-category')
  };

  var currentId = null;
  var editing = false;
  var openedInEdit = false;        // opened straight from a row's Edit button

  function capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function pill(kind, value) {
    var span = document.createElement('span');
    span.className = kind + '-pill ' + kind + '-' + value;
    span.textContent = capitalize(value);
    return span;
  }

  // ---------- view mode ----------

  function fillView(d) {
    el.title.textContent = d.title;

    var done = d.done === '1';
    el.status.textContent = done ? 'Completed' : 'Open';
    el.status.classList.toggle('done', done);

    var text = (d.description || '').trim();
    el.description.textContent = text || 'No description.';
    el.description.classList.toggle('empty', !text);

    var when = d.deadline.split(' · ');         // "Dec 6, 2026 · 5:41 PM" -> date and time
    el.deadline.textContent = when[0] + (d.overdue === '1' ? '  (overdue)' : '');
    el.deadline.classList.toggle('overdue', d.overdue === '1');
    el.time.textContent = when[1] || '';

    el.priority.textContent = '';
    el.priority.appendChild(pill('priority', d.priority));
    el.category.textContent = '';
    el.category.appendChild(pill('category', d.category));

    var hasAuthor = !!d.addedBy;                      // only group tasks have an author
    el.addedLabel.hidden = !hasAuthor;
    el.added.hidden = !hasAuthor;
    el.added.textContent = d.addedBy || '';
  }

  // ---------- edit mode ----------

  function fillForm(d, taskId) {
    el.form.action = '/edit-task/' + taskId;
    el.fTitle.value = d.title;
    el.fDescription.value = d.description || '';
    el.fDate.value = d.deadlineDate;
    el.fTime.value = d.deadlineTime;
    el.fPriority.value = d.priority;
    el.fCategory.value = d.category;
  }

  function showMode(isEditing) {
    editing = isEditing;
    el.view.hidden = isEditing;
    el.form.hidden = !isEditing;
    if (isEditing) el.fTitle.focus();
  }

  // ---------- open / close ----------

  // openEdit = true opens straight in edit mode (used by the Edit button on each row)
  function openTaskModal(taskId, openEdit) {
    var row = document.getElementById('task-' + taskId);
    if (!row) return;
    currentId = taskId;
    openedInEdit = !!openEdit;
    fillView(row.dataset);                            // all values are set with textContent / .value
    fillForm(row.dataset, taskId);
    showMode(!!openEdit);
    modal.classList.add('open');
  }

  function closeDetailsModal() {
    modal.classList.remove('open');
    currentId = null;
    editing = false;
  }

  window.openTaskModal = openTaskModal;               // used by the row Edit button in the HTML
  window.closeDetailsModal = closeDetailsModal;       // used by the Close button in the HTML

  function cancelEdit() {
    if (openedInEdit) closeDetailsModal();            // came from the row's Edit button: just close
    else showMode(false);                             // came from the details: go back to them
  }

  el.editButton.addEventListener('click', function () { showMode(true); });
  el.cancelButton.addEventListener('click', cancelEdit);

  // open: click anywhere on a task's text, or Enter / Space when it is focused
  document.addEventListener('click', function (event) {
    var body = event.target.closest('.task-body');
    if (body) openTaskModal(body.dataset.id, false);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && modal.classList.contains('open')) {
      if (editing) cancelEdit(); else closeDetailsModal();
      return;
    }
    if ((event.key === 'Enter' || event.key === ' ') && event.target.classList &&
        event.target.classList.contains('task-body')) {
      event.preventDefault();
      openTaskModal(event.target.dataset.id, false);
    }
  });

  modal.addEventListener('click', function (event) {
    if (event.target === modal && !editing) closeDetailsModal();   // dark area outside the box
  });
})();