/* Floating task window (Document Picture-in-Picture).
 *
 * Click "Pop out tasks" in the sidebar and a small always-on-top window shows your
 * tasks. Tick one to complete it (untick to re-open it). XP and quests count like on
 * the normal page.
 *
 * The window's markup lives in the <template>s in sidebar.html and its styles in
 * static/styles/float_window.css. This file only wires them together.
 *
 * Ticking never redraws the list: the row is crossed out in place. With "Hide completed"
 * on, it disappears half a second later. The list is only redrawn when something really
 * changed (for example a task added or finished on the SideQuest page).
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
  var HIDE_FILTERS_KEY = 'sidequest-float-filters-hidden';
  var filtersHidden = true;        // true = the filter boxes are collapsed (the default; remembered in this browser)
  try {
    var savedHidden = localStorage.getItem(HIDE_FILTERS_KEY);
    if (savedHidden !== null) filtersHidden = savedHidden === '1';
  } catch (e) {}
  var filters = { sort: 'due_date', priority: '', tag: '' };   // chosen in the window (same options as the My Tasks page)
  var lastSignature = '';  // which tasks (and done/open) are drawn; the list is redrawn only when this changes

  var HIDE_DELAY_MS = 500;   // buffer before a ticked task disappears (only with "Hide completed" on)
  var REFRESH_MS = 30000;    // how often the window quietly checks for changes

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
    window.documentPictureInPicture.requestWindow({ width: 340, height: 580 }).then(function (win) {
      pip = win;
      button.classList.add('on');
      build();
      refresh();
      timer = setInterval(refresh, REFRESH_MS);
      pip.addEventListener('pagehide', function () {
        clearInterval(timer);
        pip = null;
        ui = {};
        lastSignature = '';
        filters = { sort: 'due_date', priority: '', tag: '' };
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
    buildFilters(doc);
    doc.body.appendChild(content);
    buildAddTask(doc);
  }

  // ---------- add a task (button at the bottom + a small popup form) ----------

  var ADD_FORM_HTML =
    '<h3>Add a task</h3>' +
    '<label class="ffield"><span>Task title</span>' +
      '<input name="title" type="text" maxlength="200" placeholder="What needs doing?" required></label>' +
    '<div class="frow2">' +
      '<label class="ffield"><span>Date</span><input name="deadline_date" type="date" required></label>' +
      '<label class="ffield"><span>Time</span><input name="deadline_time" type="time" required></label>' +
    '</div>' +
    '<div class="frow2">' +
      '<label class="ffield"><span>Priority</span><select name="priority">' +
        '<option value="low">Low</option><option value="medium" selected>Medium</option><option value="high">High</option>' +
      '</select></label>' +
      '<label class="ffield"><span>Category</span><select name="category">' +
        '<option value="school">School</option><option value="work">Work</option><option value="personal">Personal</option>' +
        '<option value="finance">Finance</option><option value="other" selected>Other</option>' +
      '</select></label>' +
    '</div>' +
    '<div class="ferr" hidden></div>' +
    '<div class="addactions">' +
      '<button type="button" class="gbtn" data-act="cancel">Cancel</button>' +
      '<button type="submit" class="pbtn">Add task</button>' +
    '</div>';

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function buildAddTask(doc) {
    // the button, pinned under the list
    var bar = doc.createElement('div');
    bar.className = 'addbar';
    var open = doc.createElement('button');
    open.type = 'button';
    open.className = 'addbtn';
    open.textContent = '+ Add task';
    open.addEventListener('click', openAdd);
    bar.appendChild(open);
    ui.list.parentNode.appendChild(bar);

    // the popup form (hidden until the button is clicked)
    var overlay = doc.createElement('div');
    overlay.className = 'overlay';
    overlay.hidden = true;
    var form = doc.createElement('form');
    form.className = 'addform';
    form.noValidate = false;
    form.innerHTML = ADD_FORM_HTML;          // fixed text only, nothing from the user
    overlay.appendChild(form);
    doc.body.appendChild(overlay);

    ui.addOverlay = overlay;
    ui.addForm = form;
    ui.addError = form.querySelector('.ferr');

    form.querySelector('[data-act="cancel"]').addEventListener('click', closeAdd);
    overlay.addEventListener('mousedown', function (e) { if (e.target === overlay) closeAdd(); });
    doc.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAdd(); });
    form.addEventListener('submit', function (e) { e.preventDefault(); submitAdd(); });
  }

  function openAdd() {
    if (!pip) return;
    var form = ui.addForm;
    var now = new Date();
    form.reset();
    // same defaults as the quick add on the Homepage: today, 5:00 PM, Medium, Other
    form.elements.deadline_date.value = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
    form.elements.deadline_time.value = '17:00';
    ui.addError.hidden = true;
    ui.addOverlay.hidden = false;
    form.elements.title.focus();
  }

  function closeAdd() {
    if (ui.addOverlay) ui.addOverlay.hidden = true;
  }

  function submitAdd() {
    if (busy) return;
    busy = true;
    var submit = ui.addForm.querySelector('.pbtn');
    submit.disabled = true;
    api('/api/float-tasks/add' + query(), { method: 'POST', body: new FormData(ui.addForm) }).then(function (data) {
      busy = false;
      submit.disabled = false;
      if (!pip) return;
      if (!data.ok) {
        ui.addError.textContent = data.error || 'Something went wrong.';
        ui.addError.hidden = false;
        return;
      }
      closeAdd();
      notify(data.messages);
      render(data, true);
    }).catch(function (err) {
      busy = false;
      submit.disabled = false;
      closeAdd();
      showError(err);
    });
  }

  // ---------- filters (built here, so the <template> doesn't need to change) ----------

  var SORT_OPTIONS = [['due_date', 'Due date'], ['date_added', 'Date added'], ['priority', 'Priority'], ['tag', 'Tag']];
  var PRIORITY_OPTIONS = [['', 'All'], ['low', 'Low'], ['medium', 'Medium'], ['high', 'High']];
  var CATEGORY_OPTIONS = [['', 'All'], ['school', 'School'], ['work', 'Work'], ['personal', 'Personal'],
                          ['finance', 'Finance'], ['other', 'Other']];

  function makeSelect(doc, label, key, options) {
    var field = doc.createElement('label');
    field.className = 'ffield';
    var text = doc.createElement('span');
    text.textContent = label;
    var select = doc.createElement('select');
    options.forEach(function (o) {
      var opt = doc.createElement('option');
      opt.value = o[0];
      opt.textContent = o[1];
      select.appendChild(opt);
    });
    select.value = filters[key];
    select.addEventListener('change', function () {
      filters[key] = select.value;
      updateClear();
      reload();
    });
    field.appendChild(text);
    field.appendChild(select);
    ui[key + 'Select'] = select;
    return field;
  }

  function buildFilters(doc) {
    // the filter boxes (collapsible panel, just above the "x left" row)
    var bar = doc.createElement('div');
    bar.className = 'filters';

    var grid = doc.createElement('div');
    grid.className = 'frow';
    grid.appendChild(makeSelect(doc, 'Sort by', 'sort', SORT_OPTIONS));
    grid.appendChild(makeSelect(doc, 'Priority', 'priority', PRIORITY_OPTIONS));
    grid.appendChild(makeSelect(doc, 'Category', 'tag', CATEGORY_OPTIONS));
    bar.appendChild(grid);

    var clear = doc.createElement('button');
    clear.type = 'button';
    clear.className = 'fclear';
    clear.textContent = 'Clear filters';
    clear.hidden = true;
    clear.addEventListener('click', function () {
      filters = { sort: 'due_date', priority: '', tag: '' };
      ui.sortSelect.value = 'due_date';
      ui.prioritySelect.value = '';
      ui.tagSelect.value = '';
      updateClear();
      reload();
    });
    ui.clear = clear;
    bar.appendChild(clear);
    ui.filterBody = bar;

    // one slim row: "9 left" on the left, "Filters" arrow on the right
    var row = doc.createElement('div');
    row.className = 'toolrow';

    var hide = doc.createElement('label');
    hide.className = 'fhide';
    var box = doc.createElement('input');
    box.type = 'checkbox';
    box.addEventListener('change', function () { setHideCompleted(box.checked); });
    hide.appendChild(box);
    hide.appendChild(doc.createTextNode('Hide completed tasks'));
    ui.hide = box;
    bar.insertBefore(hide, clear);      // lives inside the filters panel, on the left, above "Clear filters"

    var toggle = doc.createElement('button');
    toggle.type = 'button';
    toggle.className = 'ftoggle';
    toggle.addEventListener('click', function () {
      filtersHidden = !filtersHidden;
      try { localStorage.setItem(HIDE_FILTERS_KEY, filtersHidden ? '1' : '0'); } catch (e) {}
      updateToggle();
    });
    ui.toggle = toggle;

    ui.count.parentNode.insertBefore(bar, ui.count);
    ui.count.parentNode.insertBefore(row, ui.count);
    row.appendChild(ui.count);          // moves the "x left" text into the row
    row.appendChild(toggle);
    updateToggle();
  }

  function updateClear() {
    ui.clear.hidden = !(filters.sort !== 'due_date' || filters.priority || filters.tag);
    updateToggle();
  }

  // shows or hides the filter controls; the button is just an up / down arrow
  var ARROW_UP = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 15 12 9 18 15"/></svg>';
  var ARROW_DOWN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>';

  function updateToggle() {
    if (!ui.toggle) return;
    ui.filterBody.hidden = filtersHidden;
    var active = filters.sort !== 'due_date' || filters.priority || filters.tag;
    ui.toggle.innerHTML = '<span>Filters</span>' + (filtersHidden ? ARROW_DOWN : ARROW_UP);   // fixed markup, nothing from the user
    ui.toggle.title = filtersHidden ? 'Show filters' + (active ? ' (some are on)' : '') : 'Hide filters';
    ui.toggle.setAttribute('aria-label', ui.toggle.title);
    ui.toggle.classList.toggle('on', !!(filtersHidden && active));   // little dot: filters are hidden but still applied
  }

  // redraw the list with the current filters
  function reload() {
    if (!pip) return;
    api('/api/float-tasks' + query()).then(function (data) { render(data, true); }).catch(showError);
  }

  // "Hide completed" is the same saved setting as on the My Tasks page
  function setHideCompleted(on) {
    api('/api/float-tasks/hide-completed' + query({ hide: on ? '1' : '0' }), { method: 'POST' })
      .then(function (data) { render(data, true); })
      .catch(function (err) { ui.hide.checked = !on; showError(err); });
  }

  // ?sort=...&priority=...&tag=... for the server (empty ones are left out)
  function query(extra) {
    var params = new URLSearchParams();
    Object.keys(filters).forEach(function (k) { if (filters[k]) params.set(k, filters[k]); });
    if (extra) Object.keys(extra).forEach(function (k) { params.set(k, extra[k]); });
    var text = params.toString();
    return text ? '?' + text : '';
  }

  // ---------- data ----------

  function api(url, options) {
    return fetch(url, options).then(function (res) {
      var type = res.headers.get('content-type') || '';
      if (type.indexOf('application/json') === -1) throw new Error('login');   // bounced to the login page
      return res.json();
    });
  }

  // quiet background check: redraws only if the tasks actually changed
  function refresh() {
    if (!pip || busy) return;
    api('/api/float-tasks' + query()).then(function (data) { render(data, false); }).catch(showError);
  }

  function showError(err) {
    if (!pip) return;
    var msg = err && err.message === 'login'
      ? 'You were logged out. Log in again in the SideQuest tab.'
      : 'Could not reach SideQuest. Is the server running?';
    showMessage(msg, true);
    lastSignature = '';
  }

  // one centered line in place of the task list
  function showMessage(text, isError) {
    ui.list.textContent = '';
    var note = pip.document.createElement('div');
    note.className = 'empty' + (isError ? ' err' : '');
    note.textContent = text;
    ui.list.appendChild(note);
  }

  function signature(tasks) {
    return tasks.map(function (t) { return t.id + (t.done ? 'd' : 'o') + t.title; }).join('|');
  }

  // header numbers: cheap, updated every time without touching the list
  function renderStats(data) {
    ui.level.textContent = 'Lv ' + data.level;
    ui.streak.textContent = '🔥 ' + data.streak;
    ui.quests.textContent = data.quests_done + '/' + data.quests_total + ' quests';
    ui.xp.style.width = Math.min(100, Math.round(data.xp_in_level / data.xp_per_level * 100)) + '%';
    var finished = data.tasks.length - data.open_count;
    ui.count.textContent = data.open_count + ' left' + (finished ? ' · ' + finished + ' done' : '');
  }

  // force = true draws the list even if nothing changed (first draw)
  function render(data, force) {
    if (!pip) return;
    renderStats(data);
    ui.hide.checked = !!data.hide_completed;

    var sig = signature(data.tasks);
    if (!force && sig === lastSignature) return;      // nothing changed: leave the list alone
    lastSignature = sig;

    if (!data.tasks.length) {
      showMessage(filters.priority || filters.tag ? 'No tasks match these filters.' : 'All clear! Nothing left to do.', false);
      return;
    }

    ui.list.textContent = '';
    var template = document.getElementById('float-task-template');
    data.tasks.forEach(function (task) {
      var row = pip.document.importNode(template.content, true);
      var parts = refs(row);
      var box = row.querySelector('input');
      var rowEl = row.querySelector('.task');

      parts.title.textContent = task.title;          // textContent: titles are user input
      parts.due.textContent = task.due;
      if (task.overdue) parts.due.classList.add('late');
      box.checked = task.done;                       // finished tasks stay in the list, ticked
      parts.dot.classList.add(task.priority);
      parts.dot.title = task.priority + ' priority';
      if (task.done) rowEl.classList.add('done');

      box.addEventListener('change', function () { toggleTask(task, rowEl, box); });
      ui.list.appendChild(row);
    });
  }

  // ---------- actions ----------

  // ticking completes a task, unticking re-opens it; the row changes in place (no redraw)
  function toggleTask(task, rowEl, box) {
    var wasChecked = !box.checked;       // state before the click
    if (busy) { box.checked = wasChecked; return; }
    busy = true;
    api('/api/float-tasks/' + task.id + '/toggle' + query(), { method: 'POST' }).then(function (data) {
      busy = false;
      if (!data.ok) {
        box.checked = wasChecked;
        notify([data.error || 'Something went wrong.'], true);
        return;
      }
      notify(data.messages);
      renderStats(data);
      ui.hide.checked = !!data.hide_completed;
      lastSignature = signature(data.tasks);         // we already show this state, so a later check won't redraw

      var nowDone = box.checked;
      task.done = nowDone;
      rowEl.classList.toggle('done', nowDone);

      var hiddenByServer = !data.tasks.some(function (t) { return t.id === task.id; });
      if (nowDone && hiddenByServer) {               // "Hide completed" is on: remove it after a short buffer
        setTimeout(function () {
          if (!pip || !box.checked) return;          // window closed, or it was unticked again in time
          rowEl.remove();
          if (!ui.list.querySelector('.task')) showMessage('All clear! Nothing left to do.', false);
        }, HIDE_DELAY_MS);
      }
    }).catch(function (err) {
      busy = false;
      showError(err);
    });
  }

  function notify(messages, isError) {
    if (!pip || !messages || !messages.length) return;
    ui.toast.textContent = messages.join('  •  ');
    ui.toast.classList.toggle('err', !!isError);
    ui.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { if (pip) ui.toast.classList.remove('show'); }, 4000);
  }
})();