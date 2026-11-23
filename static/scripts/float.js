/* Floating task window (Document Picture-in-Picture).
 *
 * Click "Pop out tasks" in the sidebar and a small always-on-top window shows your
 * tasks. Tick one to complete it (it stays in the list, crossed out; untick to re-open it).
 * XP and quests count like on the normal page.
 *
 * The window's markup lives in the <template>s in sidebar.html and its styles in
 * static/styles/float_window.css. This file only wires them together.
 *
 * Needs Chrome or Edge 116+. The window lives while this SideQuest tab stays open.
 */
(function () {
  var button = document.getElementById('float-open');
  if (!button) return;

  var supported = 'documentPictureInPicture' in window;
  var pip = null;        // the floating window, or null when closed
  var timer = null;      // refresh interval
  var toastTimer = null;
  var ui = {};           // elements inside the floating window, by data-ref
  var busy = false;      // true while a tick request is running

  // theme colors copied from the main page so the window matches your theme
  var THEME_VARS = ['--bg', '--panel', '--border', '--text', '--text-muted',
                    '--primary', '--primary-dark', '--primary-soft', '--danger', '--success'];

  // ---------- open / close ----------

  button.addEventListener('click', function () {
    if (!supported) {
      alert('The floating window needs Chrome or Edge (version 116 or newer).');
      return;
    }
    if (pip) { pip.close(); return; }
    openWindow();
  });

  function openWindow() {
    window.documentPictureInPicture.requestWindow({ width: 340, height: 500 }).then(function (win) {
      pip = win;
      button.classList.add('on');
      build();
      refresh();
      timer = setInterval(refresh, 30000);
      pip.addEventListener('focus', refresh);
      pip.addEventListener('pagehide', function () {
        clearInterval(timer);
        pip = null;
        ui = {};
        button.classList.remove('on');
      });
    }).catch(function (err) {
      console.error('Could not open the floating window:', err);
    });
  }

  // ---------- build the window from the template ----------

  // finds the elements marked data-ref="..." inside a node
  function refs(root) {
    var found = {};
    root.querySelectorAll('[data-ref]').forEach(function (node) { found[node.dataset.ref] = node; });
    return found;
  }

  function build() {
    var doc = pip.document;
    doc.title = 'SideQuest tasks';

    var css = doc.createElement('link');
    css.rel = 'stylesheet';
    css.href = new URL(button.dataset.css, location.href).href;
    doc.head.appendChild(css);

    var computed = getComputedStyle(document.documentElement);
    THEME_VARS.forEach(function (name) {
      var value = computed.getPropertyValue(name).trim();
      if (value) doc.documentElement.style.setProperty(name, value);
    });

    var content = doc.importNode(document.getElementById('float-window-template').content, true);
    ui = refs(content);
    doc.body.appendChild(content);
  }

  // ---------- data ----------

  function api(url, options) {
    return fetch(url, options).then(function (res) {
      var type = res.headers.get('content-type') || '';
      if (type.indexOf('application/json') === -1) throw new Error('login');   // bounced to the login page
      return res.json();
    });
  }

  function refresh() {
    if (!pip || busy) return;
    api('/api/float-tasks').then(render).catch(showError);
  }

  function showError(err) {
    if (!pip) return;
    var msg = err && err.message === 'login'
      ? 'You were logged out. Log in again in the SideQuest tab.'
      : 'Could not reach SideQuest. Is the server running?';
    showMessage(msg, true);
  }

  // one centered line in place of the task list
  function showMessage(text, isError) {
    ui.list.textContent = '';
    var note = pip.document.createElement('div');
    note.className = 'empty' + (isError ? ' err' : '');
    note.textContent = text;
    ui.list.appendChild(note);
  }

  function render(data) {
    if (!pip) return;
    ui.level.textContent = 'Lv ' + data.level;
    ui.streak.textContent = '🔥 ' + data.streak;
    ui.quests.textContent = data.quests_done + '/' + data.quests_total + ' quests';
    ui.xp.style.width = Math.min(100, Math.round(data.xp_in_level / data.xp_per_level * 100)) + '%';
    var finished = data.tasks.length - data.open_count;
    ui.count.textContent = data.open_count + ' left' + (finished ? ' \u00B7 ' + finished + ' done' : '');

    if (!data.tasks.length) {
      showMessage('No tasks yet. Add some in SideQuest.', false);
      return;
    }

    ui.list.textContent = '';
    var template = document.getElementById('float-task-template');
    data.tasks.forEach(function (task) {
      var row = pip.document.importNode(template.content, true);
      var parts = refs(row);
      var box = row.querySelector('input');

      parts.title.textContent = task.title;          // textContent: titles are user input
      parts.due.textContent = task.due;
      if (task.overdue) parts.due.classList.add('late');
      box.checked = task.done;                       // finished tasks stay in the list, ticked
      parts.dot.classList.add(task.priority);
      parts.dot.title = task.priority + ' priority';

      var rowEl = row.querySelector('.task');
      if (task.done) rowEl.classList.add('done');
      box.addEventListener('change', function () { toggleTask(task.id, box); });
      ui.list.appendChild(row);
    });
  }

  // ---------- actions ----------

  // ticking completes a task, unticking re-opens it
  function toggleTask(id, box) {
    var wasChecked = !box.checked;       // state before the click
    if (busy) { box.checked = wasChecked; return; }
    busy = true;
    api('/api/float-tasks/' + id + '/toggle', { method: 'POST' }).then(function (data) {
      busy = false;
      if (data.ok) {
        notify(data.messages);
        render(data);
      } else {
        box.checked = wasChecked;
        notify([data.error || 'Something went wrong.']);
      }
    }).catch(function (err) {
      busy = false;
      showError(err);
    });
  }

  function notify(messages) {
    if (!pip || !messages || !messages.length) return;
    ui.toast.textContent = messages.join('  •  ');
    ui.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { if (pip) ui.toast.classList.remove('show'); }, 4000);
  }
})();