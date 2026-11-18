// Ticket Arena: collect Google Chat user IDs from the page you have open.
// Paste this into the DevTools Console of a chat.google.com tab (F12 -> Console) and press Enter.
// It reads only what is already on your screen and copies {"Name": "id", ...} to your clipboard.
// Tip: open the space's member list (space name -> Manage members) and scroll to the bottom first,
// so every member is loaded.
(() => {
  const found = {};
  const docs = [document, ...[...document.querySelectorAll('iframe')].map((f) => { try { return f.contentDocument; } catch { return null; } }).filter(Boolean)];
  for (const doc of docs) {
    doc.querySelectorAll('[data-member-id^="user/human/"], [data-member-id^="users/"]').forEach((el) => {
      const id = el.getAttribute('data-member-id').split('/').pop();
      const name = (el.getAttribute('data-name') || el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || '')
        .replace(/\s+/g, ' ').trim();
      if (id && /^\d{10,}$/.test(id) && name && name.length < 80 && !found[name]) found[name] = id;
    });
  }
  const n = Object.keys(found).length;
  if (!n) {
    console.warn('No user IDs found. Open a space with messages or its member list, scroll so people are visible, then run this again. If Chat is inside Gmail, switch the Console context (top-left dropdown) to the chat frame.');
    return;
  }
  const out = JSON.stringify(found, null, 2);
  try { copy(out); console.log(`Copied ${n} people to the clipboard.`); } catch { console.log('Copy this:'); }
  console.log(out);
})();
