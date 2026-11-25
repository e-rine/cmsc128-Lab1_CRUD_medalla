// turns flash messages into toast

(function () {
  var SHOW_MS = 4000;          // success and other messages
  var SHOW_ERROR_MS = 7000;    // errors stay longer so they can be read

  var stack = null;

  function getStack() {
    if (stack) return stack;
    stack = document.createElement('div');
    stack.className = 'toast-stack';
    stack.setAttribute('role', 'status');
    stack.setAttribute('aria-live', 'polite');
    document.body.appendChild(stack);
    return stack;
  }

  function dismiss(toast) {
    if (!toast.parentNode) return;
    toast.classList.add('leaving');
    setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 220);
  }

  function showToast(text, kind) {
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + kind;

    var label = document.createElement('span');
    label.className = 'toast-text';
    label.textContent = text;                       // textContent: messages can contain user text

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('aria-label', 'Dismiss');
    close.textContent = '×';
    close.addEventListener('click', function () { dismiss(toast); });

    toast.appendChild(label);
    toast.appendChild(close);
    getStack().appendChild(toast);

    setTimeout(function () { dismiss(toast); }, kind === 'error' ? SHOW_ERROR_MS : SHOW_MS);
  }

  // other pages can call this too, e.g. showToast('Saved', 'success')
  window.showToast = showToast;

  function convertFlashMessages() {
    document.querySelectorAll('.flash-message').forEach(function (box) {
      var kind = 'info';
      if (box.classList.contains('flash-success')) kind = 'success';
      else if (box.classList.contains('flash-error')) kind = 'error';
      var text = box.textContent.trim();
      box.remove();
      if (text) showToast(text, kind);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', convertFlashMessages);
  } else {
    convertFlashMessages();
  }
})();