// ---------- Login / Signup page ----------
var COPY = {
  login:  { heading: 'Welcome back',       sub: 'Log in to see your tasks.',            title: 'SideQuest | Log in' },
  signup: { heading: 'Create your account', sub: 'Sign up to start tracking tasks.',    title: 'SideQuest | Sign up' }
};

function showAuth(mode) {
  var other = mode === 'login' ? 'signup' : 'login';
  document.getElementById('form-' + mode).classList.add('active');
  document.getElementById('form-' + other).classList.remove('active');
  document.getElementById('tab-' + mode).classList.add('active');
  document.getElementById('tab-' + other).classList.remove('active');
  document.getElementById('auth-heading').textContent = COPY[mode].heading;
  document.getElementById('auth-sub').textContent = COPY[mode].sub;
  document.title = COPY[mode].title;
  history.replaceState(null, '', '#' + mode);
}

// open the right tab from the URL, e.g. /login-signup#signup
if (location.hash === '#signup') showAuth('signup');

// block signup if passwords differ
document.getElementById('form-signup').addEventListener('submit', function (e) {
  var pw = document.getElementById('signup-password').value;
  var confirm = document.getElementById('signup-confirm').value;
  var err = document.getElementById('confirm-error');
  if (pw !== confirm) {
    e.preventDefault();
    err.classList.add('show');
  } else {
    err.classList.remove('show');
  }
});