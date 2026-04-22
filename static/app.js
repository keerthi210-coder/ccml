// ── Modal System ──────────────────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('active');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  document.getElementById(id).classList.remove('active');
  document.body.style.overflow = '';
}
function switchModal(closeId, openId) {
  closeModal(closeId);
  setTimeout(() => openModal(openId), 150);
}
function openPortal(tab) {
  switchTab(tab || 'login');
  openModal('portalModal');
}
function switchTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('panelLogin').style.display = isLogin ? 'block' : 'none';
  document.getElementById('panelSignup').style.display = isLogin ? 'none' : 'block';
  document.getElementById('tabLogin').classList.toggle('active', isLogin);
  document.getElementById('tabSignup').classList.toggle('active', !isLogin);
}
// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', function(e) {
    if (e.target === this) closeModal(this.id);
  });
});
// Close on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => closeModal(m.id));
  }
});

// ── Password Toggle ───────────────────────────────────────────────────────────
function togglePwd(id, icon) {
  const el = document.getElementById(id);
  if (el.type === 'password') {
    el.type = 'text';
    icon.classList.replace('fa-eye', 'fa-eye-slash');
  } else {
    el.type = 'password';
    icon.classList.replace('fa-eye-slash', 'fa-eye');
  }
}

// ── Auth Forms (AJAX) ─────────────────────────────────────────────────────────
let pendingEmail = '';
let otpTimer = null;

// Set DOB max to today and wire phone live validation
document.addEventListener('DOMContentLoaded', function() {
  const dobEl = document.getElementById('s_dob');
  if (dobEl) dobEl.max = new Date().toISOString().split('T')[0];

  const phoneEl = document.getElementById('s_phone');
  const phoneMsg = document.getElementById('phoneValidMsg');
  if (phoneEl && phoneMsg) {
    phoneEl.addEventListener('input', function() {
      const v = this.value.replace(/\D/g, '');
      if (v.length === 0) { phoneMsg.textContent = ''; return; }
      if (v.length < 10) {
        phoneMsg.style.color = 'var(--accent)';
        phoneMsg.textContent = `${10 - v.length} more digit(s) needed`;
      } else {
        phoneMsg.style.color = 'var(--green)';
        phoneMsg.textContent = '✓ Valid number';
      }
    });
  }
});

function submitSignup(e) {
  e.preventDefault();
  const errEl = document.getElementById('signupError');
  errEl.textContent = '';
  const btn = document.getElementById('sendOtpBtn');
  btn.textContent = 'Sending OTP...';
  btn.disabled = true;

  const payload = {
    name:     document.getElementById('s_name').value.trim(),
    email:    document.getElementById('s_email').value.trim(),
    mobile:   document.getElementById('s_mobile').value.trim(),
    password: document.getElementById('spwd').value,
    aadhaar:  document.getElementById('s_aadhaar').value.replace(/\s/g,''),
    present_address:          document.getElementById('s_present_address').value.trim(),
    permanent_address:        document.getElementById('s_permanent_address').value.trim(),
    blood_group:              document.getElementById('s_blood_group').value,
    educational_qualification: document.getElementById('s_edu_qual').value,
    dob:   document.getElementById('s_dob').value,
    phone: document.getElementById('s_phone').value.trim()
  };

  // Phone validation
  const phoneVal = payload.phone.replace(/\D/g, '');
  if (phoneVal.length !== 10) {
    errEl.textContent = 'Enter a valid 10-digit phone number.';
    btn.textContent = 'Send OTP to Email & Phone';
    btn.disabled = false;
    return;
  }

  fetch('/send-otp', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  })  .then(r => r.json())
  .then(d => {
    btn.textContent = 'Send OTP to Email & Phone';
    btn.disabled = false;
    if (d.success) {
      pendingEmail = payload.email;
      document.getElementById('otpEmailDisplay').textContent = `${payload.email} & +91${payload.phone}`;
      document.getElementById('signupStep1').style.display = 'none';
      document.getElementById('signupStep2').style.display = 'block';
      // Clear OTP boxes
      document.querySelectorAll('.otp-box').forEach(b => { b.value = ''; b.classList.remove('filled'); });
      document.querySelectorAll('.otp-box')[0].focus();
      startOtpTimer();
      if (d.dev) {
        document.getElementById('otpError').style.color = 'var(--green)';
        document.getElementById('otpError').textContent = d.message;
      }
    } else {
      errEl.textContent = d.error || 'Failed to send OTP.';
    }
  })
  .catch(() => { btn.textContent = 'Send OTP to Email'; btn.disabled = false; errEl.textContent = 'Network error.'; });
}

function verifyOtp() {
  const boxes = document.querySelectorAll('.otp-box');
  const otp = [...boxes].map(b => b.value).join('');
  const errEl = document.getElementById('otpError');
  errEl.style.color = 'var(--accent)';
  if (otp.length < 6) { errEl.textContent = 'Please enter all 6 digits.'; return; }
  errEl.textContent = '';

  fetch('/verify-otp', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ email: pendingEmail, otp })
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      closeModal('portalModal');
      if (d.new_user) {
        // Show welcome and scroll to courses
        window.location.href = d.redirect || '/';
      } else {
        window.location.href = d.redirect || '/';
      }
    } else {
      errEl.textContent = d.error || 'Invalid OTP.';
      boxes.forEach(b => { b.style.borderColor = 'var(--accent)'; });
    }
  })
  .catch(() => { errEl.textContent = 'Network error.'; });
}

