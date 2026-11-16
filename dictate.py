"""Dictate button for st.chat_input, using the browser's built-in speech recognition.

Works in Chrome, Edge and Safari (not Firefox). Needs HTTPS (or localhost) for microphone access.
The transcript is typed into the chat box so the learner can edit it, then press Enter to send.
"""
import json

import streamlit.components.v1 as components

# Runs in the parent page (not the component iframe), so it survives Streamlit reruns.
_INIT = r"""
(function () {
  if (window.__dictateInit) return;
  window.__dictateInit = true;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec = null, listening = false, base = '', suppress = false;

  var btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = '🎤';
  btn.title = 'Dictate your message';
  btn.setAttribute('aria-label', 'Dictate your message');
  btn.style.cssText = 'position:fixed;z-index:1000;display:none;width:36px;height:36px;border-radius:50%;' +
    'border:1px solid #4a426b;background:#1c1a2e;color:#fff;cursor:pointer;font-size:16px;padding:0;';
  document.body.appendChild(btn);

  function box() {
    return document.querySelector('textarea[data-testid="stChatInputTextArea"]') ||
           document.querySelector('[data-testid="stChatInput"] textarea');
  }
  function setValue(el, v) {
    var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    setter.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));   // lets Streamlit/React see the change
  }
  function place() {
    var el = box();
    if (!el) { btn.style.display = 'none'; if (listening && rec) rec.stop(); return; }
    var r = el.getBoundingClientRect();
    btn.style.display = 'block';
    btn.style.top = (r.top + r.height / 2 - 18) + 'px';
    btn.style.left = (r.right - 96) + 'px';
    el.style.paddingRight = '56px';
  }
  setInterval(place, 400);
  window.addEventListener('resize', place);

  document.addEventListener('keydown', function (e) {     // Enter sends the message: stop listening
    if (listening && e.key === 'Enter' && !e.shiftKey) { suppress = true; if (rec) rec.abort(); }
  }, true);

  btn.addEventListener('click', function () {
    if (!SR) { alert('Dictation is not supported in this browser. Try Chrome, Edge or Safari.'); return; }
    if (listening) { rec.stop(); return; }
    var el = box();
    if (!el) return;
    suppress = false;
    base = el.value ? el.value.replace(/\s+$/, '') + ' ' : '';
    rec = new SR();
    rec.lang = navigator.language || 'en-US';
    rec.continuous = true;
    rec.interimResults = true;
    rec.onstart = function () { listening = true; btn.textContent = '⏹'; btn.style.background = '#c62828'; };
    rec.onresult = function (e) {
      if (suppress) return;
      var t = '';
      for (var i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      var el2 = box();
      if (el2) setValue(el2, base + t);
    };
    rec.onerror = function (e) {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed')
        alert('Microphone access is blocked. Allow it in your browser settings and try again.');
    };
    rec.onend = function () {
      listening = false; btn.textContent = '🎤'; btn.style.background = '#1c1a2e';
      var el3 = box(); if (el3 && !suppress) el3.focus();
    };
    rec.start();
  });
})();
"""


def dictate_button() -> None:
    """Call once per run on the page that has st.chat_input."""
    components.html(f"""<script>
      var P = window.parent;
      if (!P.__dictateInit) {{
        var s = P.document.createElement('script');
        s.textContent = {json.dumps(_INIT)};
        P.document.head.appendChild(s);
      }}
    </script>""", height=0)