/*
 * seed.js - fills localStorage with 30 days of fake training + meal data for
 * manual testing of dashboard.html (PR board, streak, kcal ring, plateau notes, etc.).
 *
 * This file is never loaded by dashboard.html or referenced by build.py - it's a
 * standalone dev tool. To use it:
 *   1. Open dashboard.html in a browser and unlock the gate.
 *   2. Open the browser console, paste the contents of this file, press enter.
 *   3. Call seedDashboardTestData() to write the data, then reload the page.
 * Call clearDashboardTestData() to remove only what this script wrote.
 *
 * Mirrors the exercise keys used by build.py's SESSION_CATALOG:
 *   gsA (Mon) has 6 exercises, gsB (Wed) has 5, gsC (Fri) has 6 - keys look like
 *   "gsA::0".."gsA::5". Only strength days get sets; other weekdays are left alone.
 */
(function (global) {
  const SET_LOG_KEY = "garminDashboardSetLog_v1";
  const EXTRAS_KEY = "garminDashboardExtras_v1";

  const EXERCISE_COUNTS = { gsA: 6, gsB: 5, gsC: 6 };
  const EXERCISE_LABELS = {
    gsA: ["Glute bridge", "Beinpress", "Benkpress i maskin", "Sittende roing", "Hip thrust", "Pallof press"],
    gsB: ["Aktiveringssuperset", "Rumensk markløft", "Nedtrekk bredt grep", "Skulderpress", "Sideplanke med hoftehev"],
    gsC: ["Armhevinger mot benk", "Goblet squat", "Stående kabelrad", "Step-up", "Dead bug med vekt", "Planke med skulderberøring"],
  };
  // weekday() in build.py: 0=Mon .. 6=Sun. JS Date#getDay(): 0=Sun .. 6=Sat.
  const SESSION_BY_WEEKDAY = { 1: "gsA", 3: "gsB", 5: "gsC" }; // JS getDay() values for Mon/Wed/Fri
  const EXTRA_PRESETS = [
    { name: "Sjokolade", kcal: 250 },
    { name: "Glass vin", kcal: 120 },
    { name: "Øl", kcal: 150 },
    { name: "Frukt", kcal: 80 },
    { name: "Nøtter", kcal: 180 },
  ];

  function isoDaysAgo(n) {
    const d = new Date();
    d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }

  function loadLS(key, fallback) {
    try {
      const v = JSON.parse(localStorage.getItem(key));
      return v === null || v === undefined ? fallback : v;
    } catch (e) { return fallback; }
  }
  function saveLS(key, val) { localStorage.setItem(key, JSON.stringify(val)); }

  function buildSetLog() {
    const log = [];
    for (let daysAgo = 29; daysAgo >= 0; daysAgo--) {
      const date = isoDaysAgo(daysAgo);
      const weekday = new Date(date + "T00:00:00").getDay();
      const sessKey = SESSION_BY_WEEKDAY[weekday];
      if (!sessKey) continue; // rest / cycling day - no sets

      const count = EXERCISE_COUNTS[sessKey];
      const labels = EXERCISE_LABELS[sessKey];
      // mild progressive overload over the 30-day window so PR / plateau logic has something to chew on
      const weekNum = Math.floor((29 - daysAgo) / 7);
      for (let idx = 0; idx < count; idx++) {
        const baseWeight = 10 + idx * 2.5;
        const setsThisSession = 3;
        for (let setNum = 0; setNum < setsThisSession; setNum++) {
          log.push({
            id: "set-" + Date.now() + Math.random(),
            exercise: `${sessKey}::${idx}`,
            label: labels[idx],
            date,
            weight: baseWeight + weekNum * 1.25,
            reps: 10 + Math.max(0, weekNum - setNum),
          });
        }
      }
    }
    return log;
  }

  function buildExtras() {
    const extras = [];
    for (let daysAgo = 29; daysAgo >= 0; daysAgo--) {
      const date = isoDaysAgo(daysAgo);
      const count = Math.floor(Math.random() * 3); // 0-2 extras per day
      for (let i = 0; i < count; i++) {
        const preset = EXTRA_PRESETS[Math.floor(Math.random() * EXTRA_PRESETS.length)];
        extras.push({
          id: "extra-" + Date.now() + Math.random(),
          date,
          name: preset.name,
          kcal: preset.kcal,
        });
      }
    }
    return extras;
  }

  function seedDashboardTestData() {
    const existingSets = loadLS(SET_LOG_KEY, []);
    const existingExtras = loadLS(EXTRAS_KEY, []);
    saveLS(SET_LOG_KEY, existingSets.concat(buildSetLog()));
    saveLS(EXTRAS_KEY, existingExtras.concat(buildExtras()));
    console.log("Seeded 30 days of fake training + meal data. Reload the page to see it.");
  }

  function clearDashboardTestData() {
    localStorage.removeItem(SET_LOG_KEY);
    localStorage.removeItem(EXTRAS_KEY);
    console.log("Cleared seeded training + meal data (and anything else in those two keys).");
  }

  global.seedDashboardTestData = seedDashboardTestData;
  global.clearDashboardTestData = clearDashboardTestData;
})(typeof window !== "undefined" ? window : globalThis);
