const $ = (sel) => document.querySelector(sel);
const DATA = "../data";

let deckId = null;
let cards = [];
let order = [];
let pos = 0;
let srs = {};
const audio = new Audio();

const srsKey = () => `srs:${deckId}`;

function loadSrs() {
  try {
    srs = JSON.parse(localStorage.getItem(srsKey())) || {};
  } catch {
    srs = {};
  }
}

function box(id) {
  return (srs[id] && srs[id].box) || 0;
}

function setBox(id, value) {
  srs[id] = { box: Math.max(0, value) };
  localStorage.setItem(srsKey(), JSON.stringify(srs));
}

async function loadDecks() {
  let decks = [];
  try {
    const res = await fetch(`${DATA}/decks.json`, { cache: "no-store" });
    decks = await res.json();
  } catch {
    decks = [];
  }

  const select = $("#deck");
  select.innerHTML = "";
  if (!decks.length) {
    $("#empty").textContent =
      "No decks yet. Run: python -m mandarin.run <youtube-url>";
    return;
  }

  for (const d of decks) {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = `${d.title} (${d.count})`;
    select.appendChild(opt);
  }
  select.onchange = () => loadDeck(select.value);
  await loadDeck(decks[0].id);
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
  $("#card").classList.remove("hidden");
  $("#empty").classList.add("hidden");
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

function flip() {
  $("#back").classList.toggle("hidden");
}

function next() {
  pos = (pos + 1) % order.length;
  render();
}

function prev() {
  pos = (pos - 1 + order.length) % order.length;
  render();
}

function grade(known) {
  const card = current();
  setBox(card.id, known ? box(card.id) + 1 : 0);
  next();
}

$("#play").onclick = playAudio;
$("#flip").onclick = flip;
$("#again").onclick = () => grade(false);
$("#known").onclick = () => grade(true);
$("#shuffle").onclick = shuffle;

document.addEventListener("keydown", (e) => {
  if (e.key === " ") {
    e.preventDefault();
    playAudio();
  } else if (e.key === "ArrowRight") {
    next();
  } else if (e.key === "ArrowLeft") {
    prev();
  } else if (e.key.toLowerCase() === "f") {
    flip();
  } else if (e.key === "1") {
    grade(false);
  } else if (e.key === "2") {
    grade(true);
  }
});

loadDecks();