function resendOtp() {
  fetch('/resend-otp', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ email: pendingEmail })
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      document.getElementById('otpError').style.color = 'var(--green)';
      document.getElementById('otpError').textContent = d.dev ? d.message : 'OTP resent to your email!';
      document.getElementById('resendBtn').style.display = 'none';
      startOtpTimer();
    }
  });
}

function backToSignup() {
  document.getElementById('signupStep2').style.display = 'none';
  document.getElementById('signupStep1').style.display = 'block';
  clearInterval(otpTimer);
}

function copySameAddress(cb) {
  if (cb.checked) {
    document.getElementById('s_permanent_address').value = document.getElementById('s_present_address').value;
  }
}

function startOtpTimer() {
  clearInterval(otpTimer);
  let secs = 60;
  const el = document.getElementById('otpCountdown');
  const resendBtn = document.getElementById('resendBtn');
  resendBtn.style.display = 'none';
  el.textContent = secs;
  otpTimer = setInterval(() => {
    secs--;
    el.textContent = secs;
    if (secs <= 0) {
      clearInterval(otpTimer);
      document.querySelector('.otp-timer').textContent = 'OTP expired. ';
      resendBtn.style.display = 'inline';
    }
  }, 1000);
}

function submitLogin(e) {
  e.preventDefault();
  const form = e.target;
  const errEl = document.getElementById('loginError');
  errEl.textContent = '';
  const email = form.querySelector('[name="email"]').value.trim();
  const password = form.querySelector('[name="password"]').value;
  fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: `email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`
  })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        closeModal('portalModal');
        window.location.href = d.redirect || '/';
      } else if (d.unverified) {
        pendingEmail = d.email;
        switchTab('signup');
        document.getElementById('signupStep1').style.display = 'none';
        document.getElementById('signupStep2').style.display = 'block';
        document.getElementById('otpEmailDisplay').textContent = d.email;
        startOtpTimer();
      } else {
        errEl.textContent = d.error || 'Invalid credentials.';
      }
    })
    .catch(() => { errEl.textContent = 'Login failed. Please try /direct-login instead.'; });
}

// ── Mobile Nav ────────────────────────────────────────────────────────────────
const hamburger = document.getElementById('hamburger');
const navMenu = document.getElementById('navMenu');
if (hamburger && navMenu) {
  hamburger.addEventListener('click', () => {
    navMenu.classList.toggle('open');
  });
  // Mobile dropdown toggle
  document.querySelectorAll('.has-dropdown > a').forEach(link => {
    link.addEventListener('click', function(e) {
      if (window.innerWidth <= 1024) {
        e.preventDefault();
        this.parentElement.classList.toggle('open');
      }
    });
  });
}

// Auto-open portal modal from URL param
document.addEventListener('DOMContentLoaded', function() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('open') === 'signup') openPortal('signup');
  if (params.get('open') === 'login') openPortal('login');
});

// ── User menu click toggle ────────────────────────────────────────────────────
const userBtn = document.querySelector('.user-btn');
if (userBtn) {
  userBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    this.closest('.user-menu-wrap').classList.toggle('open');
  });
  document.addEventListener('click', function() {
    document.querySelectorAll('.user-menu-wrap.open').forEach(el => el.classList.remove('open'));
  });
}

// ── Sticky Navbar shadow ──────────────────────────────────────────────────────
window.addEventListener('scroll', () => {
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    navbar.style.boxShadow = window.scrollY > 10
      ? '0 4px 20px rgba(0,0,0,0.12)'
      : '0 2px 12px rgba(0,0,0,0.08)';
  }
});

// ── Aadhaar number formatter (XXXX XXXX XXXX) ────────────────────────────────
function formatAadhaar(input) {
  let val = input.value.replace(/\D/g, '').slice(0, 12);
  input.value = val.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
}

// ── OTP box auto-advance ──────────────────────────────────────────────────────
document.addEventListener('input', function(e) {
  if (!e.target.classList.contains('otp-box')) return;
  const boxes = [...document.querySelectorAll('.otp-box')];
  const idx = boxes.indexOf(e.target);
  e.target.value = e.target.value.replace(/\D/g, '').slice(-1);
  if (e.target.value) {
    e.target.classList.add('filled');
    e.target.style.borderColor = 'var(--primary)';
    if (idx < boxes.length - 1) boxes[idx + 1].focus();
    // Auto-submit when all filled
    if (boxes.every(b => b.value)) verifyOtp();
  } else {
    e.target.classList.remove('filled');
    e.target.style.borderColor = '';
  }
});
document.addEventListener('keydown', function(e) {
  if (!e.target.classList.contains('otp-box')) return;
  const boxes = [...document.querySelectorAll('.otp-box')];
  const idx = boxes.indexOf(e.target);
  if (e.key === 'Backspace' && !e.target.value && idx > 0) boxes[idx - 1].focus();
});

// ── Auto-dismiss flash messages ───────────────────────────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => el.remove(), 5000);
});
