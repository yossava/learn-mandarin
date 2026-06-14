const $ = (sel) => document.querySelector(sel);
const DATA = "../data";

let deckId = null;
let cards = [];
let order = [];
let pos = 0;
let srs = {};
let apiMode = false;
const audio = new Audio();

const srsKey = () => `srs:${deckId}`;
function loadSrs() {
  try { srs = JSON.parse(localStorage.getItem(srsKey())) || {}; }
  catch { srs = {}; }
}
function box(id) { return (srs[id] && srs[id].box) || 0; }
function setBox(id, value) {
  srs[id] = { box: Math.max(0, value) };
  localStorage.setItem(srsKey(), JSON.stringify(srs));
}

// ---------- decks ----------
async function fetchDecks() {
  const url = apiMode ? "/api/decks" : `${DATA}/decks.json`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

async function loadDecks(selectId) {
  const decks = await fetchDecks();
  const sel = $("#deck");
  sel.innerHTML = "";
  if (!decks.length) {
    $("#card").classList.add("hidden");
    $("#empty").classList.remove("hidden");
    $("#empty").textContent = apiMode
      ? "No lessons yet — paste a YouTube URL above to add one."
      : "No decks yet. Run: python3 -m mandarin.run <youtube-url>";
    return;
  }
  for (const d of decks) {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = `${d.title} (${d.count})`;
    sel.appendChild(opt);
  }
  const pick = selectId && decks.some((d) => d.id === selectId) ? selectId : decks[0].id;
  sel.value = pick;
  sel.onchange = () => loadDeck(sel.value);
  await loadDeck(pick);
}

async function loadDeck(id) {
  deckId = id;
  const res = await fetch(`${DATA}/${id}/cards.json`, { cache: "no-store" });
  cards = await res.json();
  loadSrs();
  order = [...cards.keys()].sort((a, b) => box(cards[a].id) - box(cards[b].id));
  pos = 0;
  render();
}

// ---------- study ----------
function shuffle() {
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  pos = 0;
  render();
}

const current = () => cards[order[pos]];

function render() {
  const card = current();
  $("#empty").classList.add("hidden");
  $("#card").classList.remove("hidden");
  $("#back").classList.add("hidden");
  if (!card) return;

  $("#hanzi").textContent = card.chinese;
  $("#pinyin").textContent = card.pinyin;
  $("#translation").textContent = card.translation;
  $("#note").textContent = card.note || "";

  const table = $("#words");
  table.innerHTML = "";
  for (const w of card.words || []) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${w.hanzi}</td><td>${w.pinyin}</td><td>${w.gloss}</td>`;
    table.appendChild(row);
  }

  const learned = cards.filter((c) => box(c.id) >= 2).length;
  $("#progress").textContent = `${pos + 1}/${cards.length} · learned ${learned}`;
  playAudio();
}

function playAudio() {
  const card = current();
  if (!card) return;
  audio.src = `${DATA}/${deckId}/${card.audio}`;
  audio.play().catch(() => {});
}

function flip() { $("#back").classList.toggle("hidden"); }
function next() { pos = (pos + 1) % order.length; render(); }
function prev() { pos = (pos - 1 + order.length) % order.length; render(); }
function grade(known) {
  const card = current();
  setBox(card.id, known ? box(card.id) + 1 : 0);
  next();
}

// ---------- add a lesson ----------
function setJob(show, frac, msg, isError) {
  $("#job").classList.toggle("hidden", !show);
  $("#bar-fill").style.width = `${Math.round((frac || 0) * 100)}%`;
  $("#bar-fill").classList.toggle("error", !!isError);
  $("#job-msg").textContent = msg || "";
}

async function addLesson(event) {
  event.preventDefault();
  const url = $("#url").value.trim();
  if (!url) return;
  $("#addbtn").disabled = true;
  setJob(true, 0.02, "Queued");
  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    pollJob(data.id);
  } catch (err) {
    setJob(true, 1, `Error: ${err.message}`, true);
    $("#addbtn").disabled = false;
  }
}

function pollJob(id) {
  const tick = async () => {
    let job;
    try {
      job = await (await fetch(`/api/jobs/${id}`, { cache: "no-store" })).json();
    } catch {
      setTimeout(tick, 1500);
      return;
    }
    const overall = job.total ? (job.step - 1 + (job.frac || 0)) / job.total : 0;
    const steps = job.step ? ` (${job.step}/${job.total})` : "";

    if (job.status === "done") {
      setJob(true, 1, `Added ${job.count} cards`);
      $("#url").value = "";
      $("#addbtn").disabled = false;
      loadDecks(job.deck_id);
      setTimeout(() => setJob(false), 2500);
      return;
    }
    if (job.status === "error") {
      setJob(true, Math.max(0.05, overall), `Error: ${job.message}`, true);
      $("#addbtn").disabled = false;
      return;
    }
    setJob(true, Math.max(0.02, overall), `${job.message}${steps}`);
    setTimeout(tick, 1200);
  };
  tick();
}

// ---------- wiring ----------
$("#play").onclick = playAudio;
$("#flip").onclick = flip;
$("#again").onclick = () => grade(false);
$("#known").onclick = () => grade(true);
$("#shuffle").onclick = shuffle;
$("#add").addEventListener("submit", addLesson);

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return; // don't hijack the URL box
  if (e.key === " ") { e.preventDefault(); playAudio(); }
  else if (e.key === "ArrowRight") next();
  else if (e.key === "ArrowLeft") prev();
  else if (e.key.toLowerCase() === "f") flip();
  else if (e.key === "1") grade(false);
  else if (e.key === "2") grade(true);
});

async function init() {
  try {
    const res = await fetch("/api/decks", { cache: "no-store" });
    apiMode = res.ok;
  } catch {
    apiMode = false;
  }
  if (apiMode) $("#add").classList.remove("hidden");
  loadDecks();
}

init();
