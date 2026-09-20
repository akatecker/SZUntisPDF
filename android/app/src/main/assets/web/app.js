/* SZUntisPDF - Oberflaeche.
 *
 * Spricht ausschliesslich mit dem lokalen Programm auf 127.0.0.1; dieses
 * wiederum mit WebUntis. Direkt ginge es nicht: WebUntis erlaubt keine
 * Cross-Origin-Zugriffe.
 */
"use strict";

const WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
const PALETTE = ["#dbeafe", "#dcfce7", "#fef3c7", "#fae8ff", "#ffe4e6",
                 "#ccfbf1", "#e0e7ff", "#fee2e2", "#ecfccb", "#eef2f6"];

const $ = (id) => document.getElementById(id);

/* Startgeheimnis aus der Adresse holen und diese bereinigen, damit es nicht
   im Verlauf oder in Lesezeichen stehen bleibt. */
let schluessel = sessionStorage.getItem("szu-schluessel") || "";
{
  const ausAdresse = new URLSearchParams(location.search).get("s");
  if (ausAdresse) {
    schluessel = ausAdresse;
    sessionStorage.setItem("szu-schluessel", schluessel);
    history.replaceState(null, "", location.pathname);
  }
}

async function ruf(pfad, optionen = {}) {
  const antwort = await fetch(pfad, {
    ...optionen,
    headers: { "Content-Type": "application/json", "X-SZU-Schluessel": schluessel, ...(optionen.headers || {}) },
  });
  const daten = await antwort.json().catch(() => ({}));
  if (!antwort.ok) throw new Error(daten.fehler || `Fehler ${antwort.status}`);
  return daten;
}

function melde(text, art) {
  const feld = $("meldung");
  feld.textContent = text;
  feld.className = "meldung" + (art ? " " + art : "");
  feld.hidden = !text;
}

function laden(an) { $("laden").hidden = !an; }

/* ================= Einrichtung ================= */

document.querySelectorAll(".reiter button").forEach((knopf) => {
  knopf.addEventListener("click", () => {
    document.querySelectorAll(".reiter button").forEach((b) => b.classList.toggle("aktiv", b === knopf));
    document.querySelectorAll(".seite").forEach((s) => s.classList.toggle("aktiv", s.id === knopf.dataset.ziel));
    if (knopf.dataset.ziel !== "seite-kamera") kameraStoppen();
  });
});

async function kontoSenden(rumpf) {
  laden(true);
  try {
    const d = await ruf("/api/konto", { method: "POST", body: JSON.stringify(rumpf) });
    melde(`Verbunden als ${d.name}.`, "gut");
    kameraStoppen();
    await starte();
  } catch (fehler) {
    melde(fehler.message, "schlecht");
  } finally {
    laden(false);
  }
}

/* --- QR-Erkennung im Bild --- */

let detektor = null;
if ("BarcodeDetector" in window) {
  try { detektor = new BarcodeDetector({ formats: ["qr_code"] }); } catch { detektor = null; }
}

async function qrAusLeinwand(leinwand) {
  if (detektor) {
    const funde = await detektor.detect(leinwand).catch(() => []);
    if (funde.length) return funde[0].rawValue;
  }
  if (typeof jsQR === "function") {
    const ktx = leinwand.getContext("2d", { willReadFrequently: true });
    const bild = ktx.getImageData(0, 0, leinwand.width, leinwand.height);
    const fund = jsQR(bild.data, bild.width, bild.height, { inversionAttempts: "attemptBoth" });
    if (fund) return fund.data;
  }
  return null;
}

function aufLeinwand(quelle, breite, hoehe, maxKante = 1400) {
  const faktor = Math.min(1, maxKante / Math.max(breite, hoehe));
  const leinwand = document.createElement("canvas");
  leinwand.width = Math.round(breite * faktor);
  leinwand.height = Math.round(hoehe * faktor);
  leinwand.getContext("2d", { willReadFrequently: true })
    .drawImage(quelle, 0, 0, leinwand.width, leinwand.height);
  return leinwand;
}

async function verarbeiteCode(text) {
  if (!text) return false;
  if (!text.startsWith("untis://")) {
    melde("Das ist ein QR-Code, aber kein Untis-Zugangscode.\nGelesen: " + text.slice(0, 80), "schlecht");
    return false;
  }
  await kontoSenden({ qr: text });
  return true;
}

/* --- Kamera --- */

let strom = null;
let kameraLaeuft = false;

function kameraStoppen() {
  kameraLaeuft = false;
  if (strom) { strom.getTracks().forEach((t) => t.stop()); strom = null; }
  $("kamera-start").textContent = "Kamera starten";
}

