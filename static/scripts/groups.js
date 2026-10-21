// Scripts for the My Groups page (create, add member, remove member / leave, delete modals)
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  clearModalError(id);
}

// Inline error shown inside a modal so it stays open when something is wrong
function showModalError(modalId, message) {
  var form = document.querySelector('#' + modalId + ' form');
  var err = form.querySelector('.gm-error');
  if (!err) {
    err = document.createElement('div');
    err.className = 'gm-error';
    err.setAttribute('role', 'alert');
    form.insertBefore(err, form.firstChild);
  }
  err.textContent = message;
}

function clearModalError(modalId) {
  var err = document.querySelector('#' + modalId + ' .gm-error');
  if (err) err.remove();
}

// Submit a modal form with fetch so a validation error keeps the modal open
function submitModalForm(form, modalId) {
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearModalError(modalId);
    var submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'fetch' },
      body: new URLSearchParams(new FormData(form))
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (r) {
        if (r.ok && r.data.ok) {
          window.location.href = r.data.redirect || '/groups';
        } else {
          showModalError(modalId, r.data.error || 'Something went wrong. Please try again.');
          submitBtn.disabled = false;
        }
      })
      .catch(function () {
        showModalError(modalId, 'Could not reach the server. Please try again.');
        submitBtn.disabled = false;
      });
  });
}

function addMemberRow() {
  var row = document.createElement('div');
  row.className = 'gm-member-row';
  row.innerHTML =
    '<div class="field"><input type="email" name="emails" placeholder="friend@example.com" /></div>' +
    '<button type="button" class="gm-remove" title="Remove" onclick="this.parentNode.remove()">&times;</button>';
  document.getElementById('member-rows').appendChild(row);
  return row;
}

function openCreateModal() {
  document.getElementById('group-name').value = '';
  document.getElementById('member-rows').innerHTML = '';
  addMemberRow();
  clearModalError('create-modal');
  document.getElementById('create-modal').classList.add('open');
  document.getElementById('group-name').focus();
}

// Reopens the create popup after the server rejected it, keeping what was typed.
function reopenCreateModal(name, emails) {
  document.getElementById('group-name').value = name;
  document.getElementById('member-rows').innerHTML = '';
  emails.forEach(function (email) {
    addMemberRow().querySelector('input').value = email;
  });
  if (emails.length === 0) addMemberRow();
  document.getElementById('create-modal').classList.add('open');
}

function openAddMemberModal(groupId, groupName) {
  document.getElementById('add-member-form').action = '/groups/' + groupId + '/members';
  document.getElementById('add-member-note').textContent = 'Add someone to "' + groupName + '" using their account email.';
  document.getElementById('member-email').value = '';
  clearModalError('add-member-modal');
  document.getElementById('add-member-modal').classList.add('open');
  document.getElementById('member-email').focus();
}

function openMembersModal(groupId, groupName) {
  var card = document.getElementById('group-' + groupId);
  document.getElementById('members-title').textContent = groupName;
  document.getElementById('members-note').textContent = card.querySelector('.card-note').textContent.replace(/\s+/g, ' ').trim();
  document.getElementById('members-list').innerHTML = card.querySelector('.member-list').innerHTML;
  document.getElementById('members-modal').classList.add('open');
}

function openDeleteModal(groupId, groupName) {
  document.getElementById('delete-form').action = '/groups/' + groupId + '/delete';
  document.getElementById('delete-note').textContent =
    'This permanently deletes "' + groupName + '", its shared tasks, and removes all members. This can\'t be undone.';
  clearModalError('delete-modal');
  document.getElementById('delete-modal').classList.add('open');
}

// Opens the confirm popup for removing a member, or for the current user leaving.
// `btn` carries data-group-id, data-group-name, data-member-id, data-member-name, data-self.
function openRemoveMemberModal(btn) {
  var d = btn.dataset;
  var isSelf = d.self === '1';

  document.getElementById('remove-member-form').action =
    '/groups/' + d.groupId + '/members/' + d.memberId + '/remove';
  document.getElementById('remove-member-title').textContent = isSelf ? 'Leave group?' : 'Remove member?';
  document.getElementById('remove-member-note').textContent = isSelf
    ? 'You will lose access to "' + d.groupName + '" and its shared tasks. The owner can add you back later.'
    : 'Remove ' + d.memberName + ' from "' + d.groupName + '"? They will lose access to its shared tasks.';
  document.getElementById('remove-member-submit').textContent = isSelf ? 'Leave group' : 'Remove member';

  closeModal('members-modal');          // in case it was opened from the members popup
  clearModalError('remove-member-modal');
  document.getElementById('remove-member-modal').classList.add('open');
}

// Click the dark backdrop or press Esc to close
document.querySelectorAll('.gm-overlay').forEach(function (overlay) {
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal(overlay.id);
  });
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.gm-overlay.open').forEach(function (o) { closeModal(o.id); });
  }
});

// Show today's date in the top bar (same as the My Tasks page)
var topbarDate = document.getElementById('topbar-date');
if (topbarDate) {
  topbarDate.textContent = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
}

submitModalForm(document.querySelector('#create-modal form'), 'create-modal');
submitModalForm(document.getElementById('add-member-form'), 'add-member-modal');
submitModalForm(document.getElementById('delete-form'), 'delete-modal');
submitModalForm(document.getElementById('remove-member-form'), 'remove-member-modal');