async function kameraStarten() {
  if (kameraLaeuft) { kameraStoppen(); return; }
  melde("");
  try {
    strom = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 } }, audio: false,
    });
  } catch (fehler) {
    melde("Kamera nicht verfügbar: " + fehler.message +
          "\nDer Zugriff muss im Browser erlaubt werden.", "schlecht");
    return;
  }
  const video = $("video");
  video.srcObject = strom;
  await video.play();
  kameraLaeuft = true;
  $("kamera-start").textContent = "Kamera stoppen";
  melde("QR-Code ins Bild halten …");

  while (kameraLaeuft) {
    if (video.videoWidth) {
      const leinwand = aufLeinwand(video, video.videoWidth, video.videoHeight, 800);
      const text = await qrAusLeinwand(leinwand);
      if (text && await verarbeiteCode(text)) return;
    }
    await new Promise((f) => setTimeout(f, 200));
  }
}

$("kamera-start").addEventListener("click", kameraStarten);

/* --- Bilddatei --- */

async function bildVerarbeiten(datei) {
  if (!datei) return;
  melde("");
  const adresse = URL.createObjectURL(datei);
  const bild = new Image();
  try {
    await new Promise((fertig, schief) => {
      bild.onload = fertig;
      bild.onerror = () => schief(new Error("Datei konnte nicht als Bild gelesen werden."));
      bild.src = adresse;
    });
  } catch (fehler) {
    melde(fehler.message + "\nHEIC-Fotos kennt nicht jeder Browser – dann als JPEG oder PNG sichern.", "schlecht");
    return;
  }
  $("vorschau").src = adresse;
  $("vorschau").hidden = false;
  $("ablage").querySelector("span").hidden = true;

  /* Erst in voller Groesse, dann kleiner: Beides hilft je nach Foto. */
  for (const kante of [1600, 1000, 600]) {
    const text = await qrAusLeinwand(aufLeinwand(bild, bild.naturalWidth, bild.naturalHeight, kante));
    if (text) { await verarbeiteCode(text); return; }
  }
  melde("In diesem Bild wurde kein QR-Code gefunden.\n" +
        "Möglichst nah und gerade fotografieren – oder die Werte unter „Manuell“ eintragen.", "schlecht");
}

$("datei").addEventListener("change", (e) => bildVerarbeiten(e.target.files[0]));
$("ablage").addEventListener("dragover", (e) => { e.preventDefault(); $("ablage").classList.add("bereit"); });
$("ablage").addEventListener("dragleave", () => $("ablage").classList.remove("bereit"));
$("ablage").addEventListener("drop", (e) => {
  e.preventDefault();
  $("ablage").classList.remove("bereit");
  bildVerarbeiten(e.dataTransfer.files[0]);
});

/* --- Manuell --- */

$("manuell-ok").addEventListener("click", () => kontoSenden({
  server: $("f-server").value,
  schule: $("f-schule").value,
  benutzer: $("f-benutzer").value,
  schluessel: $("f-schluessel").value,
}));

/* ================= Stundenplan ================= */

let montag = null;

function montagVon(datum) {
  const d = new Date(datum);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d;
}

/** Ab Samstag ist die laufende Woche schulisch vorbei. */
function standardMontag() {
  const heute = new Date();
  const mo = montagVon(heute);
  if (heute.getDay() === 6 || heute.getDay() === 0) mo.setDate(mo.getDate() + 7);
  return mo;
}

const alsIso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const kurz = (d) => `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;

function fachfarbe(kuerzel) {
  if (!kuerzel) return "#eef2f6";
  let summe = 0;
  for (let i = 0; i < kuerzel.length; i++) summe += kuerzel.charCodeAt(i) * (i + 7);
  return PALETTE[summe % PALETTE.length];
}

const minuten = (iso) => { const t = iso.slice(11); return +t.slice(0, 2) * 60 + +t.slice(3, 5); };

function planZeichnen(daten) {
  const raster = $("raster");
  raster.innerHTML = "";
  const termine = daten.termine;

  $("schueler").textContent = daten.name;
  $("druck-name").textContent = daten.name;
  const sonntag = new Date(montag); sonntag.setDate(sonntag.getDate() + 6);
  const spanneText = `${kurz(montag)} – ${kurz(sonntag)}${sonntag.getFullYear()}`;
  $("woche-text").textContent = spanneText;
  $("druck-woche").textContent = "Woche " + spanneText;

  if (!termine.length) {
    raster.style.gridTemplateColumns = "1fr";
    raster.innerHTML = '<p style="padding:28px;text-align:center;color:var(--gedimmt)">Keine Termine in dieser Woche.</p>';
    $("fusszeile").textContent = "";
    return;
  }

  /* Tage: Mo-Fr immer, Wochenende nur mit Terminen. */
  const tage = [];
  for (let i = 0; i < 7; i++) {
    const tag = new Date(montag); tag.setDate(tag.getDate() + i);
    const iso = alsIso(tag);
    const drauf = termine.filter((t) => t.tag === iso);
    if (i < 5 || drauf.length) tage.push({ tag, iso, termine: drauf });
  }

  const von = Math.floor(Math.min(...termine.map((t) => minuten(t.beginn))) / 60) * 60;
  const bis = Math.ceil(Math.max(...termine.map((t) => minuten(t.ende))) / 60) * 60;
  const spanne = Math.max(bis - von, 60);
  const lage = (m) => ((m - von) / spanne) * 100;

  raster.style.gridTemplateColumns = `46px repeat(${tage.length}, 1fr)`;
  raster.style.gridTemplateRows = "auto 1fr";

  const heuteIso = alsIso(new Date());

  raster.insertAdjacentHTML("beforeend", '<div class="spaltenkopf zeitspalte"></div>');
  for (const { tag, iso } of tage) {
    raster.insertAdjacentHTML("beforeend",
      `<div class="spaltenkopf${iso === heuteIso ? " heute" : ""}">${WOCHENTAGE[(tag.getDay() + 6) % 7]} ${kurz(tag)}</div>`);
  }

  const achse = document.createElement("div");
  achse.className = "zeitachse";
  for (let m = von; m <= bis; m += 60) {
    achse.insertAdjacentHTML("beforeend",
      `<span class="uhrzeit" style="top:${lage(m)}%">${String(m / 60 | 0).padStart(2, "0")}:00</span>`);
  }
  raster.appendChild(achse);

  for (const { termine: desTages } of tage) {
    const spalte = document.createElement("div");
    spalte.className = "tagspalte";
    for (let m = von; m <= bis; m += 30) {
      spalte.insertAdjacentHTML("beforeend",
        `<div class="stundenlinie${m % 60 === 0 ? " voll" : ""}" style="top:${lage(m)}%"></div>`);
    }
    for (const [termin, versatz, anzahl] of nebeneinander(desTages)) {
      spalte.appendChild(terminKasten(termin, lage, versatz, anzahl));
    }
    raster.appendChild(spalte);
  }

  const abgeleitet = termine.filter((t) => !t.fachExakt).length;
  const ausKlasse = termine.filter((t) => t.ausKlassenplan).length;
  const teile = [`Erstellt am ${new Date().toLocaleString("de-AT", { dateStyle: "short", timeStyle: "short" })}`,
                 "Fächerbezeichnungen: Abkürzungsverzeichnis Schulzentrum Ungargasse"];
  if (abgeleitet) teile.push(`* ${abgeleitet} Bezeichnung(en) aus der Stammform abgeleitet`);
  if (ausKlasse) teile.push(`gestrichelt = nur im Klassenplan (${ausKlasse}×)`);
  $("fusszeile").textContent = teile.join("  ·  ");
}

/** Zeitlich ueberlappende Termine nebeneinander legen statt uebereinander. */
function nebeneinander(termine) {
  const gruppen = [];
  for (const termin of [...termine].sort((a, b) => a.beginn.localeCompare(b.beginn))) {
    const passend = gruppen.find((g) => g.some((x) => termin.beginn < x.ende && x.beginn < termin.ende));
    if (passend) passend.push(termin); else gruppen.push([termin]);
  }
  return gruppen.flatMap((g) => g.map((t, i) => [t, i, g.length]));
}

function terminKasten(termin, lage, versatz, anzahl) {
  const oben = lage(minuten(termin.beginn));
  const hoehe = lage(minuten(termin.ende)) - oben;
  const breite = 100 / anzahl;

  const kasten = document.createElement("div");
  kasten.className = "termin" + (termin.entfaellt ? " entfaellt" : "") +
                     (termin.ausKlassenplan ? " klassenplan" : "");
  kasten.style.top = `calc(${oben}% + 1px)`;
  kasten.style.height = `calc(${hoehe}% - 2px)`;
  kasten.style.left = `calc(${versatz * breite}% + 2px)`;
  kasten.style.width = `calc(${breite}% - 4px)`;
  if (!termin.entfaellt) kasten.style.background = fachfarbe(termin.kuerzel);

  const zeit = termin.beginn.slice(11) + "–" + termin.ende.slice(11);
  const ort = [termin.raum, termin.lehrkraft].filter(Boolean).join(" · ");
  const teile = [`<div class="fach">${sicher(termin.fach)}${termin.fachExakt ? "" : " *"}</div>`,
                 `<div class="zeile">${zeit}</div>`];
  if (ort) teile.push(`<div class="zeile">${sicher(ort)}</div>`);
  const lageText = termin.status || termin.info;
  if (lageText) teile.push(`<div class="lage">${sicher(lageText)}</div>`);
  if (termin.ausKlassenplan) teile.push('<div class="quelle">aus Klassenplan</div>');
  else if (termin.klassenHinweis) teile.push(`<div class="quelle">${sicher(termin.klassenHinweis)}</div>`);

  kasten.innerHTML = teile.join("");
  kasten.title = `${termin.fach} (${termin.kuerzel})\n${zeit}\n${ort}`;
  return kasten;
}

const sicher = (text) => String(text ?? "").replace(/[<>&]/g, (z) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[z]);

async function planLaden() {
  laden(true);
  try {
    const daten = await ruf(`/api/plan?montag=${alsIso(montag)}&modus=${encodeURIComponent($("modus").value)}`);
    planZeichnen(daten);
  } catch (fehler) {
    $("raster").innerHTML = `<p style="padding:28px;color:var(--entfaellt)">${sicher(fehler.message)}</p>`;
  } finally {
    laden(false);
  }
}

$("woche-zurueck").addEventListener("click", () => { montag.setDate(montag.getDate() - 7); planLaden(); });
$("woche-vor").addEventListener("click", () => { montag.setDate(montag.getDate() + 7); planLaden(); });
$("woche-heute").addEventListener("click", () => { montag = standardMontag(); planLaden(); });
$("modus").addEventListener("change", planLaden);
$("drucken").addEventListener("click", () => {
  /* In der Android-App uebernimmt das System den Druckdialog; dort heisst
     "Als PDF speichern" genauso wie am Rechner. */
  if (typeof Android !== "undefined" && Android.drucken) {
    Android.drucken(`Stundenplan ${$("schueler").textContent} ${$("woche-text").textContent}`);
  } else {
    window.print();
  }
});
$("konto-wechseln").addEventListener("click", async () => {
  if (!confirm("Gespeichertes Konto entfernen und neu einrichten?")) return;
  await ruf("/api/konto", { method: "DELETE" });
  location.reload();
});

/* ================= Lebenszeichen ================= */

/* Das Programm hat kein eigenes Fenster und keine Konsole. Damit es sich
   beenden kann, wenn niemand mehr zusieht, meldet sich die Oberflaeche
   regelmaessig. Bleibt sie aus, macht das Programm von selbst Schluss. */
const aufTelefon = typeof Android !== "undefined";

if (!aufTelefon) {
  setInterval(() => { ruf("/api/puls").catch(() => {}); }, 30000);

  /* Beim Schliessen des Fensters Bescheid geben, statt den Waechter zehn
     Minuten warten zu lassen. Bewusst kein hartes Beenden: pagehide feuert
     auch beim Neuladen. Das Signal verkuerzt nur die Geduld auf wenige
     Sekunden - kommt die Seite zurueck, bleibt alles wie es war. */
  addEventListener("pagehide", () => {
    navigator.sendBeacon?.("/api/schliesst?s=" + encodeURIComponent(schluessel));
  });

  $("beenden").hidden = false;
  $("beenden").addEventListener("click", async () => {
    await ruf("/api/beenden", { method: "POST" }).catch(() => {});
    document.body.innerHTML =
      '<p style="padding:40px;font:15px sans-serif;color:#667079">' +
      "SZUntisPDF wurde beendet. Dieses Fenster kann geschlossen werden.</p>";
    setTimeout(() => window.close(), 300);
  });
}

/* ================= Start ================= */

async function starte() {
  const status = await ruf("/api/status");

  /* In der Android-App kann ein QR-Code von aussen hereingereicht werden -
     etwa beim Scannen mit einer beliebigen Kamera-App. */
  if (status.wartenderCode) {
    await kontoSenden({ qr: status.wartenderCode });
    return;
  }

  if (!status.angemeldet) {
    $("plan").hidden = true;
    $("einrichtung").hidden = false;
    return;
  }
  $("einrichtung").hidden = true;
  $("plan").hidden = false;

  if (!$("modus").options.length) {
    for (const wert of status.modi) {
      const eintrag = new Option(wert, wert, wert === status.standardModus, wert === status.standardModus);
      $("modus").add(eintrag);
    }
  }
  if (!montag) montag = standardMontag();
  await planLaden();
}

starte().catch((fehler) => {
  document.body.innerHTML =
    `<p style="padding:40px;font:14px sans-serif">Verbindung zum Programm verloren.<br><br>` +
    `<small>${sicher(fehler.message)}</small><br><br>Bitte das Programmfenster prüfen und die Seite neu laden.</p>`;
});
