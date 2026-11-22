"""
Reads data/*.json and writes dashboard.html - one self-contained file,
no server needed, charts drawn with inline SVG + vanilla JS.
"""
import json
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")

KM_PER_METER = 0.001

SPORT_MAP = {
    "strength_training": "Strength",
    "running": "Running",
    "treadmill_running": "Running",
    "trail_running": "Running",
    "track_running": "Running",
    "indoor_cycling": "Cycling",
    "cycling": "Cycling",
    "road_biking": "Cycling",
    "mountain_biking": "Cycling",
    "virtual_ride": "Cycling",
    "walking": "Walking",
    "hiking": "Walking",
}
SPORT_ORDER = ["Strength", "Cycling", "Running", "Walking", "Other"]
SPORT_COLORS = {
    "Strength": "#7a1f3d",
    "Cycling": "#9b3456",
    "Running": "#a46cc0",
    "Walking": "#e8a3b6",
    "Other": "#d9a441",
}

# ---- training program (general gym-based strength plan from 2026-11-09, "Grunnstyrke og stabilitet") ----
# Self-designed (not prescribed exercise-by-exercise by the naprapat): she was told she's generally
# weak and needs core/hip stability work, which is also likely why her knee reacts when running.
# Each strength day is full-body (push, pull, hip-hinge/glute, controlled knee-dominant, core,
# balance) so no single joint pattern gets stacked session after session, and knee-loading is spread
# across RDLs/leg press/goblet squat rather than concentrated in one heavy "leg day".
GS_START = date(2026, 11, 9)
PROGRAM = {
    0: {"key": "gsA", "label": "Styrke A: helkropp og kjerne", "type": "strength"},
    1: {"key": "cyc", "label": "Kondisjon", "type": "cardio"},
    2: {"key": "gsB", "label": "Styrke B: helkropp og kjerne", "type": "strength"},
    3: {"key": "restW", "label": "Hvile eller rolig gåtur", "type": "rest"},
    4: {"key": "gsC", "label": "Styrke C: helkropp og kjerne", "type": "strength"},
    5: {"key": "cycHard", "label": "Kondisjon - intervaller", "type": "cardio"},
    6: {"key": "rest", "label": "Hvile eller lett aktivitet", "type": "rest"},
}
GS_PROG = {
    1: {"sets": "2–3 sett", "cycle": "20–25 min", "focus": "Lær øvelsene, lett/moderat vekt, god teknikk og kontroll"},
    2: {"sets": "3 sett", "cycle": "20–30 min", "focus": "Øk vekten litt på øvelsene som føltes greie forrige uke"},
    3: {"sets": "3–4 sett", "cycle": "25–35 min", "focus": "Fortsett å øke vekt der kroppen tillater det"},
    4: {"sets": "3–4 sett", "cycle": "25–40 min", "focus": "Sikt på litt mer vekt eller reps der det er smertefritt"},
    5: {"sets": "1–2 sett", "cycle": "15–20 min", "focus": "Deload-uke: lavere vekt og volum, la kroppen hente seg inn før neste blokk", "deload": True},
}
PROG_EXERCISES = {
    "gsA": ["Hofteabduksjon stående i kabel (ankelstropp) - kjenn i ytre sete, ikke la tærne vippe opp 3×15/side",
            "Beinpress, kort bevegelsesutslag - kun hvis smertefritt 3×10–12", "Benkpress i maskin 3×8–10", "Sittende roing (kabel) 3×10–12",
            "Hip thrust (stang/manualer) - pause og klem rumpa i toppen 3×10–12", "Pallof press (kabel) 3×8–10/side"],
    "gsB": ["Supersett aktivering: Glute bridge 2×12 + Fire hydrants 2×10–12/side + Donkey kicks (spark bak på 4 bein) 2×10–12/side",
            "Rumensk markløft (manualer) - skyv hoftene bak, nøytral rygg, kjenn baksiden av lår/rumpe 3×8–10",
            "Nedtrekk, bredt grep (kabel) 3×8–10", "Skulderpress (manualer) 3×8–10",
            "Sideplanke med hoftehev 3×8–10/side"],
    "gsC": ["Armhevinger mot benk/vegg (jobb mot gulvet over tid) 3×8–12",
            "45° rygghev med fokus på rumpe (tær ut, rund øvre rygg, press gjennom hælen) 3×12",
            "Stående kabelrad 3×10–12", "Kabel-kickback - press bakover gjennom hælen, ikke svai korsryggen 3×12/side",
            "Dead bug med vekt 3×8/side", "Planke med skulderberøring 3×20–30 s"],
}
# Vises som et fast oppvarmingsblokk før alle tre styrkedagene (ikke en del av den
# indekserte exercises-loggen over - ingen vekt/reps-logging for disse, bare aktivering).
LEG_DAY_WARMUP = [
    "Rumpeklem 3×5 sek",
    "Glute bridge 2×12 (2 sek hold på toppen)",
    "Monster walk med strikk 2×10 skritt hver vei",
]

# ---- "kjenn det i rumpa"-tips for de rumpefokuserte øvelsene i hovedprogrammet (2026-11-22)
# - samme idé som startPosition/feelItWhere/commonMistakes i STABILITY_EXERCISES, men for
# Styrke A/B/C-øvelsene. Matches i JS ved at nøkkelen under er en substreng av øvelsesteksten
# i PROG_EXERCISES, så PROG_EXERCISES selv (og dermed sett-loggens indekser) ikke må endres.
GLUTE_EXERCISE_DETAILS = {
    "Hofteabduksjon stående i kabel": {
        "feelItWhere": "Øverst/ytterst i setet (gluteus medius) på beinet som jobber.",
        "cues": ["Hold overkroppen helt stille - bare beinet beveger seg", "Tenk «press hælen bakover», ikke «løft beinet høyt»"],
        "commonMistakes": ["Vipper overkroppen til siden for å få beinet lenger", "Lar tærne vippe opp i stedet for å peke fremover"],
    },
    "Hip thrust": {
        "feelItWhere": "Midt i rumpa, begge sider jevnt.",
        "cues": ["Vipp bekkenet bakover akkurat idet du når toppen, og stopp der", "Press gjennom hælene, haken inn", "Hold og knip 1-2 sek i toppen"],
        "commonMistakes": ["Overstrekker i toppen - korsryggen svaier", "Skyver fra tærne/fremfoten i stedet for hælene"],
    },
    "Glute bridge": {
        "feelItWhere": "Rumpa, ikke korsryggen.",
        "cues": ["Legg en hånd på rumpa de første repsene for å kjenne at den jobber", "Stopp når hofte og overkropp er på linje - ikke høyere"],
        "commonMistakes": ["Løfter hoften høyere enn nødvendig (overstrekk)", "Bruker korsryggen til å «svaie» opp i stedet for å bruke rumpa"],
    },
    "Rumensk markløft": {
        "feelItWhere": "Baksiden av lår og rumpe (hamstrings + glutes).",
        "cues": ["Skyv hoftene bakover som om du lukker en skuff med rumpa", "Hold en lett, fast bøy i kneet - ikke bøy mer underveis", "Skyv hoftene frem for å reise deg, og knip rumpa i toppen"],
        "commonMistakes": ["Bøyer kneet for mye (blir en knebøy i stedet for hofteleddsbøy)", "Runder i korsryggen", "Reiser seg ved å dra med korsryggen i stedet for å skyve hoftene frem"],
    },
    "45° rygghev": {
        "feelItWhere": "Rumpa og baksiden av lår, ikke korsryggen.",
        "cues": ["Tærne pekende litt ut", "Press gjennom hælene og knip rumpa på vei opp", "Stopp når kroppen er rett ut - ikke strekk lenger"],
        "commonMistakes": ["Runder øvre rygg for mye eller strekker for langt opp (overstrekk)", "Bruker fart/svai i stedet for kontroll"],
    },
    "Kabel-kickback": {
        "feelItWhere": "Rumpa på beinet som sparker bakover.",
        "cues": ["Minimal knebøy gjennom hele bevegelsen", "Tenk «press hælen bakover og litt opp», ikke «sving beinet»", "Hold overkroppen stabil - ikke bruk fart"],
        "commonMistakes": ["Svaier i korsryggen for å få beinet lenger bak", "Sparker for høyt i stedet for kontrollert"],
    },
}

# ---- Sete, kjerne og stabilitet (2026-11-17) - eget tilleggsprogram, kommer i tillegg til
# (ikke erstatter) grunnstyrkeprogrammet over. Bygget rundt et aktivt kneproblem: ingen løping,
# tunge knebøy/utfall, step-ups eller tungt beinpress, og aldri noe som gir smerte/økt hevelse.
# Nivå 1 er det eneste aktive nivået - nivå 2/3 er bevisst låst inntil fysioterapeut har vurdert
# kneet, og låses ALDRI opp automatisk basert på tid/antall uker.
STABILITY_EXERCISES = [
    {
        "key": "glute_bridge",
        "name": "Glute bridge",
        "sets": "2-3 sett",
        "repsLabel": "10-12 reps, hold 2 sek på toppen",
        "startPosition": "Ligg på ryggen med bøyde knær og føttene i gulvet, omtrent hoftebredt.",
        "steps": [
            "Spenn magen lett.",
            "Løft hoften opp uten å svaie i korsryggen.",
            "Stopp når hofte og overkropp er omtrent på linje - ikke høyere.",
            "Hold toppstillingen i 2 sekunder og kjenn etter at det er setet som jobber.",
            "Senk kontrollert tilbake til start.",
        ],
        "muscles": "Primært gluteus maximus. Noe aktivitet i hamstrings er normalt.",
        "feelItWhere": "Mest i setet. Ikke la korsrygg eller fremside lår dominere.",
        "commonMistakes": ["Svai i korsryggen i stedet for å bruke setet", "Fremside lår tar mye av jobben",
                            "Løfter hoften høyere enn nødvendig (overstrekk i rygg)"],
        "longLegsNote": "Juster fotplasseringen etter en komfortabel knevinkel - ikke sett føttene så langt unna kroppen at hamstrings tar over. Ikke press hoften høyere enn du klarer med god bekkenkontroll.",
    },
    {
        "key": "hip_abduction",
        "name": "Sideliggende hofteabduksjon",
        "sets": "2-3 sett",
        "repsLabel": "12 reps per side",
        "startPosition": "Ligg på siden med nederste bein lett bøyd for støtte. Øverste bein er rett, tærne peker fremover.",
        "steps": [
            "Før det øverste beinet litt bakover (ikke rett opp fra hoften).",
            "Hold tærne pekende fremover gjennom hele bevegelsen.",
            "Løft beinet kontrollert, omtrent 20-30 cm.",
            "Hold et øyeblikk på toppen.",
            "Senk langsomt tilbake - ikke la det falle.",
        ],
        "muscles": "Primært gluteus medius - øvre, ytre del av setet.",
        "feelItWhere": "Øverst/ytterst i setet på det løftende beinet.",
        "commonMistakes": ["Peker tærne opp i stedet for fremover", "Løfter for høyt og mister bekkenkontroll",
                            "Lar overkroppen rulle bakover for å få beinet høyere"],
        "longLegsNote": "Bruk mindre bevegelsesutslag om nødvendig. Hold bekkenet helt stabilt - det er kontrollen, ikke høyden på løftet, som gir effekten.",
    },
    {
        "key": "clamshell",
        "name": "Clamshell",
        "sets": "2 sett",
        "repsLabel": "12-15 reps per side",
        "startPosition": "Ligg på siden med bøyde knær, føttene samlet og i forlengelse av ryggen.",
        "steps": [
            "Hold føttene i kontakt med hverandre gjennom hele bevegelsen.",
            "Åpne det øverste kneet som et skjell, uten å rotere bekkenet bakover.",
            "Hold et øyeblikk i åpen posisjon.",
            "Lukk kontrollert tilbake til start.",
            "Start uten strikk til bevegelsen føles kontrollert.",
        ],
        "muscles": "Gluteus medius og omkringliggende hoftemuskulatur.",
        "feelItWhere": "I det ytre setet/hoften på det øverste beinet.",
        "commonMistakes": ["Ruller bekkenet bakover for å åpne kneet lenger", "Bruker fart i stedet for kontroll"],
        "longLegsNote": "Hold et lite, kontrollert bevegelsesutslag - det er greit om kneet ikke åpner seg veldig langt.",
    },
    {
        "key": "dead_bug",
        "name": "Dead bug",
        "sets": "2-3 sett",
        "repsLabel": "8 reps per side",
        "startPosition": "Ligg på ryggen med knærne rett over hoftene (90 grader) og armene strukket mot taket.",
        "steps": [
            "Spenn kjernen og press korsryggen svakt ned mot gulvet - hold den der.",
            "Senk motsatt arm og motsatt bein kontrollert mot gulvet.",
            "Stopp før korsryggen begynner å svaie eller løfte seg fra gulvet.",
            "Før arm og bein kontrollert tilbake til start.",
            "Bytt side.",
        ],
        "muscles": "Mage og dyp kjernemuskulatur.",
        "feelItWhere": "I mage/kjerne - korsryggen skal ikke jobbe eller svaie.",
        "commonMistakes": ["Korsryggen svaier eller løftes fra gulvet", "Senker arm/bein lenger enn kjernen klarer å kontrollere"],
        "longLegsNote": "Start med kort bevegelsesutslag og litt bøy i kneet. Ikke senk beinet lenger enn du klarer å holde bekkenet helt stabilt.",
    },
    {
        "key": "pallof_press",
        "name": "Pallof press",
        "sets": "2-3 sett",
        "repsLabel": "10 reps per side",
        "startPosition": "Stå med siden mot festepunktet (kabel/strikk), hendene samlet foran brystet.",
        "steps": [
            "Stå i en stabil, smertefri ståstilling.",
            "Press hendene rett fremover fra brystet.",
            "Motstå at strikken/kabelen drar deg i rotasjon - hold hoftene og brystet rolig fremover.",
            "Hold et øyeblikk i utstrakt posisjon.",
            "Før hendene kontrollert tilbake til brystet.",
        ],
        "muscles": "Kjernemuskulaturen rundt mage og midje (anti-rotasjon).",
        "feelItWhere": "Gjennom hele midjen/kjernen når du motstår rotasjonen.",
        "commonMistakes": ["Lar overkroppen rotere med strikken", "Låser ikke hoftene, så rotasjonen kommer derfra i stedet"],
        "longLegsNote": "Kan gjøres sittende i stedet for stående dersom stående belastning provoserer kneet.",
    },
]
STABILITY_LOCKED_LEVELS = [
    {"level": 2, "title": "Nivå 2 - Funksjonell styrke",
     "exercises": ["Hip thrust", "Kabel kickback", "Enkle hofteøvelser med økt motstand", "Kontrollert knebøyvariant", "Step-up (dersom kneet tåler det)"]},
    {"level": 3, "title": "Nivå 3 - Løpsforberedelse",
     "exercises": ["Step-down", "Enbeins RDL", "Enbeins stabilitetsøvelser", "Gradvis løp/gange", "Løpsspesifikk styrke"]},
]

# ---- kne/hofte/nakke-status vist øverst i Treningsplan (2026-11-20) ----
KNEE_PAUSE_NOTE = (
    "Løping er satt på pause pga. irritert indre leddbånd (MCL) i høyre kne. "
    "Bruk sykkel (lav motstand), elliptisk eller rask gåtur i stedet, samme varighet."
)
KNEE_RESUME_CRITERIA = [
    "Kneet er rolig i hvile",
    "15 ettbeins glute bridges per side, smertefritt",
    "Rolig ettbeins knebøy ned på en stol, uten smerte",
]
KNEE_PAIN_RULE = "Smerte opp til 2-3 av 10 er ok hvis det har roet seg dagen etter. Ellers: trapp ned."
GLUTE_TECHNIQUE_CUES = [
    "Vipp bekkenet litt bakover på toppen av bridge/hip thrust",
    "Press gjennom hælen, haken inn",
    "Kne over 2.-3. tå, ikke la det falle innover",
    "Kjenner du det ikke i rumpa: senk vekta",
]

# ---- daglig rutine (kne/hofte-bekken-mobilisering/nakke, ~8-10 min) - separat fra
# treningsplanen, vist som egen sjekkliste på Hjem. Bare mobilisering/tøying for hofte og
# bekken her (ingen rumpestyrke - det dekkes av selve treningsplanen), og kun 2 nakkeøvelser.
# Krysses av dag for dag (nullstilles automatisk hver dag siden loggen er nøkklet på dato),
# ikke koblet til sett-logg/PR-systemet.
DAILY_ROUTINE_ITEMS = [
    {"key": "quadSet", "group": "Kne", "label": "Quad-set med håndkle under kneet 2×10 (5 sek hold)"},
    {"key": "helSklie", "group": "Kne", "label": "Hælsklie på ryggen 2×10"},
    {"key": "bekkentilt", "group": "Hofte og bekken", "label": "Bekkentilt på ryggen 10 rep"},
    {"key": "hoftebøyerstrekk", "group": "Hofte og bekken", "label": "Hoftebøyerstrekk i halv knestående 2×30 sek/side"},
    {"key": "figur4", "group": "Hofte og bekken", "label": "Liggende figur 4-tøy 2×30 sek/side"},
    {"key": "haketrekk", "group": "Nakke", "label": "Haketrekk liggende på ryggen 10×5 sek"},
    {"key": "yT", "group": "Nakke", "label": "Liggende Y- og T-løft på magen 2×10 hver"},
]
# Built-in ingredient catalog: kcal/protein per 100g, used for the "bytt ingrediens" feature
# in the meal plan. Values are standard reference estimates (±10%, same spirit as the rest
# of the nutrition numbers in this app) - she can add her own ingredients or correct these
# in the app itself (stored in localStorage, layered on top of this list).
# "dept" groups an ingredient into a shopping-list section (see SHOP_DEPT_ORDER in the JS).
INGREDIENT_CATALOG = {
    "kyllingfilet": {"label": "Kyllingfilet", "kcal100": 165, "protein100": 31, "dept": "Kjøtt og fisk"},
    "kyllingkjottdeig": {"label": "Kyllingkjøttdeig", "kcal100": 143, "protein100": 18, "dept": "Kjøtt og fisk"},
    "karbonadedeig": {"label": "Karbonadedeig", "kcal100": 220, "protein100": 18, "dept": "Kjøtt og fisk"},
    "kalkunfilet": {"label": "Kalkunfilet", "kcal100": 135, "protein100": 29, "dept": "Kjøtt og fisk"},
    "laksefilet": {"label": "Laksefilet", "kcal100": 208, "protein100": 20, "dept": "Kjøtt og fisk"},
    "torsk": {"label": "Torsk/hvit fisk", "kcal100": 82, "protein100": 18, "dept": "Kjøtt og fisk"},
    "egg": {"label": "Egg", "kcal100": 155, "protein100": 13, "dept": "Meieri"},
    "ris": {"label": "Ris (tørrvekt)", "kcal100": 360, "protein100": 7, "dept": "Tørrvarer"},
    "quinoa": {"label": "Quinoa (tørrvekt)", "kcal100": 368, "protein100": 14, "dept": "Tørrvarer"},
    "pasta": {"label": "Pasta (tørrvekt)", "kcal100": 350, "protein100": 12, "dept": "Tørrvarer"},
    "poteter": {"label": "Poteter", "kcal100": 77, "protein100": 2, "dept": "Frukt og grønt"},
    "havregryn": {"label": "Havregryn", "kcal100": 375, "protein100": 13, "dept": "Tørrvarer"},
    "proteinpulver": {"label": "Proteinpulver", "kcal100": 380, "protein100": 75, "dept": "Tørrvarer"},
    "proteinmelk": {"label": "Proteinmelk", "kcal100": 55, "protein100": 8, "dept": "Meieri"},
    "gresk_yoghurt": {"label": "Gresk yoghurt", "kcal100": 97, "protein100": 9, "dept": "Meieri"},
    "mager_kesam": {"label": "Mager kesam", "kcal100": 70, "protein100": 12, "dept": "Meieri"},
    "cottage_cheese": {"label": "Cottage cheese", "kcal100": 98, "protein100": 11, "dept": "Meieri"},
    "skyr": {"label": "Høyprotein yoghurt/skyr", "kcal100": 60, "protein100": 10, "dept": "Meieri"},
    "kakaogranola": {"label": "Kakaogranola", "kcal100": 450, "protein100": 8, "dept": "Tørrvarer"},
    "chiafro": {"label": "Chiafrø", "kcal100": 486, "protein100": 17, "dept": "Tørrvarer"},
    "brokkoli": {"label": "Brokkoli", "kcal100": 34, "protein100": 2.8, "dept": "Frukt og grønt"},
    "sotpotet": {"label": "Søtpotet", "kcal100": 86, "protein100": 1.6, "dept": "Frukt og grønt"},
    "kikerter": {"label": "Kikerter (avrent, boks)", "kcal100": 164, "protein100": 8.9, "dept": "Tørrvarer"},
}

# Each recipe's "items" are either a structured, swappable ingredient line
# ({"ing": <catalog key>, "amount": grams, optionally "display": "<custom label>"})
# or a plain non-swappable display line ({"text": "..."}) for garnish/sauces that
# aren't worth a full macro breakdown. "kcal"/"protein" stay the original hand-estimated
# totals for the recipe; _finalize_nutrition_plan() below backs out how much of that total
# isn't explained by the structured ingredients ("extraKcal"/"extraProtein" - covers the
# text-only lines), so swapping a structured ingredient recalculates the total correctly
# without needing to re-type every recipe's numbers by hand.
NUTRITION_PLAN = {
    "dailyKcal": 1750,
    "proteinMin": 140,
    "note": "Tallene er grove anslag basert på vanlige produktverdier (±10%) - sjekk egne etiketter (proteinpulver, YT-produkter) for mer nøyaktige tall.",
    "breakfast": {
        "label": "Frokost - standard, eller velg et eget forslag",
        "options": [
            {"name": "Havregrøt med protein", "items": [
                {"ing": "havregryn", "amount": 40},
                {"ing": "proteinpulver", "amount": 20},
                {"ing": "proteinmelk", "amount": 100, "display": "1 dl proteinmelk"},
                {"ing": "chiafro", "amount": 10},
                {"ing": "gresk_yoghurt", "amount": 100},
            ], "kcal": 450, "protein": 32},
            {"name": "Eggerøre med cottage cheese", "items": [
                {"ing": "egg", "amount": 150, "display": "3 egg"},
                {"ing": "cottage_cheese", "amount": 50},
                {"text": "1 skive grovbrød"},
            ], "kcal": 360, "protein": 28},
            {"name": "Skyr-bowl med granola (ingen koking)", "items": [
                {"ing": "skyr", "amount": 200, "display": "200 g høyprotein yoghurt/skyr"},
                {"ing": "kakaogranola", "amount": 20},
                {"text": "bringebær"},
            ], "kcal": 240, "protein": 22},
        ],
    },
    "lunch": {
        "label": "Lunsj - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingfilet-wrap", "items": [
                {"ing": "kyllingfilet", "amount": 130},
                {"text": "1 grovt pitabrød"},
                {"text": "agurk og paprika"},
                {"text": "1 ss lett rømme/yoghurtdressing"},
            ], "kcal": 400, "protein": 35},
            {"name": "Karbonadedeig med ris", "mealprep": True, "items": [
                {"ing": "karbonadedeig", "amount": 120},
                {"ing": "ris", "amount": 60, "display": "60 g ris (tørrvekt)"},
                {"text": "agurk og paprika"},
            ], "kcal": 430, "protein": 28},
            {"name": "Kyllingfilet med ris og agurk", "mealprep": True, "items": [
                {"ing": "kyllingfilet", "amount": 150},
                {"ing": "ris", "amount": 50, "display": "50 g ris (tørrvekt)"},
                {"text": "agurk"},
            ], "kcal": 430, "protein": 50},
            {"name": "Pasta med kyllingfilet", "mealprep": True, "items": [
                {"ing": "pasta", "amount": 70, "display": "70 g pasta (tørrvekt)"},
                {"ing": "kyllingfilet", "amount": 120},
                {"text": "tomatsaus og litt parmesan"},
            ], "kcal": 480, "protein": 46},
            {"name": "Kyllingkjøttdeig-taco", "items": [
                {"ing": "kyllingkjottdeig", "amount": 130},
                {"text": "2 extra thin tacolefser"},
                {"text": "agurk og paprika"},
                {"text": "litt mager kesam"},
            ], "kcal": 400, "protein": 32},
            {"name": "Proteinrundstykke med kyllingfilet", "items": [
                {"text": "1 proteinrundstykke"},
                {"ing": "kyllingfilet", "amount": 80, "display": "80 g kyllingfilet-pålegg"},
                {"text": "salat og tomat"},
                {"text": "litt lett dressing"},
            ], "kcal": 350, "protein": 30},
            {"name": "Wrap med ferdigstekt kylling", "items": [
                {"text": "1 grov tortillalefse"},
                {"ing": "kyllingfilet", "amount": 100, "display": "100 g ferdigstekt kyllingfilet (butikk)"},
                {"text": "agurk og paprika"},
                {"text": "litt lett dressing"},
            ], "kcal": 380, "protein": 30},
            {"name": "Kylling-bowl med quinoa og brokkoli", "mealprep": True, "items": [
                {"ing": "kyllingfilet", "amount": 120},
                {"ing": "quinoa", "amount": 50, "display": "50 g quinoa (tørrvekt)"},
                {"ing": "brokkoli", "amount": 100},
                {"text": "litt olivenolje og sitron"},
            ], "kcal": 460, "protein": 47},
        ],
    },
    "snack": {
        "label": "Mellommåltid - velg én",
        "options": [
            {"name": "Yoghurt med bringebær og granola", "items": [
                {"ing": "skyr", "amount": 150, "display": "150 g høyprotein yoghurt/skyr"},
                {"ing": "kakaogranola", "amount": 20},
                {"text": "bringebær"},
                {"text": "1 ts Biscoff"},
            ], "kcal": 230, "protein": 18},
            {"name": "YT proteinprodukt", "items": [
                {"text": "1 stk (sjekk etiketten for nøyaktige tall)"},
            ], "kcal": 180, "protein": 20},
            {"name": "Mager kesam med bringebær", "items": [
                {"ing": "mager_kesam", "amount": 150},
                {"text": "bringebær"},
            ], "kcal": 110, "protein": 18},
            {"name": "2 kokte egg", "items": [
                {"ing": "egg", "amount": 120, "display": "2 egg"},
            ], "kcal": 190, "protein": 16},
        ],
    },
    "dinner": {
        "label": "Middag - velg én, rullér gjennom uken",
        "options": [
            {"name": "Kyllingkjøttdeig-stekt ris", "mealprep": True, "items": [
                {"ing": "kyllingkjottdeig", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "amerikansk grønnsaksblanding (frossen)"},
                {"text": "litt soyasaus"},
            ], "kcal": 520, "protein": 42},
            {"name": "Pasta med kjøttsaus", "mealprep": True, "items": [
                {"ing": "pasta", "amount": 80, "display": "80 g pasta (tørrvekt)"},
                {"ing": "karbonadedeig", "amount": 130},
                {"text": "litt tomatsaus"},
                {"text": "paprika"},
            ], "kcal": 560, "protein": 33},
            {"name": "Kylling med ris", "mealprep": True, "items": [
                {"ing": "kyllingfilet", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "agurk og paprika"},
            ], "kcal": 480, "protein": 44},
            {"name": "Laks med poteter", "mealprep": True, "items": [
                {"ing": "laksefilet", "amount": 150},
                {"ing": "poteter", "amount": 200},
                {"text": "brokkoli"},
            ], "kcal": 490, "protein": 38},
            {"name": "Taco-gryte", "mealprep": True, "items": [
                {"ing": "kyllingkjottdeig", "amount": 150},
                {"text": "100 g mais og bønner"},
                {"text": "1 dl lettrømme"},
                {"text": "liten porsjon tortillachips"},
            ], "kcal": 540, "protein": 36},
            {"name": "Ovnsbakt laks med søtpotet og brokkoli", "mealprep": True, "items": [
                {"ing": "laksefilet", "amount": 150},
                {"ing": "sotpotet", "amount": 200, "display": "200 g søtpotet"},
                {"ing": "brokkoli", "amount": 150},
            ], "kcal": 540, "protein": 38},
            {"name": "Kyllinggryte med kikerter og ris", "mealprep": True, "items": [
                {"ing": "kyllingfilet", "amount": 100},
                {"ing": "kikerter", "amount": 120, "display": "120 g kikerter (avrent)"},
                {"ing": "ris", "amount": 40, "display": "40 g ris (tørrvekt)"},
                {"text": "karripasta og litt kokosmelk"},
            ], "kcal": 520, "protein": 46},
            {"name": "Laks med mangochutney og crème fraiche", "mealprep": True, "items": [
                {"ing": "laksefilet", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "mangochutney og litt crème fraiche"},
            ], "kcal": 620, "protein": 36},
            {"name": "Kalkunfilet med ris", "mealprep": True, "items": [
                {"ing": "kalkunfilet", "amount": 150},
                {"ing": "ris", "amount": 70, "display": "70 g ris (tørrvekt)"},
                {"text": "agurk og paprika"},
            ], "kcal": 460, "protein": 48},
            {"name": "Kyllingfilet-gryte med pasta", "mealprep": True, "items": [
                {"ing": "kyllingfilet", "amount": 130},
                {"ing": "pasta", "amount": 60, "display": "60 g pasta (tørrvekt)"},
                {"text": "tomatsaus og paprika"},
            ], "kcal": 460, "protein": 47},
        ],
    },
}


def _finalize_nutrition_plan(plan, catalog):
    for group_key in ("breakfast", "lunch", "snack", "dinner"):
        for opt in plan[group_key]["options"]:
            structured_kcal = sum(catalog[i["ing"]]["kcal100"] * i["amount"] / 100 for i in opt["items"] if "ing" in i)
            structured_protein = sum(catalog[i["ing"]]["protein100"] * i["amount"] / 100 for i in opt["items"] if "ing" in i)
            opt["extraKcal"] = round(opt["kcal"] - structured_kcal)
            opt["extraProtein"] = round(opt["protein"] - structured_protein, 1)
    return plan


NUTRITION_PLAN = _finalize_nutrition_plan(NUTRITION_PLAN, INGREDIENT_CATALOG)
# ---- budget (starting points - fully editable in the app; income 32k/mnd) ----
# Økonomimåned: 15.-14. "cap" is the initial budget amount;
# the app converts this to a capHistory (effective-dated) list on first load so that
# later edits only affect the economic month they were made in, and onward.
BUDGET_DEFAULTS = {
    "income": 32000,
    "categories": [
        # faste utgifter
        {"key": "husleie", "label": "Husleie", "type": "fixed", "icon": "🏠", "cap": 13500},
        {"key": "strom", "label": "Strøm", "type": "fixed", "icon": "⚡", "cap": 1000},
        {"key": "forsikring", "label": "Forsikring", "type": "fixed", "icon": "🛡️", "cap": 764},
        {"key": "mobil_internett", "label": "Mobil og internett", "type": "fixed", "icon": "📱", "cap": 299},
        {"key": "abonnementer", "label": "Abonnementer", "type": "fixed", "icon": "🔁", "cap": 496},
        {"key": "treningssenter", "label": "Treningssenter", "type": "fixed", "icon": "🏋️", "cap": 449},
        {"key": "studielan", "label": "Studielån", "type": "fixed", "icon": "🎓", "cap": 3730},
        {"key": "ruter", "label": "Ruter", "type": "fixed", "icon": "🚌", "cap": 495},
        # variable utgifter
        {"key": "mat", "label": "Mat og dagligvarer", "type": "variable", "icon": "🛒", "cap": 3800},
        {"key": "transport", "label": "Transport", "type": "variable", "icon": "🚗", "cap": 900},
        {"key": "klaer_velvare", "label": "Klær og velvære", "type": "variable", "icon": "👗", "cap": 700},
        {"key": "fritid_sosialt", "label": "Fritid og sosialt", "type": "variable", "icon": "🎉", "cap": 800},
        {"key": "gaver", "label": "Gaver", "type": "variable", "icon": "🎁", "cap": 500},
        {"key": "snus", "label": "Snus", "type": "variable", "icon": "🚬", "cap": 500},
        {"key": "annet", "label": "Annet", "type": "variable", "icon": "📦", "cap": 500},
        # sparing (egne linjer, men regnes som variable utgifter)
        {"key": "hundefond", "label": "Sparing: Hund", "type": "variable", "savings": True, "icon": "🐶", "cap": 1000},
        {"key": "sparing_pensjon", "label": "Sparing: Pensjon", "type": "variable", "savings": True, "icon": "👵", "cap": 1000},
        {"key": "sparing_hoyrente", "label": "Sparing: Høyrente", "type": "variable", "savings": True, "icon": "💰", "cap": 1000},
        {"key": "sparing_buffer", "label": "Sparing: Bufferspar", "type": "variable", "savings": True, "icon": "🧯", "cap": 1000},
        {"key": "sparekrukke", "label": "Sparekrukka", "type": "variable", "savings": True, "icon": "🫙", "cap": 500},
    ],
}
DOG_FUND = {"target": 30000, "startSaved": 5000, "category": "hundefond"}
ACTIVE_CAL_GOAL_DEFAULT = 400

# ---- points / levels ----
POINTS_CONFIG = {
    "levelThreshold": 600,
    "perCompletedSession": 15,
    "perStepGoalDay": 5,
    "perWeightWeek": 10,
    "perMeasurementMonth": 15,
    "perNewRecord": 20,
    "perFundMilestone": 50,
    "levelNames": ["Frø", "Spire", "Knopp", "Blomst", "Bukett", "Hage", "Rosekongen"],
    "levelRewards": [
        "Start! 🌱", "Nye treningssokker eller fin hårklype",
        "Et lite sølvsmykke, f.eks. øredobber eller et armbånd",
        "Ny spilleliste og fin vannflaske til treningsbagen",
        "Manikyr eller en bukett blomster til deg selv",
        "Noe fint til leiligheten, f.eks. en plante eller pute",
        "En hel dag fri fra alt, akkurat som du vil 👑",
    ],
}
WEEKDAY_LABELS_NO = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
STRENGTH_TYPE_KEYS = {"strength_training"}
CYCLING_TYPE_KEYS = {"indoor_cycling", "cycling", "road_biking", "mountain_biking", "virtual_ride", "elliptical"}
RUNNING_TYPE_KEYS = {"running", "treadmill_running", "trail_running", "track_running"}
WALK_TYPE_KEYS = {"walking", "hiking"}
# "cardio" is deliberately generic: a planned "Kondisjon" day is satisfied by any cardio
# activity Garmin logs that day (cycling, running, walking, elliptical, ...), not just cycling.
CARDIO_TYPE_KEYS = CYCLING_TYPE_KEYS | RUNNING_TYPE_KEYS | WALK_TYPE_KEYS
TYPE_KEYS_BY_BUCKET = {"strength": STRENGTH_TYPE_KEYS, "cardio": CARDIO_TYPE_KEYS}

# swap options a session can be manually changed to, for the interactive plan
SESSION_CATALOG = {
    "gsA": {"label": PROGRAM[0]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsA"]},
    "gsB": {"label": PROGRAM[2]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsB"]},
    "gsC": {"label": PROGRAM[4]["label"], "type": "strength", "exercises": PROG_EXERCISES["gsC"]},
    "cyc": {"label": "Kondisjon", "type": "cardio", "note": "Løping er satt på pause pga. kneet - bruk sykkel (lav motstand), elliptisk eller rask gåtur i stedet, samme varighet. Egen takt - du skal kunne prate i hele setninger."},
    "cycHard": {"label": "Kondisjon - intervaller", "type": "cardio", "note": "Løping er satt på pause pga. kneet - kjør intervallene på sykkel, ellipse eller rask gange i bakke i stedet. 4×4-intervaller: 4 min hardt (du skal IKKE kunne prate i hele setninger), 3 min rolig aktiv pause, gjenta 4 ganger."},
    "walk": {"label": "Gåtur", "type": "cardio"},
    "rest": {"label": "Hvile", "type": "rest"},
}


def gs_week(d):
    n = (d - GS_START).days // 7 + 1
    n = max(1, n)
    return (n - 1) % 5 + 1


def session_for(d):
    sess = dict(PROGRAM[d.weekday()])
    week = gs_week(d)
    if sess["key"] in ("cyc", "cycHard"):
        sess["label"] = f"{SESSION_CATALOG[sess['key']]['label']} ({GS_PROG[week]['cycle']})"
    return sess


def load_json(name, default):
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def sport_for(type_key):
    return SPORT_MAP.get(type_key, "Other")


def iso_week_start(d):
    return d - timedelta(days=d.weekday())


def week_label(d):
    return d.strftime("%Y-%m-%d")


def safe_round(x, n=0):
    if x is None:
        return None
    return round(x, n) if n else int(round(x))


VO2_SPORT_LABELS_NO = {"RUNNING": "Løping", "WALKING": "Gange", "CYCLING": "Sykling"}


def parse_vo2max():
    """Garmin's VO2 max estimate, from the confirmed-working Personal API endpoint
    (verified live against the real account). Entries only appear on days Garmin actually
    recomputed an estimate, so this picks the most recent one in the pulled window. Garmin's
    separate "Training Status" (Productive/Peaking/etc.) isn't available via this API at all -
    that's part of a different, paid Garmin business product."""
    raw = load_json("vo2max.json", None)
    if not raw or not raw.get("data"):
        return None
    entries = [e for e in raw["data"] if (e.get("generic") or {}).get("vo2MaxValue") is not None]
    if not entries:
        return None
    entries.sort(key=lambda e: e["generic"]["calendarDate"])
    latest = entries[-1]["generic"]
    vo2max = latest.get("vo2MaxPreciseValue")
    if vo2max is None:
        vo2max = latest.get("vo2MaxValue")
    sport = latest.get("sport")
    return {
        "vo2Max": safe_round(vo2max, 1),
        "date": latest.get("calendarDate"),
        "sport": VO2_SPORT_LABELS_NO.get(sport, sport),
    }


def main():
    activities = load_json("activities.json", [])
    daily = load_json("daily_summaries.json", {})
    sleep = load_json("sleep.json", {})
    hrv = load_json("hrv.json", {})
    weight = load_json("weight.json", {})
    # Only the fields the dashboard actually shows (kg, body fat %, muscle mass) - the rest
    # of what pull_weight() captures (bmi, visceralFat, ...) stays in data/weight.json for
    # later, unverified until a real smart-scale reading comes through.
    garmin_weight = {}
    for d, v in weight.items():
        entry = {"kg": round(v["weightGrams"] / 1000, 1)}
        if v.get("bodyFat") is not None:
            entry["bodyFat"] = round(v["bodyFat"], 1)
        if v.get("muscleMass") is not None:
            entry["muscleMassKg"] = round(v["muscleMass"] / 1000, 1)
        garmin_weight[d] = entry

    # ---------------------------------------------------------------- dates
    all_dates = set(daily.keys()) | set(sleep.keys()) | set(hrv.keys())
    for a in activities:
        if a.get("startTimeLocal"):
            all_dates.add(a["startTimeLocal"][:10])
    if not all_dates:
        raise SystemExit("No data found in data/. Run pull.py first.")
    min_date, max_date = min(all_dates), max(all_dates)

    # -------------------------------------------------------- top stat cards
    def latest_entries(d, n=30):
        keys = sorted(d.keys())
        return keys[-n:]

    daily_keys = sorted(daily.keys())
    sleep_keys = sorted(sleep.keys())
    hrv_keys = sorted(hrv.keys())

    def trend_series(d, keys, extractor, n=30):
        out = []
        for k in keys[-n:]:
            v = extractor(d[k])
            out.append(v)
        return out

    top_stats = {}

    if hrv_keys:
        last_k = hrv_keys[-1]
        top_stats["hrv"] = {
            "value": safe_round(hrv[last_k].get("lastNightAvg")),
            "weeklyAvg": safe_round(hrv[last_k].get("weeklyAvg")),
            "status": hrv[last_k].get("status"),
            "date": last_k,
            "trend": trend_series(hrv, hrv_keys, lambda v: v.get("lastNightAvg")),
        }

    if sleep_keys:
        last_k = sleep_keys[-1]
        s = sleep[last_k]
        score = ((s.get("sleepScores") or {}).get("overall") or {}).get("value")
        top_stats["sleep"] = {
            "hours": safe_round((s.get("sleepTimeSeconds") or 0) / 3600, 1),
            "score": safe_round(score),
            "date": last_k,
            "trend": trend_series(
                sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 1)
            ),
        }

    if daily_keys:
        last_k = daily_keys[-1]
        d0 = daily[last_k]
        cal = (d0.get("calories") or {}).get("burnedTotal")
        steps = (d0.get("movement") or {}).get("steps", {}).get("value")
        resting_hr = (d0.get("heartRate") or {}).get("restingValue")
        top_stats["calories"] = {
            "value": safe_round(cal),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("calories") or {}).get("burnedTotal"))),
        }
        top_stats["steps"] = {
            "value": safe_round(steps),
            "goal": safe_round((d0.get("movement") or {}).get("steps", {}).get("goal")),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("movement") or {}).get("steps", {}).get("value"))),
        }
        top_stats["restingHR"] = {
            "value": safe_round(resting_hr),
            "date": last_k,
            "trend": trend_series(daily, daily_keys, lambda v: safe_round((v.get("heartRate") or {}).get("restingValue"))),
        }

    # ------------------------------------------------------ weekly by sport
    weekly_sport = defaultdict(lambda: defaultdict(lambda: {"sessions": 0, "minutes": 0.0, "distanceKm": 0.0, "calories": 0.0}))
    for a in activities:
        start = a.get("startTimeLocal")
        if not start:
            continue
        d = datetime.strptime(start[:10], "%Y-%m-%d").date()
        wk = week_label(iso_week_start(d))
        sport = sport_for((a.get("activityType") or {}).get("typeKey", ""))
        entry = weekly_sport[wk][sport]
        entry["sessions"] += 1
        entry["minutes"] += (a.get("duration") or 0) / 60
        entry["distanceKm"] += (a.get("distance") or 0) * KM_PER_METER
        entry["calories"] += a.get("calories") or 0

    sorted_weeks = sorted(weekly_sport.keys())
    recent_weeks = sorted_weeks[-10:]
    weekly_by_sport_out = []
    for wk in recent_weeks:
        sports_out = {}
        for sport in SPORT_ORDER:
            e = weekly_sport[wk].get(sport)
            if e:
                sports_out[sport] = {
                    "sessions": e["sessions"],
                    "minutes": safe_round(e["minutes"]),
                    "distanceKm": safe_round(e["distanceKm"], 1),
                    "calories": safe_round(e["calories"]),
                }
        weekly_by_sport_out.append({"week": wk, "sports": sports_out})

    # -------------------------------------------------------------- goal (leaner)
    def week_totals(weeks_slice):
        total_cal, total_sessions, total_minutes = 0, 0, 0
        for wk in weeks_slice:
            for sport, e in weekly_sport[wk].items():
                total_cal += e["calories"]
                total_sessions += e["sessions"]
                total_minutes += e["minutes"]
        n = max(len(weeks_slice), 1)
        return total_cal / n, total_sessions / n, total_minutes / n

    recent_8 = sorted_weeks[-8:]
    prior_8 = sorted_weeks[-16:-8]

    def daily_steps_avg(keys_slice):
        vals = [
            (daily[k].get("movement") or {}).get("steps", {}).get("value")
            for k in keys_slice
            if k in daily
        ]
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else None

    def week_dates(wk_label):
        start = datetime.strptime(wk_label, "%Y-%m-%d").date()
        return [week_label_date(start + timedelta(days=i)) for i in range(7)]

    def week_label_date(d):
        return d.strftime("%Y-%m-%d")

    recent_day_keys = [d for wk in recent_8 for d in week_dates(wk) if d in daily]
    prior_day_keys = [d for wk in prior_8 for d in week_dates(wk) if d in daily]

    recent_cal, recent_sessions, recent_minutes = week_totals(recent_8)
    prior_cal, prior_sessions, prior_minutes = week_totals(prior_8) if prior_8 else (None, None, None)
    recent_steps = daily_steps_avg(recent_day_keys)
    prior_steps = daily_steps_avg(prior_day_keys)

    def pct_change(new, old):
        if not old:
            return None
        return safe_round(100 * (new - old) / old)

    goal = {
        "type": "leaner",
        "recentActiveCaloriesPerWeek": safe_round(recent_cal),
        "priorActiveCaloriesPerWeek": safe_round(prior_cal) if prior_cal is not None else None,
        "caloriesPctChange": pct_change(recent_cal, prior_cal) if prior_cal else None,
        "recentSessionsPerWeek": safe_round(recent_sessions, 1),
        "priorSessionsPerWeek": safe_round(prior_sessions, 1) if prior_sessions is not None else None,
        "recentStepsPerDay": safe_round(recent_steps) if recent_steps else None,
        "priorStepsPerDay": safe_round(prior_steps) if prior_steps else None,
        "stepsPctChange": pct_change(recent_steps, prior_steps) if prior_steps else None,
    }

    # -------------------------------------------------------------- trends
    def week_of(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return week_label(iso_week_start(d))

    def weekly_avg(data_dict, extractor, max_weeks=104):
        buckets = defaultdict(list)
        for k, v in data_dict.items():
            val = extractor(v)
            if val is not None:
                buckets[week_of(k)].append(val)
        weeks = sorted(buckets.keys())[-max_weeks:]
        return weeks, [safe_round(statistics.mean(buckets[w]), 1) for w in weeks]

    load_buckets = defaultdict(list)
    for a in activities:
        start = a.get("startTimeLocal")
        tl = a.get("activityTrainingLoad")
        if start and tl is not None:
            load_buckets[week_of(start[:10])].append(tl)
    load_weeks = sorted(load_buckets.keys())[-104:]
    training_load = [safe_round(sum(load_buckets[w])) for w in load_weeks]

    rhr_weeks, rhr_vals = weekly_avg(daily, lambda v: (v.get("heartRate") or {}).get("restingValue"))
    hrv_weeks, hrv_vals = weekly_avg(hrv, lambda v: v.get("lastNightAvg"))
    sleep_weeks, sleep_vals = weekly_avg(sleep, lambda v: (v.get("sleepTimeSeconds") or 0) / 3600)
    sleep_score_weeks, sleep_score_vals = weekly_avg(
        sleep, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value")
    )
    steps_weeks, steps_vals = weekly_avg(daily, lambda v: (v.get("movement") or {}).get("steps", {}).get("value"))
    active_cal_weeks, active_cal_vals = weekly_avg(daily, lambda v: (v.get("calories") or {}).get("burnedActive"))
    stress_weeks, stress_vals = weekly_avg(daily, lambda v: (v.get("stress") or {}).get("avgLevel"))

    # align all trend series onto the union of weeks present in training load / rhr (use rhr as backbone, it's most complete)
    trends = {
        "trainingLoad": {"weeks": load_weeks, "values": training_load},
        "restingHR": {"weeks": rhr_weeks, "values": rhr_vals},
        "hrv": {"weeks": hrv_weeks, "values": hrv_vals},
        "sleepHours": {"weeks": sleep_weeks, "values": sleep_vals},
        "sleepScore": {"weeks": sleep_score_weeks, "values": sleep_score_vals},
        "steps": {"weeks": steps_weeks, "values": steps_vals},
        "activeCalories": {"weeks": active_cal_weeks, "values": active_cal_vals},
        "stress": {"weeks": stress_weeks, "values": stress_vals},
    }

    # -------------------------------------------------------------- records
    records = {}

    def best_activity(predicate_key, sport_filter=None, pick_max=True):
        candidates = [
            a for a in activities
            if a.get(predicate_key) is not None
            and (sport_filter is None or sport_for((a.get("activityType") or {}).get("typeKey", "")) == sport_filter)
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda a: a[predicate_key]) if pick_max else min(candidates, key=lambda a: a[predicate_key])
        return best

    # cycling in this dataset is all indoor (distance always 0), so measure rides by time instead
    cycling_activities = [a for a in activities if sport_for((a.get("activityType") or {}).get("typeKey", "")) == "Cycling"]
    any_ride_distance = any((a.get("distance") or 0) > 0 for a in cycling_activities)
    longest_ride = best_activity("distance" if any_ride_distance else "duration", sport_filter="Cycling")
    longest_run = best_activity("distance", sport_filter="Running")
    longest_strength = best_activity("duration", sport_filter="Strength")
    highest_load_activity = best_activity("activityTrainingLoad")

    def activity_record(a, value_key, unit, convert=lambda v: v):
        if not a:
            return None
        return {
            "value": convert(a[value_key]),
            "unit": unit,
            "date": (a.get("startTimeLocal") or "")[:10],
            "name": a.get("activityName"),
        }

    if any_ride_distance:
        records["longestRide"] = activity_record(longest_ride, "distance", "km", lambda v: safe_round(v * KM_PER_METER, 1))
    else:
        records["longestRide"] = activity_record(longest_ride, "duration", "min", lambda v: safe_round(v / 60))
    records["longestRun"] = activity_record(longest_run, "distance", "km", lambda v: safe_round(v * KM_PER_METER, 1))
    records["longestStrength"] = activity_record(longest_strength, "duration", "min", lambda v: safe_round(v / 60))
    records["highestTrainingLoad"] = activity_record(highest_load_activity, "activityTrainingLoad", "load", lambda v: safe_round(v))

    if daily_keys:
        best_steps_day = max(daily_keys, key=lambda k: (daily[k].get("movement") or {}).get("steps", {}).get("value") or 0)
        best_cal_day = max(daily_keys, key=lambda k: (daily[k].get("calories") or {}).get("burnedTotal") or 0)
        records["mostSteps"] = {
            "value": safe_round((daily[best_steps_day].get("movement") or {}).get("steps", {}).get("value")),
            "date": best_steps_day,
        }
        records["mostCalories"] = {
            "value": safe_round((daily[best_cal_day].get("calories") or {}).get("burnedTotal")),
            "date": best_cal_day,
        }

    if sleep_keys:
        longest_sleep_day = max(sleep_keys, key=lambda k: sleep[k].get("sleepTimeSeconds") or 0)
        records["longestSleep"] = {
            "value": safe_round((sleep[longest_sleep_day].get("sleepTimeSeconds") or 0) / 3600, 1),
            "date": longest_sleep_day,
        }

    if hrv_keys:
        best_hrv_day = max(hrv_keys, key=lambda k: hrv[k].get("lastNightAvg") or 0)
        records["bestHRV"] = {
            "value": safe_round(hrv[best_hrv_day].get("lastNightAvg")),
            "date": best_hrv_day,
        }

    # -------------------------------------------------------------- report metrics (morning/evening/weekly coach)
    def window_avg(d, keys_sorted, extractor, days, exclude_last=True):
        keys = keys_sorted[:-1] if (exclude_last and keys_sorted) else keys_sorted
        keys = keys[-days:]
        vals = [v for v in (extractor(d[k]) for k in keys) if v is not None]
        return safe_round(statistics.mean(vals), 1) if vals else None

    def latest_of(d, keys_sorted, extractor):
        return extractor(d[keys_sorted[-1]]) if keys_sorted else None

    REPORT_METRIC_DEFS = {
        "sleepHours": (sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 1)),
        "deepSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("deepSleepSeconds") or 0) / 60)),
        "remSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("remSleepSeconds") or 0) / 60)),
        "lightSleepMin": (sleep, sleep_keys, lambda v: safe_round((v.get("lightSleepSeconds") or 0) / 60)),
        "sleepScore": (sleep, sleep_keys, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value")),
        "bodyBatteryCharged": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("chargedValue")),
        "bodyBatteryLatest": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("latestValue")),
        "bodyBatteryMin": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("minValue")),
        "bodyBatteryMax": (daily, daily_keys, lambda v: (v.get("bodyBattery") or {}).get("maxValue")),
        "restingHR": (daily, daily_keys, lambda v: (v.get("heartRate") or {}).get("restingValue")),
        "hrv": (hrv, hrv_keys, lambda v: v.get("lastNightAvg")),
        "steps": (daily, daily_keys, lambda v: (v.get("movement") or {}).get("steps", {}).get("value")),
        "stress": (daily, daily_keys, lambda v: (v.get("stress") or {}).get("avgLevel")),
        "calories": (daily, daily_keys, lambda v: (v.get("calories") or {}).get("burnedTotal")),
        "activeCalories": (daily, daily_keys, lambda v: (v.get("calories") or {}).get("burnedActive")),
    }
    report_metrics = {}
    for rm_key, (rm_src, rm_keys, rm_extractor) in REPORT_METRIC_DEFS.items():
        report_metrics[rm_key] = {
            "today": latest_of(rm_src, rm_keys, rm_extractor),
            "avg7": window_avg(rm_src, rm_keys, rm_extractor, 7),
            "avg30": window_avg(rm_src, rm_keys, rm_extractor, 30),
        }

    # last ~5 weeks of per-day Garmin metrics, so the client can join them against
    # locally-logged training/food/budget data (which only lives in localStorage) to
    # find patterns for the weekly report.
    daily_history = []
    history_dates = sorted((set(daily_keys[-35:]) | set(sleep_keys[-35:]) | set(hrv_keys[-35:])))[-35:]
    for hk in history_dates:
        d_day = daily.get(hk, {})
        s_day = sleep.get(hk, {})
        h_day = hrv.get(hk, {})
        bb = d_day.get("bodyBattery") or {}
        daily_history.append({
            "date": hk,
            "weekday": datetime.strptime(hk, "%Y-%m-%d").date().weekday(),
            "sleepHours": safe_round((s_day.get("sleepTimeSeconds") or 0) / 3600, 1) if s_day else None,
            "deepSleepMin": safe_round((s_day.get("deepSleepSeconds") or 0) / 60) if s_day else None,
            "sleepScore": ((s_day.get("sleepScores") or {}).get("overall") or {}).get("value") if s_day else None,
            "bodyBatteryCharged": bb.get("chargedValue"),
            "bodyBatteryLatest": bb.get("latestValue"),
            "restingHR": (d_day.get("heartRate") or {}).get("restingValue") if d_day else None,
            "hrv": h_day.get("lastNightAvg") if h_day else None,
            "steps": (d_day.get("movement") or {}).get("steps", {}).get("value") if d_day else None,
            "stress": (d_day.get("stress") or {}).get("avgLevel") if d_day else None,
            "calories": (d_day.get("calories") or {}).get("burnedTotal") if d_day else None,
        })

    # -------------------------------------------------------------- training plan
    def trailing_baseline(d, keys_sorted, extractor, window=14):
        if not keys_sorted:
            return None, None
        latest_val = extractor(d[keys_sorted[-1]])
        prior_keys = keys_sorted[-(window + 1):-1]
        prior_vals = [v for v in (extractor(d[k]) for k in prior_keys) if v is not None]
        baseline = statistics.mean(prior_vals) if prior_vals else None
        return latest_val, baseline

    def activities_on(d):
        ds = d.isoformat()
        return [a for a in activities if (a.get("startTimeLocal") or "")[:10] == ds]

    def logged_activities_on(d):
        out = []
        for a in activities_on(d):
            tk = (a.get("activityType") or {}).get("typeKey", "")
            for bucket, keys in TYPE_KEYS_BY_BUCKET.items():
                if tk in keys:
                    out.append({
                        "type": bucket,
                        "sport": sport_for(tk),
                        "name": a.get("activityName"),
                        "minutes": safe_round((a.get("duration") or 0) / 60),
                        "distanceKm": safe_round((a.get("distance") or 0) * KM_PER_METER, 1) or None,
                        "avgHr": safe_round(a.get("averageHR")) if a.get("averageHR") else None,
                        "calories": safe_round(a.get("calories")) if a.get("calories") else None,
                        "activityId": a.get("activityId"),
                    })
                    break
        return out

    today = date.today()
    week_num = gs_week(today)
    prog_week = GS_PROG[week_num]

    hrv_latest, hrv_baseline = trailing_baseline(hrv, hrv_keys, lambda v: v.get("lastNightAvg"))
    hrv_status = hrv[hrv_keys[-1]].get("status") if hrv_keys else None
    rhr_latest, rhr_baseline = trailing_baseline(daily, daily_keys, lambda v: (v.get("heartRate") or {}).get("restingValue"))
    sleep_hours_latest, _ = trailing_baseline(sleep, sleep_keys, lambda v: safe_round((v.get("sleepTimeSeconds") or 0) / 3600, 1))
    sleep_score_latest, _ = trailing_baseline(sleep, sleep_keys, lambda v: ((v.get("sleepScores") or {}).get("overall") or {}).get("value"))
    stress_latest, _ = trailing_baseline(daily, daily_keys, lambda v: (v.get("stress") or {}).get("avgLevel"))

    readiness_score = 0
    reasons = []
    if hrv_status in ("LOW", "UNBALANCED"):
        readiness_score -= 2
        reasons.append(f"HRV er {'lav' if hrv_status == 'LOW' else 'ubalansert'} i natt ({hrv_latest} ms)")
    elif hrv_status == "BALANCED" and hrv_latest is not None:
        reasons.append(f"HRV er balansert i natt ({hrv_latest} ms)")

    if rhr_latest is not None and rhr_baseline is not None and rhr_latest - rhr_baseline >= 4:
        readiness_score -= 1
        reasons.append(f"Hvilepuls er høyere enn vanlig ({rhr_latest} vs. snitt {safe_round(rhr_baseline)})")

    if sleep_hours_latest is not None and sleep_hours_latest < 6:
        readiness_score -= 1
        reasons.append(f"Lite søvn i natt ({sleep_hours_latest} t)")
    elif sleep_score_latest is not None and sleep_score_latest < 60:
        readiness_score -= 1
        reasons.append(f"Lav søvnscore i natt ({safe_round(sleep_score_latest)})")

    if stress_latest is not None and stress_latest >= 50:
        readiness_score -= 1
        reasons.append(f"Høyt stressnivå siste døgn ({safe_round(stress_latest)})")

    if not reasons:
        reasons.append("Ingen tegn til ekstra belastning i dataene dine")

    readiness = "light" if readiness_score <= -2 else "caution" if readiness_score == -1 else "go"

    # ------------------------------------------------------- recovery / strain scores (Sonar-style)
    def sub_score(value, baseline, higher_is_better, swing):
        """0-100, where 50 = exactly at your personal baseline. swing is the fractional
        deviation from baseline that reaches 0 or 100 (e.g. 0.3 = 30% off baseline)."""
        if value is None or baseline is None or baseline == 0:
            return None
        diff = (value - baseline) / baseline
        if not higher_is_better:
            diff = -diff
        return max(0, min(100, round(50 + diff / swing * 50)))

    hrv_sub = sub_score(hrv_latest, hrv_baseline, higher_is_better=True, swing=0.3)
    rhr_sub = sub_score(rhr_latest, rhr_baseline, higher_is_better=False, swing=0.12)
    sleep_sub = round(sleep_score_latest) if sleep_score_latest is not None else None
    stress_sub = round(100 - stress_latest) if stress_latest is not None else None
    recovery_parts = [(v, w) for v, w in (
        (hrv_sub, 0.30), (rhr_sub, 0.20), (sleep_sub, 0.30), (stress_sub, 0.20),
    ) if v is not None]
    recovery_score = (
        round(sum(v * w for v, w in recovery_parts) / sum(w for _, w in recovery_parts))
        if recovery_parts else None
    )

    daily_load = defaultdict(float)
    for a in activities:
        start = a.get("startTimeLocal")
        tl = a.get("activityTrainingLoad")
        if start and tl is not None:
            daily_load[start.split("T")[0]] += tl
    today_load = daily_load.get(today.isoformat(), 0)
    load_window_start = (today - timedelta(days=90)).isoformat()
    recent_loads = [v for k, v in daily_load.items() if k >= load_window_start and v > 0]
    load_reference = max(recent_loads) if recent_loads else None
    if load_reference:
        strain_score = round(min(100, 100 * today_load / load_reference))
    else:
        strain_score = 0 if today_load == 0 else None

    week_start = iso_week_start(today)
    week_days_out = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        sess = session_for(d)
        week_days_out.append({
            "date": d.isoformat(),
            "weekday": WEEKDAY_LABELS_NO[i],
            "defaultKey": sess["key"],
            "sessionLabel": sess["label"],
            "sessionType": sess["type"],
            "isToday": d == today,
            "loggedActivities": logged_activities_on(d) if d <= today else [],
        })

    next_week_start = week_start + timedelta(days=7)
    next_week_days_out = []
    for i in range(7):
        d = next_week_start + timedelta(days=i)
        sess = session_for(d)
        next_week_days_out.append({
            "date": d.isoformat(),
            "weekday": WEEKDAY_LABELS_NO[i],
            "defaultKey": sess["key"],
            "sessionLabel": sess["label"],
            "sessionType": sess["type"],
            "isToday": False,
            "loggedActivities": [],
        })
    next_week_num = gs_week(next_week_start)
    next_prog_week = GS_PROG[next_week_num]

    program = {
        "currentWeek": week_num,
        "weekFocus": prog_week["focus"],
        "weekSetsNote": prog_week["sets"],
        "weekCycleNote": prog_week["cycle"],
        "weekIsDeload": bool(prog_week.get("deload")),
        "today": {
            "date": today.isoformat(),
            "readiness": readiness,
            "reasons": reasons,
            "recoveryScore": recovery_score,
            "strainScore": strain_score,
        },
        "week": week_days_out,
        "nextWeek": next_week_days_out,
        "nextWeekFocus": next_prog_week["focus"],
        "nextWeekIsDeload": bool(next_prog_week.get("deload")),
    }

    # ---------------------------------------------------- training history (for points)
    # Default plan only (ignores swap overrides, which live client-side) so points
    # reflect the program as prescribed, not whatever was last picked in the dropdown.
    training_history = []
    d = GS_START
    while d <= today:
        sess = session_for(d)
        logged = logged_activities_on(d)
        steps_goal = ((daily.get(d.isoformat()) or {}).get("movement") or {}).get("steps", {})
        training_history.append({
            "date": d.isoformat(),
            "sessionType": sess["type"],
            "loggedTypes": sorted({a["type"] for a in logged}),
            "stepGoalMet": bool(steps_goal.get("value") and steps_goal.get("goal") and steps_goal["value"] >= steps_goal["goal"]),
        })
        d += timedelta(days=1)

    dataset = {
        "meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "dateRange": [min_date, max_date],
            "units": "km",
            "totalActivities": len(activities),
        },
        "topStats": top_stats,
        "reportMetrics": report_metrics,
        "dailyHistory": daily_history,
        "goal": goal,
        "program": program,
        "sessionCatalog": SESSION_CATALOG,
        "stabilityExercises": STABILITY_EXERCISES,
        "stabilityLockedLevels": STABILITY_LOCKED_LEVELS,
        "legDayWarmup": LEG_DAY_WARMUP,
        "gluteExerciseDetails": GLUTE_EXERCISE_DETAILS,
        "kneePauseNote": KNEE_PAUSE_NOTE,
        "kneeResumeCriteria": KNEE_RESUME_CRITERIA,
        "kneePainRule": KNEE_PAIN_RULE,
        "gluteTechniqueCues": GLUTE_TECHNIQUE_CUES,
        "dailyRoutineItems": DAILY_ROUTINE_ITEMS,
        "garminWeight": garmin_weight,
        "nutritionPlan": NUTRITION_PLAN,
        "ingredientCatalog": INGREDIENT_CATALOG,
        "weeklyBySport": weekly_by_sport_out,
        "trends": trends,
        "records": records,
        "sportColors": SPORT_COLORS,
        "sportOrder": SPORT_ORDER,
        "budgetDefaults": BUDGET_DEFAULTS,
        "dogFund": DOG_FUND,
        "vo2Max": parse_vo2max(),
        "activeCalGoalDefault": ACTIVE_CAL_GOAL_DEFAULT,
        "pointsConfig": POINTS_CONFIG,
        "trainingHistory": training_history,
        "programStart": GS_START.isoformat(),
    }

    html = render_html(dataset)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH}")


def render_html(dataset):
    data_json = json.dumps(dataset)
    return TEMPLATE.replace("__DASHBOARD_DATA__", data_json)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Katrine 2027</title>
<link rel="icon" href="icons/favicon-32.png" sizes="32x32">
<link rel="icon" href="icons/favicon-16.png" sizes="16x16">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#7a1f3d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Katrine 2027">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #fff6f8;
    --card: #ffffff;
    --ink: #3d1d29;
    --muted: #8a6472;
    --line: #f0d5de;
    --accent: #7a1f3d;
    --accent2: #a46cc0;
    --accent3: #e8a3b6;
    --shadow: 0 2px 10px rgba(122, 31, 61, 0.07);
  }
  * { box-sizing: border-box; }
  html { -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0;
    font-family: Nunito, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--ink);
    padding: 0 0 90px;
    overflow-x: hidden;
  }
  button, .btn, a { touch-action: manipulation; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 0 20px; }
  h1, h2, h3 { font-family: "Playfair Display", serif; }

  header.hero {
    background: linear-gradient(135deg, #7a1f3d 0%, #a8406a 100%);
    color: #fff;
    padding: calc(24px + env(safe-area-inset-top)) 22px 28px;
  }
  header.hero .wrap { display: flex; flex-direction: column; gap: 6px; }
  header.hero .hero-greeting { font-family: "Playfair Display", serif; font-weight: 700; font-size: 30px; letter-spacing: .01em; }
  header.hero .hero-datetime { color: #f2ccda; font-size: 13px; font-weight: 500; letter-spacing: .02em; }
  .hero-status-strip { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
  .hss-chip { display: flex; flex-direction: column; gap: 7px; padding: 0 18px; }
  .hss-chip:not(:first-child) { border-left: 1px solid rgba(255, 255, 255, .18); }
  .hss-chip:first-child { padding-left: 0; }
  .hss-main { font-size: 14.5px; font-weight: 700; color: #fff; white-space: nowrap; letter-spacing: .01em; }
  .hss-spark { width: 48px; height: 14px; display: block; color: #f3b9cc; opacity: .8; }

  .goal-row {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin: 10px 0 24px;
  }
  .goal-chip {
    background: #fff0f4;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 13px;
    color: var(--muted);
  }
  .goal-chip b { font-size: 16px; display: block; color: var(--ink); }
  .goal-chip .delta-up { color: #2f8a4e; }
  .goal-chip .delta-down { color: #c0392b; }

  .plan-card {
    background: var(--card);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 22px;
    border-left: 5px solid var(--accent);
    margin-top: 16px;
  }
  .plan-card.caution { border-left-color: #d9a441; }
  .plan-card.light { border-left-color: var(--accent3); }
  .plan-card .plan-eyebrow { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
  .plan-card h3 { margin: 0; font-size: 20px; }
  .plan-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 4px 0 10px; }
  select.swap {
    font-family: Nunito, -apple-system, sans-serif;
    font-size: 12px;
    color: var(--ink);
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 6px 12px;
  }
  .week-day select.swap { margin-top: 8px; width: 100%; font-size: 11px; padding: 4px 4px; border-radius: 10px; }
  .plan-card .exercises { margin-top: 14px; font-size: 13px; }
  .plan-card .exercises > .exercise-row { padding: 8px 0; border-top: 1px solid var(--line); }
  .plan-card .exercises .exercise-name { padding: 0 0 6px; }
  .plan-card .exercises .exercise-suggestion { font-size: 11px; color: var(--muted); padding: 0 0 8px; }
  .plan-card .exercises .glute-tip-toggle { margin: 0 0 8px; font-size: 11px; padding: 5px 10px; min-height: 0; }
  .plan-card .exercises .glute-tip-box {
    background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 12px; margin: 0 0 10px; font-size: 12px; line-height: 1.5; color: var(--ink);
  }
  .plan-card .exercises .glute-tip-box ul { margin: 2px 0 0; padding-left: 18px; }
  .plan-card .exercises .set-log-form { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .plan-card .exercises .set-log-form input { width: 70px; padding: 5px 8px; font-size: 12px; border: 1px solid var(--line); border-radius: 8px; font-family: Nunito, sans-serif; }
  .plan-card .exercises .set-log-today { margin-top: 6px; font-size: 11px; color: var(--muted); display: flex; gap: 6px; flex-wrap: wrap; }
  .plan-card .exercises .set-chip { background: var(--accent3); border-radius: 10px; padding: 2px 8px; display: inline-flex; align-items: center; gap: 4px; }
  .plan-card .exercises .set-chip-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 11px; padding: 0; line-height: 1; }

  .stability-exercise { background: var(--card); border-radius: 14px; box-shadow: var(--shadow); padding: 14px 16px; margin-bottom: 10px; }
  .stability-exercise .exercise-name { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
  .stability-setsreps { font-size: 12px; color: var(--muted); font-weight: 400; margin-left: 6px; }
  .stability-detail { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); font-size: 13px; }
  .stability-detail-block { margin-top: 10px; }
  .stability-detail-block b { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); margin-bottom: 4px; }
  .stability-detail-block ol, .stability-detail-block ul { margin: 0; padding-left: 18px; }
  .stability-detail-block li { margin-bottom: 3px; }
  .stability-illustration { display: flex; justify-content: center; background: var(--bg); border-radius: 10px; padding: 10px; }
  .stability-svg { width: 100%; max-width: 220px; height: auto; }
  .stability-fig { stroke: var(--ink); stroke-width: 5; stroke-linecap: round; fill: none; }
  .stability-fig-accent { stroke: var(--accent); stroke-width: 4; stroke-linecap: round; fill: none; }
  .stability-ground { stroke: var(--line); stroke-width: 3; }
  .stability-dashed { stroke: var(--accent2); stroke-width: 2; stroke-dasharray: 4 4; fill: none; }
  .stability-log-form { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-top: 10px; }
  .stability-log-form input, .stability-log-form select { font-family: inherit; font-size: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; background: #fff; min-width: 0; }
  .stability-weight, .stability-reps { width: 100px; }
  .stability-technique-check { font-size: 12px; display: inline-flex; align-items: center; gap: 4px; }
  .stability-locked-card { opacity: .6; margin-bottom: 10px; }
  .stability-locked-list { margin: 0; padding-left: 18px; font-size: 13px; color: var(--muted); }
  .pr-row { display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--line); font-size: 13px; }
  .pr-row:first-child { border-top: none; }
  .pr-row .pr-ex { color: var(--muted); flex: 1; margin-right: 10px; }
  .pr-row b { white-space: nowrap; }
  .rest-timer { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  .rest-timer .rt-display { font-family: "Playfair Display", serif; font-size: 32px; font-weight: 700; min-width: 80px; }
  .rest-timer .rt-presets { display: flex; gap: 6px; flex-wrap: wrap; }
  .rt-presets { display: flex; gap: 6px; flex-wrap: wrap; }
  .rest-pref-select { font-size: 11px; padding: 2px 4px; border-radius: 6px; border: 1px solid var(--line); font-family: Nunito, sans-serif; color: var(--muted); }
  .rest-bubble {
    display: none; position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%);
    background: var(--ink); color: #fff; border-radius: 999px; padding: 10px 18px;
    align-items: center; gap: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); z-index: 500;
  }
  .rest-bubble.active { display: flex; }
  .rest-bubble .rt-bubble-label { font-size: 12px; opacity: 0.85; max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rest-bubble .rt-bubble-display { font-family: "Playfair Display", serif; font-size: 22px; font-weight: 700; min-width: 32px; text-align: center; }
  .rest-bubble .rt-bubble-actions { display: flex; gap: 6px; }
  .rest-bubble button { background: rgba(255,255,255,0.15); color: #fff; border: none; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-family: Nunito, sans-serif; cursor: pointer; }
  .confetti-container { position: fixed; inset: 0; pointer-events: none; z-index: 999; overflow: hidden; }
  .confetti-piece { position: absolute; top: -10px; width: 8px; height: 14px; opacity: 0.9; animation: confetti-fall 1.8s ease-in forwards; }
  @keyframes confetti-fall { to { transform: translateY(100vh) rotate(360deg); opacity: 0; } }
  .plan-card .done-badge {
    display: inline-block;
    background: var(--accent);
    color: #fff;
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 20px;
    margin-top: 4px;
  }
  .plan-card .plan-reasons { list-style: none; padding: 0; margin: 14px 0 0; font-size: 13px; color: var(--muted); }
  .plan-card .plan-reasons li { padding: 3px 0; }
  .plan-card .plan-reasons li::before { content: "– "; color: var(--accent2); }

  .week-row { display: flex; gap: 8px; margin-top: 16px; overflow-x: auto; }
  .week-day {
    flex: 1;
    min-width: 92px;
    background: var(--card);
    border-radius: 12px;
    box-shadow: var(--shadow);
    padding: 10px 8px;
    text-align: center;
  }
  .week-day.today { outline: 2px solid var(--accent); outline-offset: -1px; }
  .week-day .wd { color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .04em; display: flex; align-items: center; justify-content: space-between; gap: 4px; }
  .week-day .sess { font-size: 12px; margin: 6px 0; min-height: 30px; color: var(--ink); }
  .week-day .mark { font-size: 15px; color: var(--accent); }
  .week-day .mark.missed { color: var(--muted); font-size: 13px; }
  .week-day-handle {
    cursor: grab; color: var(--muted); font-size: 13px; line-height: 1; padding: 2px 4px;
    touch-action: none; user-select: none; -webkit-user-select: none;
  }
  .week-day.dragging { opacity: 0.4; }
  .week-day.drop-target { outline: 2px dashed var(--accent2); outline-offset: -1px; }

  .missed-day-box {
    background: #fff0f4; border: 1px solid var(--line); border-radius: 12px;
    padding: 12px 14px; margin: 10px 0 14px; font-size: 13px; color: var(--ink);
  }
  .missed-day-actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

  .kcal-row { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
  .kcal-chip {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 12px;
    color: var(--muted);
  }
  .kcal-chip b { color: var(--ink); font-size: 14px; display: block; }
  .kcal-chip.good { border-left: 4px solid #7bd88f; }
  .kcal-chip.warn { border-left: 4px solid #f6c667; }
  .kcal-chip.over { border-left: 4px solid #e37878; }

  .kosthold-meal-card { margin-top: 14px; }
  .kosthold-meal-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 0 0 8px; }
  .kosthold-meal-card-head h4 { font-size: 14px; margin: 0; color: var(--ink); }
  .meal-option {
    background: var(--card);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 14px 16px;
    margin-bottom: 8px;
  }
  .meal-option .meal-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
  .meal-option .meal-head b { font-size: 14px; margin-right: auto; }
  .meal-option .meal-macro { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .meal-fav-btn {
    background: none; border: none; cursor: pointer; font-size: 15px; line-height: 1;
    padding: 0; color: var(--muted);
  }
  .meal-fav-btn.active { color: #d9a441; }
  .meal-row-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
  .meal-items { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px 10px; }
  .meal-item-text, .meal-item-ing { min-width: 0; max-width: 100%; }
  .meal-item-ing.meal-item-overridden { color: var(--accent); font-weight: 700; }
  .meal-ing-swap-btn, .meal-ing-reset-btn {
    background: none; border: none; color: var(--accent2); cursor: pointer;
    font-size: 11px; padding: 0; margin-left: 3px; text-decoration: underline;
  }
  .meal-option-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 11px; padding: 0; margin-left: 6px; }
  .meal-add-form { margin-top: 2px; }
  .ing-swap-form {
    background: var(--bg); border: 1px solid var(--line); border-radius: 10px;
    padding: 10px; margin-top: 6px; display: flex; flex-direction: column; gap: 8px;
  }
  .ing-swap-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .ing-swap-row select { font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; background: #fff; }
  .ing-swap-row input { width: 64px; font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; }
  .ing-new-form { display: flex; gap: 6px; flex-wrap: wrap; }
  .ing-new-form input { font-family: inherit; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; padding: 5px 6px; }
  .ing-new-form input[type="text"] { width: 140px; }
  .ing-new-form input[type="number"] { width: 90px; }
  .nutrition-note { font-size: 11px; color: var(--muted); margin-top: 14px; font-style: italic; }
  .meal-planned-badge { font-size: 11px; color: var(--accent); font-weight: 700; }

  .plan-meal-day {
    background: var(--card); border-radius: 14px; box-shadow: var(--shadow);
    padding: 12px 16px; margin-bottom: 8px;
  }
  .plan-meal-day .wd { color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: .04em; margin-bottom: 8px; }
  .plan-generated-line { font-size: 13px; color: var(--ink); margin-top: 4px; line-height: 1.4; white-space: normal; }
  .plan-meal-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 10px; }
  .plan-meal-field { display: flex; flex-direction: column; gap: 3px; font-size: 11px; color: var(--muted); min-width: 0; }
  .plan-meal-field select, .plan-next-swap {
    font-family: inherit; font-size: 12.5px; border: 1px solid var(--line); border-radius: 8px;
    padding: 6px 6px; background: #fff; color: var(--ink);
    width: 100%; min-width: 0; box-sizing: border-box;
  }
  .mealprep-dept { margin-bottom: 10px; }
  .mealprep-dept-label { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin-bottom: 4px; }
  .mealprep-ing-check { display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px; margin: 0 10px 6px 0; }
  .mealprep-suggestion {
    background: var(--bg); border: 1px solid var(--line); border-radius: 12px;
    padding: 12px 14px; margin-top: 10px;
  }
  .meal-item-ing.mealprep-missing { color: var(--muted); font-style: italic; }
  .mealprep-days { display: flex; flex-wrap: wrap; gap: 4px 10px; margin: 8px 0; }
  .mealprep-day-check { font-size: 12px; display: inline-flex; align-items: center; gap: 3px; }

  .report-tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
  .report-tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .report-card { line-height: 1.6; }
  .report-card:empty { display: none; }
  .report-card h3 { margin: 20px 0 8px; font-size: 17px; }
  .report-card .report-section:first-child h3 { margin-top: 0; }
  .report-card .report-section { margin-bottom: 20px; }
  .report-card .report-section:last-child { margin-bottom: 0; }
  .report-card p { font-size: 13.5px; margin: 0 0 10px; }
  .report-card ul { margin: 0 0 6px; padding-left: 20px; }
  .report-card li { margin-bottom: 7px; font-size: 13.5px; }
  .report-card .report-highlight { background: var(--bg); border-radius: 10px; padding: 10px 14px; font-size: 13px; margin: 10px 0; }
  .report-card .report-empty { font-size: 13px; color: var(--muted); }
  .report-card .report-title { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 2px; }


  section { margin-top: 36px; }
  section h2 {
    font-size: 18px;
    margin: 0 0 4px;
  }
  section .section-sub { font-size: 13px; color: var(--muted); margin-bottom: 16px; }

  .card {
    background: var(--card);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 20px;
  }

  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px; color: var(--muted); }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
  .sport-legend-btn {
    display: inline-flex; align-items: center; gap: 6px; background: none; border: none;
    font-family: Nunito, sans-serif; font-size: 12px; color: var(--muted); cursor: pointer; padding: 2px 0;
  }
  .sport-legend-btn i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
  .sport-legend-btn.off { opacity: .4; text-decoration: line-through; }

  .tooltip {
    position: absolute;
    pointer-events: none;
    background: #7a1f3d;
    color: #fff;
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 8px;
    transform: translate(-50%, -115%);
    white-space: nowrap;
    opacity: 0;
    transition: opacity .1s;
    z-index: 10;
  }
  .chart-wrap { position: relative; }
  .chart-wrap svg { display: block; width: 100%; height: auto; }

  .records-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  .record-card {
    background: var(--card);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 16px;
  }
  .record-card .label { font-size: 12px; color: var(--muted); }
  .record-card .value { font-size: 22px; font-weight: 700; margin: 4px 0 2px; }
  .record-card .date { font-size: 11px; color: var(--muted); }

  .trend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

  footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 40px; }
  #footer-settings-link {
    background: none; border: 1px solid var(--line); color: var(--muted); border-radius: 20px;
    padding: 8px 16px; font-size: 12.5px; font-family: Nunito, sans-serif; cursor: pointer;
  }
  #footer-generated { margin-top: 10px; }
  .settings-card { margin: 24px 0 0; }
  .settings-toggle-row { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-top: 10px; cursor: pointer; }
  .sync-card { margin: 16px 0 0; }
  .backup-card { margin: 16px 0 0; }
  .backup-actions { display: flex; gap: 8px; flex-wrap: wrap; }

  /* ---- fremgang / points / logging ---- */
  .snapshot-row { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 14px; }
  .snapshot-chip {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 8px 16px; font-size: 12px; color: var(--muted); flex: 1; min-width: 130px;
  }
  .snapshot-chip b { color: var(--ink); font-size: 16px; display: block; }

  .level-card { margin-top: 14px; }
  .level-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .level-head .level-name { font-family: "Playfair Display", serif; font-size: 20px; font-weight: 700; }
  .level-head .level-pts { font-size: 12px; color: var(--muted); }
  .level-bar { height: 10px; border-radius: 6px; background: var(--line); margin-top: 10px; overflow: hidden; }
  .level-bar > div { height: 100%; background: linear-gradient(90deg, var(--accent2), var(--accent)); border-radius: 6px; transition: width .3s; }
  .level-reward { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .level-explainer { font-size: 11px; color: var(--muted); margin-top: 10px; line-height: 1.6; border-top: 1px solid var(--line); padding-top: 8px; }
  .level-explainer span { display: inline-block; margin-right: 10px; white-space: nowrap; }

  .celebrate-banner {
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    color: #fff; border-radius: 14px; padding: 14px 18px; margin-top: 14px;
    font-size: 14px; font-weight: 700; box-shadow: var(--shadow);
  }

  .log-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px; }
  .log-form { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
  .log-form input, .log-form select {
    font-family: Nunito, sans-serif; font-size: 14px; border: 1px solid var(--line);
    border-radius: 10px; padding: 11px 12px; background: var(--bg); color: var(--ink); min-height: 44px;
  }
  .log-form input[type="number"] { width: 100px; }
  .log-form input[type="date"] { width: 150px; }
  .log-form input[type="text"] { flex: 1; min-width: 120px; }
  .mvd-settings-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  .mvd-settings-field input { margin-top: 0; }
  .btn {
    font-family: Nunito, sans-serif; font-size: 14px; font-weight: 700; color: #fff;
    background: var(--accent); border: none; border-radius: 10px; padding: 12px 20px;
    min-height: 44px; cursor: pointer;
  }
  .btn.secondary { background: var(--accent3); color: var(--ink); }
  .btn.ghost { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn.small { padding: 6px 12px; font-size: 12px; min-height: 0; }
  .btn-big { width: 100%; padding: 15px; font-size: 16px; margin-top: 2px; }
  .log-list { list-style: none; padding: 0; margin: 10px 0 0; font-size: 13px; }
  .log-list li { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-top: 1px solid var(--line); color: var(--muted); }
  .log-list li b { color: var(--ink); }
  .weight-source-tag {
    font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.02em;
    color: var(--accent); border: 1px solid var(--accent); border-radius: 8px; padding: 1px 5px;
  }
  .craving-comment-input {
    flex: 1; min-width: 0; width: 100%; box-sizing: border-box;
    font-family: inherit; font-size: 13px; border: none; background: transparent; color: var(--muted);
    padding: 2px 0;
  }
  .craving-comment-input:focus { color: var(--ink); outline: none; border-bottom: 1px solid var(--line); }
  .log-remove-btn {
    background: none; border: none; color: var(--muted); cursor: pointer; font-size: 14px;
    min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center;
    margin: -11px -10px -11px 0; flex-shrink: 0;
  }
  .log-delta { font-size: 11px; }
  .log-delta.down { color: #2f8a4e; }
  .log-delta.up { color: var(--accent); }
  .weight-trend-box { font-size: 13px; color: var(--muted); margin: 2px 0 10px; }
  .weight-trend-box b { color: var(--ink); }
  .buy-check-box { font-size: 13px; color: var(--muted); margin: 10px 0 0; }
  .buy-check-box b { color: var(--ink); }
  .buy-check-settings { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
  .buy-check-settings label { font-size: 12px; color: var(--muted); display: flex; flex-direction: column; gap: 3px; }
  .buy-check-settings input { width: 100px; padding: 5px 8px; font-size: 13px; border: 1px solid var(--line); border-radius: 8px; font-family: Nunito, sans-serif; }
  .buy-growth-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
  .buy-growth-chip {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 8px 16px; font-size: 12px; color: var(--muted); flex: 1; min-width: 100px;
  }
  .buy-growth-chip b { color: var(--ink); font-size: 15px; display: block; }
  .forgotten-savings-card { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .forgotten-savings-card .fs-info { font-size: 13px; color: var(--muted); }
  .forgotten-savings-card .fs-amount { font-family: "Playfair Display", serif; font-size: 20px; font-weight: 700; color: var(--ink); }
  .forgotten-savings-card.pulse .fs-amount { animation: fs-pulse 0.6s ease; }
  @keyframes fs-pulse { 0% { transform: scale(1); color: var(--ink); } 40% { transform: scale(1.25); color: #2e8b57; } 100% { transform: scale(1); color: var(--ink); } }
  .save-presets { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .save-presets-label { font-size: 12px; color: var(--muted); }
  .extras-presets { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; flex-wrap: wrap; }

  /* ---- handleliste ---- */
  .shop-quickadd { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .shop-list { list-style: none; padding: 0; margin: 14px 0 0; }
  .shop-list li {
    display: flex; align-items: center; gap: 10px; padding: 8px 4px;
    border-top: 1px solid var(--line); font-size: 14px;
  }
  .shop-list li.checked span { text-decoration: line-through; color: var(--muted); }
  .shop-list li button { margin-left: auto; background: none; border: none; color: var(--muted); cursor: pointer; font-size: 14px; }
  .shop-list li.shop-dept-head {
    border-top: none; padding: 14px 4px 4px; font-size: 11px; font-weight: 700; letter-spacing: .03em;
    text-transform: uppercase; color: var(--accent);
  }
  .shop-list li.shop-dept-head:first-child { padding-top: 4px; }
  .meal-picker-group { margin-bottom: 14px; }
  .meal-picker-group-title { font-weight: 700; font-size: 13px; margin-bottom: 6px; }
  .meal-picker-opt { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13.5px; }
  .quicklog-drawer .meal-picker-opt input[type="checkbox"] { width: auto; margin: 0; }

  /* ---- budsjett ---- */
  .month-nav { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
  .month-nav .btn { padding: 4px 12px; }
  .month-nav .month-label { font-weight: 700; font-size: 15px; min-width: 140px; text-align: center; }
  .budget-section-title { margin: 0 0 12px; font-size: 14px; color: var(--accent); display: flex; align-items: center; gap: 6px; }
  .budget-cat-list { display: flex; flex-direction: column; gap: 14px; }
  .cat-row { margin-top: 0; }
  .cat-row .cat-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); }
  .cat-row .cat-head b { color: var(--ink); }
  .cat-bar { height: 8px; border-radius: 5px; background: var(--line); margin-top: 4px; overflow: hidden; }
  .cat-bar > div { height: 100%; border-radius: 5px; background: var(--accent2); }
  .cat-bar > div.good { background: #7bd88f; }
  .cat-bar > div.warn { background: #f6c667; }
  .cat-bar > div.over { background: #e37878; }
  .cat-grace { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .cat-row input.cap-edit {
    width: 64px; font-size: 11px; border: 1px solid var(--line); border-radius: 6px;
    padding: 2px 4px; background: var(--bg); color: var(--muted); text-align: right;
  }
  .fund-card { background: linear-gradient(135deg, #fff0f4, #fde6ee); border-radius: 16px; padding: 18px; margin-top: 14px; }
  .fund-card .fund-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }
  .fund-card .fund-amount { font-size: 24px; font-weight: 700; font-family: "Playfair Display", serif; }
  .fund-card .fund-eta { font-size: 12px; color: var(--muted); margin-top: 6px; }
  .fund-bar { height: 12px; border-radius: 7px; background: #fff; margin-top: 10px; overflow: hidden; }
  .fund-bar > div { height: 100%; border-radius: 7px; background: linear-gradient(90deg, var(--accent2), var(--accent)); }
  .budget-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 16px; }

  /* ---- fremgang (long-term trends/goals) ---- */
  .fremgang-section { margin: 36px 0; }
  .fremgang-section:first-of-type { margin-top: 18px; }
  .fremgang-section h3 { margin: 0 0 4px; font-size: 16px; }
  .fremgang-section .section-sub { margin-bottom: 14px; }
  .period-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .period-btn, .measure-select-btn {
    border: 1px solid var(--line); background: #fff; color: var(--ink);
    border-radius: 999px; padding: 6px 14px; font-size: 12.5px; font-family: inherit;
    cursor: pointer; transition: background .15s, color .15s, border-color .15s;
  }
  .period-btn.active, .measure-select-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .context-note {
    background: #fff0f4; border-radius: 10px; padding: 10px 14px;
    font-size: 13px; color: var(--ink); margin-top: 10px; line-height: 1.5;
  }
  .tooltip.ml { white-space: normal; text-align: left; line-height: 1.5; transform: translate(-50%, -108%); }
  .weight-goal-row { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
  .weight-goal-row input { width: 70px; border: 1px solid var(--line); border-radius: 8px; padding: 4px 6px; font-family: inherit; font-size: 13px; }
  .savings-goal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .savings-goal-card { background: #fff0f4; border-radius: 14px; padding: 16px; }
  .savings-goal-card .sg-label { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
  .savings-goal-card .sg-amount { font-size: 19px; font-weight: 700; font-family: "Playfair Display", serif; margin-top: 4px; }
  .savings-goal-card .sg-goal-row { display: flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; color: var(--muted); }
  .savings-goal-card .sg-goal-row input { width: 92px; border: 1px solid var(--line); border-radius: 8px; padding: 3px 6px; font-family: inherit; font-size: 12px; }
  .savings-goal-card .sg-eta { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .fund-summary-row { display: flex; gap: 22px; flex-wrap: wrap; margin-top: 14px; }
  .fund-summary-row .fs-item { font-size: 13px; }
  .fund-summary-row .fs-item b { display: block; font-size: 17px; font-family: "Playfair Display", serif; }
  .fund-summary-row .fs-item b.pos { color: #3f9a5a; }
  .fund-summary-row .fs-item b.neg { color: #c24545; }

  /* ---- tabs ---- */
  .tab-nav {
    /* Erstattet av bunn-navigasjonen (.quicklog-bar) - beholdt i DOM (showTab() leser
       fortsatt .active-state fra knappene her), men vises ikke lenger. */
    display: none;
  }
  .tab-nav button {
    flex: 0 0 auto;
    font-family: Nunito, sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: var(--muted);
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 13px 22px;
    min-height: 46px;
    cursor: pointer;
  }
  .tab-nav button.active { color: #fff; background: var(--accent); border-color: var(--accent); font-weight: 800; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  .quiet-actions-bottom {
    display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin: 40px 0 16px; padding-top: 16px;
    border-top: 1px solid var(--line);
  }
  .quiet-actions-bottom .support-btn {
    flex: 0 1 auto; margin: 0; font-size: 12px; padding: 7px 14px; min-height: 0;
    color: var(--muted); border-color: var(--line);
  }
  .support-picker-box {
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 12px; margin-top: 10px; display: flex; flex-direction: column; gap: 8px;
  }
  .support-picker-box button { text-align: left; }
  .overwhelm-box, .sickday-box {
    background: var(--card); border: 1px solid var(--line); border-radius: 14px;
    padding: 16px; margin-top: 10px; line-height: 1.6; font-size: 14px;
  }
  .sickday-box .log-form { margin: 10px 0; }
  .sickday-list { list-style: none; margin: 10px 0 0; padding: 0; }
  .sickday-list li {
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
    padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 13px;
  }
  .sickday-list button { flex: 0 0 auto; }
  .daily-routine-groups { display: flex; flex-direction: column; gap: 14px; }
  .daily-routine-group-label { font-size: 12px; font-weight: 800; color: var(--accent); text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 4px; }
  .daily-routine-item { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; font-size: 13px; cursor: pointer; }
  .daily-routine-item input[type="checkbox"] { margin-top: 3px; flex: 0 0 auto; }
  #plateau-card:empty { display: none; }
  #nutrition-coach-card:empty { display: none; }

  .badday-panel { display: none; max-width: 420px; margin: 24px auto; text-align: center; }
  body.badday-active header,
  body.badday-active .quicklog-bar,
  body.badday-active .wrap > *:not(.badday-panel) { display: none !important; }
  body.badday-active .badday-panel { display: block; }
  .badday-quickbtns { display: flex; flex-direction: column; gap: 12px; margin: 24px 0; }
  .badday-quickbtns > button { padding: 16px; font-size: 16px; }
  .badday-quickbtns #badday-trained-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
  .badday-expense-row { display: flex; gap: 8px; }
  .badday-expense-row input { flex: 1; min-width: 0; padding: 12px; font-size: 15px; border: 1px solid var(--line); border-radius: 10px; font-family: Nunito, sans-serif; box-sizing: border-box; }
  .badday-expense-row button { flex: 1; padding: 12px; font-size: 15px; }
  .badday-saved-msg { font-size: 12px; color: var(--muted); min-height: 16px; margin-top: 4px; }

  .freeday-panel { display: none; max-width: 420px; margin: 24px auto; text-align: left; }
  body.freeday-active header,
  body.freeday-active .quicklog-bar,
  body.freeday-active .wrap > *:not(.freeday-panel) { display: none !important; }
  body.freeday-active .freeday-panel { display: block; }
  .freeday-task-card {
    background: var(--card); border-radius: 14px; box-shadow: var(--shadow);
    padding: 20px; margin-top: 16px; text-align: center;
  }
  .freeday-task-name { font-family: "Playfair Display", serif; font-size: 17px; margin-bottom: 8px; }
  .freeday-microstep { font-size: 15px; color: var(--ink); margin-bottom: 4px; line-height: 1.5; }
  .freeday-actions { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
  .freeday-actions > button { padding: 14px; font-size: 15px; }
  .freeday-rest-list { margin-top: 10px; font-size: 13px; color: var(--muted); text-align: left; padding-left: 18px; }
  .mvd-box { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; text-align: left; }
  .mvd-title { font-family: "Playfair Display", serif; font-size: 17px; font-weight: 700; margin-bottom: 8px; }
  .mvd-list { list-style: none; margin: 0; padding: 0; font-size: 14px; }
  .mvd-list li { padding: 4px 0; color: var(--muted); }
  .mvd-list li.done { color: var(--ink); font-weight: 700; }
  .mvd-sub { font-weight: 400; color: var(--muted); font-size: 12px; }
  .mvd-note { font-size: 12.5px; color: var(--muted); margin-top: 8px; }
  .mvd-complete { font-size: 13px; color: #2f8a4e; font-weight: 700; margin-top: 8px; }

  /* ---- Hjem dashboard (light, mobile-first start page) ---- */
  .hjem-dash {
    --hj-bg: var(--bg); --hj-card: var(--card); --hj-card2: #fff0f4; --hj-ink: var(--ink);
    --hj-muted: var(--muted); --hj-accent: #f6c667; --hj-accent2: var(--accent2); --hj-line: var(--line);
    margin: 0 0 24px; font-family: Nunito, sans-serif;
  }
  .hjem-topbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
  .hjem-topbar .hjem-why { margin: 0; flex: 1; min-width: 0; }
  .hjem-greeting { font-family: "Playfair Display", serif; font-size: 19px; }
  .hjem-datetime { font-size: 12px; color: var(--hj-muted); margin-top: 2px; }
  .hjem-badday-toggle {
    background: var(--hj-card2); color: var(--hj-ink); border: 1px solid var(--hj-line);
    border-radius: 20px; padding: 6px 12px; font-size: 12px; cursor: pointer;
  }
  .hjem-why { font-size: 12px; color: var(--hj-muted); cursor: pointer; }
  .hjem-why.empty { font-style: italic; }
  .hjem-zone { margin-bottom: 18px; }
  .hjem-zone-title { font-size: 13px; color: var(--hj-muted); text-transform: uppercase; letter-spacing: .06em; margin: 0 0 8px; }
  .hjem-card {
    background: var(--hj-card); box-shadow: var(--shadow); border-radius: 14px;
    padding: 12px 14px; color: var(--hj-ink);
  }
  .hjem-card-title { font-size: 12px; color: var(--hj-muted); margin-bottom: 6px; }
  .hjem-topbar-btns { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .hjem-refresh-btn {
    background: var(--hj-card2); color: var(--hj-ink); border: 1px solid var(--hj-line);
    border-radius: 50%; width: 30px; height: 30px; font-size: 15px; line-height: 1; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }
  .hjem-refresh-btn.spinning { animation: hjem-spin .6s linear; }
  @keyframes hjem-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .hjem-section-1 .hjem-card { margin-bottom: 10px; }
  .hjem-section-1 .hjem-card:last-child { margin-bottom: 0; }
  .hjem-session { display: flex; flex-direction: column; gap: 12px; }
  .hs-top { display: flex; align-items: center; gap: 14px; }
  .hs-info { flex: 1; min-width: 0; }
  .hjem-session .hs-label { font-size: 15px; font-weight: 700; }
  .hjem-session .hs-sub { font-size: 12px; color: var(--hj-muted); margin-bottom: 6px; }
  .score-ring { position: relative; display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }
  .score-ring svg { display: block; }
  .score-ring-num { position: absolute; font-family: "Playfair Display", serif; font-weight: 700; line-height: 1; }
  .hs-score-block { display: flex; flex-direction: column; align-items: center; gap: 4px; }
  .hs-score-block .hs-score-label { font-size: 10px; color: var(--hj-muted); text-transform: uppercase; letter-spacing: .04em; }
  .hs-recovery-note { font-size: 12px; color: var(--hj-muted); line-height: 1.45; }
  .hs-secondary-scores { display: flex; flex-direction: column; gap: 10px; }
  .hs-mini-score { display: flex; align-items: flex-start; gap: 10px; }
  .hs-mini-score .hs-mini-label { font-size: 11px; color: var(--hj-muted); flex: 1; min-width: 0; padding-top: 3px; }
  .hs-mini-score .hs-mini-label b { display: block; font-size: 13px; color: var(--hj-ink); font-weight: 700; }
  .hs-mini-note { display: block; font-size: 10.5px; color: var(--hj-muted); margin-top: 2px; line-height: 1.3; }
  .rpe-picker { margin-top: 2px; }
  .rpe-buttons { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 5px; }
  .rpe-btn {
    width: 26px; height: 26px; border-radius: 8px; border: 1px solid var(--hj-line);
    background: var(--hj-card2); color: var(--hj-ink); font-family: Nunito, sans-serif;
    font-size: 12px; font-weight: 700; cursor: pointer; padding: 0;
  }
  .rpe-btn:active { background: var(--hj-accent); }
  .hjem-session .hs-status { font-size: 11px; padding: 3px 9px; border-radius: 12px; font-weight: 700; }
  .hjem-session .hs-status.notstarted { background: var(--hj-card2); color: var(--hj-muted); }
  .hjem-session .hs-status.inprogress { background: rgba(246,198,103,.18); color: #b8860b; }
  .hjem-session .hs-status.done { background: rgba(123,216,143,.16); color: #2f8a4e; }
  .hjem-session .hs-status.hs-status-tap { cursor: pointer; }
  .hs-activity-details {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: -4px 0 4px;
    background: var(--hj-card2); border-radius: 10px; padding: 10px 12px;
  }
  .hs-activity-details div { font-size: 11px; color: var(--hj-muted); }
  .hs-activity-details div b { display: block; font-size: 14px; color: var(--hj-ink); font-weight: 700; margin-top: 1px; }
  .hjem-session .hs-link {
    background: none; border: 1px solid var(--hj-line); color: var(--hj-ink);
    border-radius: 10px; padding: 6px 10px; font-size: 12px; cursor: pointer; font-family: Nunito, sans-serif;
  }
  .hjem-nutri-quick { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .hjem-nutri-quick .hnq-label { font-size: 12px; color: var(--hj-muted); }
  .hjem-nutri-quick .hnq-val { font-size: 17px; font-weight: 700; margin-top: 2px; }
  .hjem-nutri-quick .hnq-val.over { color: #b8860b; }
  .hjem-nutri-quick .hnq-macro { font-size: 11px; color: var(--hj-muted); margin-top: 2px; }
  .hjem-nutri-quick .hnq-macro.over { color: #b8860b; }
  .hjem-nutri-quick .hnq-balance { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--hj-line); font-size: 11px; color: var(--hj-muted); display: flex; flex-direction: column; gap: 2px; }
  .hjem-nutri-quick .hnq-balance-diff { font-size: 13px; font-weight: 700; color: #2f8a4e; }
  .hjem-nutri-quick .hnq-balance-diff.over { color: #b8860b; }
  .hjem-nutri-quick button {
    background: var(--hj-accent); color: var(--ink); border: none; border-radius: 10px;
    padding: 8px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif; white-space: nowrap;
  }
  .hjem-tx-list { list-style: none; margin: 0; padding: 0; font-size: 13px; max-height: 120px; overflow-y: auto; }
  .hjem-tx-list li { display: flex; justify-content: space-between; gap: 8px; padding: 5px 0; border-top: 1px solid var(--hj-line); }
  .hjem-tx-list li:first-child { border-top: none; }
  .hjem-tx-list .tx-name { color: var(--hj-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hjem-tx-empty { color: var(--hj-muted); }
  .hjem-tx-total { display: flex; justify-content: space-between; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--hj-line); font-weight: 700; font-size: 13px; }
  .hjem-body-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .hjem-body-group-label {
    grid-column: 1 / -1; font-size: 10.5px; color: var(--hj-muted); text-transform: uppercase;
    letter-spacing: .05em; margin: 10px 0 -2px;
  }
  .hjem-body-group-label:first-child { margin-top: 0; }
  .hjem-bigstat .hbs-label { font-size: 11px; color: var(--hj-muted); text-transform: uppercase; }
  .hjem-bigstat .hbs-num { font-size: 24px; font-weight: 700; margin: 2px 0 6px; font-family: "Playfair Display", serif; }
  .hjem-bigstat .hbs-bar { background: var(--hj-line); border-radius: 8px; height: 7px; overflow: hidden; }
  .hjem-bigstat .hbs-bar > div { background: var(--hj-accent); height: 100%; }
  .hjem-bigstat .hbs-bar > div.goalmet { background: #7bd88f; }
  .hjem-minirow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; grid-column: 1 / -1; }
  .hjem-minicard .label { font-size: 11px; color: var(--hj-muted); text-transform: uppercase; }
  .hjem-minicard .value { font-size: 15px; font-weight: 700; margin-top: 3px; display: flex; align-items: center; }
  .hjem-minicard .sub { font-size: 11px; color: var(--hj-muted); margin-top: 1px; min-height: 13px; }
  .stress-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; flex: 0 0 auto; }
  .stress-dot.green { background: #7bd88f; }
  .stress-dot.yellow { background: var(--hj-accent); }
  .stress-dot.red { background: #e37878; }
  .hjem-finance-row { margin-bottom: 10px; cursor: default; }
  .hjem-finance-row:last-child { margin-bottom: 0; }
  .hjem-finance-row .hf-label { font-size: 12px; color: var(--hj-muted); display: flex; justify-content: space-between; }
  .hjem-finance-row .hf-val { font-size: 15px; font-weight: 700; margin-top: 2px; }
  .hjem-finance-bar { background: var(--hj-line); border-radius: 8px; height: 8px; overflow: hidden; margin-top: 6px; }
  .hjem-finance-bar > div { background: var(--hj-accent); height: 100%; }
  .hjem-finance-bar > div.over { background: #e37878; }
  .hjem-finance-bar > div.savings { background: #2f8a4e; }
  .hjem-tx-nudge {
    display: block; width: 100%; margin-top: 8px; padding: 9px 12px; border: none; border-radius: 10px;
    background: var(--hj-card2); color: var(--hj-ink); font-family: Nunito, sans-serif; font-size: 12.5px;
    font-weight: 700; text-align: center; cursor: pointer;
  }
  .hjem-tx-nudge:active { background: var(--hj-accent); }
  .hjem-reminder-banner {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;
    background: rgba(246, 198, 103, 0.14); border: 1px solid var(--hj-accent); color: var(--hj-ink);
    border-radius: 12px; padding: 10px 12px; margin-bottom: 10px; font-size: 13px;
  }
  .hjem-reminder-banner button {
    background: var(--hj-accent); color: var(--ink); border: none; border-radius: 8px;
    padding: 6px 12px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif;
  }
  .hjem-reminder-banner button.hjem-badday-toggle { background: transparent; border: 1px solid var(--hj-line); }
  .hjem-main-grid { display: flex; flex-direction: column; gap: 18px; }
  @media (min-width: 900px) {
    .hjem-main-grid { display: grid; grid-template-columns: 1fr 300px; gap: 20px; align-items: start; }
  }
  .hjem-rail { position: relative; padding-left: 30px; }
  .hjem-rail::before {
    content: ""; position: absolute; left: 8px; top: 8px; bottom: 8px; width: 3px;
    background: var(--hj-line); border-radius: 2px;
  }
  .hjem-rail-item { position: relative; margin-bottom: 18px; }
  .hjem-rail-item:last-child { margin-bottom: 0; }
  .hjem-rail-dot {
    position: absolute; left: -30px; top: 1px; width: 16px; height: 16px; border-radius: 50%;
    background: var(--hj-accent2); border: 4px solid var(--hj-bg);
  }
  .hjem-rail-label {
    font-size: 11.5px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase;
    color: var(--hj-muted); margin-bottom: 7px;
  }
  .hjem-rail-item .hjem-card { margin-bottom: 10px; }
  .hjem-rail-item .hjem-card:last-child { margin-bottom: 0; }
  .hjem-siderail { display: flex; flex-direction: column; gap: 14px; }
  .hjem-siderail-card .hjem-zone-title { margin: 0 0 10px; }
  .hjem-shortcut-list { display: flex; flex-direction: column; gap: 8px; }
  .hjem-shortcut-btn {
    display: flex; align-items: center; justify-content: space-between; width: 100%;
    background: var(--hj-card2); color: var(--hj-ink); border: none; border-radius: 10px;
    padding: 10px 12px; font-size: 13px; font-weight: 700; cursor: pointer; font-family: Nunito, sans-serif;
  }
  .hjem-week-charts { display: flex; flex-direction: column; gap: 14px; }
  @media (min-width: 700px) {
    .hjem-week-charts { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  }

  .quicklog-bar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 90;
    display: flex; justify-content: space-around; background: var(--card); border-top: 1px solid var(--line);
    box-shadow: 0 -2px 10px rgba(122, 31, 61, 0.07);
    padding: 6px max(4px, env(safe-area-inset-left)) calc(6px + env(safe-area-inset-bottom)) max(4px, env(safe-area-inset-right));
  }
  .quicklog-bar button {
    background: none; border: none; color: var(--muted); display: flex;
    flex: 1 1 0; flex-direction: column; align-items: center; gap: 2px; padding: 6px 4px; border-radius: 12px;
    cursor: pointer; font-family: Nunito, sans-serif; font-weight: 700; font-size: 11px;
  }
  .quicklog-bar button:active { background: var(--line); }
  .quicklog-bar button.active { color: var(--accent); }
  .quicklog-bar .ql-icon { font-size: 20px; }
  .quicklog-drawer {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 91; background: var(--card); color: var(--ink);
    border-top: 1px solid var(--line); border-radius: 16px 16px 0 0; padding: 14px 16px;
    box-shadow: 0 -2px 16px rgba(122, 31, 61, 0.1);
    transform: translateY(100%); transition: transform .2s ease; max-height: 60vh; overflow-y: auto;
    padding-bottom: calc(76px + env(safe-area-inset-bottom));
  }
  .quicklog-drawer.open { transform: translateY(0); }
  .quicklog-drawer-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; font-weight: 700; }
  .quicklog-drawer-head button { background: none; border: none; color: var(--muted); font-size: 16px; cursor: pointer; }
  .quicklog-drawer .ql-presets { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .quicklog-drawer .ql-presets button {
    background: var(--bg); border: 1px solid var(--line); color: var(--ink); border-radius: 20px;
    padding: 8px 14px; font-size: 13px; cursor: pointer;
  }
  .quicklog-drawer input, .quicklog-drawer select {
    width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid var(--line); border-radius: 10px;
    font-family: Nunito, sans-serif; background: var(--bg); color: var(--ink); box-sizing: border-box; margin-bottom: 8px;
  }
  .quicklog-drawer .btn { width: 100%; }
  .more-menu { display: flex; flex-direction: column; gap: 4px; }
  .more-menu-btn {
    display: flex; align-items: center; gap: 12px; width: 100%; text-align: left;
    background: none; border: none; border-bottom: 1px solid var(--line); color: var(--ink);
    padding: 14px 4px; font-family: Nunito, sans-serif; font-weight: 700; font-size: 15px; cursor: pointer;
  }
  .more-menu-btn:last-child { border-bottom: none; }
  .more-menu-btn .ql-icon { font-size: 18px; }

  @media (max-width: 480px) {
    .hjem-dash { padding: 14px; }
  }

  /* ---- access gate ---- */
  #gate-overlay {
    position: fixed; inset: 0; z-index: 1000;
    background: linear-gradient(135deg, #7a1f3d 0%, #a8406a 100%);
    display: flex; align-items: center; justify-content: center; padding: 20px;
  }
  #gate-overlay .gate-box {
    background: #fff; border-radius: 18px; padding: 28px 24px; max-width: 320px; width: 100%;
    text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  }
  #gate-overlay h2 { margin: 0 0 6px; font-size: 20px; color: var(--ink); }
  #gate-overlay p { font-size: 12px; color: var(--muted); margin: 0 0 16px; }
  #gate-overlay input {
    width: 100%; font-family: Nunito, sans-serif; font-size: 15px; text-align: center;
    border: 1px solid var(--line); border-radius: 10px; padding: 10px; margin-bottom: 10px;
    background: var(--bg); color: var(--ink);
  }
  #gate-overlay .btn { width: 100%; padding: 10px; }
  #gate-overlay .gate-error { color: #c0392b; font-size: 12px; margin-top: 8px; min-height: 16px; }
  #gate-overlay.shake .gate-box { animation: shake .3s; }
  @keyframes shake { 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }

  @media (max-width: 720px) {
    .records-grid { grid-template-columns: repeat(2, 1fr); }
    .trend-grid { grid-template-columns: 1fr; }
    .week-row { overflow-x: scroll; }
    .week-day { min-width: 76px; }
    .log-grid { grid-template-columns: 1fr; }
    .budget-summary-grid { grid-template-columns: 1fr; }
    .savings-goal-grid { grid-template-columns: 1fr; }

    /* inputs/selects under 16px make iOS Safari auto-zoom the page on focus */
    input, select, textarea { font-size: 16px !important; }
    .cat-row .cat-head { flex-wrap: wrap; row-gap: 4px; }
    .cat-row input.cap-edit { width: 72px; }
    .tab-nav { scrollbar-width: none; -webkit-overflow-scrolling: touch; }
    .tab-nav::-webkit-scrollbar { display: none; }
  }
</style>
</head>
<body>

<div id="gate-overlay">
  <div class="gate-box">
    <h2>🔒 Logg inn</h2>
    <p>Logg inn for å åpne dashbordet og synkronisere data på tvers av enhetene dine.</p>
    <input type="email" id="gate-email" placeholder="E-post" autocomplete="username" autocapitalize="off" autocorrect="off" spellcheck="false">
    <input type="password" id="gate-input" placeholder="Passord" autocomplete="current-password">
    <button class="btn" id="gate-submit">Logg inn</button>
    <div class="gate-error" id="gate-error"></div>
  </div>
</div>

<header class="hero">
  <div class="wrap">
    <div class="hero-greeting" id="hero-greeting"></div>
    <div class="hero-datetime" id="hero-datetime"></div>
    <div class="hero-status-strip" id="hero-status-strip"></div>
  </div>
</header>

<div class="wrap">
  <nav class="tab-nav" id="tab-nav">
    <button data-tab="hjem">Hjem</button>
    <button data-tab="kosthold">Kosthold</button>
    <button data-tab="budsjett">Budsjett</button>
    <button data-tab="trening">Treningsplan</button>
    <button data-tab="planlegg">📝 Planlegg</button>
    <button data-tab="fremgang">Fremgang</button>
    <button data-tab="handleliste">Handleliste</button>
    <button data-tab="rapport">Rapport</button>
    <button data-tab="statistikk">Statistikk</button>
  </nav>

  <div class="rest-bubble" id="rest-bubble">
    <div class="rt-bubble-label" id="rt-bubble-label">Hvile</div>
    <div class="rt-bubble-display" id="rt-bubble-display">90</div>
    <div class="rt-bubble-actions">
      <button id="rt-bubble-pause">Pause</button>
      <button id="rt-bubble-skip">Hopp over</button>
    </div>
  </div>

  <div class="badday-panel" id="badday-panel">
    <h2 style="margin-top:0;">Minimumsdag</h2>
    <div class="section-sub">Bare det viktigste i dag. Trykk en knapp for å logge, gå tilbake når du vil.</div>
    <div id="badday-mvd"></div>
    <div class="badday-quickbtns" id="badday-quickbtns"></div>
    <div class="badday-saved-msg" id="badday-saved-msg"></div>
    <button class="btn ghost" id="badday-exit" style="display:block;margin-top:24px;">Tilbake til vanlig visning</button>
  </div>

  <div class="freeday-panel" id="freeday-panel">
    <h2 style="margin-top:0;">🌤️ Fri dag</h2>
    <div class="section-sub">Skriv inn det du har tenkt å gjøre i dag. Vi viser bare én ting om gangen, brutt ned til et lite første steg - resten er gjemt til du er klar for det.</div>
    <div class="log-form" style="margin-top:14px;">
      <input type="text" id="freeday-add-input" placeholder="Hva skal du gjøre?">
      <button class="btn" id="freeday-add-btn">Legg til</button>
    </div>
    <div id="freeday-current"></div>
    <div id="freeday-rest-toggle"></div>
    <button class="btn ghost" id="freeday-exit" style="display:block;margin-top:24px;">Tilbake til vanlig visning</button>
  </div>

  <div class="tab-panel" data-tab="hjem">
  <div class="hjem-dash" id="hjem-dash">
    <div class="hjem-topbar">
      <div class="hjem-why" id="hjem-why"></div>
      <div class="hjem-topbar-btns">
        <button class="hjem-refresh-btn" id="hjem-refresh-btn" title="Oppdater">⟳</button>
        <button class="hjem-badday-toggle" id="hjem-badday-toggle">🌱 Minimumsdag</button>
        <button class="hjem-badday-toggle" id="hjem-freeday-toggle">🌤️ Fri dag</button>
      </div>
    </div>

    <div id="hjem-reminder"></div>
    <div id="hjem-unplanned-cardio"></div>
    <div id="hjem-weight-reminder"></div>
    <div id="hjem-backup-reminder"></div>
    <div id="hjem-aon-banner"></div>
    <div id="hjem-protein-pace"></div>
    <div id="hjem-mvd-sunday"></div>
    <div id="hjem-next-week-preview"></div>
    <div id="hjem-freeze-notice"></div>
    <div id="hjem-monthly-insight-nudge"></div>

    <div class="card" id="hjem-daily-routine" style="margin-bottom:16px;"></div>

    <div class="hjem-main-grid">
      <div class="hjem-rail">
        <div class="hjem-rail-item">
          <div class="hjem-rail-dot"></div>
          <div class="hjem-rail-label">Kropp</div>
          <div id="hjem-body-today"></div>
        </div>
        <div class="hjem-rail-item">
          <div class="hjem-rail-dot"></div>
          <div class="hjem-rail-label">Trening</div>
          <div class="hjem-card hjem-session" id="hjem-session"></div>
        </div>
        <div class="hjem-rail-item">
          <div class="hjem-rail-dot"></div>
          <div class="hjem-rail-label">Måltid</div>
          <div class="hjem-card hjem-nutri-quick" id="hjem-kcal-ring"></div>
          <div id="hjem-social-budget"></div>
        </div>
        <div class="hjem-rail-item">
          <div class="hjem-rail-dot"></div>
          <div class="hjem-rail-label">Budsjett</div>
          <div class="hjem-card" id="hjem-tx-today"></div>
          <div class="hjem-card" id="hjem-finance"></div>
        </div>
      </div>

      <div class="hjem-siderail">
        <div class="hjem-card hjem-siderail-card">
          <h3 class="hjem-zone-title">Denne uken</h3>
          <div class="snapshot-row" id="weekly-snapshot"></div>
        </div>
        <div class="hjem-card hjem-siderail-card">
          <h3 class="hjem-zone-title">Raskt videre</h3>
          <div class="hjem-shortcut-list">
            <button class="hjem-shortcut-btn" data-goto-tab="trening">Treningsplan →</button>
            <button class="hjem-shortcut-btn" data-goto-tab="kosthold">Kosthold →</button>
            <button class="hjem-shortcut-btn" data-goto-tab="budsjett">Budsjett →</button>
          </div>
        </div>
      </div>
    </div>

    <section class="hjem-zone hjem-section-4">
      <h3 class="hjem-zone-title">Poeng &amp; Nivå</h3>
      <div id="celebrate-banner"></div>
      <div class="card level-card" id="level-card"></div>
      <div class="card" id="plateau-card"></div>
    </section>

    <section class="hjem-zone hjem-section-5">
      <h3 class="hjem-zone-title">Siste 7 dager</h3>
      <div class="hjem-week-charts">
        <div class="hjem-card">
          <div class="hjem-card-title">👣 Skritt per dag</div>
          <div class="chart-wrap"><svg id="hjem-chart-steps"></svg><div class="tooltip" id="tt-hjem-steps"></div></div>
        </div>
        <div class="hjem-card">
          <div class="hjem-card-title">😴 Søvn per natt</div>
          <div class="chart-wrap"><svg id="hjem-chart-sleep"></svg><div class="tooltip" id="tt-hjem-sleep"></div></div>
        </div>
      </div>
    </section>

  </div>
  </div>

  <div class="tab-panel" data-tab="rapport">
  <section>
    <h2>Rapport</h2>
    <div class="section-sub">Din personlige coach - en grundig gjennomgang av dataene dine, ikke bare tall og grafer.</div>
    <div class="report-tabs" id="report-tabs">
      <button class="btn secondary small report-tab-btn" data-report="evening">🌙 Kveldsrapport</button>
      <button class="btn secondary small report-tab-btn" data-report="weekly">📊 Ukens innsikt</button>
      <button class="btn secondary small report-tab-btn" data-report="monthly">📅 Månedens innsikt</button>
    </div>
    <div class="card report-card" id="report-output"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="trening">
  <section>
    <h2>Treningsplan</h2>
    <div class="card" id="knee-guidance-card" style="margin-bottom:16px;"></div>
    <div class="section-sub" id="plan-sub"></div>
    <div id="missed-day-banner"></div>
    <div class="section-sub" style="margin-top:-8px;">Dra i ⠿-håndtaket på et kort for å bytte økt med en annen dag denne uken</div>
    <div class="week-row" id="plan-week"></div>
    <div class="plan-card" id="plan-today"></div>
    <div class="card" id="rest-timer-card"></div>
  </section>

  <section style="margin-top:28px;">
    <h2>🏆 Rekorder</h2>
    <div class="section-sub">Dine beste løft, oppdateres automatisk når du logger sett</div>
    <div class="card" id="pr-board-card"></div>
  </section>

  <section style="margin-top:28px;">
    <h2>🍑 Sete, kjerne og stabilitet</h2>
    <div class="section-sub">Et eget tillegg for setemuskulatur, kjernestyrke og hoftekontroll - kommer i tillegg til, og endrer ikke, resten av treningsplanen din. Tenkt gjort på styrkedagene dine (mandag/onsdag/fredag), ca. 15-20 minutter. Ingen øvelse skal gi smerte eller økt hevelse i kneet - stopp og juster om noe gjør vondt.</div>
    <div id="stability-exercises"></div>

    <div class="card" id="knee-checkin-card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">Hvordan var kneet etter økten?</h3>
      <div class="section-sub" style="margin-bottom:10px;">Valgfritt. "Neste morgen" for gårsdagens økt kan du fylle inn i dag.</div>
      <div id="knee-checkin-form"></div>
    </div>

    <h3 style="margin:28px 0 4px;font-size:15px;">🔒 Fremtidige nivåer</h3>
    <div class="section-sub" style="margin-bottom:10px;">Låst inntil kneet er vurdert av fysioterapeut - låses aldri opp automatisk basert på tid.</div>
    <div id="stability-locked-levels"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="planlegg">
  <section>
    <h2>📝 Planlegg neste uke</h2>
    <div class="section-sub" id="plan-week-sub"></div>

    <h3 style="margin:24px 0 4px;font-size:15px;">Trening</h3>
    <div class="section-sub" style="margin-top:-2px;margin-bottom:10px;">Bytt type økt for en dag med nedtrekksmenyen</div>
    <div class="week-row" id="plan-next-week-training"></div>

    <h3 style="margin:28px 0 4px;font-size:15px;">🪄 Generer ukeplan</h3>
    <div class="card" id="plan-generator-card">
      <div class="section-sub" style="margin-bottom:8px;">Setter sammen et forslag til lunsj og middag for hele uken fra dine favorittretter (kjøttdeig, kylling, pasta, ris, fisk av og til) - treffer kalori-/proteinbudsjettet ditt. Ikke ekte AI, bare smarte regler tilpasset deg.</div>
      <button class="btn ghost small" id="plan-generate-btn">Generer forslag</button>
      <div id="plan-generated-preview"></div>
      <div class="badday-saved-msg" id="plan-generator-saved-msg"></div>
    </div>

    <h3 style="margin:28px 0 4px;font-size:15px;">Måltider</h3>
    <div class="section-sub" style="margin-top:-2px;margin-bottom:10px;">Velg hvilken rett som er planen for hver dag - du logger som vanlig i Kosthold når dagen kommer</div>
    <div id="plan-next-week-meals"></div>

    <h3 style="margin:28px 0 4px;font-size:15px;">🥘 Mealprep for uken</h3>
    <div class="card" id="plan-mealprep-card">
      <div class="section-sub" style="margin-bottom:8px;">Kryss av det du har hjemme akkurat nå, så foreslår vi retter som passer</div>
      <div id="plan-mealprep-have"></div>
      <button class="btn ghost small" id="plan-mealprep-find-btn" style="margin-top:4px;">Finn forslag</button>
      <div id="plan-mealprep-suggestions"></div>
      <div class="badday-saved-msg" id="plan-mealprep-saved-msg"></div>
    </div>

    <h3 style="margin:28px 0 4px;font-size:15px;">📌 Ukens planer/avtaler</h3>
    <div class="section-sub" style="margin-top:-2px;margin-bottom:8px;">Sosiale avtaler, reiser eller annet som påvirker uken</div>
    <textarea id="plan-agenda-text" rows="3" style="width:100%;box-sizing:border-box;font-family:inherit;font-size:13px;border:1px solid var(--line);border-radius:10px;padding:10px;" placeholder="F.eks. bursdagsmiddag torsdag, bortreist i helgen..."></textarea>
    <div class="badday-saved-msg" id="plan-agenda-saved-msg"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="kosthold">
  <section>
    <h2>Kosthold</h2>
    <div class="section-sub" id="kosthold-mode-note"></div>

    <div class="card" id="lifesum-entry-card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">📲 Dagens inntak (fra Lifesum)</h3>
      <div class="section-sub" style="margin-bottom:10px;">Før inn dagstotalen fra Lifesum her - dette blir fasiten for i dag, så du slipper å logge maten to steder.</div>
      <div class="log-form">
        <input type="number" step="10" id="lifesum-kcal" placeholder="Kalorier">
        <input type="number" step="1" id="lifesum-protein" placeholder="Protein (g)">
        <input type="number" step="1" id="lifesum-fat" placeholder="Fett (g)">
        <input type="number" step="1" id="lifesum-carbs" placeholder="Karbohydrater (g)">
        <button class="btn" id="lifesum-save">Lagre</button>
      </div>
      <div class="badday-saved-msg" id="lifesum-saved-msg"></div>
    </div>

    <div class="card" id="kosthold-today-card" style="margin-top:14px;"></div>

    <div class="card" id="craving-card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">🍬 Søtsug</h3>
      <div class="section-sub" style="margin-bottom:10px;">Trykk når du kjenner på søtsug - helt greit, bare nyttig å se mønstre over tid.</div>
      <button class="btn ghost" id="craving-log-btn">Logg søtsug</button>
      <ul class="log-list" id="craving-list"></ul>
    </div>

    <div id="kosthold-meal-cards"></div>

    <div class="card" id="nutrition-coach-card" style="margin-top:14px;"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="fremgang">
  <section>
    <h2>Fremgang</h2>
    <div class="section-sub">Langsiktige mål, trender og historikk - i motsetning til dashbordet, som bare viser dagens status</div>
    <div class="section-sub" id="fremgang-meta" style="margin-top:-8px;"></div>
    <div class="goal-row" id="goal-chips"></div>

    <div class="fremgang-section card">
      <h3>⚖️ Kropp &amp; mål</h3>
      <div class="section-sub">Vekt og et kroppsmål vist som % endring fra start av perioden, så de to kan sammenlignes direkte</div>
      <div class="weight-goal-row">Målvekt: <input type="number" step="0.5" id="weight-goal-input"> kg <button class="btn ghost small" id="weight-goal-save">Lagre</button></div>
      <div class="period-tabs" id="body-period-tabs">
        <button class="period-btn" data-period="1">1 mnd</button>
        <button class="period-btn" data-period="3">3 mnd</button>
        <button class="period-btn active" data-period="12">1 år</button>
      </div>
      <div class="period-tabs" id="body-measure-tabs">
        <button class="measure-select-btn active" data-measure="waist">Mage</button>
        <button class="measure-select-btn" data-measure="hips">Hofte</button>
        <button class="measure-select-btn" data-measure="arm">Arm</button>
        <button class="measure-select-btn" data-measure="thigh">Lår</button>
        <button class="measure-select-btn" data-measure="chest">Bryst</button>
      </div>
      <div class="legend" id="legend-body"></div>
      <div class="chart-wrap"><svg id="chart-body"></svg><div class="tooltip ml" id="tt-body"></div></div>
      <div class="context-note" id="body-context-note"></div>
      <div id="calorie-calibration-note"></div>

      <div class="log-grid">
        <div class="card">
          <h3 style="margin:0 0 4px;font-size:15px;">Vekt</h3>
          <div class="section-sub" style="margin-bottom:0;">Logg hver uke</div>
          <div class="log-form">
            <input type="date" id="weight-date">
            <input type="number" step="0.1" id="weight-kg" placeholder="kg">
            <button class="btn" id="weight-add">Lagre</button>
          </div>
          <div id="weight-trend"></div>
          <div class="chart-wrap"><svg id="chart-weight"></svg><div class="tooltip" id="tt-weight"></div></div>
          <ul class="log-list" id="weight-list"></ul>
        </div>
        <div class="card">
          <h3 style="margin:0 0 4px;font-size:15px;">Kroppsmål</h3>
          <div class="section-sub" style="margin-bottom:0;">Logg den 1. hver måned</div>
          <div class="log-form">
            <input type="date" id="measure-date">
            <input type="number" step="0.5" id="measure-waist" placeholder="Mage (cm)">
            <input type="number" step="0.5" id="measure-hips" placeholder="Hofte (cm)">
            <input type="number" step="0.5" id="measure-arm" placeholder="Arm (cm)">
            <input type="number" step="0.5" id="measure-thigh" placeholder="Lår (cm)">
            <input type="number" step="0.5" id="measure-chest" placeholder="Bryst (cm)">
            <button class="btn" id="measure-add">Lagre</button>
          </div>
          <ul class="log-list" id="measure-list"></ul>
        </div>
      </div>
    </div>

    <div class="fremgang-section card">
      <h3>🏃 Aktivitets-trender</h3>
      <div class="section-sub">Ukentlige snitt fra klokken, over tid</div>
      <div class="trend-grid">
        <div>
          <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Skritt &amp; aktive kalorier</div>
          <div class="legend" id="legend-activity"></div>
          <div class="chart-wrap"><svg id="chart-activity"></svg><div class="tooltip ml" id="tt-activity"></div></div>
        </div>
        <div>
          <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Stressnivå &amp; søvnkvalitet</div>
          <div class="legend" id="legend-stress-sleep"></div>
          <div class="chart-wrap"><svg id="chart-stress-sleep"></svg><div class="tooltip ml" id="tt-stress-sleep"></div></div>
        </div>
      </div>
      <div class="context-note" id="activity-context-note"></div>
    </div>

    <div class="fremgang-section card">
      <h3>💰 Variable utgifter</h3>
      <div class="section-sub">Per økonomimåned (15.–14.), siste 12 måneder - faste utgifter er ikke med, siden de er faste uansett</div>
      <div class="chart-wrap"><svg id="chart-expenses"></svg><div class="tooltip ml" id="tt-expenses"></div></div>
    </div>

    <div class="fremgang-section card">
      <h3>🐶 Sparemål</h3>
      <div class="section-sub">De tre faste sparekategoriene fra budsjettet</div>
      <div class="savings-goal-grid" id="savings-goals"></div>
    </div>

    <div class="fremgang-section card">
      <h3>📈 Fond-utvikling</h3>
      <div class="section-sub">Innskutt kapital vs. faktisk verdi, slik at du ser avkastningen</div>
      <div class="log-form">
        <input type="date" id="fund-log-date">
        <input type="number" step="100" id="fund-log-contributed" placeholder="Innskutt totalt (kr)">
        <input type="number" step="100" id="fund-log-value" placeholder="Fondsverdi i dag (kr)">
        <button class="btn" id="fund-log-add">Lagre</button>
      </div>
      <div class="legend" id="legend-fund"></div>
      <div class="chart-wrap"><svg id="chart-fund"></svg><div class="tooltip ml" id="tt-fund"></div></div>
      <div class="fund-summary-row" id="fund-summary"></div>
    </div>

    <div class="fremgang-section card" id="fremgang-weekly-report"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="handleliste">
  <section>
    <h2>Handleliste</h2>
    <div class="section-sub">Bygget fra matplanen din - kryss av det du har kjøpt</div>
    <div class="card">
      <div class="log-form">
        <input type="text" id="shop-input" placeholder="Legg til vare...">
        <button class="btn" id="shop-add">Legg til</button>
      </div>
      <div class="shop-quickadd">
        <button class="btn secondary small" id="shop-quickadd-protein">+ Faste proteinvarer</button>
        <button class="btn secondary small" id="shop-quickadd-meals">+ Fra måltidsideene</button>
        <button class="btn ghost small" id="shop-clear-checked">Fjern det som er kjøpt</button>
        <button class="btn ghost small" id="shop-clear-all">Tøm listen</button>
      </div>
      <ul class="shop-list" id="shop-list"></ul>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="budsjett">
  <section>
    <h2>Budsjett</h2>
    <div class="section-sub">Faste utgifter er faste kostnader du uansett betaler - logg bare variable utgifter her</div>
    <div class="card">
      <div class="month-nav">
        <button class="btn ghost small" id="em-prev">‹</button>
        <div class="month-label" id="em-label"></div>
        <button class="btn ghost small" id="em-next">›</button>
      </div>
      <h3 style="margin:10px 0 2px;font-size:15px;">Logg utgift</h3>
      <div class="log-form">
        <input type="date" id="tx-date">
        <input type="number" step="1" id="tx-amount" placeholder="Beløp (kr)">
        <select id="tx-category"></select>
        <input type="text" id="tx-name" placeholder="Hva var det?">
        <button class="btn btn-big" id="tx-add">Legg til</button>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 class="budget-section-title">🏠 Faste utgifter</h3>
      <div class="budget-cat-list" id="fixed-cat-list"></div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 class="budget-section-title">🛍️ Variable utgifter</h3>
      <div class="budget-cat-list" id="variable-cat-list"></div>
    </div>

    <div class="budget-summary-grid" id="budget-summary"></div>

    <div class="fund-card" id="fund-card"></div>
    <div class="card forgotten-savings-card" id="forgotten-savings-card" style="margin-top:14px;"></div>
    <div class="card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">Kjøpe eller spare?</h3>
      <div class="section-sub" style="margin-bottom:0;">Var du fristet til å kjøpe noe - takeaway, godteri, en genser? Sjekk hva det egentlig koster deg, og legg det i Sparekrukka i stedet hvis du lar være.</div>
      <div class="log-form">
        <input type="number" step="1" id="save-amount" placeholder="Beløp (kr)">
        <input type="text" id="save-name" placeholder="Fristet av hva?">
        <button class="btn ghost" id="buy-check">Sjekk</button>
        <button class="btn" id="save-add">Legg i Sparekrukka</button>
      </div>
      <div class="buy-check-settings">
        <label>Timelønn (kr)<input type="number" step="10" id="buy-wage" placeholder="f.eks. 250"></label>
        <label>Forventet årlig avkastning (%)<input type="number" step="0.5" id="buy-rate" placeholder="7"></label>
      </div>
      <div id="buy-check-out"></div>
      <div class="save-presets">
        <span class="save-presets-label">Rask sparing:</span>
        <button class="btn secondary small" data-preset="20">+20 kr</button>
        <button class="btn secondary small" data-preset="50">+50 kr</button>
        <button class="btn secondary small" data-preset="100">+100 kr</button>
      </div>
    </div>

    <div class="card" style="margin-top:14px;">
      <h3 style="margin:0 0 4px;font-size:15px;">📜 Historikk</h3>
      <div class="section-sub" style="margin-bottom:0;">Transaksjoner denne økonomimåneden</div>
      <ul class="log-list" id="tx-list"></ul>
    </div>
  </section>
  </div>

  <div class="tab-panel" data-tab="statistikk">
  <section id="vo2max-section" style="display:none;">
    <h2>VO2 Max</h2>
    <div class="section-sub">Garmins kondisjonsestimat, hentet direkte fra kontoen din</div>
    <div class="card" id="vo2max-card"></div>
  </section>

  <section>
    <h2>Denne uken vs. nylige uker</h2>
    <div class="section-sub">Økter, tid og distanse per idrett, siste 10 uker</div>
    <div class="card">
      <div class="legend" id="sport-legend"></div>
      <div class="chart-wrap"><svg id="chart-weekly-sport"></svg><div class="tooltip" id="tt-weekly"></div></div>
    </div>
  </section>

  <section>
    <h2>Trender</h2>
    <div class="section-sub">Ukentlig snitt, siste 6 måneder</div>
    <div class="trend-grid">
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Treningsbelastning</div>
        <div class="chart-wrap"><svg id="chart-load"></svg><div class="tooltip" id="tt-load"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Hvilepuls</div>
        <div class="chart-wrap"><svg id="chart-rhr"></svg><div class="tooltip" id="tt-rhr"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">HRV (nattlig snitt)</div>
        <div class="chart-wrap"><svg id="chart-hrv"></svg><div class="tooltip" id="tt-hrv"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Søvn (timer/natt, snitt)</div>
        <div class="chart-wrap"><svg id="chart-sleep"></svg><div class="tooltip" id="tt-sleep"></div></div>
      </div>
      <div class="card">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Treningsvolum (vekt × reps per uke)</div>
        <div class="chart-wrap"><svg id="chart-volume"></svg><div class="tooltip" id="tt-volume"></div></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Toppnoteringer</h2>
    <div class="section-sub">Dine største dager og økter</div>
    <div class="records-grid" id="records-grid"></div>
  </section>
  </div>

  <div class="tab-panel" data-tab="innstillinger">
  <section>
    <h2>Innstillinger</h2>

    <div class="card settings-card" id="settings-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Generelt</h3>
      <label class="settings-toggle-row">
        <input type="checkbox" id="settings-personality-toggle">
        <span>Personlighet (konfetti og påminnelser)</span>
      </label>
      <label class="settings-toggle-row">
        <input type="checkbox" id="settings-vacation-toggle">
        <span>Ferie/pause-modus - ingen påminnelser, streaken fryses</span>
      </label>
      <label class="settings-toggle-row">
        <input type="checkbox" id="settings-focus-mode-toggle">
        <span>Fokusmodus på Kosthold (vis kalorier og protein). Av = Livsstilsmodus: tall skjules, men du kan fortsatt logge måltider og bruke favoritter som vanlig.</span>
      </label>
    </div>

    <div class="card" id="push-settings-card">
      <h3 style="margin:0 0 4px;font-size:15px;">🔔 Varsler</h3>
      <div class="section-sub" style="margin-bottom:10px;">Push-varsler rett på telefonen: kveldsrapport klar, skritt-tempo, påminnelse om å føre inn Lifesum-tallene, og søndagsplanlegging. På iPhone må siden først legges til på Hjem-skjermen (Del-knappen i Safari → "Legg til på Hjem-skjermen") - åpne appen derfra og kom tilbake hit.</div>
      <div id="push-unsupported-msg" class="section-sub" style="display:none;color:#a15b5b;"></div>
      <div id="push-setup-area">
        <button class="btn secondary small" id="push-enable-btn">Aktiver varsler</button>
      </div>
      <div id="push-status" class="section-sub" style="margin:8px 0 0;"></div>
      <div id="push-subscription-area" style="display:none;">
        <div class="section-sub" style="margin:8px 0 4px;">Varsler er aktivert på denne telefonen. Kopier teksten under og send den til meg, så kobler jeg den til - det gjøres kun én gang.</div>
        <textarea id="push-subscription-text" readonly style="width:100%;min-height:90px;font-size:11px;font-family:monospace;box-sizing:border-box;"></textarea>
        <button class="btn ghost small" id="push-copy-btn">Kopier</button>
      </div>
    </div>

    <div class="card" id="mvd-settings-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Minimum Viable Day (MVD)</h3>
      <div class="section-sub" style="margin-bottom:10px;">De tre tersklene som teller som en fullført minimumsdag - vises på Minimumsdag-knappen og automatisk på søndager.</div>
      <div class="log-form">
        <label class="mvd-settings-field">Protein per måltid (g)<input type="number" step="1" id="mvd-protein-input"></label>
        <label class="mvd-settings-field">Skritt<input type="number" step="500" id="mvd-steps-input"></label>
        <label class="mvd-settings-field">Minutter bevegelse<input type="number" step="5" id="mvd-minutes-input"></label>
        <button class="btn ghost small" id="mvd-settings-save">Lagre MVD</button>
      </div>
      <div class="badday-saved-msg" id="mvd-settings-saved-msg"></div>
    </div>

    <div class="card sync-card" id="sync-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Skylagring</h3>
      <div class="section-sub" style="margin-bottom:10px;">Data synkroniseres automatisk med kontoen din i bakgrunnen. Bruk knappen under om noe virker bakpå, f.eks. rett etter du har gjort endringer på en annen enhet.</div>
      <div class="backup-actions">
        <button class="btn secondary small" id="sync-now-btn">Synk nå</button>
        <button class="btn ghost small" id="sync-logout-btn">Logg ut</button>
      </div>
      <div id="sync-status" class="section-sub" style="margin:8px 0 0;"></div>
    </div>

    <div class="card backup-card" id="backup-card">
      <h3 style="margin:0 0 4px;font-size:15px;">Sikkerhetskopi (fil)</h3>
      <div class="section-sub" style="margin-bottom:10px;">Et ekstra trygghetsnett i tillegg til skylagringen over - last ned en kopi innimellom, eller bruk den til å gjenopprette data manuelt.</div>
      <div class="backup-actions">
        <button class="btn secondary small" id="backup-export">Last ned kopi</button>
        <button class="btn ghost small" id="backup-import-btn">Gjenopprett fra fil</button>
        <input type="file" id="backup-import-file" accept="application/json" style="display:none;">
      </div>
      <div id="backup-status" class="section-sub" style="margin:8px 0 0;"></div>
    </div>
  </section>
  </div>

  <div class="quiet-actions-bottom">
    <button class="btn ghost support-btn" id="support-btn">🤍 Trenger du noe i dag?</button>
  </div>
  <div id="support-picker"></div>
  <div id="overwhelm-out"></div>
  <div id="sickday-out"></div>

  <footer id="footer">
    <button id="footer-settings-link">⚙️ Innstillinger</button>
    <div id="footer-generated"></div>
  </footer>
</div>

<div class="quicklog-drawer" id="quicklog-drawer">
  <div class="quicklog-drawer-head">
    <span id="quicklog-drawer-title"></span>
    <button id="quicklog-drawer-close">✕</button>
  </div>
  <div id="quicklog-drawer-body"></div>
</div>
<nav class="quicklog-bar" id="quicklog-bar">
  <button class="bottomnav-btn" data-tab="hjem"><span class="ql-icon">🏠</span><span class="ql-label">Hjem</span></button>
  <button class="bottomnav-btn" data-tab="kosthold"><span class="ql-icon">🍽️</span><span class="ql-label">Kosthold</span></button>
  <button class="bottomnav-btn" data-tab="trening"><span class="ql-icon">🏋️</span><span class="ql-label">Trening</span></button>
  <button class="bottomnav-btn" data-tab="rapport"><span class="ql-icon">📊</span><span class="ql-label">Rapport</span></button>
  <button class="bottomnav-btn" id="bottomnav-more"><span class="ql-icon">⋯</span><span class="ql-label">Mer</span></button>
</nav>

<script>
const DATA = __DASHBOARD_DATA__;

// Transient (not persisted) UI state for the "kjenn det i rumpa"-tips på rumpeøvelser i
// Treningsplan - deklarert her, tidlig, siden renderPlan() kan kjøre før andre deler av
// filen (samme TDZ-hensyn som andre tidlig-deklarerte konstanter i denne filen).
let gluteTipExpandedKey = null;

// ---------------------------------------------------------------- settings
const SETTINGS_KEY = "garminDashboardSettings_v1";
function loadSettings() {
  return Object.assign({
    dailyKcal: DATA.nutritionPlan.dailyKcal,
    proteinMin: DATA.nutritionPlan.proteinMin,
    savingsTarget: DATA.dogFund.target,
    weightGoal: null,
    personalityEnabled: true,
    mvdProtein: 15,
    mvdSteps: 5000,
    mvdMinutes: 15,
    kostholdFocusMode: true,
  }, loadLS(SETTINGS_KEY, {}));
}
function saveSettings(s) { saveLS(SETTINGS_KEY, s); }
(function applySettings() {
  const s = loadSettings();
  DATA.nutritionPlan.dailyKcal = s.dailyKcal;
  DATA.nutritionPlan.proteinMin = s.proteinMin;
  DATA.dogFund.target = s.savingsTarget;
})();

// ---------------------------------------------------------------- mitt hvorfor
const WHY_KEY = "garminDashboardWhy_v1";
function loadWhy() { return loadLS(WHY_KEY, ""); }
function saveWhy(v) { saveLS(WHY_KEY, v); }

// ---------------------------------------------------------------- ferie / pause-modus
const VACATION_KEY = "garminDashboardVacation_v1";
function loadVacationRanges() { return loadLS(VACATION_KEY, []); }
function saveVacationRanges(r) { saveLS(VACATION_KEY, r); }
function isVacationActive() {
  const r = loadVacationRanges();
  return r.length > 0 && !r[r.length - 1].end;
}
function setVacationActive(active) {
  const r = loadVacationRanges();
  const open = r.length && !r[r.length - 1].end;
  if (active && !open) r.push({ start: todayISO(), end: null });
  else if (!active && open) r[r.length - 1].end = todayISO();
  saveVacationRanges(r);
}
function inVacationRange(date) {
  return loadVacationRanges().some(r => date >= r.start && date <= (r.end || "9999-99-99"));
}

// ---------------------------------------------------------------- sykedager (migrene o.l.)
// Logget i etterkant - hun kan ikke røre appen midt i en migrene. Sykedager fryser streak
// og minimumsdag-krav for de dagene, og holdes helt utenfor ukens/månedens mønstre og mål,
// akkurat som ferie/pause-modus.
const SICK_DAY_KEY = "garminDashboardSickDays_v1";
const DAILY_ROUTINE_LOG_KEY = "garminDashboardDailyRoutine_v1";
function loadSickDays() { return loadLS(SICK_DAY_KEY, []); }
function saveSickDays(d) { saveLS(SICK_DAY_KEY, d); }
function isSickDay(date) { return loadSickDays().some(d => d.date === date); }
function addSickDayRange(fromDate, toDate, note) {
  const days = loadSickDays();
  const existing = new Set(days.map(d => d.date));
  for (let iso = fromDate; iso <= toDate; iso = isoAddDays(iso, 1)) {
    if (!existing.has(iso)) days.push({ date: iso, note: note || "" });
  }
  days.sort((a, b) => b.date.localeCompare(a.date));
  saveSickDays(days);
}
function removeSickDay(date) {
  saveSickDays(loadSickDays().filter(d => d.date !== date));
}

// ---------------------------------------------------------------- access gate / cloud auth
// The actual Firebase auth + Firestore sync logic lives in the <script type="module"> at the
// bottom of the page (modules need their own scope for the Firebase imports) and talks to this
// classic script through window.__cloudAuth (calls into the module) and the two callbacks below
// (calls from the module back into here). window.__cloudAuth may not exist yet if this code runs
// before that module has finished loading, so every call into it is guarded.
const overlay = document.getElementById("gate-overlay");

function setSyncStatus(msg) {
  const el = document.getElementById("sync-status");
  if (el) el.textContent = msg;
}
window.__cloudSyncStatus = setSyncStatus;

window.__onAuthStateChanged = function (user) {
  if (user) {
    overlay.style.display = "none";
    window.__cloudAuth.pullNow();
    if (location.hash === "#debug") renderDebugPage();
  } else {
    overlay.style.display = "flex";
  }
};

async function tryLogin() {
  const email = document.getElementById("gate-email").value.trim();
  const password = document.getElementById("gate-input").value;
  const errEl = document.getElementById("gate-error");
  if (!email || !password) return;
  if (!window.__cloudAuth) { errEl.textContent = "Laster innloggingen ennå - prøv igjen om et par sekunder."; return; }
  try {
    await window.__cloudAuth.signIn(email, password);
    errEl.textContent = "";
  } catch (e) {
    const code = e && e.code || "";
    const messages = {
      "auth/user-not-found": "Finner ingen bruker med den e-posten - sjekk at den er skrevet nøyaktig som i Firebase-konsollen (Authentication → Users).",
      "auth/wrong-password": "Feil passord for denne e-posten.",
      "auth/invalid-credential": "Feil e-post eller passord.",
      "auth/invalid-email": "Det ser ikke ut som en gyldig e-postadresse.",
      "auth/too-many-requests": "For mange forsøk - vent litt og prøv igjen.",
      "auth/network-request-failed": "Ingen nettverksforbindelse - sjekk internett og prøv igjen.",
    };
    errEl.textContent = (messages[code] || "Innlogging feilet") + (code ? ` (${code})` : "");
    overlay.classList.remove("shake");
    void overlay.offsetWidth;
    overlay.classList.add("shake");
  }
}
document.getElementById("gate-submit").addEventListener("click", tryLogin);
["gate-email", "gate-input"].forEach(id => {
  document.getElementById(id).addEventListener("keydown", e => {
    if (e.key === "Enter") tryLogin();
  });
});

function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
function fmtShort(s) {
  if (!s) return "";
  const d = new Date(s + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
// Norwegian decimal comma instead of JS's default period (e.g. "9,1" not "9.1") -
// used anywhere a possibly-decimal number from Garmin data gets written into report text.
function fmtNo(n) {
  if (n == null) return n;
  return n.toLocaleString("no-NO");
}

// ---------------------------------------------------------------- header
const NO_WEEKDAYS_FULL = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
const NO_MONTHS_FULL = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"];
function nowDateTimeLabel() {
  const now = new Date();
  const weekday = NO_WEEKDAYS_FULL[now.getDay()];
  const day = now.getDate();
  const month = NO_MONTHS_FULL[now.getMonth()];
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  return { full: `${weekday} ${day}. ${month}`, time };
}
function renderHeroGreeting() {
  const h = new Date().getHours();
  const greet = h < 10 ? "God morgen" : h < 17 ? "God dag" : "God kveld";
  const el = document.getElementById("hero-greeting");
  if (el) el.textContent = `${greet}, Katrine`;
  const dt = nowDateTimeLabel();
  const sub = document.getElementById("hero-datetime");
  if (sub) sub.textContent = `${dt.full} · ${dt.time}`;
}
renderHeroGreeting();
setInterval(renderHeroGreeting, 30000);

function heroSparkline(values) {
  const vals = (values || []).filter(v => v !== null && v !== undefined);
  if (vals.length < 2) return "";
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = (max - min) || 1;
  const w = 50, h = 14;
  const step = w / (values.length - 1);
  const pts = [];
  values.forEach((v, i) => {
    if (v === null || v === undefined) return;
    pts.push([i * step, h - ((v - min) / range) * (h - 3) - 1.5]);
  });
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  return `<svg class="hss-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
function renderHeroStatusStrip() {
  const el = document.getElementById("hero-status-strip");
  if (!el) return;
  const ts = DATA.topStats || {};
  const items = [
    ts.sleep && ts.sleep.hours != null ? { icon: "😴", text: `${ts.sleep.hours.toLocaleString("no-NO")}t`, trend: ts.sleep.trend } : null,
    ts.hrv && ts.hrv.value != null ? { icon: "❤️", text: `${ts.hrv.value} ms`, trend: ts.hrv.trend } : null,
    ts.calories && ts.calories.value != null ? { icon: "🔥", text: `${ts.calories.value.toLocaleString("no-NO")} kcal`, trend: ts.calories.trend } : null,
    ts.steps && ts.steps.value != null ? { icon: "👣", text: `${ts.steps.value.toLocaleString("no-NO")}`, trend: ts.steps.trend } : null,
  ].filter(Boolean);
  el.innerHTML = items.map(i => `
    <div class="hss-chip">
      <span class="hss-main">${i.icon} ${i.text}</span>
      ${heroSparkline(i.trend)}
    </div>
  `).join("");
}
renderHeroStatusStrip();

// activity-count + weekly goal chips used to live in the header - moved to Fremgang,
// since they're long-term trend info, not something needed on every screen.
function renderFremgangMeta() {
  const metaEl = document.getElementById("fremgang-meta");
  if (metaEl) {
    metaEl.textContent = `${DATA.meta.totalActivities} aktiviteter registrert, ${fmtDate(DATA.meta.dateRange[0])} – ${fmtDate(DATA.meta.dateRange[1])}`;
  }
  const goalChips = document.getElementById("goal-chips");
  if (!goalChips) return;
  const g = DATA.goal;
  function deltaSpan(pct) {
    if (pct === null || pct === undefined) return "";
    const cls = pct >= 0 ? "delta-up" : "delta-down";
    const sign = pct >= 0 ? "+" : "";
    return ` <span class="${cls}">${sign}${pct}%</span>`;
  }
  let html = "";
  if (g.recentActiveCaloriesPerWeek) {
    html += `<div class="goal-chip">Aktive kalorier/uke<b>${g.recentActiveCaloriesPerWeek.toLocaleString()}${deltaSpan(g.caloriesPctChange)}</b></div>`;
  }
  if (g.recentSessionsPerWeek) {
    html += `<div class="goal-chip">Økter/uke<b>${g.recentSessionsPerWeek}</b></div>`;
  }
  if (g.recentStepsPerDay) {
    html += `<div class="goal-chip">Skritt/dag<b>${g.recentStepsPerDay.toLocaleString()}${deltaSpan(g.stepsPctChange)}</b></div>`;
  }
  goalChips.innerHTML = html;
}
renderFremgangMeta();

// ---------------------------------------------------------------- tabs
const ACTIVE_TAB_KEY = "garminDashboardActiveTab_v1";
function showTab(tab) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("active", p.dataset.tab === tab));
  document.querySelectorAll("#tab-nav button, .bottomnav-btn[data-tab]").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  document.body.classList.toggle("tab-is-hjem", tab === "hjem");
  localStorage.setItem(ACTIVE_TAB_KEY, tab);
}
function gotoTab(tab) {
  showTab(tab);
  if (tab === "planlegg") renderPlanlegg();
}
document.querySelectorAll("#tab-nav button, .bottomnav-btn[data-tab]").forEach(btn => {
  btn.addEventListener("click", () => gotoTab(btn.dataset.tab));
});
const rememberedTab = localStorage.getItem(ACTIVE_TAB_KEY);
const validTabs = Array.from(document.querySelectorAll(".tab-panel")).map(p => p.dataset.tab);
showTab(validTabs.includes(rememberedTab) ? rememberedTab : "hjem");
document.getElementById("footer-settings-link").addEventListener("click", () => {
  showTab("innstillinger");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ---------------------------------------------------------------- training plan
const PLAN_OVERRIDES_KEY = "garminDashboardPlanOverrides_v1";
const SWAP_OPTIONS = ["gsA", "gsB", "gsC", "cyc", "cycHard", "walk", "rest"];
const SWAP_NAMES = { gsA: "Styrke A", gsB: "Styrke B", gsC: "Styrke C", cyc: "Kondisjon", cycHard: "Kondisjon (intervaller)", walk: "Gåtur", rest: "Hvile" };

function loadPlanOverrides() {
  try { return JSON.parse(localStorage.getItem(PLAN_OVERRIDES_KEY) || "{}"); } catch (e) { return {}; }
}
function savePlanOverrides(o) { localStorage.setItem(PLAN_OVERRIDES_KEY, JSON.stringify(o)); }

function resolvePlanDay(d, overrides) {
  const ov = overrides[d.date];
  const cat = DATA.sessionCatalog;
  let key, label, type, exercises, cycleNote;
  if (ov && cat[ov]) {
    key = ov;
    label = cat[ov].label + ((ov === "cyc" || ov === "cycHard") ? ` (${DATA.program.weekCycleNote})` : "");
    type = cat[ov].type;
    exercises = cat[ov].exercises || null;
    cycleNote = cat[ov].note || null;
  } else {
    key = d.defaultKey;
    label = d.sessionLabel;
    type = d.sessionType;
    exercises = (cat[d.defaultKey] || {}).exercises || null;
    cycleNote = (cat[d.defaultKey] || {}).note || null;
  }
  const matched = type === "rest" ? null : (d.loggedActivities || []).find(a => a.type === type) || null;
  return { key, label, type, exercises, cycleNote, done: type === "rest" ? null : !!matched, matchedActivity: matched };
}

function swapSelectHtml(date, resolvedKey) {
  const selKey = SWAP_OPTIONS.includes(resolvedKey) ? resolvedKey : "rest";
  const opts = SWAP_OPTIONS.map(k => `<option value="${k}" ${k === selKey ? "selected" : ""}>${SWAP_NAMES[k]}</option>`).join("");
  return `<select class="swap" data-date="${date}" aria-label="Bytt økt">${opts}</select>`;
}
function normalizeSwapKey(key) { return SWAP_OPTIONS.includes(key) ? key : "rest"; }
function isDefaultKeyForDay(day, key) {
  return key === day.defaultKey || (key === "rest" && (day.defaultKey === "rest" || day.defaultKey === "restW"));
}
// swaps which session is planned on two days of the current week (drag-and-drop), for
// this week only - each day's override is set to the other's resolved session, or cleared
// if that happens to already be that day's own default.
function swapPlanDays(dateA, dateB) {
  const p = DATA.program;
  const dayA = p.week.find(d => d.date === dateA);
  const dayB = p.week.find(d => d.date === dateB);
  if (!dayA || !dayB || dateA === dateB) return;
  const overrides = loadPlanOverrides();
  const keyA = normalizeSwapKey(resolvePlanDay(dayA, overrides).key);
  const keyB = normalizeSwapKey(resolvePlanDay(dayB, overrides).key);
  if (isDefaultKeyForDay(dayA, keyB)) delete overrides[dateA]; else overrides[dateA] = keyB;
  if (isDefaultKeyForDay(dayB, keyA)) delete overrides[dateB]; else overrides[dateB] = keyA;
  savePlanOverrides(overrides);
  renderPlan();
  renderMissedDayPrompt();
}
// touch/mouse-friendly drag via Pointer Events (native HTML5 drag-and-drop doesn't work on
// iOS touch) - dragging is only initiated from the small ⠿ handle, not the whole card, so
// the week row's own horizontal swipe-scroll still works everywhere else on the card.
function setupWeekDrag() {
  const todayStr = DATA.program.today.date;
  const isDroppable = dateStr => !!dateStr && dateStr >= todayStr;
  document.querySelectorAll(".week-day-handle").forEach(handle => {
    handle.addEventListener("pointerdown", startEvt => {
      const card = handle.closest(".week-day");
      const fromDate = card.dataset.date;
      const startX = startEvt.clientX, startY = startEvt.clientY;
      let dragging = false;

      function clearTargets() {
        document.querySelectorAll(".week-day.drop-target").forEach(c => c.classList.remove("drop-target"));
      }
      function onMove(ev) {
        if (!dragging) {
          if (Math.abs(ev.clientX - startX) < 8 && Math.abs(ev.clientY - startY) < 8) return;
          dragging = true;
          card.classList.add("dragging");
          handle.setPointerCapture(startEvt.pointerId);
        }
        ev.preventDefault();
        clearTargets();
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const target = el && el.closest(".week-day");
        if (target && target !== card && isDroppable(target.dataset.date)) target.classList.add("drop-target");
      }
      function onUp(ev) {
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        card.classList.remove("dragging");
        clearTargets();
        if (!dragging) return;
        const el = document.elementFromPoint(ev.clientX, ev.clientY);
        const target = el && el.closest(".week-day");
        if (target && target.dataset.date && target.dataset.date !== fromDate && isDroppable(target.dataset.date)) {
          swapPlanDays(fromDate, target.dataset.date);
        }
      }
      handle.addEventListener("pointermove", onMove, { passive: false });
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    });
  });
}

// ---- manual RPE fallback for days Garmin doesn't give a training load for the session ----
const RPE_LOG_KEY = "garminDashboardRpeLog_v1";
function loadRpeLog() { return loadLS(RPE_LOG_KEY, {}); }
function saveRpeLog(l) { saveLS(RPE_LOG_KEY, l); }
function todayRpe() {
  const v = loadRpeLog()[todayISO()];
  return v == null ? null : v;
}
function effectiveStrainScore(garminStrain) {
  if (garminStrain != null && garminStrain > 0) return garminStrain;
  const rpe = todayRpe();
  if (rpe != null) return Math.min(100, rpe * 10);
  return garminStrain;
}

// ---- "du hoppet over en dag" - offer to move it to tomorrow, or drop it for this week ----
// ---- unplanned cardio activity detection (Garmin logged something that wasn't the planned session) ----
const UNPLANNED_CARDIO_ACK_KEY = "garminDashboardUnplannedCardioAck_v1";
function loadUnplannedCardioAck() { return loadLS(UNPLANNED_CARDIO_ACK_KEY, []); }
function ackUnplannedCardio(ackId) {
  const a = loadUnplannedCardioAck();
  if (!a.includes(ackId)) { a.push(ackId); saveLS(UNPLANNED_CARDIO_ACK_KEY, a); }
}
function renderHjemUnplannedCardio() {
  const el = document.getElementById("hjem-unplanned-cardio");
  const p = DATA.program;
  if (!el || !p || isVacationActive()) { if (el) el.innerHTML = ""; return; }
  const overrides = loadPlanOverrides();
  const todayDay = p.week.find(d => d.isToday);
  if (!todayDay) { el.innerHTML = ""; return; }
  const resolved = resolvePlanDay(todayDay, overrides);
  const cardioActivity = (todayDay.loggedActivities || []).find(a => a.type === "cardio");
  const ack = loadUnplannedCardioAck();
  const ackId = todayISO() + "|" + (cardioActivity ? cardioActivity.activityId : "");
  if (!cardioActivity || resolved.type === "cardio" || ack.includes(ackId)) { el.innerHTML = ""; return; }

  const sportLabel = SPORT_LABELS_NO[cardioActivity.sport] || cardioActivity.sport;
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>🏃 Garmin registrerte ${sportLabel.toLowerCase()} (${cardioActivity.minutes} min) i dag, som ikke var planlagt. Vil du legge til denne økten i treningsloggen din?</span>
      <div class="hjem-topbar-btns">
        <button id="hjem-unplanned-cardio-add">Legg til</button>
        <button class="hjem-badday-toggle" id="hjem-unplanned-cardio-dismiss">Nei takk</button>
      </div>
    </div>
  `;
  document.getElementById("hjem-unplanned-cardio-add").addEventListener("click", () => {
    const current = loadPlanOverrides();
    current[todayISO()] = "cyc";
    savePlanOverrides(current);
    ackUnplannedCardio(ackId);
    renderHjem();
    renderPlan();
  });
  document.getElementById("hjem-unplanned-cardio-dismiss").addEventListener("click", () => {
    ackUnplannedCardio(ackId);
    renderHjemUnplannedCardio();
  });
}

function daysSinceDate(dateStr) {
  if (!dateStr) return null;
  return Math.round((new Date(todayISO() + "T00:00:00") - new Date(dateStr + "T00:00:00")) / 86400000);
}

// ---- "all-or-nothing" detector: a deviation day followed by 2 days of no logging at all
// tends to mean she's given up rather than just having had an off day - greet her warmly
// instead of silence when she comes back, rather than letting it go unnoticed ----
function isDeviationDay(date) {
  const totals = dayNutritionTotals(date);
  const goal = DATA.nutritionPlan.dailyKcal;
  return (goal && withKcalMargin(totals.kcal) > goal * 1.15) || (totals.extras || []).length >= 2;
}
function isEmptyLoggingDay(date) {
  const totals = dayNutritionTotals(date);
  return totals.kcal === 0 && (totals.mealsLogged || []).length === 0 && (totals.extras || []).length === 0;
}
// protein-tempo: et rolig hint hvis protein-inntaket ligger tydelig bak der det "burde" vært
// basert på klokkeslettet - grovt anslag, ikke en presis modell, og vises kun i Fokusmodus
function proteinPaceGap() {
  const n = DATA.nutritionPlan;
  if (!n) return null;
  const now = new Date();
  const hour = now.getHours() + now.getMinutes() / 60;
  const dayStart = 7, dayEnd = 21;
  if (hour <= dayStart + 1) return null;
  const elapsedFrac = Math.min(1, (hour - dayStart) / (dayEnd - dayStart));
  const expected = n.proteinMin * elapsedFrac;
  const gap = expected - dayNutritionTotals(todayISO()).protein;
  return gap >= 20 ? Math.round(gap) : null;
}
function renderHjemProteinPace() {
  const el = document.getElementById("hjem-protein-pace");
  if (!el) return;
  if (!loadSettings().kostholdFocusMode) { el.innerHTML = ""; return; }
  const gap = proteinPaceGap();
  if (gap == null) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>⚡ Du ligger litt bak protein-tempoet for klokka nå (~${gap} g) - kanskje tid for noe proteinrikt?</span>
      <div class="hjem-topbar-btns">
        <button class="hjem-badday-toggle" id="hjem-protein-pace-goto">Gå til Kosthold</button>
        <button class="hjem-badday-toggle" id="hjem-protein-pace-dismiss">Skjul</button>
      </div>
    </div>
  `;
  document.getElementById("hjem-protein-pace-goto").addEventListener("click", () => showTab("kosthold"));
  document.getElementById("hjem-protein-pace-dismiss").addEventListener("click", () => { el.innerHTML = ""; });
}

function renderHjemAllOrNothing() {
  const el = document.getElementById("hjem-aon-banner");
  if (!el) return;
  const today = todayISO();
  const d1 = isoAddDays(today, -1), d2 = isoAddDays(today, -2), d3 = isoAddDays(today, -3);
  const triggered = isEmptyLoggingDay(d1) && isEmptyLoggingDay(d2) && isDeviationDay(d3);
  if (!triggered) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>🌱 Jeg ser at du har hatt noen dager med avvik. Det er helt normalt. Ikke la det stoppe deg. Skal vi gjøre en mini-økt i dag for å komme i gang igjen?</span>
      <div class="hjem-topbar-btns">
        <button id="hjem-aon-session">Mini-økt</button>
        <button class="hjem-badday-toggle" id="hjem-aon-dismiss">Skjul</button>
      </div>
    </div>
  `;
  document.getElementById("hjem-aon-session").addEventListener("click", () => showTab("trening"));
  document.getElementById("hjem-aon-dismiss").addEventListener("click", () => { el.innerHTML = ""; });
}

// ---- weight/measurement logging reminder (points reward weekly weigh-ins and monthly
// measurements, but nothing used to nudge her to actually do them) ----
function renderHjemWeightReminder() {
  const el = document.getElementById("hjem-weight-reminder");
  if (!el) return;
  if (!loadSettings().personalityEnabled || isVacationActive()) { el.innerHTML = ""; return; }

  const weightLog = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  const measureLog = loadMeasureLog().sort((a, b) => a.date.localeCompare(b.date));
  const weightDays = weightLog.length ? daysSinceDate(weightLog[weightLog.length - 1].date) : null;
  const measureDays = measureLog.length ? daysSinceDate(measureLog[measureLog.length - 1].date) : null;

  const msgs = [];
  if (weightDays == null || weightDays >= 10) {
    msgs.push({ text: weightDays == null ? "Du har ikke registrert vekt ennå" : `Du har ikke veid deg på ${weightDays} dager`, target: "weight-date" });
  }
  if (measureDays == null || measureDays >= 35) {
    msgs.push({ text: measureDays == null ? "Du har ikke tatt mål ennå" : `Du har ikke tatt mål på ${measureDays} dager`, target: "measure-date" });
  }
  if (!msgs.length) { el.innerHTML = ""; return; }

  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>⚖️ ${msgs.map(m => m.text).join(" · ")}</span>
      <button id="hjem-weight-reminder-link">Logg nå</button>
    </div>
  `;
  document.getElementById("hjem-weight-reminder-link").addEventListener("click", () => {
    showTab("fremgang");
    setTimeout(() => {
      const target = document.getElementById(msgs[0].target);
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
}

// ---- backup reminder (all data lives only in this browser's localStorage, so a stale or
// missing backup means a lost phone/cleared browser data loses everything) ----
const LAST_BACKUP_KEY = "garminDashboardLastBackup_v1";
function renderHjemBackupReminder() {
  const el = document.getElementById("hjem-backup-reminder");
  if (!el) return;
  const days = daysSinceDate(loadLS(LAST_BACKUP_KEY, null));
  if (days != null && days < 30) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>💾 ${days == null ? "Du har aldri lastet ned en sikkerhetskopi" : `Sist sikkerhetskopiert for ${days} dager siden`}. All data ligger bare i denne nettleseren.</span>
      <button id="hjem-backup-reminder-link">Gå til Innstillinger</button>
    </div>
  `;
  document.getElementById("hjem-backup-reminder-link").addEventListener("click", () => {
    showTab("innstillinger");
    setTimeout(() => {
      const target = document.getElementById("backup-card");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
}

const MISSED_DAY_ACK_KEY = "garminDashboardMissedDayAck_v1";
function loadMissedDayAck() { return loadLS(MISSED_DAY_ACK_KEY, []); }
function ackMissedDay(dateStr) {
  const a = loadMissedDayAck();
  if (!a.includes(dateStr)) { a.push(dateStr); saveLS(MISSED_DAY_ACK_KEY, a); }
}
function renderMissedDayPrompt() {
  const el = document.getElementById("missed-day-banner");
  const p = DATA.program;
  if (!el || !p) return;
  const overrides = loadPlanOverrides();
  const ack = loadMissedDayAck();
  const missedDay = p.week.slice().reverse().find(d => {
    if (d.date >= p.today.date || ack.includes(d.date)) return false;
    const r = resolvePlanDay(d, overrides);
    return r.type !== "rest" && r.done !== true;
  });
  if (!missedDay) { el.innerHTML = ""; return; }
  const r = resolvePlanDay(missedDay, overrides);
  el.innerHTML = `<div class="missed-day-box">
    Du hoppet over <b>${r.label}</b> (${fmtShort(missedDay.date)}) - vil du flytte den til i morgen, eller droppe den denne uken?
    <div class="missed-day-actions">
      <button class="btn small" id="missed-day-move">Flytt til i morgen</button>
      <button class="btn ghost small" id="missed-day-skip">Dropp denne uken</button>
    </div>
  </div>`;
  document.getElementById("missed-day-move").addEventListener("click", () => {
    const tomorrow = isoAddDays(todayISO(), 1);
    const current = loadPlanOverrides();
    current[tomorrow] = normalizeSwapKey(r.key);
    savePlanOverrides(current);
    ackMissedDay(missedDay.date);
    renderPlan();
    renderMissedDayPrompt();
  });
  document.getElementById("missed-day-skip").addEventListener("click", () => {
    ackMissedDay(missedDay.date);
    renderMissedDayPrompt();
  });
}

const SET_LOG_KEY = "garminDashboardSetLog_v1";
function loadSetLogAll() { return loadLS(SET_LOG_KEY, []); }
function loadSetLog() { return loadSetLogAll().filter(s => !s.deleted); }
function saveSetLog(l) { saveLS(SET_LOG_KEY, l); }
function addSet(exKey, label, date, weight, reps, extra) {
  const log = loadSetLogAll();
  log.push(Object.assign({ id: "set-" + Date.now() + Math.random(), exercise: exKey, label, date, weight, reps }, extra || {}));
  saveSetLog(log);
}
function softDeleteSet(id) {
  const all = loadSetLogAll();
  const item = all.find(s => s.id === id);
  if (item) { item.deleted = true; item.deletedAt = Date.now(); }
  saveSetLog(all);
}
function lastSetFor(exKey, date) {
  const entries = loadSetLog().filter(s => s.exercise === exKey).sort((a, b) => a.date.localeCompare(b.date));
  const upToToday = entries.filter(s => s.date <= date);
  return upToToday.length ? upToToday[upToToday.length - 1] : null;
}
function setsFor(exKey, date) { return loadSetLog().filter(s => s.exercise === exKey && s.date === date); }

// ---- rest timer: shared floating-bubble module ----
const REST_PREFS_KEY = "garminDashboardRestPrefs_v1";
function loadRestPrefs() { return loadLS(REST_PREFS_KEY, {}); }
function saveRestPrefs(p) { saveLS(REST_PREFS_KEY, p); }
function restDurationFor(exKey) { return loadRestPrefs()[exKey] || 90; }

let restTimerInterval = null;
let restTimerEndsAt = 0; // absolute timestamp (ms) the timer finishes at - not a tick counter,
                          // since mobile browsers throttle/pause setInterval while backgrounded
let restTimerPausedRemaining = null; // seconds left, frozen while paused; null while running

function playRestBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) { /* audio not available, vibration still fires */ }
}
function restTimerSecondsLeft() {
  if (restTimerPausedRemaining != null) return restTimerPausedRemaining;
  return Math.max(0, Math.ceil((restTimerEndsAt - Date.now()) / 1000));
}
function updateRestBubbleDisplay() {
  document.getElementById("rt-bubble-display").textContent = restTimerSecondsLeft();
}
function stopRestTimer() {
  if (restTimerInterval) clearInterval(restTimerInterval);
  restTimerInterval = null;
  restTimerPausedRemaining = null;
  document.getElementById("rest-bubble").classList.remove("active");
}
function tickRestTimer() {
  if (restTimerPausedRemaining != null) return;
  const left = restTimerSecondsLeft();
  updateRestBubbleDisplay();
  if (left <= 0) {
    if (window.navigator.vibrate) window.navigator.vibrate([200, 100, 200]);
    playRestBeep();
    stopRestTimer();
  }
}
function startRestTimer(seconds, label) {
  stopRestTimer();
  restTimerEndsAt = Date.now() + seconds * 1000;
  restTimerPausedRemaining = null;
  document.getElementById("rt-bubble-label").textContent = label || "Hvile";
  document.getElementById("rt-bubble-pause").textContent = "Pause";
  updateRestBubbleDisplay();
  document.getElementById("rest-bubble").classList.add("active");
  restTimerInterval = setInterval(tickRestTimer, 1000);
}
document.getElementById("rt-bubble-pause").addEventListener("click", () => {
  if (restTimerPausedRemaining != null) {
    restTimerEndsAt = Date.now() + restTimerPausedRemaining * 1000;
    restTimerPausedRemaining = null;
    document.getElementById("rt-bubble-pause").textContent = "Pause";
  } else {
    restTimerPausedRemaining = restTimerSecondsLeft();
    document.getElementById("rt-bubble-pause").textContent = "Fortsett";
  }
});
document.getElementById("rt-bubble-skip").addEventListener("click", stopRestTimer);
// background tabs/apps throttle or fully pause setInterval (especially on iOS), so the display
// can go stale while you're away - catch up the instant you come back instead of waiting for
// the next (possibly delayed) tick, so a finished rest shows "ferdig" right away, not a frozen number.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && restTimerInterval) tickRestTimer();
});

function parseRepTarget(text) {
  const m = text.match(/(\d+)\s*[×x]\s*(\d+)(?:\s*[–\-]\s*(\d+))?/);
  if (!m) return null;
  const low = parseInt(m[2], 10);
  const high = m[3] ? parseInt(m[3], 10) : low;
  const after = text.slice(m.index + m[0].length).trimStart();
  const timeBased = after.startsWith("s") || after.startsWith("sek");
  return { low, high, timeBased };
}

function progressSuggestion(exKey, text, readiness) {
  const target = parseRepTarget(text);
  if (!target || target.timeBased) return null;
  const best = bestSetFor(exKey);
  if (!best || !best.reps) return null;
  const easing = readiness === "light" || readiness === "caution";
  if (best.reps >= target.high) {
    if (easing) return `Du klarte toppen av målet (${best.reps} reps) forrige gang, men hold vekten i dag siden kroppen signaliserer ekstra belastning.`;
    if (best.weight != null) return `Du klarte ${best.reps} reps forrige gang - prøv ${(best.weight + 2.5).toLocaleString()} kg i dag.`;
    return `Du klarte ${best.reps} reps forrige gang - prøv noen flere reps i dag.`;
  }
  if (best.reps < target.low) {
    return `Hold samme vekt og jobb mot ${target.low}+ reps i dag.`;
  }
  return `Du er i målsonen (${target.low}–${target.high} reps) - fortsett på samme vekt.`;
}

// Finner en "kjenn det i rumpa"-detalj for en øvelsestekst, ved å matche på hvilken nøkkel
// i DATA.gluteExerciseDetails som er en substreng av teksten - PROG_EXERCISES-strengene (og
// dermed sett-loggens indekser) trenger ikke endres for å koble dem sammen.
function findGluteDetail(text) {
  const details = DATA.gluteExerciseDetails || {};
  const key = Object.keys(details).find(k => text.includes(k));
  return key ? details[key] : null;
}

function exerciseRowHtml(sessKey, idx, text, date, readiness) {
  const exKey = sessKey + "::" + idx;
  const last = lastSetFor(exKey, date);
  const todaySets = setsFor(exKey, date);
  const pref = restDurationFor(exKey);
  const restOptions = [60, 90, 120, 180].map(s => `<option value="${s}" ${s === pref ? "selected" : ""}>${s}s</option>`).join("");
  const suggestion = progressSuggestion(exKey, text, readiness);
  const glute = findGluteDetail(text);
  const gluteExpanded = glute && gluteTipExpandedKey === exKey;
  return `<div class="exercise-row" data-ex="${exKey}">
    <div class="exercise-name">${text}</div>
    ${suggestion ? `<div class="exercise-suggestion">💡 ${suggestion}</div>` : ""}
    ${glute ? `<button class="btn ghost small glute-tip-toggle" data-ex-key="${exKey}">${gluteExpanded ? "Skjul tips" : "💡 Tips for å kjenne det i rumpa"}</button>` : ""}
    ${gluteExpanded ? `
      <div class="glute-tip-box">
        <div><b>Kjenn det her:</b> ${glute.feelItWhere}</div>
        ${glute.cues && glute.cues.length ? `<div style="margin-top:6px;"><b>Cues:</b><ul>${glute.cues.map(c => `<li>${c}</li>`).join("")}</ul></div>` : ""}
        ${glute.commonMistakes && glute.commonMistakes.length ? `<div style="margin-top:6px;"><b>Vanlige feil:</b><ul>${glute.commonMistakes.map(c => `<li>${c}</li>`).join("")}</ul></div>` : ""}
      </div>` : ""}
    <div class="set-log-form">
      <input type="number" step="0.5" class="set-weight-input" placeholder="kg" ${last && last.weight != null ? `value="${last.weight}"` : ""}>
      <input type="number" class="set-reps-input" placeholder="reps" ${last ? `value="${last.reps}"` : ""}>
      <button class="btn secondary small set-log-add">+ Logg sett</button>
      ${last ? `<button class="btn ghost small set-log-fill" style="font-size:11px;">Bruk forrige: ${last.weight != null ? last.weight + " kg × " : ""}${last.reps} reps</button>` : `<span style="font-size:11px;color:var(--muted)">ingen tidligere logg</span>`}
      <select class="rest-pref-select" data-ex="${exKey}">${restOptions}</select>
    </div>
    <div class="set-log-today">${todaySets.map((s, i) => `<span class="set-chip">Sett ${i + 1}: ${s.weight != null ? s.weight + " kg × " : ""}${s.reps} reps<button class="set-chip-remove" data-set-remove="${s.id}">✕</button></span>`).join("")}</div>
  </div>`;
}

function isBetterSet(a, b) {
  if (!b) return true;
  if (a.weight != null && b.weight != null) {
    return a.weight > b.weight || (a.weight === b.weight && a.reps > b.reps);
  }
  return a.reps > b.reps;
}
function bestSetFor(exKey) {
  const entries = loadSetLog().filter(s => s.exercise === exKey);
  let best = null;
  entries.forEach(s => { if (isBetterSet(s, best)) best = s; });
  return best;
}
function triggerConfetti() {
  const colors = ["#7a1f3d", "#e8a3b6", "#a46cc0", "#f6c667", "#9b3456"];
  const container = document.createElement("div");
  container.className = "confetti-container";
  for (let i = 0; i < 24; i++) {
    const piece = document.createElement("div");
    piece.className = "confetti-piece";
    piece.style.left = Math.random() * 100 + "vw";
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDelay = (Math.random() * 0.3) + "s";
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    container.appendChild(piece);
  }
  document.body.appendChild(container);
  setTimeout(() => container.remove(), 2200);
}

// ---------------------------------------------------------------- sete, kjerne og stabilitet
// Eget tilleggsprogram (2026-11-17) - gjenbruker addSet/setsFor/lastSetFor/softDeleteSet
// (samme lagringsmotor som resten av treningsplanen), bare med en egen exKey-serie
// ("stability::<nøkkel>") slik at ingenting blandes med gsA/gsB/gsC-loggen.
function stabilityExKey(key) { return "stability::" + key; }

const STABILITY_DIFFICULTY_LABELS = { lett: "Lett", passe: "Passe", tungt: "Tungt" };
const STABILITY_KNEE_LABELS = { ingen: "ingen reaksjon", lett: "lett ubehag", smerte: "smerte" };

// enkle, skjematiske strek-illustrasjoner (ikke anatomiske foto) - nok til å vise grunnposisjonen
const STABILITY_ILLUSTRATIONS = {
  glute_bridge: `<svg viewBox="0 0 160 100" class="stability-svg"><line x1="10" y1="92" x2="150" y2="92" class="stability-ground"/><circle cx="22" cy="80" r="9" class="stability-fig"/><line x1="31" y1="83" x2="75" y2="55" class="stability-fig"/><line x1="75" y1="55" x2="112" y2="80" class="stability-fig"/><line x1="112" y1="80" x2="126" y2="92" class="stability-fig"/><line x1="60" y1="66" x2="55" y2="40" class="stability-fig"/></svg>`,
  hip_abduction: `<svg viewBox="0 0 160 100" class="stability-svg"><line x1="10" y1="97" x2="150" y2="97" class="stability-ground"/><circle cx="22" cy="42" r="9" class="stability-fig"/><line x1="31" y1="46" x2="72" y2="70" class="stability-fig"/><line x1="72" y1="70" x2="60" y2="90" class="stability-fig"/><line x1="60" y1="90" x2="78" y2="96" class="stability-fig"/><line x1="72" y1="70" x2="132" y2="52" class="stability-fig-accent"/></svg>`,
  clamshell: `<svg viewBox="0 0 160 100" class="stability-svg"><line x1="10" y1="97" x2="150" y2="97" class="stability-ground"/><circle cx="22" cy="42" r="9" class="stability-fig"/><line x1="31" y1="46" x2="72" y2="70" class="stability-fig"/><line x1="72" y1="70" x2="98" y2="88" class="stability-fig"/><line x1="98" y1="88" x2="74" y2="95" class="stability-fig"/><line x1="72" y1="70" x2="102" y2="66" class="stability-fig-accent"/><line x1="102" y1="66" x2="80" y2="92" class="stability-fig-accent"/></svg>`,
  dead_bug: `<svg viewBox="0 0 160 100" class="stability-svg"><line x1="10" y1="95" x2="150" y2="95" class="stability-ground"/><circle cx="38" cy="86" r="9" class="stability-fig"/><line x1="47" y1="86" x2="95" y2="86" class="stability-fig"/><line x1="52" y1="84" x2="28" y2="52" class="stability-fig-accent"/><line x1="60" y1="84" x2="62" y2="58" class="stability-fig"/><line x1="90" y1="86" x2="90" y2="58" class="stability-fig"/><line x1="90" y1="58" x2="68" y2="48" class="stability-fig-accent"/><line x1="98" y1="86" x2="100" y2="60" class="stability-fig"/></svg>`,
  pallof_press: `<svg viewBox="0 0 160 100" class="stability-svg"><line x1="10" y1="97" x2="150" y2="97" class="stability-ground"/><rect x="14" y="36" width="8" height="8" class="stability-fig"/><line x1="22" y1="40" x2="110" y2="40" class="stability-dashed"/><circle cx="80" cy="20" r="9" class="stability-fig"/><line x1="80" y1="29" x2="80" y2="72" class="stability-fig"/><line x1="80" y1="72" x2="66" y2="97" class="stability-fig"/><line x1="80" y1="72" x2="94" y2="97" class="stability-fig"/><line x1="80" y1="40" x2="112" y2="40" class="stability-fig-accent"/></svg>`,
};

let stabilityExpandedDetail = null;

function stabilityExerciseHtml(ex) {
  const exKey = stabilityExKey(ex.key);
  const today = todayISO();
  const last = lastSetFor(exKey, today);
  const todaySets = setsFor(exKey, today);
  const expanded = stabilityExpandedDetail === ex.key;
  const detailHtml = expanded ? `
    <div class="stability-detail">
      <div class="stability-illustration">${STABILITY_ILLUSTRATIONS[ex.key] || ""}</div>
      <div class="stability-detail-block"><b>Startposisjon</b><div>${ex.startPosition}</div></div>
      <div class="stability-detail-block"><b>Steg for steg</b><ol>${ex.steps.map(s => `<li>${s}</li>`).join("")}</ol></div>
      <div class="stability-detail-block"><b>Muskler som trenes</b><div>${ex.muscles}</div></div>
      <div class="stability-detail-block"><b>Du bør kjenne det</b><div>${ex.feelItWhere}</div></div>
      <div class="stability-detail-block"><b>Vanlige feil</b><ul>${ex.commonMistakes.map(s => `<li>${s}</li>`).join("")}</ul></div>
      <div class="stability-detail-block"><b>Tilpasning for lange bein</b><div>${ex.longLegsNote}</div></div>
    </div>` : "";

  return `<div class="exercise-row stability-exercise" data-ex="${exKey}">
    <div class="exercise-name">${ex.name} <span class="stability-setsreps">${ex.sets} · ${ex.repsLabel}</span></div>
    <button class="btn ghost small stability-detail-toggle" data-key="${ex.key}">${expanded ? "Skjul detaljer" : "Detaljer"}</button>
    ${detailHtml}
    <div class="set-log-form stability-log-form">
      <input type="number" step="0.5" class="set-weight-input stability-weight" placeholder="kg/motstand (valgfritt)" ${last && last.weight != null ? `value="${last.weight}"` : ""}>
      <input type="number" class="set-reps-input stability-reps" placeholder="reps" ${last ? `value="${last.reps}"` : ""}>
      <select class="stability-difficulty-select">
        <option value="">Vanskelighetsgrad</option>
        <option value="lett">Lett</option>
        <option value="passe">Passe</option>
        <option value="tungt">Tungt</option>
      </select>
      <select class="stability-knee-select">
        <option value="ingen">Kneet: ingen reaksjon</option>
        <option value="lett">Kneet: lett ubehag</option>
        <option value="smerte">Kneet: smerte</option>
      </select>
      <label class="stability-technique-check"><input type="checkbox" class="stability-technique-checkbox" checked> God teknikk</label>
      <button class="btn secondary small stability-log-add" data-key="${ex.key}">+ Logg sett</button>
    </div>
    <div class="set-log-today">${todaySets.map((s, i) => `<span class="set-chip">Sett ${i + 1}: ${s.weight != null ? s.weight + " kg × " : ""}${s.reps} reps${s.difficulty ? ` · ${STABILITY_DIFFICULTY_LABELS[s.difficulty] || s.difficulty}` : ""}${s.knee && s.knee !== "ingen" ? ` · ⚠️ kne: ${STABILITY_KNEE_LABELS[s.knee] || s.knee}` : ""}<button class="set-chip-remove" data-set-remove="${s.id}">✕</button></span>`).join("")}</div>
  </div>`;
}

function renderKneeGuidance() {
  const el = document.getElementById("knee-guidance-card");
  if (!el) return;
  const criteria = DATA.kneeResumeCriteria || [];
  const cues = DATA.gluteTechniqueCues || [];
  el.innerHTML = `
    <h3 style="margin:0 0 6px;font-size:15px;">🦵 Kne - status og regler</h3>
    ${DATA.kneePauseNote ? `<div class="section-sub" style="margin-bottom:8px;">${DATA.kneePauseNote}</div>` : ""}
    ${criteria.length ? `
      <div class="section-sub" style="margin-bottom:2px;"><b>Klar for å løpe igjen når alt dette stemmer:</b></div>
      <ul class="section-sub" style="margin:0 0 8px;padding-left:18px;">${criteria.map(c => `<li>${c}</li>`).join("")}</ul>
      <div class="section-sub" style="margin-bottom:8px;">Start kort og rolig.</div>` : ""}
    ${DATA.kneePainRule ? `<div class="section-sub" style="margin-bottom:8px;"><b>Smerteregel:</b> ${DATA.kneePainRule}</div>` : ""}
    ${cues.length ? `
      <div class="section-sub" style="margin-bottom:2px;"><b>Teknikk for rumpeøvelser:</b></div>
      <ul class="section-sub" style="margin:0;padding-left:18px;">${cues.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
  `;
}

function renderStabilitySection() {
  const el = document.getElementById("stability-exercises");
  if (!el || !DATA.stabilityExercises) return;
  el.innerHTML = DATA.stabilityExercises.map(stabilityExerciseHtml).join("");

  el.querySelectorAll(".stability-detail-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      stabilityExpandedDetail = stabilityExpandedDetail === btn.dataset.key ? null : btn.dataset.key;
      renderStabilitySection();
    });
  });
  el.querySelectorAll(".stability-log-add").forEach(btn => {
    btn.addEventListener("click", () => {
      const row = btn.closest(".stability-exercise");
      const ex = DATA.stabilityExercises.find(x => x.key === btn.dataset.key);
      const reps = parseInt(row.querySelector(".stability-reps").value, 10);
      if (!reps) return;
      const weightRaw = parseFloat(row.querySelector(".stability-weight").value);
      const difficulty = row.querySelector(".stability-difficulty-select").value || null;
      const knee = row.querySelector(".stability-knee-select").value || null;
      const goodTechnique = row.querySelector(".stability-technique-checkbox").checked;
      addSet(stabilityExKey(ex.key), ex.name, todayISO(), isNaN(weightRaw) ? null : weightRaw, reps, { difficulty, knee, goodTechnique });
      renderStabilitySection();
      renderPrBoard();
    });
  });
  el.querySelectorAll("[data-set-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      softDeleteSet(btn.dataset.setRemove);
      renderStabilitySection();
      renderPrBoard();
    });
  });
}

function renderStabilityLockedLevels() {
  const el = document.getElementById("stability-locked-levels");
  if (!el || !DATA.stabilityLockedLevels) return;
  el.innerHTML = DATA.stabilityLockedLevels.map(lvl => `
    <div class="card stability-locked-card">
      <h4 style="margin:0 0 6px;font-size:14px;">${lvl.title} 🔒</h4>
      <ul class="stability-locked-list">${lvl.exercises.map(e => `<li>${e}</li>`).join("")}</ul>
    </div>
  `).join("");
}

// ---- kne-oppfølging: hvordan kneet reagerte etter økten, samme dag og morgenen etter -----
const KNEE_CHECKIN_KEY = "garminDashboardKneeCheckin_v1";
function loadKneeCheckins() { return loadLS(KNEE_CHECKIN_KEY, {}); }
function saveKneeCheckins(l) { saveLS(KNEE_CHECKIN_KEY, l); }
function kneeCheckinFor(date) { return loadKneeCheckins()[date] || {}; }
function setKneeCheckin(date, patch) {
  const l = loadKneeCheckins();
  l[date] = Object.assign({}, l[date] || {}, patch);
  saveKneeCheckins(l);
}
function renderKneeCheckin() {
  const el = document.getElementById("knee-checkin-form");
  if (!el) return;
  const today = todayISO();
  const yesterday = isoAddDays(today, -1);
  const todayEntry = kneeCheckinFor(today);
  const yesterdayEntry = kneeCheckinFor(yesterday);
  const opts = ["", "Ingen endring", "Litt verre", "Mye verre"];
  const selectHtml = (value, cls) => `<select class="${cls}">${opts.map(o => `<option value="${o}" ${o === (value || "") ? "selected" : ""}>${o || "Velg..."}</option>`).join("")}</select>`;
  el.innerHTML = `
    <label class="mvd-settings-field">Kneet senere i dag (etter dagens økt)${selectHtml(todayEntry.sameDay, "knee-checkin-sameday")}</label>
    <label class="mvd-settings-field">Kneet neste morgen (for gårsdagens økt)${selectHtml(yesterdayEntry.nextMorning, "knee-checkin-nextmorning")}</label>
    <button class="btn ghost small" id="knee-checkin-save">Lagre</button>
    <div class="badday-saved-msg" id="knee-checkin-saved-msg"></div>
  `;
  document.getElementById("knee-checkin-save").addEventListener("click", () => {
    const sameDay = el.querySelector(".knee-checkin-sameday").value;
    const nextMorning = el.querySelector(".knee-checkin-nextmorning").value;
    if (sameDay) setKneeCheckin(today, { sameDay });
    if (nextMorning) setKneeCheckin(yesterday, { nextMorning });
    flashSaved("knee-checkin-saved-msg", "Lagret ✓");
  });
}

function renderPrBoard() {
  const card = document.getElementById("pr-board-card");
  const log = loadSetLog();
  if (!log.length) {
    card.innerHTML = `<h3 style="margin:0 0 4px;font-size:15px;">Personlige rekorder</h3><div class="section-sub" style="margin:0;">Logg sett på treningsøktene for å se rekordene dine her.</div>`;
    return;
  }
  const byEx = {};
  log.forEach(s => {
    const cur = byEx[s.exercise];
    if (isBetterSet(s, cur)) byEx[s.exercise] = { label: s.label, weight: s.weight, reps: s.reps, date: s.date };
  });
  const rows = Object.values(byEx).sort((a, b) => b.date.localeCompare(a.date));
  card.innerHTML = `<h3 style="margin:0 0 10px;font-size:15px;">Personlige rekorder</h3>` +
    rows.map(r => `<div class="pr-row"><span class="pr-ex">${r.label}</span><b>${r.weight != null ? r.weight + " kg × " + r.reps : r.reps + " reps"}</b></div>`).join("");
}

function renderRestTimer() {
  const card = document.getElementById("rest-timer-card");
  card.innerHTML = `
    <h3 style="margin:0 0 4px;font-size:15px;">Hviletimer</h3>
    <div class="section-sub" style="margin:0 0 10px;">Starter automatisk når du logger et sett (lengden er satt per øvelse). Du kan også starte den manuelt her.</div>
    <div class="rt-presets">
      <button class="btn secondary small" data-rt="60">60 s</button>
      <button class="btn secondary small" data-rt="90">90 s</button>
      <button class="btn secondary small" data-rt="120">120 s</button>
      <button class="btn secondary small" data-rt="180">180 s</button>
      <button class="btn ghost small" id="rt-stop">Stopp</button>
    </div>
  `;
  card.querySelectorAll("[data-rt]").forEach(btn =>
    btn.addEventListener("click", () => startRestTimer(parseInt(btn.dataset.rt, 10), "Hviletimer")));
  document.getElementById("rt-stop").addEventListener("click", stopRestTimer);
}

function renderPlan() {
  const p = DATA.program;
  if (!p) return;
  const overrides = loadPlanOverrides();

  const weekTag = p.weekIsDeload ? `Uke ${p.currentWeek} · Deload` : `Uke ${p.currentWeek} av 4`;
  document.getElementById("plan-sub").textContent = `${weekTag} · ${p.weekFocus}`;

  const todayDay = p.week.find(d => d.isToday);
  const resolved = resolvePlanDay(todayDay, overrides);
  const readinessLabel = { go: "Klar for økta", caution: "Vurder en lettere variant", light: "Prioriter hvile i dag" }[p.today.readiness];
  const card = document.getElementById("plan-today");
  card.className = "plan-card " + p.today.readiness;

  let body = `<div class="plan-eyebrow">I dag · ${readinessLabel}</div>`;
  body += `<div class="plan-head"><h3>${resolved.label}</h3>${swapSelectHtml(todayDay.date, resolved.key)}</div>`;

  if (resolved.done) {
    const extra = resolved.matchedActivity ? `: ${resolved.matchedActivity.name} (${resolved.matchedActivity.minutes} min)` : "";
    body += `<div class="done-badge">✓ Gjort${extra}</div>`;
  } else if (resolved.type === "rest") {
    body += `<div style="color:var(--muted);font-size:13px">Ingen planlagt økt i dag. Ta en rolig tur hvis du har overskudd.</div>`;
  } else {
    if (resolved.type === "strength" && DATA.legDayWarmup && DATA.legDayWarmup.length) {
      body += `<div class="section-sub" style="margin-bottom:4px;"><b>Oppvarming</b></div>
        <ul class="section-sub" style="margin:0 0 12px;padding-left:18px;">${DATA.legDayWarmup.map(w => `<li>${w}</li>`).join("")}</ul>`;
    }
    if (resolved.exercises) {
      const hasRepeatable = resolved.exercises.some((e, idx) => {
        const exKey = resolved.key + "::" + idx;
        return lastSetFor(exKey, todayDay.date) && setsFor(exKey, todayDay.date).length === 0;
      });
      if (hasRepeatable) {
        body += `<button class="btn ghost small repeat-session-btn" style="margin-bottom:10px;">🔁 Gjenta forrige økt</button>`;
      }
      body += `<div class="exercises">${resolved.exercises.map((e, idx) => exerciseRowHtml(resolved.key, idx, e, todayDay.date, p.today.readiness)).join("")}</div>`;
    }
    if (resolved.cycleNote) {
      body += `<div class="exercises"><div>${resolved.cycleNote}</div></div>`;
    }
    if (resolved.type === "strength") {
      body += `<div style="margin-top:10px;font-size:13px;color:var(--muted)">Kjenner du det i kneet på en øvelse? Reduser bevegelsesutslaget eller bytt den ut - ikke press gjennom smerte.</div>`;
    }
  }

  body += `<ul class="plan-reasons">${p.today.reasons.map(r => `<li>${r}</li>`).join("")}</ul>`;
  card.innerHTML = body;

  const repeatBtn = card.querySelector(".repeat-session-btn");
  if (repeatBtn) {
    repeatBtn.addEventListener("click", () => {
      let anyPR = false;
      resolved.exercises.forEach((e, idx) => {
        const exKey = resolved.key + "::" + idx;
        if (setsFor(exKey, todayDay.date).length > 0) return;
        const last = lastSetFor(exKey, todayDay.date);
        if (!last) return;
        const prevBest = bestSetFor(exKey);
        addSet(exKey, e, todayDay.date, last.weight, last.reps);
        if (isBetterSet({ weight: last.weight, reps: last.reps }, prevBest)) anyPR = true;
      });
      if (anyPR && loadSettings().personalityEnabled) triggerConfetti();
      renderPlan();
      renderPrBoard();
      renderHjemSession();
    });
  }

  card.querySelectorAll(".exercise-row").forEach(row => {
    const exKey = row.dataset.ex;
    const wIn = row.querySelector(".set-weight-input");
    const rIn = row.querySelector(".set-reps-input");
    const tipToggle = row.querySelector(".glute-tip-toggle");
    if (tipToggle) {
      tipToggle.addEventListener("click", () => {
        gluteTipExpandedKey = gluteTipExpandedKey === exKey ? null : exKey;
        renderPlan();
      });
    }
    const fillBtn = row.querySelector(".set-log-fill");
    if (fillBtn) {
      fillBtn.addEventListener("click", () => {
        const last = lastSetFor(exKey, todayDay.date);
        if (!last) return;
        if (last.weight != null) wIn.value = last.weight;
        rIn.value = last.reps;
      });
    }
    row.querySelectorAll("[data-set-remove]").forEach(delBtn => {
      delBtn.addEventListener("click", () => {
        softDeleteSet(delBtn.dataset.setRemove);
        renderPlan();
        renderPrBoard();
      });
    });
    const restSelect = row.querySelector(".rest-pref-select");
    if (restSelect) {
      restSelect.addEventListener("change", () => {
        const prefs = loadRestPrefs();
        prefs[exKey] = parseInt(restSelect.value, 10);
        saveRestPrefs(prefs);
      });
    }
    const addBtn = row.querySelector(".set-log-add");
    if (!addBtn) return;
    addBtn.addEventListener("click", () => {
      const weight = wIn.value ? parseFloat(wIn.value) : null;
      const reps = parseInt(rIn.value, 10);
      if (!reps) return;
      const label = row.querySelector(".exercise-name").textContent;
      const prevBest = bestSetFor(exKey);
      addSet(exKey, label, todayDay.date, weight, reps);
      if (isBetterSet({ weight, reps }, prevBest) && loadSettings().personalityEnabled) triggerConfetti();
      startRestTimer(restDurationFor(exKey), label);
      renderPlan();
      renderPrBoard();
      renderHjemSession();
    });
  });

  const weekEl = document.getElementById("plan-week");
  weekEl.innerHTML = p.week.map(d => {
    const r = resolvePlanDay(d, overrides);
    const missed = r.type !== "rest" && !d.isToday && d.date < p.today.date && r.done !== true;
    const mark = r.done === true ? "✓"
      : d.isToday ? "●"
      : r.type === "rest" ? "–"
      : missed ? "○"
      : "";
    return `<div class="week-day${d.isToday ? " today" : ""}" data-date="${d.date}">
      <div class="wd"><span>${d.weekday}</span>${d.date >= p.today.date ? `<span class="week-day-handle" title="Dra for å bytte dag">⠿</span>` : ""}</div>
      <div class="sess">${r.label}</div>
      <div class="mark${missed ? " missed" : ""}" ${missed ? `title="Ikke logget - helt greit, fortsett i dag."` : ""}>${mark}</div>
      ${swapSelectHtml(d.date, r.key)}
    </div>`;
  }).join("");

  document.querySelectorAll("select.swap").forEach(sel => {
    sel.addEventListener("change", () => {
      const current = loadPlanOverrides();
      const day = p.week.find(x => x.date === sel.dataset.date);
      if (isDefaultKeyForDay(day, sel.value)) {
        delete current[sel.dataset.date];
      } else {
        current[sel.dataset.date] = sel.value;
      }
      savePlanOverrides(current);
      renderPlan();
    });
  });

  setupWeekDrag();
}
renderPlan();
renderMissedDayPrompt();
renderPrBoard();
renderRestTimer();
renderKneeGuidance();
renderStabilitySection();
renderStabilityLockedLevels();
renderKneeCheckin();

// ---------------------------------------------------------------- nutrition
const EXTRAS_KEY = "garminDashboardExtras_v1";
const CUSTOM_MEALS_KEY = "garminDashboardCustomMeals_v1";
const MEAL_LOG_KEY = "garminDashboardMealLog_v1";
const FAVORITE_MEALS_KEY = "garminDashboardFavoriteMeals_v1";
const MEAL_TYPE_ORDER = ["breakfast", "lunch", "snack", "dinner"];
const MEAL_TYPE_LABELS = { breakfast: "Frokost", lunch: "Lunsj", snack: "Mellommåltid", dinner: "Middag" };
// Kalorianslag (spesielt for hjemmelagde/øyemål-retter) har lett for å bli satt litt lavt -
// vis derfor alltid kalorier med en fast +5% margin, uansett hvor de vises i appen. Protein
// og kalorimålet hennes vises alltid uendret (rått anslag). Legges kun på ved visning -
// aldri lagret, og aldri lagt på igjen ved ny visning/summering av et allerede margin-justert tall.
const KCAL_MARGIN = 1.05;
function withKcalMargin(rawKcal) { return Math.round((rawKcal || 0) * KCAL_MARGIN); }

// dagens inntak ført manuelt fra Lifesum - når denne finnes for en dato, er den fasiten for
// hvor mye som faktisk er spist den dagen (ikke måltidsloggen/ekstra-loggen), slik at hun
// slipper å føre maten to steder
const LIFESUM_LOG_KEY = "garminDashboardLifesumLog_v1";
function loadLifesumLog() { return loadLS(LIFESUM_LOG_KEY, {}); }
function saveLifesumLog(l) { saveLS(LIFESUM_LOG_KEY, l); }
function lifesumEntryFor(date) { return loadLifesumLog()[date] || null; }
function setLifesumEntry(date, entry) {
  const l = loadLifesumLog();
  l[date] = entry;
  saveLifesumLog(l);
}
function clearLifesumEntry(date) {
  const l = loadLifesumLog();
  delete l[date];
  saveLifesumLog(l);
}
// planlagt rett per dag+måltidstype (satt i Planlegg-fanen) - definert her, før
// renderNutrition() sitt første kall lenger ned, siden den leser plannedMealFor()
// for å vise "📌 Planlagt"-merket
const MEAL_PLAN_OVERRIDES_KEY = "garminDashboardMealPlanOverrides_v1";
function loadMealPlanOverrides() { return loadLS(MEAL_PLAN_OVERRIDES_KEY, {}); }
function saveMealPlanOverrides(o) { saveLS(MEAL_PLAN_OVERRIDES_KEY, o); }
function mealPlanKey(date, type) { return `${date}|${type}`; }
function plannedMealFor(date, type) { return loadMealPlanOverrides()[mealPlanKey(date, type)] || null; }
function setPlannedMeal(date, type, name) {
  const o = loadMealPlanOverrides();
  o[mealPlanKey(date, type)] = name;
  saveMealPlanOverrides(o);
}
function clearPlannedMeal(date, type) {
  const o = loadMealPlanOverrides();
  delete o[mealPlanKey(date, type)];
  saveMealPlanOverrides(o);
}
const CUSTOM_INGREDIENTS_KEY = "garminDashboardCustomIngredients_v1";
const MEAL_ING_OVERRIDES_KEY = "garminDashboardMealIngOverrides_v1";
function loadCustomMeals() { return Object.assign({ breakfast: [], lunch: [], snack: [], dinner: [] }, loadLS(CUSTOM_MEALS_KEY, {})); }
function saveCustomMeals(m) { saveLS(CUSTOM_MEALS_KEY, m); }

function loadFavoriteMeals() { return Object.assign({ breakfast: [], lunch: [], snack: [], dinner: [] }, loadLS(FAVORITE_MEALS_KEY, {})); }
function saveFavoriteMeals(f) { saveLS(FAVORITE_MEALS_KEY, f); }
function isFavoriteMeal(type, name) { return loadFavoriteMeals()[type].includes(name); }
function toggleFavoriteMeal(type, name) {
  const f = loadFavoriteMeals();
  const i = f[type].indexOf(name);
  if (i === -1) f[type].push(name); else f[type].splice(i, 1);
  saveFavoriteMeals(f);
}

// Historisk logg fra da måltider kunne merkes "spist" i appen - ikke lenger skrevet til
// (hun logger alt via Lifesum nå), men dayNutritionTotals() leser den fortsatt som fallback
// for gamle datoer som ble logget før den endringen.
function loadMealLog() { return loadLS(MEAL_LOG_KEY, []); }

// ---- ingredient catalog (built-in + her own additions) and per-day swap overrides ----
function loadCustomIngredients() { return loadLS(CUSTOM_INGREDIENTS_KEY, {}); }
function saveCustomIngredients(c) { saveLS(CUSTOM_INGREDIENTS_KEY, c); }
function getIngredient(key) {
  const custom = loadCustomIngredients();
  return custom[key] || DATA.ingredientCatalog[key] || null;
}
function ingredientOptionsForSelect(selectedKey) {
  const all = Object.assign({}, DATA.ingredientCatalog, loadCustomIngredients());
  const keys = Object.keys(all).sort((a, b) => all[a].label.localeCompare(all[b].label, "no"));
  return keys.map(k => `<option value="${k}" ${k === selectedKey ? "selected" : ""}>${all[k].label}</option>`).join("");
}
function ingOverrideKey(date, type, optIdx, itemIdx) { return `${date}|${type}|${optIdx}|${itemIdx}`; }
function loadMealIngOverrides() { return loadLS(MEAL_ING_OVERRIDES_KEY, {}); }
function saveMealIngOverrides(o) { saveLS(MEAL_ING_OVERRIDES_KEY, o); }
function getIngOverride(date, type, optIdx, itemIdx) {
  return loadMealIngOverrides()[ingOverrideKey(date, type, optIdx, itemIdx)] || null;
}
function setIngOverride(date, type, optIdx, itemIdx, ing, amount) {
  const o = loadMealIngOverrides();
  o[ingOverrideKey(date, type, optIdx, itemIdx)] = { ing, amount };
  saveMealIngOverrides(o);
}
function clearIngOverride(date, type, optIdx, itemIdx) {
  const o = loadMealIngOverrides();
  delete o[ingOverrideKey(date, type, optIdx, itemIdx)];
  saveMealIngOverrides(o);
}
// recomputes a built-in option's macros for the given date, applying any ingredient
// swaps logged for that day - custom (no-ingredient) meals pass through unchanged.
function effectiveMealOption(type, optIdx, opt, date) {
  if (!opt.items || !opt.items.some(i => i.ing)) {
    return Object.assign({}, opt, { effectiveItems: (opt.items || []).map(i => ({ text: i.text })) });
  }
  let kcal = opt.extraKcal || 0;
  let protein = opt.extraProtein || 0;
  const effectiveItems = opt.items.map((item, itemIdx) => {
    if (!item.ing) return { text: item.text };
    const override = getIngOverride(date, type, optIdx, itemIdx);
    const ing = override ? override.ing : item.ing;
    const amount = override ? override.amount : item.amount;
    const data = getIngredient(ing);
    if (data) {
      kcal += data.kcal100 * amount / 100;
      protein += data.protein100 * amount / 100;
    }
    return {
      ing, amount, itemIdx,
      label: data ? data.label : ing,
      display: override ? `${amount} g` : (item.display || `${amount} g`),
      overridden: !!override,
    };
  });
  return { name: opt.name, kcal: Math.round(kcal), protein: Math.round(protein), effectiveItems };
}

// totals actually eaten on a given date. If a Lifesum entry exists for that date, it's the
// source of truth (she logs the real thing there - no point also totalling meal-log/extras
// and risking double counting). Otherwise falls back to meals explicitly logged that day
// (breakfast included - nothing is assumed eaten until you log it) + anything logged as an "extra".
function dayNutritionTotals(date) {
  const lifesum = lifesumEntryFor(date);
  if (lifesum) {
    return {
      kcal: lifesum.kcal || 0,
      protein: lifesum.protein || 0,
      fat: lifesum.fat || 0,
      carbs: lifesum.carbs || 0,
      mealsLogged: [],
      extras: [],
      fromLifesum: true,
    };
  }
  const meals = loadMealLog().filter(m => m.date === date);
  const extrasForDay = loadExtras().filter(e => e.date === date);
  const extrasKcal = extrasForDay.reduce((s, e) => s + (e.kcal || 0), 0);
  const extrasProtein = extrasForDay.reduce((s, e) => s + (e.protein || 0), 0);
  return {
    kcal: meals.reduce((s, m) => s + (m.kcal || 0), 0) + extrasKcal,
    protein: meals.reduce((s, m) => s + (m.protein || 0), 0) + extrasProtein,
    mealsLogged: meals,
    extras: extrasForDay,
  };
}

// transient UI state (not persisted)
let openIngSwapKey = null;
let openIngSwapShowCustomForm = false;
let kostholdExpandedDetail = null;
const kostholdExpandedTypes = new Set();
let kostholdNewOptionOpenType = null;
let kostholdGoalEditOpen = false;

// kompakt rad for ett måltidsforslag - utvides til ingredienser/bytte bare når "Detaljer" er åpnet
function mealRowHtml(type, idx, opt, meta, focus) {
  const hasItems = (opt.effectiveItems || []).length > 0;
  const detailKey = `${type}:${idx}`;
  const expanded = hasItems && kostholdExpandedDetail === detailKey;
  const isFav = isFavoriteMeal(type, opt.name);

  let detailHtml = "";
  if (expanded) {
    const itemsHtml = opt.effectiveItems.map(item => {
      if (item.text) return `<span class="meal-item-text">${item.text}</span>`;
      const key = ingOverrideKey(todayISO(), type, idx, item.itemIdx);
      return `<span class="meal-item-ing${item.overridden ? " meal-item-overridden" : ""}">
        ${item.display} ${item.label}
        <button class="meal-ing-swap-btn" data-swap-key="${key}">Endre</button>
        ${item.overridden ? `<button class="meal-ing-reset-btn" data-type="${type}" data-opt-idx="${idx}" data-item-idx="${item.itemIdx}">↺</button>` : ""}
      </span>`;
    }).join("");
    let swapFormHtml = "";
    opt.effectiveItems.forEach(item => {
      if (item.text) return;
      const key = ingOverrideKey(todayISO(), type, idx, item.itemIdx);
      if (openIngSwapKey !== key) return;
      swapFormHtml = `<div class="ing-swap-form">
        <div class="section-sub" style="margin:0 0 2px;">Behold samme ingrediens og bare endre gram, eller velg en annen - begge deler oppdaterer kcal/protein.</div>
        <div class="ing-swap-row">
          <select class="ing-swap-select">${ingredientOptionsForSelect(item.ing)}</select>
          <input type="number" class="ing-swap-amount" value="${item.amount}"> g
          <button class="btn small ing-swap-save" data-type="${type}" data-opt-idx="${idx}" data-item-idx="${item.itemIdx}">Lagre</button>
          <button class="btn ghost small ing-swap-cancel">Avbryt</button>
        </div>
        ${openIngSwapShowCustomForm
          ? `<div class="ing-new-form">
              <input type="text" class="ing-new-name" placeholder="Navn på ny ingrediens">
              <input type="number" class="ing-new-kcal" placeholder="kcal/100g">
              <input type="number" class="ing-new-protein" placeholder="protein/100g">
              <button class="btn ghost small ing-new-save" data-type="${type}" data-opt-idx="${idx}" data-item-idx="${item.itemIdx}">Legg til og bruk</button>
            </div>`
          : `<button class="btn ghost small ing-swap-new-toggle">+ Legg til ny ingrediens</button>`}
      </div>`;
    });
    detailHtml = `<div class="meal-items">${itemsHtml}</div>${swapFormHtml}`;
  }

  return `<div class="meal-option">
    <div class="meal-head">
      <button class="meal-fav-btn${isFav ? " active" : ""}" data-fav-type="${type}" data-fav-name="${opt.name}" title="Favoritt">${isFav ? "⭐" : "☆"}</button>
      <b>${opt.name}</b>
      ${opt.planned ? `<span class="meal-planned-badge">📌 Planlagt</span>` : ""}
      ${focus ? `<span class="meal-macro">${opt.protein} g protein</span>` : ""}
      ${meta.removeId ? `<button class="meal-option-remove" data-meal-remove="${meta.removeId}">✕</button>` : ""}
    </div>
    ${hasItems ? `<div class="meal-row-actions">
      <button class="btn ghost small meal-detail-toggle" data-detail-key="${detailKey}">${expanded ? "Skjul detaljer" : "Detaljer"}</button>
    </div>` : ""}
    ${detailHtml}
  </div>`;
}

function renderMealTypeCard(type) {
  const n = DATA.nutritionPlan;
  const today = todayISO();
  const group = n[type];
  const focus = loadSettings().kostholdFocusMode;
  const custom = loadCustomMeals()[type] || [];
  const allOptions = group.options.map((o, idx) => ({ o, idx, custom: false }))
    .concat(custom.map((o, i) => ({ o, idx: group.options.length + i, custom: true })));

  const favs = loadFavoriteMeals()[type] || [];
  const planned = plannedMealFor(today, type);
  const scoreOf = x => (x.o.name === planned ? 2 : 0) + (favs.includes(x.o.name) ? 1 : 0);
  // blant like score (f.eks. ingen er favoritt/planlagt) - vis de mest proteineffektive
  // rettene først, siden hun vil ha mest mulig protein per kalori i underskudd
  const proteinDensity = o => (o.protein || 0) / Math.max(1, o.kcal || 1);
  const sorted = allOptions.map((x, i) => ({ x, i })).sort((a, b) => {
    const scoreDiff = scoreOf(b.x) - scoreOf(a.x);
    if (scoreDiff !== 0) return scoreDiff;
    const densityDiff = proteinDensity(b.x.o) - proteinDensity(a.x.o);
    if (Math.abs(densityDiff) > 0.0001) return densityDiff;
    return a.i - b.i;
  }).map(w => w.x);
  const expanded = kostholdExpandedTypes.has(type);
  const visible = expanded ? sorted : sorted.slice(0, 3);
  const hiddenCount = sorted.length - visible.length;

  const rowsHtml = visible.map(x => {
    const eOpt = effectiveMealOption(type, x.idx, x.o, today);
    eOpt.planned = x.o.name === planned;
    return mealRowHtml(type, x.idx, eOpt, { removeId: x.custom ? x.o.id : null }, focus);
  }).join("");

  const moreHtml = hiddenCount > 0
    ? `<button class="btn ghost small kosthold-more-btn" data-more-type="${type}">Vis ${hiddenCount} flere forslag</button>`
    : (expanded && sorted.length > 3 ? `<button class="btn ghost small kosthold-more-btn" data-more-type="${type}">Vis færre</button>` : "");

  const newOptFormHtml = kostholdNewOptionOpenType === type ? `
    <div class="log-form meal-add-form">
      <input type="text" id="meal-add-name-${type}" placeholder="Navn">
      <input type="number" step="10" id="meal-add-kcal-${type}" placeholder="kcal">
      <input type="number" step="1" id="meal-add-protein-${type}" placeholder="protein g">
      <button class="btn ghost small" data-meal-add="${type}">Legg til</button>
    </div>` : "";

  const bodyHtml = rowsHtml + moreHtml
    + `<button class="btn ghost small kosthold-newopt-toggle" data-newopt-type="${type}">+ Nytt forslag</button>`
    + newOptFormHtml;

  return `<div class="card kosthold-meal-card">
    <div class="kosthold-meal-card-head"><h4>${group.label}</h4></div>
    ${bodyHtml}
  </div>`;
}

// gjør "X g protein igjen" konkret og handlingsorientert i stedet for bare et tall
function proteinEquivalentNote(gramsNeeded) {
  const cat = DATA.ingredientCatalog || {};
  const chickenPer100 = (cat.kyllingfilet || {}).protein100 || 31;
  const skyrPer100 = (cat.skyr || {}).protein100 || 10;
  const chickenG = Math.round(gramsNeeded / chickenPer100 * 100);
  const skyrServings = Math.round((gramsNeeded / (skyrPer100 * 1.5)) * 2) / 2; // ett beger skyr ≈ 150 g
  const skyrText = skyrServings > 0 ? `${skyrServings} beger skyr` : null;
  return `Tilsvarer ca. ${chickenG} g kyllingfilet${skyrText ? ` eller ${skyrText}` : ""} for å nå målet.`;
}

function renderKostholdToday() {
  const n = DATA.nutritionPlan;
  const el = document.getElementById("kosthold-today-card");
  if (!n || !el) return;
  const focus = loadSettings().kostholdFocusMode;
  const modeNote = document.getElementById("kosthold-mode-note");
  if (modeNote) {
    modeNote.textContent = focus ? "" : "Livsstilsmodus er på - tall er skjult, men logging og favoritter fungerer som vanlig.";
  }

  if (!focus) {
    el.innerHTML = `<div class="section-sub" style="margin:0;">God dag med maten, uansett hvordan den ser ut i tall. 🌿</div>`;
    return;
  }

  const totals = dayNutritionTotals(todayISO());
  const kcalShown = withKcalMargin(totals.kcal);
  const remaining = n.dailyKcal - kcalShown;
  // rolig fargekode (samme dempede farger som budsjett-stolpene) - en rask visuell pekepinn,
  // ikke et varsel. Kun ett steg over normalt teller som "over": en liten margin først.
  const kcalCls = kcalShown <= n.dailyKcal ? "good" : kcalShown <= n.dailyKcal * 1.1 ? "warn" : "over";
  const proteinCls = totals.protein >= n.proteinMin ? "good" : totals.protein >= n.proteinMin * 0.8 ? "warn" : "over";
  const proteinGap = n.proteinMin - totals.protein;
  el.innerHTML = `
    <h3 style="margin:0 0 10px;font-size:15px;">Dagens oversikt</h3>
    <div class="kcal-row">
      <div class="kcal-chip ${kcalCls}">Spist<b>~${kcalShown} kcal</b></div>
      <div class="kcal-chip ${kcalCls}">${remaining >= 0 ? "Igjen av målet" : "Over målet"}<b>${Math.abs(remaining)} kcal</b></div>
      <div class="kcal-chip ${proteinCls}">Protein<b>${totals.protein} / ${n.proteinMin} g</b></div>
    </div>
    ${proteinGap > 5 ? `<div class="section-sub" style="margin-top:6px;">${proteinEquivalentNote(proteinGap)}</div>` : ""}
    ${totals.fromLifesum ? `<div class="section-sub" style="margin-top:6px;">Hentet fra Lifesum-innføringen din i dag${totals.fat || totals.carbs ? ` · ${totals.fat || 0} g fett · ${totals.carbs || 0} g karbo` : ""}.</div>` : ""}
    <div class="section-sub" style="margin:10px 0 0;">Mål: ${n.dailyKcal} kcal · ${n.proteinMin} g+ protein
      <button class="btn ghost small" id="kosthold-goal-edit-toggle" style="margin-left:6px;">Endre mål</button>
    </div>
    <div class="section-sub" style="margin-top:6px;font-style:italic;">Kalorier vises med 5 % anslagsmargin. Protein vises som vanlig anslag.</div>
    ${kostholdGoalEditOpen ? `
      <div class="log-form" style="margin-top:10px;">
        <input type="number" step="50" id="kcal-goal-input" value="${n.dailyKcal}" placeholder="kcal-mål">
        <button class="btn ghost small" id="kcal-goal-save">Lagre</button>
        <input type="number" step="5" id="protein-goal-input" value="${n.proteinMin}" placeholder="proteinmål">
        <button class="btn ghost small" id="protein-goal-save">Lagre</button>
      </div>` : ""}
  `;

  const goalToggle = document.getElementById("kosthold-goal-edit-toggle");
  if (goalToggle) goalToggle.addEventListener("click", () => { kostholdGoalEditOpen = !kostholdGoalEditOpen; renderKostholdToday(); });
  const kcalGoalSave = document.getElementById("kcal-goal-save");
  if (kcalGoalSave) kcalGoalSave.addEventListener("click", () => {
    const val = parseInt(document.getElementById("kcal-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.dailyKcal = val;
    saveSettings(s);
    DATA.nutritionPlan.dailyKcal = val;
    kostholdGoalEditOpen = false;
    renderKostholdToday();
    renderExtras();
    renderHjemKcalRing();
  });
  const proteinGoalSave = document.getElementById("protein-goal-save");
  if (proteinGoalSave) proteinGoalSave.addEventListener("click", () => {
    const val = parseInt(document.getElementById("protein-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.proteinMin = val;
    saveSettings(s);
    DATA.nutritionPlan.proteinMin = val;
    kostholdGoalEditOpen = false;
    renderKostholdToday();
  });
}

function renderKostholdMealCards() {
  const n = DATA.nutritionPlan;
  const el = document.getElementById("kosthold-meal-cards");
  if (!n || !el) return;
  const today = todayISO();

  el.innerHTML = MEAL_TYPE_ORDER.map(renderMealTypeCard).join("") + `<div class="nutrition-note">${n.note}</div>`;

  el.querySelectorAll(".meal-fav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      toggleFavoriteMeal(btn.dataset.favType, btn.dataset.favName);
      renderNutrition();
    });
  });
  el.querySelectorAll(".meal-detail-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      kostholdExpandedDetail = kostholdExpandedDetail === btn.dataset.detailKey ? null : btn.dataset.detailKey;
      openIngSwapKey = null;
      openIngSwapShowCustomForm = false;
      renderNutrition();
    });
  });
  el.querySelectorAll(".kosthold-more-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.moreType;
      if (kostholdExpandedTypes.has(type)) kostholdExpandedTypes.delete(type); else kostholdExpandedTypes.add(type);
      renderNutrition();
    });
  });
  el.querySelectorAll(".kosthold-newopt-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      kostholdNewOptionOpenType = kostholdNewOptionOpenType === btn.dataset.newoptType ? null : btn.dataset.newoptType;
      renderNutrition();
    });
  });

  el.querySelectorAll(".meal-ing-swap-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      openIngSwapKey = openIngSwapKey === btn.dataset.swapKey ? null : btn.dataset.swapKey;
      openIngSwapShowCustomForm = false;
      renderNutrition();
    });
  });
  el.querySelectorAll(".meal-ing-reset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      clearIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10));
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });
  el.querySelectorAll(".ing-swap-cancel").forEach(btn => {
    btn.addEventListener("click", () => { openIngSwapKey = null; renderNutrition(); });
  });
  el.querySelectorAll(".ing-swap-new-toggle").forEach(btn => {
    btn.addEventListener("click", () => { openIngSwapShowCustomForm = true; renderNutrition(); });
  });
  el.querySelectorAll(".ing-swap-save").forEach(btn => {
    btn.addEventListener("click", () => {
      const form = btn.closest(".ing-swap-form");
      const ing = form.querySelector(".ing-swap-select").value;
      const amount = parseFloat(form.querySelector(".ing-swap-amount").value) || 0;
      setIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10), ing, amount);
      openIngSwapKey = null;
      openIngSwapShowCustomForm = false;
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });
  el.querySelectorAll(".ing-new-save").forEach(btn => {
    btn.addEventListener("click", () => {
      const form = btn.closest(".ing-swap-form");
      const name = form.querySelector(".ing-new-name").value.trim();
      const kcal100 = parseFloat(form.querySelector(".ing-new-kcal").value);
      const protein100 = parseFloat(form.querySelector(".ing-new-protein").value) || 0;
      if (!name || !kcal100) return;
      const amount = parseFloat(form.querySelector(".ing-swap-amount").value) || 100;
      const key = "custom_" + Date.now();
      const customIng = loadCustomIngredients();
      customIng[key] = { label: name, kcal100, protein100 };
      saveCustomIngredients(customIng);
      setIngOverride(today, btn.dataset.type, parseInt(btn.dataset.optIdx, 10), parseInt(btn.dataset.itemIdx, 10), key, amount);
      openIngSwapKey = null;
      openIngSwapShowCustomForm = false;
      renderNutrition();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });

  el.querySelectorAll("[data-meal-add]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.mealAdd;
      const name = document.getElementById(`meal-add-name-${key}`).value.trim();
      const kcal = parseInt(document.getElementById(`meal-add-kcal-${key}`).value, 10);
      const protein = parseInt(document.getElementById(`meal-add-protein-${key}`).value, 10) || 0;
      if (!name || !kcal) return;
      const m = loadCustomMeals();
      m[key].push({ id: "meal-" + Date.now() + Math.random(), name, kcal, protein, items: [] });
      saveCustomMeals(m);
      kostholdNewOptionOpenType = null;
      renderNutrition();
    });
  });
  el.querySelectorAll("[data-meal-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.mealRemove;
      const m = loadCustomMeals();
      MEAL_TYPE_ORDER.forEach(key => { m[key] = m[key].filter(o => o.id !== id); });
      saveCustomMeals(m);
      renderNutrition();
    });
  });
}

function renderNutrition() {
  if (!DATA.nutritionPlan) return;
  renderKostholdToday();
  renderKostholdMealCards();
}
renderNutrition();

function loadExtrasAll() { return loadLS(EXTRAS_KEY, []); }
function loadExtras() { return loadExtrasAll().filter(e => !e.deleted); }
function saveExtras(l) { saveLS(EXTRAS_KEY, l); }
function softDeleteExtra(id) {
  const all = loadExtrasAll();
  const item = all.find(e => e.id === id);
  if (item) { item.deleted = true; item.deletedAt = Date.now(); }
  saveExtras(all);
}

function addExtra(name, kcal, protein) {
  const list = loadExtras();
  list.push({ id: "extra-" + Date.now() + Math.random(), date: todayISO(), name, kcal: kcal || null, protein: protein || null });
  saveExtras(list);
  renderExtras();
  renderNutritionCoach();
  renderHjemKcalRing();
}


// "Legg til noe annet" og "Fyll opp protein" er fjernet fra Kosthold (hun bruker kun Lifesum
// for logging nå) - men addExtra()/loadExtras() lever videre, siden Hjem sin egen
// "+ Logg måltid"-skuff fortsatt bruker dem, og dayNutritionTotals() faller fortsatt tilbake
// til dem for dager uten en Lifesum-innføring. renderExtras() no-opper trygt uten UI-en.
function renderExtras() {
  const totalEl = document.getElementById("extras-today-total");
  if (!totalEl) return;
  const todays = loadExtras().filter(e => e.date === todayISO()).sort((a, b) => b.id.localeCompare(a.id));
  const totalKcalRaw = todays.reduce((s, e) => s + (e.kcal || 0), 0);
  const totalProtein = todays.reduce((s, e) => s + (e.protein || 0), 0);
  const focus = loadSettings().kostholdFocusMode;
  totalEl.innerHTML = (todays.length && focus)
    ? `<div class="section-sub" style="margin:4px 0 10px;">I dag: <b>~${withKcalMargin(totalKcalRaw)} kcal</b>${totalProtein ? ` · ${totalProtein} g protein` : ""} utenom planen</div>`
    : "";
  document.getElementById("extras-list").innerHTML = todays.map(e => `
    <li data-id="${e.id}"><span>${e.name}${focus && e.kcal ? ` · ~${withKcalMargin(e.kcal)} kcal` : ""}${focus && e.protein ? ` · ${e.protein} g protein` : ""}</span>
      <button class="log-remove-btn" data-extra-remove="${e.id}">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingenting logget i dag</li>`;

  document.querySelectorAll("#extras-list button[data-extra-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      softDeleteExtra(btn.dataset.extraRemove);
      renderExtras();
      renderNutritionCoach();
      renderHjemKcalRing();
    });
  });
}

function renderNutritionCoach() {
  const card = document.getElementById("nutrition-coach-card");
  if (!card) return;
  const tips = [];

  const since = new Date();
  since.setDate(since.getDate() - 6);
  const sinceStr = since.toISOString().slice(0, 10);
  const extrasThisWeek = loadExtras().filter(e => e.date >= sinceStr);
  if (extrasThisWeek.length >= 4) {
    tips.push("Du har logget ekstra mat/drikke flere ganger denne uken - helt greit! Husk bare å legge det inn så kaloriringen stemmer.");
  }

  // søtsug-mønster: sammenlign protein på dager med vs. uten loggført søtsug siste 30 dager -
  // trenger nok data i begge grupper før det sier noe reelt, ikke bare støy
  const today = todayISO();
  const windowStart = isoAddDays(today, -30);
  const cravingDays = Array.from(new Set(loadCravingLog().filter(c => c.date >= windowStart && c.date <= today).map(c => c.date)));
  const allWindowDays = [];
  for (let d = windowStart; d <= today; d = isoAddDays(d, 1)) allWindowDays.push(d);
  const proteinOn = d => dayNutritionTotals(d).protein;
  const cravingDaysWithData = cravingDays.filter(d => proteinOn(d) > 0);
  const normalDaysWithData = allWindowDays.filter(d => !cravingDays.includes(d) && proteinOn(d) > 0);
  if (cravingDaysWithData.length >= 5 && normalDaysWithData.length >= 5) {
    const avgCraving = cravingDaysWithData.reduce((s, d) => s + proteinOn(d), 0) / cravingDaysWithData.length;
    const avgNormal = normalDaysWithData.reduce((s, d) => s + proteinOn(d), 0) / normalDaysWithData.length;
    if (avgNormal > 0 && avgCraving < avgNormal * 0.9) {
      tips.push(`Du har logget søtsug ${cravingDaysWithData.length} dager siste måned. Disse dagene hadde du i snitt ${Math.round(avgCraving)} g protein, mot ${Math.round(avgNormal)} g på dager uten søtsug - kan være verdt å teste med et ekstra proteinrikt måltid på dager du kjenner på suget.`);
    }
  }

  if (!tips.length) { card.innerHTML = ""; return; }
  card.innerHTML = `<h3 style="margin:0 0 8px;font-size:15px;">💡 Tips</h3>` +
    tips.map(t => `<div class="section-sub" style="margin:0 0 8px;">${t}</div>`).join("");
}

// ---- Lifesum dagsinnføring ----
function renderLifesumEntry() {
  const kcalInput = document.getElementById("lifesum-kcal");
  if (!kcalInput) return;
  const entry = lifesumEntryFor(todayISO());
  document.getElementById("lifesum-kcal").value = entry ? entry.kcal : "";
  document.getElementById("lifesum-protein").value = entry && entry.protein != null ? entry.protein : "";
  document.getElementById("lifesum-fat").value = entry && entry.fat != null ? entry.fat : "";
  document.getElementById("lifesum-carbs").value = entry && entry.carbs != null ? entry.carbs : "";
}
document.getElementById("lifesum-save").addEventListener("click", () => {
  const kcal = parseInt(document.getElementById("lifesum-kcal").value, 10);
  if (!kcal) {
    flashSaved("lifesum-saved-msg", "Fyll inn minst kalorier");
    return;
  }
  const protein = parseInt(document.getElementById("lifesum-protein").value, 10) || 0;
  const fat = parseInt(document.getElementById("lifesum-fat").value, 10) || 0;
  const carbs = parseInt(document.getElementById("lifesum-carbs").value, 10) || 0;
  setLifesumEntry(todayISO(), { kcal, protein, fat, carbs });
  renderKostholdToday();
  renderHjemKcalRing();
  flashSaved("lifesum-saved-msg", "Lagret ✓");
});

// ---- søtsug-logg ----
const CRAVING_LOG_KEY = "garminDashboardCravingLog_v1";
function loadCravingLog() { return loadLS(CRAVING_LOG_KEY, []); }
function saveCravingLog(l) { saveLS(CRAVING_LOG_KEY, l); }
function addCraving() {
  const list = loadCravingLog();
  list.push({ id: "cr-" + Date.now() + Math.random(), date: todayISO(), time: new Date().toTimeString().slice(0, 5), comment: "" });
  saveCravingLog(list);
}
function updateCravingComment(id, comment) {
  const list = loadCravingLog();
  const c = list.find(x => x.id === id);
  if (c) c.comment = comment;
  saveCravingLog(list);
}
function removeCraving(id) { saveCravingLog(loadCravingLog().filter(x => x.id !== id)); }

function renderCravingToday() {
  const el = document.getElementById("craving-list");
  if (!el) return;
  const todays = loadCravingLog().filter(c => c.date === todayISO()).sort((a, b) => a.time.localeCompare(b.time));
  el.innerHTML = todays.map(c => `
    <li data-id="${c.id}">
      <input type="text" class="craving-comment-input" data-id="${c.id}" value="${c.comment || ""}" placeholder="Kl. ${c.time} - kommentar (valgfritt)">
      <button class="log-remove-btn" data-craving-remove="${c.id}">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingen søtsug logget i dag</li>`;
  el.querySelectorAll(".craving-comment-input").forEach(inp => {
    inp.addEventListener("change", () => updateCravingComment(inp.dataset.id, inp.value.trim()));
  });
  el.querySelectorAll("[data-craving-remove]").forEach(btn => {
    btn.addEventListener("click", () => { removeCraving(btn.dataset.cravingRemove); renderCravingToday(); });
  });
}
document.getElementById("craving-log-btn").addEventListener("click", () => {
  addCraving();
  renderCravingToday();
});

renderExtras();
renderLifesumEntry();
renderCravingToday();

// ---------------------------------------------------------------- shared storage helpers
const WEIGHT_LOG_KEY = "garminDashboardWeightLog_v1";
const MEASURE_LOG_KEY = "garminDashboardMeasureLog_v1";
const SHOP_LIST_KEY = "garminDashboardShoppingList_v1";
const TX_KEY = "garminDashboardTransactions_v1";
const BUDGET_CONFIG_KEY = "garminDashboardBudgetConfig_v1";
const SEEN_KEY = "garminDashboardSeen_v1";
const WAGE_KEY = "garminDashboardWage_v1";
const RATE_KEY = "garminDashboardInvestRate_v1";
const FORGOTTEN_SAVINGS_KEY = "garminDashboardForgottenSavings_v1";
const INVEST_FUND_KEY = "garminDashboardInvestFund_v1";
const SAVINGS_GOALS_KEY = "garminDashboardSavingsGoals_v1";
const BADDAY_LOG_KEY = "garminDashboardBadDayLog_v1";
const BADDAY_MODE_KEY = "garminDashboardBadDayActive_v1";
const WATER_KEY = "garminDashboardWater_v1";
const STREAK_BEST_KEY = "garminDashboardStreakBest_v1";

function loadLS(key, fallback) {
  try {
    const v = JSON.parse(localStorage.getItem(key));
    return v === null || v === undefined ? fallback : v;
  } catch (e) { return fallback; }
}
function saveLS(key, val) {
  localStorage.setItem(key, JSON.stringify(val));
  if (window.__cloudAuth) window.__cloudAuth.schedulePush();
}
function todayISO() { return new Date().toISOString().slice(0, 10); }
function isoWeekOf(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  return d.toISOString().slice(0, 10);
}
function monthOf(dateStr) { return dateStr.slice(0, 7); }

// ---- økonomimåned: 15. i hver måned til 14. i neste ----
const NO_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Des"];
function emKeyForDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  let y = d.getFullYear(), m = d.getMonth();
  if (d.getDate() <= 14) { m -= 1; if (m < 0) { m = 11; y -= 1; } }
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}
function emAddMonths(emKey, delta) {
  let [y, m] = emKey.split("-").map(Number);
  m = m - 1 + delta;
  y += Math.floor(m / 12);
  m = ((m % 12) + 12) % 12;
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}
function emStart(emKey) { return `${emKey}-15`; }
function emEnd(emKey) { return `${emAddMonths(emKey, 1)}-14`; }
function emLabel(emKey) {
  const [, m] = emKey.split("-").map(Number);
  const [, nm] = emAddMonths(emKey, 1).split("-").map(Number);
  return `Økonomimåned: 15. ${NO_MONTHS_SHORT[m - 1]} – 14. ${NO_MONTHS_SHORT[nm - 1]}`;
}
function emShortLabel(emKey) {
  const [y, m] = emKey.split("-").map(Number);
  return `${NO_MONTHS_SHORT[m - 1]} ${y}`;
}
function emKeysBack(n) {
  // the trailing n economic months up to and including the current one, oldest first
  const current = emKeyForDate(todayISO());
  const keys = [];
  for (let i = n - 1; i >= 0; i--) keys.push(emAddMonths(current, -i));
  return keys;
}

// ---- weight log ----
function loadWeightLog() { return loadLS(WEIGHT_LOG_KEY, []); }
function saveWeightLog(l) { saveLS(WEIGHT_LOG_KEY, l); }

// Slår sammen manuelt loggført vekt med det Garmin-vekten synkroniserer automatisk.
// Garmin vinner når begge finnes for samme dato (det er nå hovedkilden), men gammel
// manuell historikk før hun fikk vekten blir stående akkurat som den er. Brukes for all
// visning/analyse av vekt - selve "legg til/fjern"-skjemaet jobber fortsatt direkte på
// loadWeightLog()/saveWeightLog(), siden det bare er ment for manuelle korreksjoner.
function effectiveWeightLog() {
  const byDate = {};
  loadWeightLog().forEach(e => { byDate[e.date] = { date: e.date, kg: e.kg, source: "manual" }; });
  const garmin = DATA.garminWeight || {};
  Object.keys(garmin).forEach(d => {
    byDate[d] = Object.assign({ date: d, source: "garmin" }, garmin[d]);
  });
  return Object.values(byDate);
}

// ---- measurement log ----
function loadMeasureLog() { return loadLS(MEASURE_LOG_KEY, []); }
function saveMeasureLog(l) { saveLS(MEASURE_LOG_KEY, l); }

// ---- shopping list ----
function loadShopList() { return loadLS(SHOP_LIST_KEY, []); }
function saveShopList(l) { saveLS(SHOP_LIST_KEY, l); }

// ---- budget config / transactions ----
// one-time migration from the old flat-cap/calendar-month category set to the new
// fixed/variable/sparing categories + økonomimåned (15.-14.) model. Carries over
// cap customizations and re-tags existing transactions where a direct equivalent exists.
function migrateBudgetConfig(stored) {
  const fresh = JSON.parse(JSON.stringify(DATA.budgetDefaults));
  const OLD_KEY_MAP = {
    bolig: "husleie", mat: "mat", restaurant: "fritid_sosialt", transport: "transport",
    abonnement: "abonnementer", klaer: "klaer_velvare", trening: "treningssenter",
    hundefond: "hundefond", annet: "annet",
  };
  (stored.categories || []).forEach(oldCat => {
    const newKey = OLD_KEY_MAP[oldCat.key];
    const freshCat = newKey && fresh.categories.find(c => c.key === newKey);
    if (freshCat && oldCat.cap != null) freshCat.cap = oldCat.cap;
  });
  saveTransactions(loadTransactions().map(t => ({ ...t, category: OLD_KEY_MAP[t.category] || t.category })));
  fresh.income = stored.income != null ? stored.income : fresh.income;
  fresh.migratedV2 = true;
  return fresh;
}
function loadBudgetConfig() {
  let stored = loadLS(BUDGET_CONFIG_KEY, null);
  let changed = false;
  if (!stored || !stored.categories) {
    stored = JSON.parse(JSON.stringify(DATA.budgetDefaults));
    stored.migratedV2 = true;
    changed = true;
  } else if (!stored.migratedV2) {
    stored = migrateBudgetConfig(stored);
    changed = true;
  }
  stored.categories.forEach(c => {
    if (!c.capHistory) {
      c.capHistory = [{ from: "2000-01-01", amount: c.cap != null ? c.cap : 0 }];
      delete c.cap;
      changed = true;
    }
  });
  // pick up any category added to the built-in defaults since she last loaded (e.g. a new
  // seasonal category) - never touches a category she already has, so her own cap edits stay put
  const existingKeys = new Set(stored.categories.map(c => c.key));
  (DATA.budgetDefaults.categories || []).forEach(def => {
    if (existingKeys.has(def.key)) return;
    const added = Object.assign({}, def, { capHistory: [{ from: "2000-01-01", amount: def.cap != null ? def.cap : 0 }] });
    delete added.cap;
    stored.categories.push(added);
    changed = true;
  });
  if (changed) saveBudgetConfig(stored);
  return stored;
}
function saveBudgetConfig(c) { saveLS(BUDGET_CONFIG_KEY, c); }
function getCategoryCap(cat, emKey) {
  const monthStart = emStart(emKey);
  let amount = 0;
  (cat.capHistory || []).forEach(h => { if (h.from <= monthStart) amount = h.amount; });
  return amount;
}
function setCategoryCap(catKey, emKey, amount) {
  const cfg = loadBudgetConfig();
  const cat = cfg.categories.find(c => c.key === catKey);
  if (!cat) return;
  const monthStart = emStart(emKey);
  cat.capHistory = cat.capHistory.filter(h => h.from !== monthStart);
  cat.capHistory.push({ from: monthStart, amount });
  cat.capHistory.sort((a, b) => a.from.localeCompare(b.from));
  saveBudgetConfig(cfg);
}
function categorySpent(key, emKey) {
  const start = emStart(emKey), end = emEnd(emKey);
  return loadTransactions().filter(t => t.category === key && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
}
function isSavingsCategory(key) {
  const cat = loadBudgetConfig().categories.find(c => c.key === key);
  return !!(cat && cat.savings);
}

// ---- savings goals (generalizes the hundefond target to all three savings categories) ----
function loadSavingsGoals() {
  const defaults = {};
  (loadBudgetConfig().categories || []).filter(c => c.savings).forEach(c => {
    defaults[c.key] = { target: 20000, startSaved: 0 };
  });
  return Object.assign(defaults, loadLS(SAVINGS_GOALS_KEY, {}));
}
function saveSavingsGoals(g) { saveLS(SAVINGS_GOALS_KEY, g); }
function savingsBalance(key) {
  if (key === DATA.dogFund.category) return fundBalance();
  const goals = loadSavingsGoals();
  const startSaved = (goals[key] && goals[key].startSaved) || 0;
  const sum = loadTransactions().filter(t => t.category === key).reduce((s, t) => s + t.amount, 0);
  return startSaved + sum;
}
function savingsTarget(key) {
  if (key === DATA.dogFund.category) return DATA.dogFund.target;
  const goals = loadSavingsGoals();
  return (goals[key] && goals[key].target) || 0;
}
function setSavingsTarget(key, target) {
  if (key === DATA.dogFund.category) {
    const s = loadSettings();
    s.savingsTarget = target;
    saveSettings(s);
    DATA.dogFund.target = target;
    return;
  }
  const goals = loadSavingsGoals();
  goals[key] = Object.assign({ startSaved: 0 }, goals[key], { target });
  saveSavingsGoals(goals);
}
function setSavingsCurrentBalance(key, currentBalance) {
  // lets you correct the balance to match what's actually on the account right now
  // (e.g. pension/høyrente accounts that existed before this app tracked them, or that
  // earn interest/returns beyond what's logged as transactions) - backs out the
  // startSaved offset needed so savingsBalance() reads exactly currentBalance today.
  const sum = loadTransactions().filter(t => t.category === key).reduce((s, t) => s + t.amount, 0);
  const goals = loadSavingsGoals();
  goals[key] = Object.assign({ target: savingsTarget(key) }, goals[key], { startSaved: currentBalance - sum });
  saveSavingsGoals(goals);
}
function savingsMonthlyRate(key, months) {
  months = months || 3;
  const tx = loadTransactions();
  const totals = emKeysBack(months).map(ek => {
    const start = emStart(ek), end = emEnd(ek);
    return tx.filter(t => t.category === key && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
  });
  return totals.reduce((s, t) => s + t, 0) / months;
}
function projectSavingsMilestone(key) {
  const target = savingsTarget(key);
  const balance = savingsBalance(key);
  if (!target || balance >= target) return null;
  const rate = savingsMonthlyRate(key);
  if (rate <= 0) return null;
  const monthsNeeded = Math.ceil((target - balance) / rate);
  return { monthsNeeded, emKey: emAddMonths(emKeyForDate(todayISO()), monthsNeeded), rate };
}
// faste utgifter er ikke med her - de logges ikke som transaksjoner, bare det faste
// beløpet hun uansett betaler (satt i "Faste utgifter"-kortet i Budsjett)
function categoryOptionsHtml(cfg) {
  const variable = cfg.categories.filter(c => c.type === "variable" && !c.savings);
  const savings = cfg.categories.filter(c => c.savings);
  const opt = c => `<option value="${c.key}">${c.icon ? c.icon + " " : ""}${c.label}</option>`;
  return `<optgroup label="Variable utgifter">${variable.map(opt).join("")}</optgroup>` +
    `<optgroup label="Sparing">${savings.map(opt).join("")}</optgroup>`;
}
function loadTransactions() { return loadLS(TX_KEY, []); }
function saveTransactions(t) { saveLS(TX_KEY, t); }

// Faste utgifter (husleie, strøm, osv.) are committed costs, not discretionary spending -
// she doesn't want them auto-logged as transactions or counted toward "brukt denne måneden"
// anywhere. One-time cleanup: strip out any transaction a previous version of this app
// auto-logged for her (tagged autoLogged: true), so old entries don't linger in her data.
(function purgeAutoLoggedFixedExpenses() {
  const tx = loadTransactions();
  const kept = tx.filter(t => !t.autoLogged);
  if (kept.length !== tx.length) saveTransactions(kept);
})();

function fundBalance() {
  const tx = loadTransactions();
  const fundKey = DATA.dogFund.category;
  const sum = tx.filter(t => t.category === fundKey).reduce((s, t) => s + t.amount, 0);
  return DATA.dogFund.startSaved + sum;
}

// ---------------------------------------------------------------- points / level / snapshot
function computePoints() {
  const th = DATA.trainingHistory || [];
  let sessionPts = 0, stepPts = 0;
  th.forEach(day => {
    if (day.sessionType !== "rest" && day.loggedTypes.includes(day.sessionType)) sessionPts++;
    if (day.stepGoalMet) stepPts++;
  });
  const weightWeeks = new Set(effectiveWeightLog().map(e => isoWeekOf(e.date))).size;
  const measureMonths = new Set(loadMeasureLog().map(e => monthOf(e.date))).size;
  const newRecords = Object.values(DATA.records || {}).filter(r => r && r.date && r.date >= DATA.programStart).length;
  const balance = fundBalance();
  const pct = 100 * balance / DATA.dogFund.target;
  const milestonesCrossed = [25, 50, 75, 100].filter(m => pct >= m).length;

  const cfg = DATA.pointsConfig;
  const total =
    sessionPts * cfg.perCompletedSession +
    stepPts * cfg.perStepGoalDay +
    weightWeeks * cfg.perWeightWeek +
    measureMonths * cfg.perMeasurementMonth +
    newRecords * cfg.perNewRecord +
    milestonesCrossed * cfg.perFundMilestone;

  return { total, sessionPts, stepPts, weightWeeks, measureMonths, newRecords, milestonesCrossed };
}

function renderLevel() {
  const cfg = DATA.pointsConfig;
  const pts = computePoints();
  const levelIdx = Math.min(Math.floor(pts.total / cfg.levelThreshold), cfg.levelNames.length - 1);
  const inLevel = pts.total - levelIdx * cfg.levelThreshold;
  const pct = levelIdx >= cfg.levelNames.length - 1 ? 100 : Math.min(100, 100 * inLevel / cfg.levelThreshold);

  document.getElementById("level-card").innerHTML = `
    <div class="level-head">
      <div class="level-name">${cfg.levelNames[levelIdx]} · nivå ${levelIdx + 1}</div>
      <div class="level-pts">${pts.total} poeng</div>
    </div>
    <div class="level-bar"><div style="width:${pct}%"></div></div>
    <div class="level-reward">🎁 ${cfg.levelRewards[levelIdx]}</div>
    <div class="level-explainer">
      <span>💪 1 økt = ${cfg.perCompletedSession}p</span>
      <span>👟 Skrittmål nådd = ${cfg.perStepGoalDay}p</span>
      <span>⚖️ Ukentlig veiing = ${cfg.perWeightWeek}p</span>
      <span>📏 Månedlig målerunde = ${cfg.perMeasurementMonth}p</span>
      <span>🏆 Ny rekord = ${cfg.perNewRecord}p</span>
      <span>🐶 Fondsmilepæl = ${cfg.perFundMilestone}p</span>
    </div>
  `;

  const seen = loadLS(SEEN_KEY, { level: 0, milestones: 0 });
  const msgs = [];
  if (levelIdx > seen.level) msgs.push(`Nytt nivå! Du er nå ${cfg.levelNames[levelIdx]} 🎉`);
  if (pts.milestonesCrossed > seen.milestones) msgs.push(`Hundefondet har passert en ny milepæl! 🐶`);
  document.getElementById("celebrate-banner").innerHTML = msgs.length
    ? `<div class="celebrate-banner">${msgs.join(" · ")}</div>` : "";
  saveLS(SEEN_KEY, { level: levelIdx, milestones: pts.milestonesCrossed });

  return pts;
}

// ---------------------------------------------------------------- streak / latest PR
// ---- streak freeze cards ("frikort") - 2 missed training days per calendar month are
// forgiven automatically, so one off day doesn't erase the whole streak. Usage is recorded
// per date (not just a counter) so repeated renders never consume more than were actually
// missed, and so the Hjem notice can say exactly which day got covered. ----
const FREEZE_CARDS_PER_MONTH = 2;
const FREEZE_CARDS_USED_KEY = "garminDashboardFreezeCardsUsed_v1";
function loadFreezeCardsUsed() { return loadLS(FREEZE_CARDS_USED_KEY, []); }
function freezeCardsLeftForMonth(monthKey) {
  const usedThisMonth = loadFreezeCardsUsed().filter(d => d.slice(0, 7) === monthKey).length;
  return Math.max(0, FREEZE_CARDS_PER_MONTH - usedThisMonth);
}
function tryUseFreezeCard(dateStr) {
  const used = loadFreezeCardsUsed();
  if (used.includes(dateStr)) return true;
  if (freezeCardsLeftForMonth(dateStr.slice(0, 7)) <= 0) return false;
  used.push(dateStr);
  saveLS(FREEZE_CARDS_USED_KEY, used);
  return true;
}
function computeStreak() {
  const th = DATA.trainingHistory || [];
  if (!th.length) return 0;
  let i = th.length - 1;
  const last = th[i];
  const lastPending = last.sessionType !== "rest" && !last.loggedTypes.includes(last.sessionType) && !inVacationRange(last.date) && !isSickDay(last.date);
  if (lastPending) i--;
  let streak = 0;
  for (; i >= 0; i--) {
    const day = th[i];
    if (inVacationRange(day.date) || isSickDay(day.date)) continue;
    let kept = day.sessionType === "rest" || day.loggedTypes.includes(day.sessionType);
    if (!kept && day.date < todayISO() && tryUseFreezeCard(day.date)) kept = true;
    if (!kept) break;
    streak++;
  }
  return streak;
}

const FREEZE_NOTICE_ACK_KEY = "garminDashboardFreezeNoticeAck_v1";
const freezeCardsUsedBeforeLoad = loadFreezeCardsUsed();
computeStreak(); // run once eagerly so a newly-missed day gets its freeze card applied right away
function renderHjemFreezeNotice() {
  const el = document.getElementById("hjem-freeze-notice");
  if (!el) return;
  const newlyUsed = loadFreezeCardsUsed().filter(d => !freezeCardsUsedBeforeLoad.includes(d));
  const ack = loadLS(FREEZE_NOTICE_ACK_KEY, []);
  const unacked = newlyUsed.filter(d => !ack.includes(d));
  if (!unacked.length) { el.innerHTML = ""; return; }
  const left = freezeCardsLeftForMonth(todayISO().slice(0, 7));
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>🧊 Streaken din er intakt - du brukte et frikort for ${unacked.map(fmtShort).join(" og ")}. ${left} frikort igjen denne måneden.</span>
      <button id="hjem-freeze-notice-dismiss">OK</button>
    </div>
  `;
  document.getElementById("hjem-freeze-notice-dismiss").addEventListener("click", () => {
    saveLS(FREEZE_NOTICE_ACK_KEY, ack.concat(unacked));
    el.innerHTML = "";
  });
}

function latestPR() {
  const log = loadSetLog().slice().sort((a, b) => a.date === b.date ? a.id.localeCompare(b.id) : a.date.localeCompare(b.date));
  const bestByEx = {};
  let last = null;
  log.forEach(s => {
    if (isBetterSet(s, bestByEx[s.exercise])) {
      bestByEx[s.exercise] = s;
      last = s;
    }
  });
  return last;
}

function renderWeeklySnapshot() {
  const since = new Date();
  since.setDate(since.getDate() - 6);
  const sinceStr = since.toISOString().slice(0, 10);

  const th = (DATA.trainingHistory || []).filter(d => d.date >= sinceStr);
  const sessionsDone = th.filter(d => d.sessionType !== "rest" && d.loggedTypes.includes(d.sessionType)).length;
  const stepsDone = th.filter(d => d.stepGoalMet).length;

  const allWeights = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  const recentWeights = allWeights.filter(e => e.date >= sinceStr);
  let kgChangeLabel = "–";
  if (recentWeights.length >= 2) {
    const diff = recentWeights[recentWeights.length - 1].kg - recentWeights[0].kg;
    kgChangeLabel = `${diff > 0 ? "+" : ""}${diff.toFixed(1)} kg`;
  }

  const krAdded = loadTransactions()
    .filter(t => t.date >= sinceStr && t.category === DATA.dogFund.category)
    .reduce((s, t) => s + t.amount, 0);

  document.getElementById("weekly-snapshot").innerHTML = `
    <div class="snapshot-chip">Økter gjort<b>${sessionsDone}</b></div>
    <div class="snapshot-chip">Stegmål nådd<b>${stepsDone} dager</b></div>
    <div class="snapshot-chip">Vektendring<b>${kgChangeLabel}</b></div>
    <div class="snapshot-chip">Lagt i hundefondet<b>${krAdded} kr</b></div>
  `;
}

// ---------------------------------------------------------------- weight / measurement logging
document.getElementById("weight-date").value = todayISO();
document.getElementById("measure-date").value = todayISO();

function renderPlateau() {
  const card = document.getElementById("plateau-card");
  const log = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 3) { card.innerHTML = ""; return; }

  const a = log[log.length - 3], z = log[log.length - 1];
  const daysBetween = (new Date(z.date) - new Date(a.date)) / 86400000;
  const stuck = daysBetween >= 14 && (a.kg - z.kg) < 0.3;
  if (!stuck) { card.innerHTML = ""; return; }

  const mlog = loadMeasureLog().filter(e => e.waist != null).sort((x, y) => x.date.localeCompare(y.date));
  let waistDown = false;
  if (mlog.length >= 2) {
    const first = mlog[mlog.length - 2], last = mlog[mlog.length - 1];
    const daysSinceLast = (new Date(z.date) - new Date(last.date)) / 86400000;
    waistDown = (first.waist - last.waist) >= 1 && daysSinceLast <= 35;
  }

  card.innerHTML = waistDown
    ? `<h3 style="margin:0 0 4px;font-size:15px;">Vekta står stille, men midjen går ned 🎉</h3><div class="section-sub" style="margin:0;">Det betyr at du mister fett og bygger muskler samtidig. Ikke endre noe, bare fortsett som nå.</div>`
    : `<h3 style="margin:0 0 4px;font-size:15px;">Vekta har stått stille i 2–3 uker</h3><div class="section-sub" style="margin:0;">Det er helt vanlig. Velg én liten justering og gi den 2 uker: spis litt mindre, eller gå litt mer hver dag. Sjekk også at du logger alt, særlig olje, saus og drikke.</div>`;
}

function weightRollingAvgSeries(log) {
  // log: ascending by date. 7-day trailing window, keyed by calendar date (not index),
  // so it stays correct whether entries are daily or more sparse.
  return log.map(entry => {
    const windowStart = new Date(entry.date + "T00:00:00");
    windowStart.setDate(windowStart.getDate() - 6);
    const ws = windowStart.toISOString().slice(0, 10);
    const inWindow = log.filter(e => e.date >= ws && e.date <= entry.date);
    return inWindow.reduce((s, e) => s + e.kg, 0) / inWindow.length;
  });
}

function renderWeightTrend() {
  const el = document.getElementById("weight-trend");
  if (!el) return;
  const log = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 3) { el.innerHTML = ""; return; }

  const series = weightRollingAvgSeries(log);
  const latest = series[series.length - 1];
  const prior = series[Math.max(0, series.length - 3)];
  const diff = latest - prior;
  el.innerHTML = `<div class="weight-trend-box">Trend (7-dagers snitt): <b>${latest.toFixed(1)} kg</b> <span class="log-delta ${diff <= 0 ? "down" : "up"}">${diff > 0 ? "+" : ""}${diff.toFixed(1)} kg siste par uker</span></div>`;
}

function renderWeightChart(svgId, tooltipId) {
  const svg = document.getElementById(svgId || "chart-weight");
  const tooltip = document.getElementById(tooltipId || "tt-weight");
  if (!svg) return;
  const log = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (log.length < 2) { svg.innerHTML = ""; return; }

  const avgSeries = weightRollingAvgSeries(log);
  const w = 480, h = 130, padLeft = 36, padBottom = 20, padTop = 10, padRight = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";
  const plotW = w - padLeft - padRight;
  const plotH = h - padBottom - padTop;

  const allVals = log.map(e => e.kg).concat(avgSeries);
  const min = Math.min(...allVals), max = Math.max(...allVals);
  const range = (max - min) || 1;
  const step = plotW / Math.max(log.length - 1, 1);
  const xAt = i => padLeft + i * step;
  const yAt = v => padTop + plotH - ((v - min) / range) * plotH;

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - padRight}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${(min + (i / 3) * range).toFixed(1)}</text>`;
  }

  let rawDots = "";
  log.forEach((e, i) => {
    rawDots += `<circle cx="${xAt(i).toFixed(1)}" cy="${yAt(e.kg).toFixed(1)}" r="2.5" fill="#7a1f3d" opacity="0.25"/>`;
  });
  svg.innerHTML += rawDots;

  const pathPts = avgSeries.map((v, i) => [xAt(i), yAt(v)]);
  const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  svg.innerHTML += `<path d="${path}" fill="none" stroke="#7a1f3d" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;

  let avgDots = "";
  avgSeries.forEach((v, i) => {
    avgDots += `<circle cx="${xAt(i).toFixed(1)}" cy="${yAt(v).toFixed(1)}" r="3" fill="#7a1f3d" class="dot" data-date="${log[i].date}" data-val="${v.toFixed(1)}" opacity="0"/>`;
  });
  svg.innerHTML += avgDots;

  [0, Math.floor(log.length / 2), log.length - 1].forEach(i => {
    svg.innerHTML += `<text x="${xAt(i)}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(log[i].date)}</text>`;
  });

  svg.querySelectorAll(".dot").forEach(dot => {
    const hit = dot.cloneNode();
    hit.setAttribute("r", 8);
    hit.setAttribute("opacity", 0);
    hit.classList.add("hit");
    svg.appendChild(hit);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${fmtDate(hit.dataset.date)}: snitt ${hit.dataset.val} kg`;
    });
    hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}

function renderWeightLog() {
  const log = effectiveWeightLog().sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("weight-list").innerHTML = log.slice(0, 8).map((e, i) => {
    const prev = log[i + 1];
    let delta = "";
    if (prev) {
      const d = e.kg - prev.kg;
      delta = `<span class="log-delta ${d <= 0 ? "down" : "up"}">${d > 0 ? "+" : ""}${d.toFixed(1)} kg</span>`;
    }
    const bits = [];
    if (e.bodyFat != null) bits.push(`${e.bodyFat}% fett`);
    if (e.muscleMassKg != null) bits.push(`${e.muscleMassKg} kg muskelmasse`);
    const compNote = bits.length ? `<div class="section-sub" style="margin:2px 0 0;width:100%;">${bits.join(" · ")}</div>` : "";
    const sourceTag = e.source === "garmin" ? `<span class="weight-source-tag" title="Synkronisert fra Garmin-vekten">Garmin</span>` : "";
    const removeBtn = e.source === "manual" ? `<button class="log-remove-btn" data-weight-remove="${e.date}">✕</button>` : "";
    return `<li data-date="${e.date}" style="${compNote ? "flex-wrap:wrap;" : ""}">
      <div style="display:flex;justify-content:space-between;align-items:center;width:100%;">
        <span>${fmtShort(e.date)} ${sourceTag}</span>
        <span><b>${e.kg} kg</b> ${delta}${removeBtn}</span>
      </div>
      ${compNote}
    </li>`;
  }).join("") || `<li style="border-top:none;color:var(--muted);">Ingen målinger ennå - logg vekten din i dag for å komme i gang 👆</li>`;
  document.querySelectorAll("#weight-list button[data-weight-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveWeightLog(loadWeightLog().filter(e => e.date !== btn.dataset.weightRemove));
      renderWeightLog();
      renderWeightTrend();
      renderWeightChart();
      renderLevel();
      renderWeeklySnapshot();
      renderPlateau();
      renderBodyGoalChart();
      renderCalorieCalibration();
    });
  });
}
document.getElementById("weight-add").addEventListener("click", () => {
  const date = document.getElementById("weight-date").value || todayISO();
  const kg = parseFloat(document.getElementById("weight-kg").value);
  if (!kg) return;
  const log = loadWeightLog().filter(e => e.date !== date);
  log.push({ date, kg });
  saveWeightLog(log);
  document.getElementById("weight-kg").value = "";
  renderWeightLog();
  renderWeightTrend();
  renderWeightChart();
  renderLevel();
  renderWeeklySnapshot();
  renderPlateau();
  renderBodyGoalChart();
  renderCalorieCalibration();
});

function renderMeasureLog() {
  const log = loadMeasureLog().sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("measure-list").innerHTML = log.slice(0, 6).map(e =>
    `<li data-date="${e.date}"><span>${fmtShort(e.date)}</span><b>${e.waist ?? "–"} / ${e.hips ?? "–"} / ${e.arm ?? "–"} / ${e.thigh ?? "–"} / ${e.chest ?? "–"} cm</b><button class="log-remove-btn" data-measure-remove="${e.date}">✕</button></li>`
  ).join("") || `<li style="border-top:none;color:var(--muted);">Ingen mål ennå - ta de første målene dine for å se endring over tid 📏</li>`;
  document.querySelectorAll("#measure-list button[data-measure-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveMeasureLog(loadMeasureLog().filter(e => e.date !== btn.dataset.measureRemove));
      renderMeasureLog();
      renderLevel();
      renderPlateau();
      renderBodyGoalChart();
    });
  });
}
document.getElementById("measure-add").addEventListener("click", () => {
  const date = document.getElementById("measure-date").value || todayISO();
  const waist = parseFloat(document.getElementById("measure-waist").value) || null;
  const hips = parseFloat(document.getElementById("measure-hips").value) || null;
  const arm = parseFloat(document.getElementById("measure-arm").value) || null;
  const thigh = parseFloat(document.getElementById("measure-thigh").value) || null;
  const chest = parseFloat(document.getElementById("measure-chest").value) || null;
  if (!waist && !hips && !arm && !thigh && !chest) return;
  const log = loadMeasureLog().filter(e => e.date !== date);
  log.push({ date, waist, hips, arm, thigh, chest });
  saveMeasureLog(log);
  document.getElementById("measure-waist").value = "";
  document.getElementById("measure-hips").value = "";
  document.getElementById("measure-arm").value = "";
  document.getElementById("measure-thigh").value = "";
  document.getElementById("measure-chest").value = "";
  renderMeasureLog();
  renderLevel();
  renderPlateau();
  renderBodyGoalChart();
  renderCalorieCalibration();
});

function showOverwhelmBox() {
  const out = document.getElementById("overwhelm-out");
  out.innerHTML = `<div class="overwhelm-box">
    <b>1. Stopp og pust 🫧</b><br>Pust inn i 4 sekunder, ut i 6. Gjør det fem ganger.<br><br>
    <b>2. Velg bare én ting</b><br>Se på neste punkt på treningsplanen eller handlelista. Alt annet kan vente - det forsvinner ikke.<br><br>
    <b>3. Gjør den i 10 minutter</b><br>Etterpå har du lov til å stoppe. Ofte blir det lettere å fortsette.
  </div>`;
}

// ---------------------------------------------------------------- sykedager (migrene o.l.)
function renderSickDayPanel() {
  const out = document.getElementById("sickday-out");
  if (!out) return;
  const days = loadSickDays();
  const listHtml = days.length
    ? `<ul class="sickday-list">${days.slice(0, 14).map(d => `
        <li><span>${fmtShort(d.date)}${d.note ? ` - ${d.note}` : ""}</span><button class="btn ghost small" data-remove-sickday="${d.date}">Fjern</button></li>
      `).join("")}</ul>`
    : `<div class="section-sub" style="margin-top:10px;">Ingen sykedager markert ennå.</div>`;
  out.innerHTML = `
    <div class="sickday-box">
      <p style="margin:0;">Marker dager du var syk (f.eks. migrene) i etterkant - de telles ikke med i streak, minimumsdag eller ukens/månedens mål og mønstre.</p>
      <div class="log-form">
        <label class="mvd-settings-field">Fra dato<input type="date" id="sickday-from"></label>
        <label class="mvd-settings-field">Til dato<input type="date" id="sickday-to"></label>
        <label class="mvd-settings-field">Notat (valgfritt)<input type="text" id="sickday-note" placeholder="f.eks. Migrene"></label>
        <button class="btn secondary small" id="sickday-save">Lagre</button>
      </div>
      ${listHtml}
    </div>`;
  document.getElementById("sickday-from").value = todayISO();
  document.getElementById("sickday-to").value = todayISO();
  document.getElementById("sickday-save").addEventListener("click", () => {
    const from = document.getElementById("sickday-from").value;
    const to = document.getElementById("sickday-to").value;
    const note = document.getElementById("sickday-note").value.trim();
    if (!from || !to || from > to) return;
    addSickDayRange(from, to, note);
    renderSickDayPanel();
  });
  out.querySelectorAll("[data-remove-sickday]").forEach(btn => {
    btn.addEventListener("click", () => {
      removeSickDay(btn.dataset.removeSickday);
      renderSickDayPanel();
    });
  });
}

// ---------------------------------------------------------------- støtte-inngang (samlet)
// "Trenger du noe i dag?" erstatter tre separate knapper (overveldet/minimumsdag/sykedag)
// med én inngang - hun velger hva slags dag det er, så ruter vi til riktig eksisterende flyt.
document.getElementById("support-btn").addEventListener("click", () => {
  const picker = document.getElementById("support-picker");
  if (picker.innerHTML) { picker.innerHTML = ""; return; }
  document.getElementById("overwhelm-out").innerHTML = "";
  document.getElementById("sickday-out").innerHTML = "";
  picker.innerHTML = `
    <div class="support-picker-box">
      <button class="btn ghost small" id="support-pick-overwhelm">😣 Alt er overveldende akkurat nå</button>
      <button class="btn ghost small" id="support-pick-minimum">🌱 Bare et minimum i dag</button>
      <button class="btn ghost small" id="support-pick-sick">🤕 Jeg har vært syk</button>
    </div>`;
  document.getElementById("support-pick-overwhelm").addEventListener("click", () => {
    picker.innerHTML = "";
    showOverwhelmBox();
  });
  document.getElementById("support-pick-minimum").addEventListener("click", () => {
    picker.innerHTML = "";
    setBadDayMode(true);
  });
  document.getElementById("support-pick-sick").addEventListener("click", () => {
    picker.innerHTML = "";
    renderSickDayPanel();
  });
});

// ---------------------------------------------------------------- bad day mode
function loadBadDayLog() { return loadLS(BADDAY_LOG_KEY, {}); }
function saveBadDayLog(v) { saveLS(BADDAY_LOG_KEY, v); }

function flashSaved(elId, msg) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  clearTimeout(flashSaved._t[elId]);
  flashSaved._t[elId] = setTimeout(() => { el.textContent = ""; }, 2000);
}
flashSaved._t = {};
function flashBadDaySaved(msg) { flashSaved("badday-saved-msg", msg); }

function badDayMarkTrained() {
  const log = loadBadDayLog();
  const today = todayISO();
  log[today] = Object.assign({}, log[today], { trained: true });
  saveBadDayLog(log);
  renderBadDayPanel();
  flashBadDaySaved("Trening logget ✓");
}

function badDayLogFood() {
  addExtra("Mat/drikke (dårlig dag)", null);
  flashBadDaySaved("Mat/drikke logget ✓");
}

function badDayLogExpense() {
  const input = document.getElementById("badday-expense-amount");
  const amount = parseFloat(input.value);
  if (!amount) return;
  addTransactionWithRoundUp(todayISO(), amount, "annet", "Minimumsdag");
  input.value = "";
  flashBadDaySaved("Utgift logget ✓");
}

// ---- Minimum Viable Day (MVD) - auto-verified against real data, not self-reported,
// so it actually holds her accountable instead of just letting her tick a box ----
function mvdStatusToday() {
  const s = loadSettings();
  const totals = dayNutritionTotals(todayISO());
  const proteinOk = (totals.mealsLogged || []).some(m => (m.protein || 0) >= s.mvdProtein);
  const steps = ((DATA.topStats || {}).steps || {}).value || 0;
  const stepsOk = steps >= s.mvdSteps;
  const todayDay = (DATA.program.week || []).find(d => d.isToday);
  const minutesLogged = ((todayDay && todayDay.loggedActivities) || []).reduce((sum, a) => sum + (a.minutes || 0), 0);
  const minutesOk = minutesLogged >= s.mvdMinutes;
  return { s, proteinOk, stepsOk, minutesOk, steps, minutesLogged, allDone: proteinOk && stepsOk && minutesOk };
}
function mvdSectionHtml() {
  const { s, proteinOk, stepsOk, minutesOk, steps, minutesLogged, allDone } = mvdStatusToday();
  return `
    <div class="mvd-box">
      <div class="mvd-title">🎯 Minimum Viable Day</div>
      <ul class="mvd-list">
        <li class="${proteinOk ? "done" : ""}">${proteinOk ? "✓" : "○"} Et måltid med ${s.mvdProtein} g+ protein</li>
        <li class="${stepsOk ? "done" : ""}">${stepsOk ? "✓" : "○"} ${s.mvdSteps.toLocaleString()} skritt <span class="mvd-sub">(${steps.toLocaleString()} så langt)</span></li>
        <li class="${minutesOk ? "done" : ""}">${minutesOk ? "✓" : "○"} ${s.mvdMinutes} min bevegelse <span class="mvd-sub">(${minutesLogged} min i dag)</span></li>
      </ul>
      ${allDone
        ? `<div class="mvd-complete">🎉 MVD fullført - det er nok for i dag.</div>`
        : `<div class="mvd-note">I dag er målet bare å fullføre MVD. Det er nok.</div>`}
    </div>
  `;
}
function renderHjemMvdSunday() {
  const el = document.getElementById("hjem-mvd-sunday");
  if (!el) return;
  if (new Date().getDay() !== 0 || isVacationActive()) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="hjem-card">${mvdSectionHtml()}</div>`;
}

// shown only on søndager - she plans next week's training then, so give her a
// read-only look at next week's default plan ahead of time
function renderHjemNextWeekPreview() {
  const el = document.getElementById("hjem-next-week-preview");
  if (!el) return;
  const p = DATA.program;
  if (new Date().getDay() !== 0 || isVacationActive() || !p || !p.nextWeek) { el.innerHTML = ""; return; }
  const overrides = loadPlanOverrides();
  const weekTag = p.nextWeekIsDeload ? "Deload-uke" : p.nextWeekFocus;
  const days = p.nextWeek.map(d => {
    const r = resolvePlanDay(d, overrides);
    return `<div class="week-day" data-date="${d.date}">
      <div class="wd"><span>${d.weekday}</span></div>
      <div class="sess">${r.label}</div>
    </div>`;
  }).join("");
  el.innerHTML = `
    <div class="hjem-card">
      <div class="hjem-body-group-label">📅 Neste treningsuke</div>
      <div class="section-sub" style="margin-bottom:8px;">${weekTag}</div>
      <div class="week-row">${days}</div>
      <button class="btn ghost small hjem-plan-next-week-btn" style="margin-top:10px;">📝 Planlegg neste uke</button>
    </div>
  `;
  const btn = el.querySelector(".hjem-plan-next-week-btn");
  if (btn) btn.addEventListener("click", () => {
    showTab("planlegg");
    renderPlanlegg();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

function renderBadDayPanel() {
  const entry = loadBadDayLog()[todayISO()] || {};
  document.getElementById("badday-mvd").innerHTML = mvdSectionHtml();
  document.getElementById("badday-quickbtns").innerHTML = `
    <button class="btn ${entry.trained ? "active" : ""}" id="badday-trained-btn">🏋️ ${entry.trained ? "Trent i dag ✓" : "Trente i dag"}</button>
    <button class="btn secondary" id="badday-food-btn">🍫 Logg mat/drikke</button>
    <div class="badday-expense-row">
      <input type="number" step="1" id="badday-expense-amount" placeholder="Beløp (kr)">
      <button class="btn secondary" id="badday-expense-btn">💸 Logg utgift</button>
    </div>
  `;
  document.getElementById("badday-trained-btn").addEventListener("click", badDayMarkTrained);
  document.getElementById("badday-food-btn").addEventListener("click", badDayLogFood);
  document.getElementById("badday-expense-btn").addEventListener("click", badDayLogExpense);
  document.getElementById("badday-saved-msg").textContent = "";
}

// ---- Fri dag: for valgfrie/ikke-presserende oppgaver (farge hår, mealprep, rydde...) der
// tankekaos lett fører til at ingenting blir gjort. Viser kun én oppgave om gangen, automatisk
// brutt ned til et lite første fysisk steg - resten er gjemt til hun er klar for det.
// Nøklene defineres her, før setBadDayMode (som refererer FREEDAY_MODE_KEY) kalles lenger ned.
const FREEDAY_MODE_KEY = "garminDashboardFreedayActive_v1";
const FREEDAY_LOG_KEY = "garminDashboardFreedayLog_v1";

function setBadDayMode(active) {
  document.body.classList.toggle("badday-active", active);
  saveLS(BADDAY_MODE_KEY, active);
  if (active) {
    document.body.classList.remove("freeday-active");
    saveLS(FREEDAY_MODE_KEY, false);
    renderBadDayPanel();
  }
}

document.getElementById("hjem-badday-toggle").addEventListener("click", () => setBadDayMode(true));
document.getElementById("badday-exit").addEventListener("click", () => setBadDayMode(false));

if (loadLS(BADDAY_MODE_KEY, false)) setBadDayMode(true);

function loadFreedayLog() { return loadLS(FREEDAY_LOG_KEY, {}); }
function saveFreedayLog(l) { saveLS(FREEDAY_LOG_KEY, l); }
function freedayTasksToday() { return loadFreedayLog()[todayISO()] || []; }
function saveFreedayTasksToday(tasks) {
  const log = loadFreedayLog();
  log[todayISO()] = tasks;
  saveFreedayLog(log);
}

// enkle nøkkelord -> et konkret, lite første steg (ikke ekte AI - appen er en statisk fil),
// med et generisk fallback-steg for alt annet
const FREEDAY_MICROSTEPS = [
  [["dusj"], "Gå til badet og skru på vannet."],
  [["hår", "farge"], "Finn frem det du trenger (farge, børste, håndkle)."],
  [["mealprep", "middag", "lunsj", "frokost", "lage mat", "matlaging"], "Gå til kjøkkenet og finn frem én ingrediens."],
  [["vask", "klesvask", "stryk"], "Samle sammen det som skal vaskes eller strykes."],
  [["rydd"], "Plukk opp én ting og sett den på plass."],
  [["støvsug", "vaske gulv"], "Finn frem støvsugeren eller moppen."],
  [["handle", "butikk", "dagligvare"], "Lag en kjapp liste på 3 ting du trenger."],
  [["tren"], "Ta på deg treningsklærne."],
  [["epost", "mail", "papirarbeid", "regning"], "Åpne det første du ser øverst."],
  [["ring", "telefon"], "Finn frem telefonen og nummeret."],
];
function guessMicroStep(text) {
  const t = text.toLowerCase();
  for (const [keywords, step] of FREEDAY_MICROSTEPS) {
    if (keywords.some(k => t.includes(k))) return step;
  }
  return "Reis deg og ta ett lite fysisk steg mot den.";
}

function addFreedayTask(text) {
  const tasks = freedayTasksToday();
  tasks.push({ id: "fd-" + Date.now() + Math.random(), text, microStep: guessMicroStep(text), status: "todo" });
  saveFreedayTasksToday(tasks);
}
function setFreedayTaskStatus(id, status) {
  const tasks = freedayTasksToday();
  const t = tasks.find(x => x.id === id);
  if (t) t.status = status;
  saveFreedayTasksToday(tasks);
}
function updateFreedayMicroStep(id, microStep) {
  const tasks = freedayTasksToday();
  const t = tasks.find(x => x.id === id);
  if (t) t.microStep = microStep;
  saveFreedayTasksToday(tasks);
}

let freedayMicroEditOpen = null;
let freedayRestOpen = false;

function renderFreedayPanel() {
  const tasks = freedayTasksToday();
  const current = tasks.find(t => t.status === "todo" || t.status === "started");
  const upcoming = tasks.filter(t => t.id !== (current && current.id) && t.status !== "done" && t.status !== "skipped");

  const currentEl = document.getElementById("freeday-current");
  if (!current) {
    currentEl.innerHTML = tasks.length
      ? `<div class="freeday-task-card"><div class="freeday-task-name">Alt er gjennomgått for i dag 🌤️</div><div class="section-sub">Det du ikke fikk til er helt greit - det kan vente til en annen dag.</div></div>`
      : `<div class="section-sub" style="margin-top:14px;">Ingenting lagt til ennå - skriv inn den første oppgaven over.</div>`;
  } else {
    const started = current.status === "started";
    currentEl.innerHTML = `
      <div class="freeday-task-card">
        <div class="freeday-task-name">${current.text}</div>
        <div class="freeday-microstep">${started ? "Du er i gang - fortsett i ditt eget tempo." : current.microStep}</div>
        ${freedayMicroEditOpen === current.id
          ? `<div class="log-form"><input type="text" id="freeday-microstep-input" value="${current.microStep}"><button class="btn ghost small" id="freeday-microstep-save" data-id="${current.id}">Lagre</button></div>`
          : (started ? "" : `<button class="btn ghost small" id="freeday-microstep-edit" data-id="${current.id}">Endre første steg</button>`)}
        <div class="freeday-actions">
          ${!started ? `<button class="btn" id="freeday-start-btn" data-id="${current.id}">Jeg er i gang 🚶</button>` : ""}
          <button class="btn ${started ? "" : "ghost"}" id="freeday-done-btn" data-id="${current.id}">Ferdig ✓</button>
          <button class="btn ghost" id="freeday-skip-btn" data-id="${current.id}">Ikke i dag</button>
        </div>
      </div>`;

    const startBtn = document.getElementById("freeday-start-btn");
    if (startBtn) startBtn.addEventListener("click", () => { setFreedayTaskStatus(startBtn.dataset.id, "started"); freedayMicroEditOpen = null; renderFreedayPanel(); });
    document.getElementById("freeday-done-btn").addEventListener("click", (e) => { setFreedayTaskStatus(e.target.dataset.id, "done"); freedayMicroEditOpen = null; renderFreedayPanel(); });
    document.getElementById("freeday-skip-btn").addEventListener("click", (e) => { setFreedayTaskStatus(e.target.dataset.id, "skipped"); freedayMicroEditOpen = null; renderFreedayPanel(); });
    const editBtn = document.getElementById("freeday-microstep-edit");
    if (editBtn) editBtn.addEventListener("click", () => { freedayMicroEditOpen = editBtn.dataset.id; renderFreedayPanel(); });
    const saveBtn = document.getElementById("freeday-microstep-save");
    if (saveBtn) saveBtn.addEventListener("click", () => {
      const val = document.getElementById("freeday-microstep-input").value.trim();
      if (val) updateFreedayMicroStep(saveBtn.dataset.id, val);
      freedayMicroEditOpen = null;
      renderFreedayPanel();
    });
  }

  const restEl = document.getElementById("freeday-rest-toggle");
  if (!upcoming.length) { restEl.innerHTML = ""; return; }
  restEl.innerHTML = `<button class="btn ghost small" id="freeday-rest-show">${freedayRestOpen ? "Skjul resten" : `Vis resten (${upcoming.length})`}</button>`
    + (freedayRestOpen ? `<ul class="freeday-rest-list">${upcoming.map(t => `<li>${t.text}</li>`).join("")}</ul>` : "");
  document.getElementById("freeday-rest-show").addEventListener("click", () => { freedayRestOpen = !freedayRestOpen; renderFreedayPanel(); });
}

document.getElementById("freeday-add-btn").addEventListener("click", () => {
  const input = document.getElementById("freeday-add-input");
  const text = input.value.trim();
  if (!text) return;
  addFreedayTask(text);
  input.value = "";
  renderFreedayPanel();
});
document.getElementById("freeday-add-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("freeday-add-btn").click();
});

function setFreedayMode(active) {
  document.body.classList.toggle("freeday-active", active);
  saveLS(FREEDAY_MODE_KEY, active);
  if (active) {
    document.body.classList.remove("badday-active");
    saveLS(BADDAY_MODE_KEY, false);
    freedayMicroEditOpen = null;
    renderFreedayPanel();
  }
}
document.getElementById("hjem-freeday-toggle").addEventListener("click", () => setFreedayMode(true));
document.getElementById("freeday-exit").addEventListener("click", () => setFreedayMode(false));

if (loadLS(FREEDAY_MODE_KEY, false)) setFreedayMode(true);

// ---------------------------------------------------------------- shopping list
const SHOP_DEPT_ORDER = ["Frukt og grønt", "Meieri", "Kjøtt og fisk", "Tørrvarer", "Frys", "Annet"];
// Order matters: checked top-to-bottom, first keyword match wins (so "frossen" beats
// "grønnsak" in "amerikansk grønnsaksblanding (frossen)", and "melk" beats "protein" in "proteinmelk").
const SHOP_DEPT_KEYWORDS = [
  ["Frys", ["frossen", "frys"]],
  ["Frukt og grønt", ["agurk", "paprika", "salat", "tomat", "brokkoli", "bringebær", "banan", "eple", "grønnsak", "frukt", "potet", "løk", "sitron", "avokado", "mais", "bønne"]],
  ["Meieri", ["melk", "yoghurt", "yogurt", "skyr", "kesam", "rømme", "ost", "egg", "cottage", "smør"]],
  ["Kjøtt og fisk", ["kylling", "kjøtt", "laks", "torsk", "fisk", "svin", "biff", "kalkun", "pølse", "bacon"]],
  ["Tørrvarer", ["ris", "pasta", "havregryn", "granola", "protein", "chiafrø", "chiafro", "lefse", "pitabrød", "rundstykke", "chips", "tortilla", "brød", "mel", "sukker", "saus", "soya", "quinoa", "nøtt", "biscoff"]],
];
function guessShopDept(name) {
  const n = name.toLowerCase();
  for (const [dept, kws] of SHOP_DEPT_KEYWORDS) {
    if (kws.some(k => n.includes(k))) return dept;
  }
  return "Annet";
}
function shopKey(name) { return name.trim().toLowerCase(); }
function addShopItems(names) {
  const list = loadShopList();
  const existing = new Set(list.map(i => shopKey(i.name)));
  names.forEach(n => {
    const k = shopKey(n);
    if (!existing.has(k)) {
      list.push({ id: k + "-" + Date.now() + Math.random(), name: n, dept: guessShopDept(n), checked: false, slot: null });
      existing.add(k);
    }
  });
  saveShopList(list);
  renderShopList();
}
// Adds/updates one ingredient line. If `slot` matches an item already on the list (the same
// recipe+ingredient position), that line is updated in place instead of duplicated - this is
// what makes swapping an ingredient (e.g. kyllingfilet -> kyllingkjøttdeig) replace the old
// shopping-list line rather than add a second one.
function upsertShopItem(name, dept, slot) {
  const list = loadShopList();
  if (slot) {
    const idx = list.findIndex(i => i.slot === slot);
    if (idx !== -1) {
      list[idx].name = name;
      list[idx].dept = dept;
      saveShopList(list);
      return;
    }
  }
  if (list.some(i => shopKey(i.name) === shopKey(name))) return;
  list.push({ id: "shop-" + Date.now() + Math.random(), name, dept, checked: false, slot: slot || null });
  saveShopList(list);
}
function addMealIngredientsToShopList(type, optIdx) {
  const n = DATA.nutritionPlan;
  const opt = n[type] && n[type].options[optIdx];
  if (!opt) return;
  const date = todayISO();
  opt.items.forEach((item, itemIdx) => {
    const slot = `meal:${type}:${optIdx}:${itemIdx}`;
    if (!item.ing) {
      upsertShopItem(item.text, guessShopDept(item.text), slot);
      return;
    }
    const override = getIngOverride(date, type, optIdx, itemIdx);
    const ing = override ? override.ing : item.ing;
    const amount = override ? override.amount : item.amount;
    const data = getIngredient(ing);
    const label = data ? data.label : ing;
    const name = override ? `${amount} g ${label}` : (item.display || `${amount} g ${label}`);
    const dept = (data && data.dept) || guessShopDept(label);
    upsertShopItem(name, dept, slot);
  });
  renderShopList();
}
function openMealPickerDrawer() {
  const n = DATA.nutritionPlan;
  const groups = [
    { key: "breakfast", label: "🥣 Frokost" },
    { key: "lunch", label: "🥙 Lunsj" },
    { key: "snack", label: "🍓 Mellommåltid" },
    { key: "dinner", label: "🍽️ Middag" },
  ];
  const bodyHtml = groups.map(g => `
    <div class="meal-picker-group">
      <div class="meal-picker-group-title">${g.label}</div>
      ${n[g.key].options.map((o, i) => `
        <label class="meal-picker-opt">
          <input type="checkbox" data-meal-type="${g.key}" data-opt-idx="${i}">
          <span>${o.name}</span>
        </label>`).join("")}
    </div>`).join("") + `<button class="btn" id="meal-picker-add">Legg til valgte</button>`;
  openQuicklogDrawer("Velg måltider å legge til", bodyHtml);
  document.getElementById("meal-picker-add").addEventListener("click", () => {
    document.querySelectorAll("#quicklog-drawer-body input[type=checkbox]:checked").forEach(cb => {
      addMealIngredientsToShopList(cb.dataset.mealType, parseInt(cb.dataset.optIdx, 10));
    });
    closeQuicklogDrawer();
  });
}
function renderShopList() {
  const list = loadShopList();
  const el = document.getElementById("shop-list");
  if (!list.length) {
    el.innerHTML = `<li style="border-top:none;color:var(--muted);">Listen er tom</li>`;
    return;
  }
  const byDept = {};
  list.forEach(i => { const d = i.dept || "Annet"; (byDept[d] = byDept[d] || []).push(i); });
  const parts = [];
  SHOP_DEPT_ORDER.forEach(d => {
    const items = byDept[d];
    if (!items || !items.length) return;
    parts.push(`<li class="shop-dept-head">${d}</li>`);
    items.forEach(i => parts.push(`
      <li class="${i.checked ? "checked" : ""}" data-id="${i.id}">
        <input type="checkbox" ${i.checked ? "checked" : ""}>
        <span>${i.name}</span>
        <button data-remove="${i.id}">✕</button>
      </li>`));
  });
  el.innerHTML = parts.join("");

  document.querySelectorAll("#shop-list input[type=checkbox]").forEach(cb => {
    cb.addEventListener("change", () => {
      const id = cb.closest("li").dataset.id;
      const l = loadShopList();
      const item = l.find(x => x.id === id);
      if (item) item.checked = cb.checked;
      saveShopList(l);
      renderShopList();
    });
  });
  document.querySelectorAll("#shop-list button[data-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveShopList(loadShopList().filter(x => x.id !== btn.dataset.remove));
      renderShopList();
    });
  });
}
document.getElementById("shop-add").addEventListener("click", () => {
  const input = document.getElementById("shop-input");
  if (input.value.trim()) { addShopItems([input.value.trim()]); input.value = ""; }
});
document.getElementById("shop-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("shop-add").click();
});
document.getElementById("shop-quickadd-protein").addEventListener("click", () => {
  addShopItems(["Havregryn", "Proteinpulver", "Proteinmelk", "Chiafrø", "Gresk yoghurt", "Mager kesam"]);
});
document.getElementById("shop-quickadd-meals").addEventListener("click", openMealPickerDrawer);
document.getElementById("shop-clear-checked").addEventListener("click", () => {
  saveShopList(loadShopList().filter(i => !i.checked));
  renderShopList();
});
document.getElementById("shop-clear-all").addEventListener("click", () => {
  if (!loadShopList().length) return;
  if (!confirm("Tømme hele handlelisten?")) return;
  saveShopList([]);
  renderShopList();
});

// ---------------------------------------------------------------- søndagsplanlegger (neste uke)
const MEALPREP_HAVE_KEY = "garminDashboardMealprepHave_v1";
const WEEK_AGENDA_KEY = "garminDashboardWeekAgenda_v1";

function loadMealprepHave() { return loadLS(MEALPREP_HAVE_KEY, []); }
function saveMealprepHave(arr) { saveLS(MEALPREP_HAVE_KEY, arr); }

function loadWeekAgenda() { return loadLS(WEEK_AGENDA_KEY, {}); }
function saveWeekAgenda(m) { saveLS(WEEK_AGENDA_KEY, m); }

// bytte av øktype for neste uke - egen select-klasse (ikke "swap") og scoped lytting,
// slik at den ikke krasjer med renderPlan() sin globale "select.swap"-lytter (som bare
// kjenner til p.week, ikke p.nextWeek)
function planSwapSelectHtml(date, resolvedKey) {
  const selKey = SWAP_OPTIONS.includes(resolvedKey) ? resolvedKey : "rest";
  const opts = SWAP_OPTIONS.map(k => `<option value="${k}" ${k === selKey ? "selected" : ""}>${SWAP_NAMES[k]}</option>`).join("");
  return `<select class="plan-next-swap" data-date="${date}" aria-label="Bytt økt">${opts}</select>`;
}
function renderPlanNextWeekTraining() {
  const el = document.getElementById("plan-next-week-training");
  if (!el) return;
  const p = DATA.program;
  if (!p || !p.nextWeek) { el.innerHTML = ""; return; }
  const overrides = loadPlanOverrides();
  el.innerHTML = p.nextWeek.map(d => {
    const r = resolvePlanDay(d, overrides);
    return `<div class="week-day" data-date="${d.date}">
      <div class="wd"><span>${d.weekday}</span></div>
      <div class="sess">${r.label}</div>
      ${planSwapSelectHtml(d.date, r.key)}
    </div>`;
  }).join("");
  el.querySelectorAll(".plan-next-swap").forEach(sel => {
    sel.addEventListener("change", () => {
      const current = loadPlanOverrides();
      const day = p.nextWeek.find(x => x.date === sel.dataset.date);
      if (isDefaultKeyForDay(day, sel.value)) delete current[sel.dataset.date];
      else current[sel.dataset.date] = sel.value;
      savePlanOverrides(current);
      renderPlanNextWeekTraining();
      renderHjemNextWeekPreview();
    });
  });
}

function renderPlanNextWeekMeals() {
  const el = document.getElementById("plan-next-week-meals");
  if (!el) return;
  const p = DATA.program;
  if (!p || !p.nextWeek) { el.innerHTML = ""; return; }
  const n = DATA.nutritionPlan;
  const custom = loadCustomMeals();
  el.innerHTML = p.nextWeek.map(d => {
    const fieldsHtml = ["breakfast", "lunch", "snack", "dinner"].map(type => {
      const names = (n[type].options || []).map(o => o.name).concat((custom[type] || []).map(o => o.name));
      const planned = plannedMealFor(d.date, type);
      const optsHtml = `<option value="">–</option>` + names.map(name =>
        `<option value="${name}" ${planned === name ? "selected" : ""}>${name}</option>`
      ).join("");
      return `<label class="plan-meal-field">${MEAL_TYPE_LABELS[type]}<select class="plan-meal-select" data-date="${d.date}" data-type="${type}">${optsHtml}</select></label>`;
    }).join("");
    return `<div class="plan-meal-day"><div class="wd">${d.weekday} ${fmtShort(d.date)}</div><div class="plan-meal-fields">${fieldsHtml}</div></div>`;
  }).join("");
  el.querySelectorAll(".plan-meal-select").forEach(sel => {
    sel.addEventListener("change", () => {
      if (sel.value) setPlannedMeal(sel.dataset.date, sel.dataset.type, sel.value);
      else clearPlannedMeal(sel.dataset.date, sel.dataset.type);
    });
  });
}

function mealprepCandidates() {
  const n = DATA.nutritionPlan;
  const out = [];
  ["lunch", "dinner"].forEach(type => {
    (n[type].options || []).forEach((opt, idx) => {
      if (opt.mealprep) out.push({ type, idx, opt });
    });
  });
  return out;
}
function scoreMealprepOption(opt, haveSet) {
  const ingItems = (opt.items || []).filter(i => i.ing);
  if (!ingItems.length) return 0;
  return ingItems.filter(i => haveSet.has(i.ing)).length / ingItems.length;
}
function renderMealprepHaveForm() {
  const el = document.getElementById("plan-mealprep-have");
  if (!el) return;
  const all = Object.assign({}, DATA.ingredientCatalog, loadCustomIngredients());
  const have = new Set(loadMealprepHave());
  const byDept = {};
  Object.entries(all).forEach(([key, ing]) => {
    const dept = ing.dept || "Annet";
    (byDept[dept] = byDept[dept] || []).push({ key, label: ing.label });
  });
  el.innerHTML = SHOP_DEPT_ORDER.filter(d => byDept[d]).map(dept => `
    <div class="mealprep-dept">
      <div class="mealprep-dept-label">${dept}</div>
      ${byDept[dept].sort((a, b) => a.label.localeCompare(b.label, "no")).map(i =>
        `<label class="mealprep-ing-check"><input type="checkbox" value="${i.key}" ${have.has(i.key) ? "checked" : ""}> ${i.label}</label>`
      ).join("")}
    </div>
  `).join("");
  el.querySelectorAll("input[type=checkbox]").forEach(cb => {
    cb.addEventListener("change", () => {
      const cur = new Set(loadMealprepHave());
      if (cb.checked) cur.add(cb.value); else cur.delete(cb.value);
      saveMealprepHave(Array.from(cur));
    });
  });
}
function renderMealprepSuggestions() {
  const el = document.getElementById("plan-mealprep-suggestions");
  if (!el) return;
  const have = new Set(loadMealprepHave());
  const scored = mealprepCandidates()
    .map(c => Object.assign({}, c, { score: scoreMealprepOption(c.opt, have) }))
    .filter(c => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
  if (!scored.length) {
    el.innerHTML = `<div class="section-sub" style="margin-top:10px;">Kryss av noen ingredienser du har hjemme, og trykk "Finn forslag".</div>`;
    return;
  }
  const nextWeek = (DATA.program && DATA.program.nextWeek) || [];
  el.innerHTML = scored.map(c => {
    const itemsHtml = (c.opt.items || []).map(item => {
      if (!item.ing) return `<span class="meal-item-text">${item.text}</span>`;
      const ing = getIngredient(item.ing);
      const haveIt = have.has(item.ing);
      return `<span class="meal-item-ing${haveIt ? "" : " mealprep-missing"}">${item.display || `${item.amount} g`} ${ing ? ing.label : item.ing}${haveIt ? " ✓" : ""}</span>`;
    }).join("");
    const dayChecks = nextWeek.map(d => `<label class="mealprep-day-check"><input type="checkbox" value="${d.date}"> ${d.weekday}</label>`).join("");
    return `<div class="mealprep-suggestion" data-type="${c.type}" data-idx="${c.idx}">
      <div class="meal-head"><b>${c.opt.name}</b><span class="meal-macro">~${withKcalMargin(c.opt.kcal)} kcal · ${c.opt.protein} g protein</span></div>
      <div class="meal-items">${itemsHtml}</div>
      <div class="mealprep-days">${dayChecks}</div>
      <button class="btn ghost small mealprep-assign-btn">Legg til i planen</button>
    </div>`;
  }).join("");

  el.querySelectorAll(".mealprep-assign-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".mealprep-suggestion");
      const type = card.dataset.type;
      const idx = parseInt(card.dataset.idx, 10);
      const opt = DATA.nutritionPlan[type].options[idx];
      if (!opt) return;
      const checkedDays = Array.from(card.querySelectorAll(".mealprep-days input:checked")).map(cb => cb.value);
      if (!checkedDays.length) {
        flashSaved("plan-mealprep-saved-msg", "Velg minst én dag først");
        return;
      }
      checkedDays.forEach(date => setPlannedMeal(date, type, opt.name));
      // tekstlinjer (uten "ing") kan ikke krysses av som "har hjemme", så de regnes
      // som manglende som standard - bedre med én overflødig handlelistelinje enn
      // at noe mangler på butikken
      const missingNames = (opt.items || []).filter(i => !i.ing || !have.has(i.ing)).map(i => {
        if (!i.ing) return i.text;
        const ing = getIngredient(i.ing);
        return i.display || `${i.amount} g ${ing ? ing.label : i.ing}`;
      });
      if (missingNames.length) addShopItems(missingNames);
      renderPlanNextWeekMeals();
      flashSaved("plan-mealprep-saved-msg", `Lagt til for ${checkedDays.length} dag${checkedDays.length === 1 ? "" : "er"} ✓${missingNames.length ? " - manglende ingredienser lagt i handlelisten" : ""}`);
    });
  });
}
document.getElementById("plan-mealprep-find-btn").addEventListener("click", renderMealprepSuggestions);

function renderPlanAgenda() {
  const ta = document.getElementById("plan-agenda-text");
  if (!ta) return;
  const p = DATA.program;
  const weekKey = p && p.nextWeek && p.nextWeek[0] ? p.nextWeek[0].date : null;
  if (!weekKey) return;
  ta.value = loadWeekAgenda()[weekKey] || "";
  ta.onblur = () => {
    const m = loadWeekAgenda();
    if (ta.value.trim()) m[weekKey] = ta.value.trim(); else delete m[weekKey];
    saveWeekAgenda(m);
    flashSaved("plan-agenda-saved-msg", "Lagret ✓");
  };
}

// ---- regelbasert ukeplan-generator (ikke ekte AI - se avklaring med henne) ----
// Hun liker ikke ferske/fryste grønnsaker utover agurk og paprika (tekstlinjer, ikke
// strukturerte ingredienser, så de påvirker ikke filteret) - filtrer bort retter som bruker
// brokkoli/søtpotet som strukturert ingrediens.
const GENERATOR_DISLIKED_ING = new Set(["brokkoli", "sotpotet"]);
const GENERATOR_FISH_ING = new Set(["laksefilet", "torsk"]);
function recipeFitsPreferences(opt) {
  return !(opt.items || []).some(i => i.ing && GENERATOR_DISLIKED_ING.has(i.ing));
}
function isFishRecipe(opt) {
  return (opt.items || []).some(i => i.ing && GENERATOR_FISH_ING.has(i.ing));
}
let generatedWeekPlan = null;

function generateWeekMealPlan() {
  const n = DATA.nutritionPlan;
  const days = (DATA.program && DATA.program.nextWeek) || [];
  if (!days.length) return [];
  const likedLunch = n.lunch.options.filter(recipeFitsPreferences);
  const likedDinnerAll = n.dinner.options.filter(recipeFitsPreferences);
  const likedDinnerNonFish = likedDinnerAll.filter(o => !isFishRecipe(o));
  const likedDinnerFish = likedDinnerAll.filter(isFishRecipe);
  // fisk "av og til" - én tilfeldig dag i uken, ikke hver runde gjennom katalogen
  const fishDayIdx = likedDinnerFish.length ? Math.floor(Math.random() * days.length) : -1;
  return days.map((d, i) => {
    const lunch = likedLunch.length ? likedLunch[(i + 1) % likedLunch.length] : null;
    const dinner = (i === fishDayIdx && likedDinnerFish.length)
      ? likedDinnerFish[0]
      : (likedDinnerNonFish.length ? likedDinnerNonFish[i % likedDinnerNonFish.length] : null);
    return { date: d.date, weekday: d.weekday, lunch, dinner };
  });
}

function renderPlanGeneratorPreview() {
  const el = document.getElementById("plan-generated-preview");
  if (!el) return;
  if (!generatedWeekPlan || !generatedWeekPlan.length) { el.innerHTML = ""; return; }
  // egne, normalt ombrytende divs - ikke .meal-items/.meal-item-text, som har white-space:nowrap
  // laget for korte ingredienslinjer og ville sprengt bredden med en hel setning her
  const rowsHtml = generatedWeekPlan.map(row => `
    <div class="plan-meal-day">
      <div class="wd">${row.weekday} ${fmtShort(row.date)}</div>
      ${row.lunch ? `<div class="plan-generated-line">🍽️ ${row.lunch.name} (~${withKcalMargin(row.lunch.kcal)} kcal, ${row.lunch.protein} g protein)</div>` : ""}
      ${row.dinner ? `<div class="plan-generated-line">🍲 ${row.dinner.name} (~${withKcalMargin(row.dinner.kcal)} kcal, ${row.dinner.protein} g protein)</div>` : ""}
    </div>`).join("");
  el.innerHTML = rowsHtml + `<button class="btn small" id="plan-generator-apply-btn" style="margin-top:10px;">Legg inn i søndagsplanleggeren</button>`;
  document.getElementById("plan-generator-apply-btn").addEventListener("click", () => {
    generatedWeekPlan.forEach(row => {
      if (row.lunch) setPlannedMeal(row.date, "lunch", row.lunch.name);
      if (row.dinner) setPlannedMeal(row.date, "dinner", row.dinner.name);
    });
    renderPlanNextWeekMeals();
    generatedWeekPlan = null;
    renderPlanGeneratorPreview();
    flashSaved("plan-generator-saved-msg", "Lagt inn i søndagsplanleggeren ✓");
  });
}
document.getElementById("plan-generate-btn").addEventListener("click", () => {
  generatedWeekPlan = generateWeekMealPlan();
  renderPlanGeneratorPreview();
});

function renderPlanlegg() {
  const p = DATA.program;
  const sub = document.getElementById("plan-week-sub");
  if (sub && p && p.nextWeek && p.nextWeek.length) {
    sub.textContent = `${fmtShort(p.nextWeek[0].date)} – ${fmtShort(p.nextWeek[6].date)} · ${p.nextWeekIsDeload ? "Deload-uke" : p.nextWeekFocus}`;
  }
  renderPlanNextWeekTraining();
  renderPlanNextWeekMeals();
  renderPlanGeneratorPreview();
  renderMealprepHaveForm();
  renderMealprepSuggestions();
  renderPlanAgenda();
}

// ---------------------------------------------------------------- budget
let currentEconMonth = emKeyForDate(todayISO());

document.getElementById("tx-date").value = todayISO();

function populateCategorySelect() {
  document.getElementById("tx-category").innerHTML = categoryOptionsHtml(loadBudgetConfig());
}

function categoryRowHtml(c, emKey) {
  const cap = getCategoryCap(c, emKey);
  const spent = categorySpent(c.key, emKey);
  const pct = cap ? 100 * spent / cap : (spent > 0 ? 100 : 0);
  const barWidth = Math.min(100, pct);
  const cls = pct >= 100 ? "over" : pct >= 80 ? "warn" : "good";
  const over = spent > cap;
  return `<div class="cat-row" data-key="${c.key}">
    <div class="cat-head"><span>${c.icon ? c.icon + " " : ""}${c.label}</span><b>${spent.toLocaleString()} / <input class="cap-edit" type="number" value="${cap}" data-cat="${c.key}"> kr</b></div>
    <div class="cat-bar"><div class="${cls}" style="width:${barWidth}%"></div></div>
    ${over ? `<div class="cat-grace">💛 Over budsjett denne økonomimåneden - det går bra, juster og fortsett.</div>` : ""}
  </div>`;
}

// faste utgifter spores ikke som "brukt" - bare det faste beløpet hun uansett betaler
function fixedCategoryRowHtml(c, emKey) {
  const cap = getCategoryCap(c, emKey);
  return `<div class="cat-row" data-key="${c.key}">
    <div class="cat-head"><span>${c.icon ? c.icon + " " : ""}${c.label}</span><b><input class="cap-edit" type="number" value="${cap}" data-cat="${c.key}"> kr</b></div>
  </div>`;
}

function renderCategoryBreakdown() {
  const cfg = loadBudgetConfig();
  const fixed = cfg.categories.filter(c => c.type === "fixed");
  const variable = cfg.categories.filter(c => c.type === "variable");
  document.getElementById("fixed-cat-list").innerHTML = fixed.map(c => fixedCategoryRowHtml(c, currentEconMonth)).join("");
  document.getElementById("variable-cat-list").innerHTML = variable.map(c => categoryRowHtml(c, currentEconMonth)).join("");

  document.querySelectorAll(".budget-cat-list .cap-edit").forEach(inp => {
    inp.addEventListener("change", () => {
      setCategoryCap(inp.dataset.cat, currentEconMonth, parseFloat(inp.value) || 0);
      renderBudget();
    });
  });
}

function renderBudgetSummary() {
  const cfg = loadBudgetConfig();
  const emKey = currentEconMonth;
  const start = emStart(emKey), end = emEnd(emKey);
  // "Brukt på variable utgifter" betyr det samme her som på Hjem - ikke faste utgifter
  // (penger hun betaler uansett) og ikke sparing (fortsatt hennes, bare lagt til side).
  // "Igjen" trekker likevel fra alle tre, siden det skal gjenspeile reelt handlingsrom.
  const fixedTotal = cfg.categories.filter(c => c.type === "fixed").reduce((s, c) => s + getCategoryCap(c, emKey), 0);
  const variableKeys = cfg.categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
  const savingsKeys = cfg.categories.filter(c => c.savings).map(c => c.key);
  const tx = loadTransactions().filter(t => t.date >= start && t.date <= end);
  const variableSpent = tx.filter(t => variableKeys.includes(t.category)).reduce((s, t) => s + t.amount, 0);
  const savingsSpent = tx.filter(t => savingsKeys.includes(t.category)).reduce((s, t) => s + t.amount, 0);
  document.getElementById("budget-summary").innerHTML = `
    <div class="snapshot-chip">Inntekt<b>${cfg.income.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Faste utgifter<b>${fixedTotal.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Brukt på variable utgifter<b>${variableSpent.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Satt av til sparing<b>${savingsSpent.toLocaleString()} kr</b></div>
    <div class="snapshot-chip">Igjen<b>${(cfg.income - fixedTotal - variableSpent - savingsSpent).toLocaleString()} kr</b></div>
  `;
}

function renderTxList() {
  const cfg = loadBudgetConfig();
  const catLabel = key => (cfg.categories.find(c => c.key === key) || {}).label || key;
  const start = emStart(currentEconMonth), end = emEnd(currentEconMonth);
  const tx = loadTransactions().filter(t => t.date >= start && t.date <= end).sort((a, b) => b.date.localeCompare(a.date));
  document.getElementById("tx-list").innerHTML = tx.map(t => `
    <li data-id="${t.id}"><span>${fmtShort(t.date)} · ${catLabel(t.category)} · ${t.name || ""}${t.autoLogged ? " 🔁" : ""}</span>
      <b>${t.amount} kr</b>
      <button class="log-remove-btn" data-tx-remove="${t.id}">✕</button>
    </li>`).join("") || `<li style="border-top:none;color:var(--muted);">Ingen transaksjoner denne økonomimåneden</li>`;

  document.querySelectorAll("#tx-list button[data-tx-remove]").forEach(btn => {
    btn.addEventListener("click", () => {
      saveTransactions(loadTransactions().filter(t => t.id !== btn.dataset.txRemove));
      renderBudget();
    });
  });
}

function fundProgress() {
  const balance = fundBalance();
  const pct = Math.min(100, 100 * balance / DATA.dogFund.target);
  const tx = loadTransactions().filter(t => t.category === DATA.dogFund.category);
  const months = new Set(tx.map(t => monthOf(t.date))).size || 1;
  const avgPerMonth = tx.reduce((s, t) => s + t.amount, 0) / months;
  const remaining = DATA.dogFund.target - balance;

  let etaText = "Legg til sparing for å se et anslag";
  if (remaining <= 0) {
    etaText = "Målet er nådd! 🐶";
  } else if (avgPerMonth > 0) {
    const monthsLeft = Math.ceil(remaining / avgPerMonth);
    etaText = `I dagens tempo (~${Math.round(avgPerMonth)} kr/mnd): ca. ${monthsLeft} ${monthsLeft === 1 ? "måned" : "måneder"} igjen`;
  }
  return { balance, pct, remaining, etaText };
}

function renderFund() {
  const { balance, pct, etaText } = fundProgress();
  document.getElementById("fund-card").innerHTML = `
    <div class="fund-head">
      <div>🐶 Hundefond</div>
      <div class="fund-amount">${balance.toLocaleString()} / ${DATA.dogFund.target.toLocaleString()} kr</div>
    </div>
    <div class="fund-bar"><div style="width:${pct}%"></div></div>
    <div class="fund-eta">${etaText}</div>
    <div class="fund-goal-edit" style="margin-top:8px;display:flex;gap:6px;align-items:center;">
      <input type="number" step="500" id="fund-goal-input" value="${DATA.dogFund.target}" style="width:90px;">
      <button class="btn ghost small" id="fund-goal-save">Lagre sparemål</button>
    </div>
  `;
  document.getElementById("fund-goal-save").addEventListener("click", () => {
    const val = parseInt(document.getElementById("fund-goal-input").value, 10);
    if (!val) return;
    const s = loadSettings();
    s.savingsTarget = val;
    saveSettings(s);
    DATA.dogFund.target = val;
    renderBudget();
  });
}

function loadForgottenSavings() { return loadLS(FORGOTTEN_SAVINGS_KEY, 0); }
function saveForgottenSavings(v) { saveLS(FORGOTTEN_SAVINGS_KEY, v); }

function renderForgottenSavings(animate) {
  const card = document.getElementById("forgotten-savings-card");
  const pot = loadForgottenSavings();
  card.innerHTML = `
    <div class="fs-info">🪙 Glemt sparing<br>Avrunding fra utgifter, samlet opp automatisk</div>
    <div class="fs-amount">${Math.round(pot).toLocaleString()} kr</div>
    <button class="btn secondary small" id="fs-move" ${pot > 0 ? "" : "disabled"}>Flytt til hundefondet</button>
  `;
  if (animate) {
    card.classList.add("pulse");
    setTimeout(() => card.classList.remove("pulse"), 650);
  }
  document.getElementById("fs-move").addEventListener("click", () => {
    const amount = loadForgottenSavings();
    if (!amount) return;
    const tx = loadTransactions();
    tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category: DATA.dogFund.category, name: "Glemt sparing" });
    saveTransactions(tx);
    saveForgottenSavings(0);
    renderBudget();
  });
}

function renderBudget() {
  renderCategoryBreakdown();
  renderBudgetSummary();
  renderTxList();
  renderFund();
  renderForgottenSavings();
  renderLevel();
  renderWeeklySnapshot();
  renderHjemTodayTx();
  renderHjemFinance();
  renderSavingsGoals();
  renderExpenseTrends();
}

document.getElementById("em-label").textContent = emLabel(currentEconMonth);
function shiftEconMonth(delta) {
  currentEconMonth = emAddMonths(currentEconMonth, delta);
  document.getElementById("em-label").textContent = emLabel(currentEconMonth);
  renderCategoryBreakdown();
  renderBudgetSummary();
  renderTxList();
}
document.getElementById("em-prev").addEventListener("click", () => shiftEconMonth(-1));
document.getElementById("em-next").addEventListener("click", () => shiftEconMonth(1));

populateCategorySelect();

function addTransactionWithRoundUp(date, amount, category, name) {
  const tx = loadTransactions();
  tx.push({ id: "tx-" + Date.now() + Math.random(), date, amount, category, name });
  saveTransactions(tx);
  let roundedUp = false;
  if (!isSavingsCategory(category)) {
    const roundUp = Math.ceil(amount / 10) * 10 - amount;
    if (roundUp > 0) {
      saveForgottenSavings(loadForgottenSavings() + roundUp);
      roundedUp = true;
    }
  }
  renderNutritionCoach();
  return roundedUp;
}

document.getElementById("tx-add").addEventListener("click", () => {
  const date = document.getElementById("tx-date").value || todayISO();
  const amount = parseFloat(document.getElementById("tx-amount").value);
  const category = document.getElementById("tx-category").value;
  const name = document.getElementById("tx-name").value.trim();
  if (!amount) return;
  const roundedUp = addTransactionWithRoundUp(date, amount, category, name);
  document.getElementById("tx-amount").value = "";
  document.getElementById("tx-name").value = "";
  currentEconMonth = emKeyForDate(date);
  document.getElementById("em-label").textContent = emLabel(currentEconMonth);
  renderBudget();
  if (roundedUp) renderForgottenSavings(true);
});

// "Kjøpe eller spare?" - penger hun bevisst lar være å bruke på noe hun var fristet
// av, og legger i Sparekrukka i stedet (ikke hundefondet - det er et eget, separat mål).
const SPAREKRUKKE_KEY = "sparekrukke";
function addToSparekrukke(amount, name) {
  const tx = loadTransactions();
  tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category: SPAREKRUKKE_KEY, name: name || "Spar i stedet" });
  saveTransactions(tx);
  document.getElementById("save-name").value = "";
  document.getElementById("buy-check-out").innerHTML = "";
  renderBudget();
}
document.getElementById("save-add").addEventListener("click", () => {
  const amount = parseFloat(document.getElementById("save-amount").value);
  if (!amount) return;
  addToSparekrukke(amount, document.getElementById("save-name").value.trim());
  document.getElementById("save-amount").value = "";
});

const wageInput = document.getElementById("buy-wage");
const rateInput = document.getElementById("buy-rate");
const savedWage = loadLS(WAGE_KEY, null);
const savedRate = loadLS(RATE_KEY, null);
if (savedWage != null) wageInput.value = savedWage;
if (savedRate != null) rateInput.value = savedRate;
wageInput.addEventListener("change", () => saveLS(WAGE_KEY, wageInput.value ? parseFloat(wageInput.value) : null));
rateInput.addEventListener("change", () => saveLS(RATE_KEY, rateInput.value ? parseFloat(rateInput.value) : null));

document.getElementById("buy-check").addEventListener("click", () => {
  const amount = parseFloat(document.getElementById("save-amount").value);
  const out = document.getElementById("buy-check-out");
  if (!amount) { out.innerHTML = ""; return; }
  const target = savingsTarget(SPAREKRUKKE_KEY);
  const balance = savingsBalance(SPAREKRUKKE_KEY);
  const remaining = Math.max(0, target - balance);
  const wage = parseFloat(wageInput.value);
  const rate = parseFloat(rateInput.value);
  const hoursLine = wage ? `<div class="buy-check-box">Det er <b>${(amount / wage).toFixed(1)} timer</b> av arbeidstiden din.</div>` : "";
  let growthHtml = "";
  if (rate) {
    const chips = [5, 10, 20].map(years => {
      const grown = amount * Math.pow(1 + rate / 100, years);
      return `<div class="buy-growth-chip">${years} år<b>${Math.round(grown).toLocaleString()} kr</b></div>`;
    }).join("");
    growthHtml = `<div class="section-sub" style="margin:10px 0 0;">Hvis du sparer det i stedet og investerer til ${rate}% årlig avkastning:</div><div class="buy-growth-row">${chips}</div>`;
  }
  const fundLine = target
    ? `<div class="buy-check-box">${amount.toLocaleString()} kr er <b>${(100 * amount / target).toFixed(1)}%</b> av sparemålet for Sparekrukka${remaining > 0 ? ` - <b>${(100 * amount / remaining).toFixed(1)}%</b> av det som gjenstår` : ""}.</div>`
    : "";
  out.innerHTML = `${fundLine}${hoursLine}${growthHtml}`;
});

document.querySelectorAll(".save-presets button[data-preset]").forEach(btn => {
  btn.addEventListener("click", () => {
    addToSparekrukke(parseFloat(btn.dataset.preset), document.getElementById("save-name").value.trim());
  });
});

renderWeightLog();
renderWeightTrend();
renderWeightChart();
renderMeasureLog();
renderPlateau();
renderShopList();
renderBudget();

// ---------------------------------------------------------------- stat cards

// ---------------------------------------------------------------- weekly by sport chart
const SPORT_LABELS_NO = { Strength: "Styrke", Cycling: "Sykling", Running: "Løping", Walking: "Gange", Other: "Annet" };

// which sports are filtered out of the "Denne uken vs. nylige uker" chart - toggled via the legend
const hiddenSports = new Set();

function renderWeeklySport() {
  const svg = document.getElementById("chart-weekly-sport");
  const tooltip = document.getElementById("tt-weekly");
  const legend = document.getElementById("sport-legend");
  const weeks = DATA.weeklyBySport;
  const sports = DATA.sportOrder;
  const colors = DATA.sportColors;

  legend.innerHTML = sports.map(sp => `
    <button class="sport-legend-btn${hiddenSports.has(sp) ? " off" : ""}" data-sport="${sp}">
      <i style="background:${colors[sp]}"></i>${SPORT_LABELS_NO[sp] || sp}
    </button>`).join("");
  legend.querySelectorAll(".sport-legend-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const sp = btn.dataset.sport;
      if (hiddenSports.has(sp)) hiddenSports.delete(sp); else hiddenSports.add(sp);
      renderWeeklySport();
    });
  });

  const visibleSports = sports.filter(sp => !hiddenSports.has(sp));

  const w = 1000, h = 190, padLeft = 40, padBottom = 24, padTop = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";
  const plotW = w - padLeft - 10;
  const plotH = h - padBottom - padTop;
  const barGroupW = plotW / weeks.length;
  const barW = Math.min(14, barGroupW / (visibleSports.length + 1));

  let maxMinutes = 0;
  weeks.forEach(wk => visibleSports.forEach(sp => {
    const e = wk.sports[sp];
    if (e) maxMinutes = Math.max(maxMinutes, e.minutes);
  }));
  maxMinutes = maxMinutes || 60;

  // gridlines
  for (let i = 0; i <= 4; i++) {
    const y = padTop + plotH - (i / 4) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - 10}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${Math.round((i / 4) * maxMinutes)}</text>`;
  }

  weeks.forEach((wk, wi) => {
    const groupX = padLeft + wi * barGroupW + barGroupW / 2;
    visibleSports.forEach((sp, si) => {
      const e = wk.sports[sp];
      const x = groupX - (visibleSports.length * barW) / 2 + si * barW;
      if (e) {
        const bh = (e.minutes / maxMinutes) * plotH;
        const y = padTop + plotH - bh;
        svg.innerHTML += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW - 2}" height="${bh.toFixed(1)}" fill="${colors[sp]}" rx="2"
          data-week="${wk.week}" data-sport="${sp}" data-minutes="${e.minutes}" data-sessions="${e.sessions}" data-dist="${e.distanceKm}" class="bar"/>`;
      }
    });
    svg.innerHTML += `<text x="${groupX}" y="${h - 6}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(wk.week)}</text>`;
  });

  svg.querySelectorAll(".bar").forEach(bar => {
    bar.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${SPORT_LABELS_NO[bar.dataset.sport] || bar.dataset.sport}: ${bar.dataset.sessions} økt(er), ${bar.dataset.minutes} min, ${bar.dataset.dist} km`;
    });
    bar.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}
renderWeeklySport();

(function renderVo2Max() {
  const section = document.getElementById("vo2max-section");
  const card = document.getElementById("vo2max-card");
  const v = DATA.vo2Max;
  if (!section || !card || !v || v.vo2Max == null) return; // intet funnet (eller ikke hentet ennå) - skjul seksjonen
  const rows = [
    `<div class="snapshot-chip">VO2 Max<b>${v.vo2Max}</b></div>`,
    `<div class="snapshot-chip">Sist beregnet<b>${fmtShort(v.date)}</b></div>`,
  ];
  if (v.sport) rows.push(`<div class="snapshot-chip">Basert på<b>${v.sport}</b></div>`);
  card.innerHTML = `<div class="snapshot-row">${rows.join("")}</div>`;
  section.style.display = "";
})();

// ---------------------------------------------------------------- line charts
function renderLineChart(svgId, ttId, weeks, values, color, unit) {
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!weeks || !weeks.length) { svg.outerHTML = '<div style="color:#8a8580;font-size:13px;">Ingen data ennå</div>'; return; }

  const w = 480, h = 130, padLeft = 36, padBottom = 20, padTop = 10, padRight = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const plotW = w - padLeft - padRight;
  const plotH = h - padBottom - padTop;

  const clean = values.map(v => (v === null || v === undefined ? null : v));
  const present = clean.filter(v => v !== null);
  const min = Math.min(...present), max = Math.max(...present);
  const range = (max - min) || 1;
  const step = plotW / Math.max(weeks.length - 1, 1);

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - padRight}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${(min + (i / 3) * range).toFixed(1)}</text>`;
  }

  let pathPts = [];
  let dots = "";
  clean.forEach((v, i) => {
    if (v === null) return;
    const x = padLeft + i * step;
    const y = padTop + plotH - ((v - min) / range) * plotH;
    pathPts.push([x, y]);
    dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${color}" data-week="${weeks[i]}" data-val="${v}" class="dot" opacity="0"/>`;
  });
  const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const areaPath = path + ` L ${pathPts[pathPts.length-1][0].toFixed(1)},${(padTop+plotH).toFixed(1)} L ${pathPts[0][0].toFixed(1)},${(padTop+plotH).toFixed(1)} Z`;

  svg.innerHTML += `<path d="${areaPath}" fill="${color}" opacity="0.08"/>`;
  svg.innerHTML += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
  svg.innerHTML += dots;

  // x labels: first, middle, last
  [0, Math.floor(weeks.length / 2), weeks.length - 1].forEach(i => {
    const x = padLeft + i * step;
    svg.innerHTML += `<text x="${x}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(weeks[i])}</text>`;
  });

  svg.querySelectorAll(".dot").forEach(dot => {
    const hit = dot.cloneNode();
    hit.setAttribute("r", 8);
    hit.setAttribute("opacity", 0);
    hit.classList.add("hit");
    svg.appendChild(hit);
    hit.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${fmtDate(hit.dataset.week)}: ${hit.dataset.val} ${unit}`;
    });
    hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}

// single-series bar chart, styled like renderLineChart above (used for the Hjem "siste 7 dager" steps chart)
function renderSimpleBarChart(svgId, ttId, labels, values, color, unit) {
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!labels || !labels.length) { svg.outerHTML = '<div style="color:#8a8580;font-size:13px;">Ingen data ennå</div>'; return; }

  const w = 480, h = 130, padLeft = 36, padBottom = 20, padTop = 10, padRight = 10;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const plotW = w - padLeft - padRight;
  const plotH = h - padBottom - padTop;

  const present = values.filter(v => v !== null && v !== undefined);
  const max = present.length ? Math.max(...present) : 0;
  const scale = max || 1;
  const groupW = plotW / labels.length;
  const barW = Math.min(36, groupW * 0.6);

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y}" x2="${w - padRight}" y2="${y}" stroke="#ece7e0" stroke-width="1"/>`;
    svg.innerHTML += `<text x="${padLeft - 6}" y="${y + 3}" font-size="9" fill="#8a8580" text-anchor="end">${Math.round((i / 3) * scale)}</text>`;
  }

  values.forEach((v, i) => {
    const groupX = padLeft + i * groupW + groupW / 2;
    svg.innerHTML += `<text x="${groupX}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${fmtShort(labels[i])}</text>`;
    if (v === null || v === undefined) return;
    const bh = (v / scale) * plotH;
    const x = groupX - barW / 2;
    const y = padTop + plotH - bh;
    svg.innerHTML += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" fill="${color}" rx="4"
      data-label="${labels[i]}" data-val="${v}" class="bar"/>`;
  });

  svg.querySelectorAll(".bar").forEach(bar => {
    bar.addEventListener("mousemove", e => {
      const r = svg.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (e.clientX - r.left) + "px";
      tooltip.style.top = (e.clientY - r.top) + "px";
      tooltip.textContent = `${fmtDate(bar.dataset.label)}: ${bar.dataset.val} ${unit}`;
    });
    bar.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
  });
}

const TREND_WEEKS_SHOWN = 26; // ~6 months - full history is overkill for these charts
renderLineChart("chart-load", "tt-load", DATA.trends.trainingLoad.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.trainingLoad.values.slice(-TREND_WEEKS_SHOWN), "#7a1f3d", "load");
renderLineChart("chart-rhr", "tt-rhr", DATA.trends.restingHR.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.restingHR.values.slice(-TREND_WEEKS_SHOWN), "#9b3456", "bpm");
renderLineChart("chart-hrv", "tt-hrv", DATA.trends.hrv.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.hrv.values.slice(-TREND_WEEKS_SHOWN), "#a46cc0", "ms");
renderLineChart("chart-sleep", "tt-sleep", DATA.trends.sleepHours.weeks.slice(-TREND_WEEKS_SHOWN), DATA.trends.sleepHours.values.slice(-TREND_WEEKS_SHOWN), "#e8a3b6", "hrs");

// ---- Hjem "siste 7 dager" mini-trends ----
(function renderHjemWeekTrends() {
  const history = (DATA.dailyHistory || []).slice(-7);
  const labels = history.map(d => d.date);
  renderSimpleBarChart("hjem-chart-steps", "tt-hjem-steps", labels, history.map(d => d.steps), "#f6c667", "skritt");
  renderLineChart("hjem-chart-sleep", "tt-hjem-sleep", labels, history.map(d => d.sleepHours), "#8b668e", "t");
})();

// ---------------------------------------------------------------- generic multi-series trend chart (Fremgang)
// series: [{ name, color, values, unit, axis: "left"|"right", decimals }], shared x-axis labels.
// Used wherever two differently-scaled metrics need to sit on one timeline (dual y-axis),
// or several same-unit series need to be compared directly (shared y-axis).
function renderTrendChart(svgId, ttId, labels, series, opts) {
  opts = opts || {};
  const svg = document.getElementById(svgId);
  const tooltip = document.getElementById(ttId);
  if (!svg) return;
  const hasData = labels && labels.length && series.some(s => s.values.some(v => v != null));
  if (!hasData) {
    svg.outerHTML = '<div style="color:#8a8580;font-size:13px;padding:30px 0;text-align:center;">Ikke nok data ennå</div>';
    if (tooltip) tooltip.style.opacity = 0;
    return;
  }
  svg.classList.add("ml-chart");
  if (tooltip) tooltip.classList.add("ml");

  const hasRight = series.some(s => s.axis === "right");
  const w = 480, h = 140, padLeft = 38, padRight = hasRight ? 38 : 12, padTop = 14, padBottom = 22;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = "";
  const plotW = w - padLeft - padRight, plotH = h - padTop - padBottom;
  const step = plotW / Math.max(labels.length - 1, 1);
  const xAt = i => padLeft + i * step;

  function scaleFor(vals) {
    const present = vals.filter(v => v != null);
    if (!present.length) return { min: 0, max: 1 };
    let min = Math.min(...present), max = Math.max(...present);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * 0.12;
    return { min: min - pad, max: max + pad };
  }
  const leftSeries = series.filter(s => s.axis !== "right");
  const rightSeries = series.filter(s => s.axis === "right");
  const leftScale = scaleFor(leftSeries.flatMap(s => s.values));
  const rightScale = rightSeries.length ? scaleFor(rightSeries.flatMap(s => s.values)) : null;
  const yAt = (v, axis) => {
    const sc = axis === "right" ? rightScale : leftScale;
    return padTop + plotH - ((v - sc.min) / (sc.max - sc.min)) * plotH;
  };

  for (let i = 0; i <= 3; i++) {
    const y = padTop + plotH - (i / 3) * plotH;
    svg.innerHTML += `<line x1="${padLeft}" y1="${y.toFixed(1)}" x2="${w - padRight}" y2="${y.toFixed(1)}" stroke="#ece7e0" stroke-width="1"/>`;
    const leftVal = leftScale.min + (i / 3) * (leftScale.max - leftScale.min);
    svg.innerHTML += `<text x="${padLeft - 6}" y="${(y + 3).toFixed(1)}" font-size="9" fill="#8a8580" text-anchor="end">${leftVal.toFixed(opts.leftDecimals ?? 0)}</text>`;
    if (rightScale) {
      const rightVal = rightScale.min + (i / 3) * (rightScale.max - rightScale.min);
      svg.innerHTML += `<text x="${w - padRight + 6}" y="${(y + 3).toFixed(1)}" font-size="9" fill="#8a8580" text-anchor="start">${rightVal.toFixed(opts.rightDecimals ?? 0)}</text>`;
    }
  }

  series.forEach(s => {
    const pathPts = [];
    let dots = "";
    s.values.forEach((v, i) => {
      if (v == null) return;
      const x = xAt(i), y = yAt(v, s.axis);
      pathPts.push([x, y]);
      dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${s.color}" opacity="0.9"/>`;
    });
    if (pathPts.length) {
      const path = pathPts.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      svg.innerHTML += `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
    }
    svg.innerHTML += dots;
  });

  const labelIdxs = labels.length > 1 ? [0, Math.floor(labels.length / 2), labels.length - 1] : [0];
  labelIdxs.forEach(i => {
    const x = xAt(i);
    svg.innerHTML += `<text x="${x.toFixed(1)}" y="${h - 4}" font-size="9" fill="#8a8580" text-anchor="middle">${opts.fmtLabel ? opts.fmtLabel(labels[i]) : fmtShort(labels[i])}</text>`;
  });

  if (tooltip) {
    labels.forEach((lab, i) => {
      const x = xAt(i);
      const hit = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      hit.setAttribute("x", (x - step / 2).toFixed(1));
      hit.setAttribute("y", padTop);
      hit.setAttribute("width", Math.max(step, 4).toFixed(1));
      hit.setAttribute("height", plotH);
      hit.setAttribute("fill", "transparent");
      svg.appendChild(hit);
      hit.addEventListener("mousemove", e => {
        const r = svg.getBoundingClientRect();
        tooltip.style.opacity = 1;
        tooltip.style.left = (e.clientX - r.left) + "px";
        tooltip.style.top = (e.clientY - r.top) + "px";
        const lines = series.filter(s => s.values[i] != null).map(s =>
          `${s.name}: <b>${s.values[i].toLocaleString()}${s.unit ? " " + s.unit : ""}</b>`
        );
        tooltip.innerHTML = `${opts.fmtLabel ? opts.fmtLabel(lab) : fmtDate(lab)}<br>${lines.join("<br>")}`;
      });
      hit.addEventListener("mouseleave", () => tooltip.style.opacity = 0);
    });
  }

  if (opts.legendId) {
    const el = document.getElementById(opts.legendId);
    if (el) el.innerHTML = series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("");
  }
}

function alignWeeklySeries(seriesList) {
  // seriesList: [{weeks, values}, ...] from DATA.trends - different metrics can have
  // slightly different week coverage, so align them onto their combined week list.
  const allWeeks = Array.from(new Set(seriesList.flatMap(s => s.weeks))).sort();
  const valuesList = seriesList.map(s => {
    const byWeek = {};
    s.weeks.forEach((w, i) => { byWeek[w] = s.values[i]; });
    return allWeeks.map(w => (byWeek[w] != null ? byWeek[w] : null));
  });
  return { weeks: allWeeks, valuesList };
}

// ---------------------------------------------------------------- fremgang: kropp & mål
const BODY_MEASURE_LABELS = { waist: "Mage", hips: "Hofte", arm: "Arm", thigh: "Lår", chest: "Bryst" };
let bodyChartPeriodMonths = 12;
let bodyChartMeasure = "waist";

function renderWeightGoalInput() {
  const inp = document.getElementById("weight-goal-input");
  if (!inp) return;
  const goal = loadSettings().weightGoal;
  inp.value = goal != null ? goal : "";
  document.getElementById("weight-goal-save").addEventListener("click", () => {
    const val = parseFloat(inp.value);
    const s = loadSettings();
    s.weightGoal = Number.isNaN(val) ? null : val;
    saveSettings(s);
    renderBodyGoalChart();
  });
}

// ---- calorie calibration: does logged intake/burn actually match real weight change? ----
function computeCalorieCalibration() {
  const history = (DATA.dailyHistory || []).filter(d => d.calories != null);
  if (history.length < 10) return null;

  const weightLog = effectiveWeightLog().sort((a, b) => a.date.localeCompare(b.date));
  if (weightLog.length < 2) return null;
  const avgSeries = weightRollingAvgSeries(weightLog);

  function weightNear(targetDate) {
    let best = null, bestDiff = Infinity;
    weightLog.forEach((e, i) => {
      const diff = Math.abs(new Date(e.date + "T00:00:00") - new Date(targetDate + "T00:00:00"));
      if (diff < bestDiff) { bestDiff = diff; best = avgSeries[i]; }
    });
    return bestDiff <= 10 * 24 * 3600 * 1000 ? best : null;
  }
  const startWeight = weightNear(history[0].date);
  const endWeight = weightNear(history[history.length - 1].date);
  if (startWeight == null || endWeight == null) return null;

  let totalDeficit = 0, loggedDays = 0;
  history.forEach(d => {
    const totals = dayNutritionTotals(d.date);
    if (totals.mealsLogged.length < 2) return; // skip days that weren't really logged
    totalDeficit += d.calories - totals.kcal;
    loggedDays++;
  });
  if (loggedDays < 7) return null;

  const KCAL_PER_KG = 7700;
  const impliedChangeKg = -totalDeficit / KCAL_PER_KG;
  const actualChangeKg = endWeight - startWeight;
  const extraDailyDeficitKcal = Math.round(((impliedChangeKg - actualChangeKg) * KCAL_PER_KG) / loggedDays);

  return {
    loggedDays, impliedChangeKg, actualChangeKg, extraDailyDeficitKcal,
    startDate: history[0].date, endDate: history[history.length - 1].date,
  };
}

function renderCalorieCalibration() {
  const el = document.getElementById("calorie-calibration-note");
  if (!el) return;
  const c = computeCalorieCalibration();
  if (!c) { el.innerHTML = ""; return; }

  const impliedTxt = `${c.impliedChangeKg >= 0 ? "+" : ""}${c.impliedChangeKg.toFixed(1)} kg`;
  const actualTxt = `${c.actualChangeKg >= 0 ? "+" : ""}${c.actualChangeKg.toFixed(1)} kg`;
  let verdict;
  if (Math.abs(c.extraDailyDeficitKcal) < 80) {
    verdict = "Loggen din stemmer godt med faktisk vektendring - ingen justering nødvendig akkurat nå.";
  } else if (c.extraDailyDeficitKcal > 0) {
    verdict = `Du har i snitt hatt et ${Math.abs(c.extraDailyDeficitKcal)} kcal/dag <b>større</b> underskudd enn loggen viser - kroppen din ser ut til å forbrenne litt mer enn Garmin-tallene antyder, eller du har fått i deg litt mindre enn det som er logget.`;
  } else {
    verdict = `Du har i snitt hatt et ${Math.abs(c.extraDailyDeficitKcal)} kcal/dag <b>mindre</b> underskudd enn loggen viser - sjekk om noe blir spist uten å bli logget, eller om Garmin overvurderer forbrenningen din litt.`;
  }
  el.innerHTML = `<div class="context-note">
    <b>Kalorikalibrering</b> (siste ${c.loggedDays} fullt loggede dager, ${fmtShort(c.startDate)}–${fmtShort(c.endDate)}): loggen antydet ${impliedTxt}, du gikk faktisk ${actualTxt}. ${verdict}
  </div>`;
}

function renderBodyGoalChart() {
  if (!document.getElementById("chart-body")) return;
  const cutoff = isoAddDays(todayISO(), -bodyChartPeriodMonths * 30);
  const weightInRange = effectiveWeightLog().filter(e => e.date >= cutoff).sort((a, b) => a.date.localeCompare(b.date));
  const measureInRange = loadMeasureLog()
    .filter(e => e.date >= cutoff && e[bodyChartMeasure] != null)
    .sort((a, b) => a.date.localeCompare(b.date));

  const weightAvgSeries = weightInRange.length ? weightRollingAvgSeries(weightInRange) : [];
  const allDates = Array.from(new Set([...weightInRange.map(e => e.date), ...measureInRange.map(e => e.date)])).sort();
  const weightByDate = {};
  weightInRange.forEach((e, i) => { weightByDate[e.date] = weightAvgSeries[i]; });
  const measureByDate = {};
  measureInRange.forEach(e => { measureByDate[e.date] = e[bodyChartMeasure]; });

  const weightVals = allDates.map(d => (weightByDate[d] != null ? weightByDate[d] : null));
  const measureVals = allDates.map(d => (measureByDate[d] != null ? measureByDate[d] : null));
  const measureLabel = BODY_MEASURE_LABELS[bodyChartMeasure];

  // Vekt (kg) og mål (cm) har helt ulike skalaer - å plotte dem på separate venstre/høyre-akser
  // kan se ut som de følger hverandre (eller ikke) rent tilfeldig, avhengig av akse-skalering.
  // Viser i stedet begge som % endring fra periodens start, på samme akse - da er det faktisk
  // riktig å sammenligne linjene direkte.
  const pctChangeSeries = vals => {
    const base = vals.find(v => v != null);
    if (base == null) return vals.map(() => null);
    return vals.map(v => (v == null ? null : Math.round(((v - base) / base) * 1000) / 10));
  };
  renderTrendChart("chart-body", "tt-body", allDates, [
    { name: "Vekt", color: "#7a1f3d", values: pctChangeSeries(weightVals), unit: "%" },
    { name: measureLabel, color: "#a46cc0", values: pctChangeSeries(measureVals), unit: "%" },
  ], { legendId: "legend-body", leftDecimals: 1 });

  const note = document.getElementById("body-context-note");
  if (!note) return;
  const wVals = weightVals.filter(v => v != null);
  const mVals = measureVals.filter(v => v != null);

  const weightGoal = loadSettings().weightGoal;
  let goalPhrase = "";
  if (weightGoal != null && wVals.length) {
    const latest = wVals[wVals.length - 1];
    const gap = latest - weightGoal;
    goalPhrase = Math.abs(gap) < 0.3
      ? ` Du er på målvekten din (${weightGoal} kg)! 🎉`
      : ` Du er ${Math.abs(gap).toFixed(1)} kg ${gap > 0 ? "over" : "under"} målvekten din på ${weightGoal} kg.`;
  }

  if (wVals.length < 2 && mVals.length < 2) {
    note.textContent = `Ikke nok logget data i denne perioden ennå til å si noe om trenden.${goalPhrase}`;
    return;
  }
  const weightDiff = wVals.length >= 2 ? wVals[wVals.length - 1] - wVals[0] : null;
  const measureDiff = mVals.length >= 2 ? mVals[mVals.length - 1] - mVals[0] : null;
  const weightPhrase = weightDiff == null ? "Ikke nok vektdata ennå i perioden"
    : Math.abs(weightDiff) < 0.3 ? "Vekten er stabil"
    : weightDiff < 0 ? `Vekten har gått ned ${Math.abs(weightDiff).toFixed(1)} kg` : `Vekten har gått opp ${weightDiff.toFixed(1)} kg`;
  const lcLabel = measureLabel.toLowerCase();
  const measurePhrase = measureDiff == null ? `ingen ${lcLabel}-mål nok ennå i perioden`
    : Math.abs(measureDiff) < 0.5 ? `${lcLabel}en er uendret`
    : measureDiff < 0 ? `${lcLabel}en har krympet ${Math.abs(measureDiff).toFixed(1)} cm` : `${lcLabel}en har økt ${measureDiff.toFixed(1)} cm`;
  note.textContent = `${weightPhrase}, og ${measurePhrase}.${goalPhrase}`;
}

// ---------------------------------------------------------------- fremgang: aktivitets-trender
function renderActivityTrends() {
  if (!document.getElementById("chart-activity")) return;
  const act = alignWeeklySeries([DATA.trends.steps, DATA.trends.activeCalories]);
  renderTrendChart("chart-activity", "tt-activity", act.weeks, [
    { name: "Skritt", color: "#7a1f3d", values: act.valuesList[0], unit: "skritt", axis: "left" },
    { name: "Aktive kalorier", color: "#f6c667", values: act.valuesList[1], unit: "kcal", axis: "right" },
  ], { legendId: "legend-activity" });

  const ss = alignWeeklySeries([DATA.trends.stress, DATA.trends.sleepScore]);
  renderTrendChart("chart-stress-sleep", "tt-stress-sleep", ss.weeks, [
    { name: "Stress", color: "#e37878", values: ss.valuesList[0], unit: "", axis: "left" },
    { name: "Søvnscore", color: "#a46cc0", values: ss.valuesList[1], unit: "", axis: "right" },
  ], { legendId: "legend-stress-sleep" });

  const note = document.getElementById("activity-context-note");
  if (!note) return;
  const pairs = ss.weeks.map((w, i) => ({ stress: ss.valuesList[0][i], sleep: ss.valuesList[1][i] }))
    .filter(p => p.stress != null && p.sleep != null);
  if (pairs.length < 4) {
    note.textContent = "Ikke nok uker med både stress- og søvndata ennå til å se mønstre.";
    return;
  }
  const sorted = [...pairs].sort((a, b) => a.stress - b.stress);
  const lowHalf = sorted.slice(0, Math.floor(sorted.length / 2));
  const highHalf = sorted.slice(Math.ceil(sorted.length / 2));
  const avgSleepLow = lowHalf.reduce((s, p) => s + p.sleep, 0) / lowHalf.length;
  const avgSleepHigh = highHalf.reduce((s, p) => s + p.sleep, 0) / highHalf.length;
  const diff = avgSleepLow - avgSleepHigh;
  note.textContent = Math.abs(diff) >= 3
    ? `I ukene med høyest stress har søvnscoren i snitt vært ${Math.abs(diff).toFixed(0)} poeng ${diff > 0 ? "lavere" : "høyere"} enn i ukene med lavest stress.`
    : "Ingen tydelig sammenheng mellom stressnivå og søvnkvalitet i perioden ennå.";
}

// ---------------------------------------------------------------- fremgang: faste vs. variable utgifter
function renderExpenseTrends() {
  if (!document.getElementById("chart-expenses")) return;
  const emKeys = emKeysBack(12);
  const cfg = loadBudgetConfig();
  const variableKeys = cfg.categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
  const tx = loadTransactions();
  const totalFor = (keys, emKey) => {
    const start = emStart(emKey), end = emEnd(emKey);
    return tx.filter(t => keys.includes(t.category) && t.date >= start && t.date <= end).reduce((s, t) => s + t.amount, 0);
  };
  const variableVals = emKeys.map(ek => totalFor(variableKeys, ek));

  renderTrendChart("chart-expenses", "tt-expenses", emKeys, [
    { name: "Variable utgifter", color: "#a46cc0", values: variableVals, unit: "kr" },
  ], { fmtLabel: emShortLabel });
}

// ---------------------------------------------------------------- fremgang: sparemål
function renderSavingsGoals() {
  const el = document.getElementById("savings-goals");
  if (!el) return;
  const cats = loadBudgetConfig().categories.filter(c => c.savings);
  el.innerHTML = cats.map(c => {
    const balance = savingsBalance(c.key);
    const target = savingsTarget(c.key);
    const pct = target ? Math.min(100, Math.round(100 * balance / target)) : 0;
    const proj = projectSavingsMilestone(c.key);
    let etaText;
    if (target > 0 && balance >= target) etaText = "🎉 Målet er nådd!";
    else if (proj) etaText = `Ved nåværende sparetakt (~${Math.round(proj.rate).toLocaleString()} kr/mnd) når du målet rundt ${emShortLabel(proj.emKey)}.`;
    else etaText = "Spar litt i denne kategorien for å se en anslått dato.";
    const isDogFund = c.key === DATA.dogFund.category;
    return `
    <div class="savings-goal-card">
      <div class="sg-label">${c.icon ? c.icon + " " : ""}${c.label}</div>
      <div class="sg-amount">${Math.round(balance).toLocaleString()} kr</div>
      <div class="cat-bar"><div class="${pct >= 100 ? "good" : ""}" style="width:${pct}%"></div></div>
      ${isDogFund ? "" : `<div class="sg-goal-row">Saldo nå: <input type="number" step="100" class="sg-balance-input" data-cat="${c.key}" value="${Math.round(balance)}"> kr</div>`}
      <div class="sg-goal-row">Mål: <input type="number" step="500" class="sg-target-input" data-cat="${c.key}" value="${target}"> kr</div>
      <div class="sg-eta">${etaText}</div>
    </div>`;
  }).join("");

  el.querySelectorAll(".sg-target-input").forEach(inp => {
    inp.addEventListener("change", () => {
      setSavingsTarget(inp.dataset.cat, parseFloat(inp.value) || 0);
      renderSavingsGoals();
      renderFund();
    });
  });
  el.querySelectorAll(".sg-balance-input").forEach(inp => {
    inp.addEventListener("change", () => {
      setSavingsCurrentBalance(inp.dataset.cat, parseFloat(inp.value) || 0);
      renderSavingsGoals();
    });
  });
}

// ---------------------------------------------------------------- fremgang: fond-utvikling
function renderFundTrend() {
  if (!document.getElementById("chart-fund")) return;
  const log = loadInvestFundLog().sort((a, b) => a.date.localeCompare(b.date));
  const labels = log.map(e => e.date);
  const valueVals = log.map(e => e.value);
  const contributedVals = log.map(e => (e.contributed != null ? e.contributed : null));

  renderTrendChart("chart-fund", "tt-fund", labels, [
    { name: "Fondsverdi", color: "#7a1f3d", values: valueVals, unit: "kr" },
    { name: "Innskutt kapital", color: "#a46cc0", values: contributedVals, unit: "kr" },
  ], { legendId: "legend-fund" });

  const summary = document.getElementById("fund-summary");
  if (!summary) return;
  if (!log.length) { summary.innerHTML = ""; return; }
  const latest = log[log.length - 1];
  if (latest.contributed != null && latest.value != null) {
    const gain = latest.value - latest.contributed;
    const gainPct = latest.contributed ? (100 * gain / latest.contributed) : 0;
    summary.innerHTML = `
      <div class="fs-item">Innskutt<br><b>${Math.round(latest.contributed).toLocaleString()} kr</b></div>
      <div class="fs-item">Verdi i dag<br><b>${Math.round(latest.value).toLocaleString()} kr</b></div>
      <div class="fs-item">Avkastning<br><b class="${gain >= 0 ? "pos" : "neg"}">${gain >= 0 ? "+" : ""}${Math.round(gain).toLocaleString()} kr (${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%)</b></div>
    `;
  } else {
    summary.innerHTML = `
      <div class="fs-item">Verdi i dag<br><b>${Math.round(latest.value).toLocaleString()} kr</b></div>
      <div class="fs-item" style="color:var(--muted);font-size:12px;max-width:220px;">Logg innskutt kapital for å se avkastningen</div>
    `;
  }
}

function isoAddDays(dateStr, days) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}
function weeklyVolumeSeries(numWeeks) {
  const log = loadSetLog();
  const byWeek = {};
  log.forEach(s => {
    if (!s.date || !s.reps) return;
    const wk = isoWeekOf(s.date);
    const vol = (s.weight != null ? s.weight : 1) * s.reps;
    byWeek[wk] = (byWeek[wk] || 0) + vol;
  });
  const base = isoWeekOf(todayISO());
  const weeks = [];
  const values = [];
  for (let i = numWeeks - 1; i >= 0; i--) {
    const key = isoAddDays(base, -i * 7);
    weeks.push(key);
    values.push(Math.round(byWeek[key] || 0));
  }
  return { weeks, values };
}
const volumeSeries = weeklyVolumeSeries(10);
renderLineChart("chart-volume", "tt-volume", volumeSeries.weeks, volumeSeries.values, "#f6c667", "vol");

// ---------------------------------------------------------------- records
const recordsGrid = document.getElementById("records-grid");
const recordDefs = [
  { key: "longestRide", label: "Lengste sykkeltur", fmt: r => `${r.value} ${r.unit}` },
  { key: "longestRun", label: "Lengste løpetur", fmt: r => `${r.value} km` },
  { key: "longestStrength", label: "Lengste styrkeøkt", fmt: r => `${r.value} min` },
  { key: "mostSteps", label: "Flest skritt på en dag", fmt: r => `${r.value.toLocaleString()}` },
  { key: "mostCalories", label: "Flest kalorier på en dag", fmt: r => `${r.value.toLocaleString()} kcal` },
  { key: "longestSleep", label: "Lengste søvn på en natt", fmt: r => `${r.value} t` },
  { key: "bestHRV", label: "Høyeste HRV-natt", fmt: r => `${r.value} ms` },
  { key: "highestTrainingLoad", label: "Høyeste treningsbelastning", fmt: r => `${r.value}` },
];
recordDefs.forEach(def => {
  const r = DATA.records[def.key];
  if (!r || r.value === null || r.value === undefined) return;
  const card = document.createElement("div");
  card.className = "record-card";
  card.innerHTML = `
    <div class="label">${def.label}</div>
    <div class="value">${def.fmt(r)}</div>
    <div class="date">${fmtDate(r.date)}</div>
  `;
  recordsGrid.appendChild(card);
});

// ---------------------------------------------------------------- hjem dashboard
function renderHjemWhy() {
  const why = loadWhy();
  const el = document.getElementById("hjem-why");
  el.textContent = why ? `💛 ${why}` : "+ Legg til ditt Hvorfor";
  el.classList.toggle("empty", !why);
}
document.getElementById("hjem-why").addEventListener("click", () => {
  const next = prompt("Hvorfor gjør du dette? Vises som en liten påminnelse på Hjem.", loadWhy());
  if (next === null) return;
  saveWhy(next.trim());
  renderHjemWhy();
});

// ---- Sonar-style daily scores: a big Recovery ring + small Strain/Nutrition rings ----
function scoreColor(score) {
  if (score == null) return "var(--hj-muted)";
  if (score >= 67) return "#2f8a4e";
  if (score >= 34) return "#b8860b";
  return "#c0392b";
}
function ringGaugeSvg(score, size, strokeWidth) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const offset = circumference * (1 - pct);
  const center = size / 2;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="var(--hj-line)" stroke-width="${strokeWidth}"/>
    <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${scoreColor(score)}" stroke-width="${strokeWidth}"
      stroke-dasharray="${circumference.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"
      stroke-linecap="round" transform="rotate(-90 ${center} ${center})"/>
  </svg>`;
}
function scoreRingHtml(score, size, strokeWidth) {
  return `<div class="score-ring" style="width:${size}px;height:${size}px;">
    ${ringGaugeSvg(score, size, strokeWidth)}
    <div class="score-ring-num" style="color:${scoreColor(score)};font-size:${Math.round(size * 0.32)}px;">${score != null ? score : "–"}</div>
  </div>`;
}
// kcal: scores 100 at the goal, falling off the further eaten is from it in either direction.
// protein: scores by how close you are to your protein floor, capped at 100 once you hit it.
function recoveryVerdict(score) {
  if (score == null) return "Ikke nok data til å beregne recovery ennå.";
  if (score >= 67) return "God recovery - kroppen er klar for en skikkelig økt i dag.";
  if (score >= 34) return "Middels recovery - kjør økta, men hold litt igjen hvis du kjenner det.";
  return "Lav recovery - vurder en lettere variant eller prioriter hvile i dag.";
}
// Tells her whether to push harder or ease off tomorrow, based on today's recovery
// (how ready the body was) against today's strain (how hard it was actually used) -
// and defers to the plan if tomorrow is already a scheduled rest day.
function strainNote(strain, recovery, p) {
  if (strain == null || recovery == null) return "Ikke nok data ennå til å si noe om i morgen.";

  const tomorrowDate = isoAddDays(todayISO(), 1);
  const tomorrowDay = p.week.find(d => d.date === tomorrowDate);
  if (tomorrowDay) {
    const tomorrowResolved = resolvePlanDay(tomorrowDay, loadPlanOverrides());
    if (tomorrowResolved.type === "rest") {
      return "I morgen er det uansett hviledag ifølge planen - fin timing uansett dagens belastning.";
    }
  }

  const highRecovery = recovery >= 67, lowRecovery = recovery < 34;
  const highStrain = strain >= 67, lowStrain = strain < 34;

  if (highRecovery && lowStrain) return "God recovery og lite belastning så langt - du kan trygt trene litt hardere i morgen.";
  if (highRecovery && highStrain) return "Du har alt hatt en tung dag med god recovery i bunn - fortsett som normalt i morgen.";
  if (lowRecovery && highStrain) return "Høy belastning på en dag med lav recovery - ta det roligere i morgen.";
  if (lowRecovery && lowStrain) return "Lav recovery selv uten mye belastning - prioriter hvile eller en lett økt i morgen.";
  if (highRecovery) return "God recovery - du tåler en normal eller litt tyngre økt i morgen.";
  if (lowRecovery) return "Lav recovery - hold morgendagens økt lett til moderat.";
  return "Middels recovery og belastning - en vanlig økt i morgen bør gå fint.";
}
let hjemActivityDetailsOpen = false;

function renderHjemSession() {
  const p = DATA.program;
  const el = document.getElementById("hjem-session");
  if (!p || !el) return;
  if (isVacationActive()) {
    el.innerHTML = `
      <div>
        <div class="hs-label">🌴 Pause-modus</div>
        <div class="hs-sub">Ingen press i dag - streaken venter til du er tilbake.</div>
      </div>
    `;
    return;
  }
  const overrides = loadPlanOverrides();
  const todayDay = p.week.find(d => d.isToday);
  const resolved = resolvePlanDay(todayDay, overrides);

  let statusKey = "notstarted", statusLabel = "Ikke startet";
  if (resolved.type === "rest") {
    statusKey = "done"; statusLabel = "Hviledag";
  } else if (resolved.done) {
    statusKey = "done";
    statusLabel = resolved.matchedActivity
      ? `${SPORT_LABELS_NO[resolved.matchedActivity.sport] || resolved.matchedActivity.sport} (Fullført)`
      : "Fullført";
  } else if (loadSetLog().some(s => s.date === todayISO() && s.exercise.startsWith(resolved.key + "::"))) {
    statusKey = "inprogress"; statusLabel = "Pågår";
  }

  const recovery = p.today.recoveryScore;
  const garminStrain = p.today.strainScore;
  const rpe = todayRpe();
  const strain = effectiveStrainScore(garminStrain);
  const recoveryText = [recoveryVerdict(recovery), ...(p.today.reasons || [])].join(" ");

  // Belastning (and especially the RPE prompt) only makes sense once the session is actually
  // underway or done - asking "how hard did it feel?" before she's started it is premature.
  const showBelastning = statusKey !== "notstarted";
  // Garmin doesn't always give indoor/manually-entered strength sessions a training load,
  // so belastning can stay at 0 even on a completed session - offer an RPE fallback then.
  const needsRpe = resolved.type !== "rest" && (garminStrain == null || garminStrain === 0) && rpe == null;
  const strainNoteText = rpe != null && (garminStrain == null || garminStrain === 0)
    ? `${strainNote(strain, recovery, p)} (basert på RPE ${rpe}/10 du satte selv)`
    : strainNote(strain, recovery, p);

  el.innerHTML = `
    <div class="hs-top">
      <div class="hs-score-block">
        ${scoreRingHtml(recovery, 72, 7)}
        <div class="hs-score-label">Recovery</div>
      </div>
      <div class="hs-info">
        <div class="hs-label">${resolved.type === "rest" ? "Hviledag" : resolved.label}</div>
        <div class="hs-sub">Uke ${p.currentWeek}${p.weekIsDeload ? " · Deload" : " av 4"} · ${p.weekFocus}</div>
        <span class="hs-status ${statusKey}${resolved.matchedActivity ? " hs-status-tap" : ""}" ${resolved.matchedActivity ? 'id="hjem-activity-details-toggle"' : ""}>${statusLabel}${resolved.matchedActivity ? (hjemActivityDetailsOpen ? " ▾" : " ▸") : ""}</span>
      </div>
    </div>
    ${resolved.matchedActivity && hjemActivityDetailsOpen ? `
      <div class="hs-activity-details">
        <div><span>Varighet</span><b>${resolved.matchedActivity.minutes} min</b></div>
        ${resolved.matchedActivity.distanceKm ? `<div><span>Distanse</span><b>${resolved.matchedActivity.distanceKm} km</b></div>` : ""}
        ${resolved.matchedActivity.avgHr ? `<div><span>Snittpuls</span><b>${resolved.matchedActivity.avgHr} bpm</b></div>` : ""}
        ${resolved.matchedActivity.calories ? `<div><span>Kalorier</span><b>${resolved.matchedActivity.calories} kcal</b></div>` : ""}
      </div>` : ""}
    <div class="hs-recovery-note">${recoveryText}</div>
    ${showBelastning ? `
    <div class="hs-secondary-scores">
      <div class="hs-mini-score">
        ${scoreRingHtml(strain, 40, 5)}
        <div class="hs-mini-label">Belastning<b>${strain != null ? strain : "–"}</b>
          ${needsRpe
            ? `<div class="rpe-picker">
                <span class="hs-mini-note">Garmin ga ingen belastning for økta - hvor hardt føltes den?</span>
                <div class="rpe-buttons">${Array.from({ length: 10 }, (_, i) => i + 1).map(n => `<button class="rpe-btn" data-rpe="${n}">${n}</button>`).join("")}</div>
              </div>`
            : `<span class="hs-mini-note">${strainNoteText}</span>`}
        </div>
      </div>
    </div>` : ""}
    <button class="hs-link" id="hjem-session-link">${resolved.type === "rest" ? "Til plan →" : "Til økta →"}</button>
  `;
  document.getElementById("hjem-session-link").addEventListener("click", () => {
    showTab("trening");
    setTimeout(() => {
      const target = document.getElementById("plan-today");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
  el.querySelectorAll(".rpe-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const log = loadRpeLog();
      log[todayISO()] = parseInt(btn.dataset.rpe, 10);
      saveRpeLog(log);
      renderHjemSession();
    });
  });
  const detailsToggle = document.getElementById("hjem-activity-details-toggle");
  if (detailsToggle) {
    detailsToggle.addEventListener("click", () => {
      hjemActivityDetailsOpen = !hjemActivityDetailsOpen;
      renderHjemSession();
    });
  }
}

// ---- social budget: set aside kcal for a planned social evening, then log a rough
// estimate afterward without any pass/fail judgment against the number ----
const SOCIAL_BUDGET_KEY = "garminDashboardSocialBudget_v1";
function loadSocialBudget() { return loadLS(SOCIAL_BUDGET_KEY, {}); }
function socialBudgetToday() { return loadSocialBudget()[todayISO()] || null; }
function openSocialBudgetSetDrawer() {
  openQuicklogDrawer("Planlegg sosialt", `
    <input type="date" id="ql-social-date" value="${todayISO()}">
    <input type="number" step="50" id="ql-social-amount" placeholder="Kcal å sette av">
    <input type="text" id="ql-social-name" placeholder="Hva skjer? (valgfritt)">
    <button class="btn" id="ql-social-save">Sett av</button>
  `);
  document.getElementById("ql-social-save").addEventListener("click", () => {
    const date = document.getElementById("ql-social-date").value || todayISO();
    const amount = parseInt(document.getElementById("ql-social-amount").value, 10);
    if (!amount) return;
    const name = document.getElementById("ql-social-name").value.trim();
    const b = loadSocialBudget();
    b[date] = { amount, loggedKcal: null, name: name || null };
    saveLS(SOCIAL_BUDGET_KEY, b);
    closeQuicklogDrawer();
    renderHjemSocialBudget();
  });
}
function openSocialBudgetLogDrawer() {
  openQuicklogDrawer("Logg et anslag for i kveld", `
    <input type="number" step="50" id="ql-social-log-kcal" placeholder="Anslag kcal">
    <button class="btn" id="ql-social-log-save">Logg</button>
  `);
  document.getElementById("ql-social-log-save").addEventListener("click", () => {
    const kcal = parseInt(document.getElementById("ql-social-log-kcal").value, 10);
    if (!kcal) return;
    const b = loadSocialBudget();
    const entry = b[todayISO()] || { amount: 0, loggedKcal: null };
    entry.loggedKcal = kcal;
    b[todayISO()] = entry;
    saveLS(SOCIAL_BUDGET_KEY, b);
    addExtra("Sosialt i kveld", kcal);
    closeQuicklogDrawer();
    renderHjemSocialBudget();
    renderHjemKcalRing();
  });
}
function renderHjemSocialBudget() {
  const el = document.getElementById("hjem-social-budget");
  if (!el) return;
  const entry = socialBudgetToday();
  if (!entry) {
    el.innerHTML = `<button class="hjem-tx-nudge" id="hjem-social-set-btn">🎉 Planlegg sosialt</button>`;
    document.getElementById("hjem-social-set-btn").addEventListener("click", openSocialBudgetSetDrawer);
    return;
  }
  if (entry.loggedKcal == null) {
    el.innerHTML = `
      <div class="hjem-reminder-banner">
        <span>🎉 ${entry.name ? `${entry.name}: ` : ""}Du har ${entry.amount.toLocaleString()} kcal til overs i kveld. Kos deg!</span>
        <button id="hjem-social-log-btn">Logg anslag</button>
      </div>`;
    document.getElementById("hjem-social-log-btn").addEventListener("click", openSocialBudgetLogDrawer);
    return;
  }
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>✅ Perfekt, du traff budsjettet.</span>
    </div>`;
}

function renderHjemKcalRing() {
  const n = DATA.nutritionPlan;
  const el = document.getElementById("hjem-kcal-ring");
  if (!n || !el) return;
  const totals = dayNutritionTotals(todayISO());
  const kcalShown = withKcalMargin(totals.kcal);
  const remaining = n.dailyKcal - kcalShown;
  const over = remaining < 0;

  // Kept deliberately separate from "igjen av målet" above: that's a fixed daily budget,
  // this is a live Garmin-based deficit/surplus (burned vs. eaten) - mixing the two into one
  // number was confusing since they answer different questions.
  const burned = reportMetric("calories").today;
  let balanceHtml = "";
  if (burned != null) {
    const diff = burned - kcalShown;
    const diffLabel = diff >= 0 ? `${diff} kcal underskudd så langt` : `${Math.abs(diff)} kcal overskudd så langt`;
    balanceHtml = `
      <div class="hnq-balance">
        <span>🔥 Forbrent i dag (Garmin): ${burned} kcal</span>
        <span class="hnq-balance-diff${diff >= 0 ? "" : " over"}">${diffLabel} (forbrent − spist)</span>
      </div>`;
  }

  el.innerHTML = `
    <div>
      <div class="hnq-label">Spist i dag</div>
      <div class="hnq-val">~${kcalShown} kcal</div>
      <div class="hnq-macro${over ? " over" : ""}">${over ? `${Math.abs(remaining)} kcal over målet` : `${remaining} kcal igjen av målet (${n.dailyKcal} kcal)`}</div>
      <div class="hnq-macro">${totals.protein} / ${n.proteinMin} g protein</div>
      ${balanceHtml}
    </div>
  `;
}

function quickSaveToCategory(category, amount, name) {
  const tx = loadTransactions();
  tx.push({ id: "save-" + Date.now() + Math.random(), date: todayISO(), amount, category, name: name || "Spar i stedet" });
  saveTransactions(tx);
}

// Alternates the empty-day savings nudge between the dog fund and the high-interest
// account by day-of-month parity, so it's not always pushing the same goal.
function savingsNudgeTarget() {
  const day = parseInt(todayISO().slice(8, 10), 10);
  return day % 2 === 0
    ? { key: "sparing_hoyrente", label: "høyrentekontoen", icon: "💰" }
    : { key: DATA.dogFund.category, label: "hundefondet", icon: "🐶" };
}

function renderHjemTodayTx() {
  const el = document.getElementById("hjem-tx-today");
  if (!el) return;
  const cfg = loadBudgetConfig();
  const catLabel = key => (cfg.categories.find(c => c.key === key) || {}).label || key;
  const tx = loadTransactions().filter(t => t.date === todayISO());
  const total = tx.reduce((s, t) => s + t.amount, 0);
  const nudge = savingsNudgeTarget();
  el.innerHTML = `
    <div class="hjem-card-title">Dagens transaksjoner</div>
    <ul class="hjem-tx-list">
      ${tx.length
        ? tx.map(t => `<li><span class="tx-name">${t.name || catLabel(t.category)}</span><b>${t.amount.toLocaleString()} kr</b></li>`).join("")
        : `<li class="hjem-tx-empty">Ingen utgifter i dag 🎉</li>`}
    </ul>
    ${tx.length
      ? `<div class="hjem-tx-total"><span>Totalt i dag</span><span>${total.toLocaleString()} kr</span></div>`
      : `<button class="hjem-tx-nudge" id="hjem-tx-nudge-btn">Kanskje du skal sette inn 50 kr på ${nudge.label} i stedet? ${nudge.icon}</button>`}
  `;
  const nudgeBtn = document.getElementById("hjem-tx-nudge-btn");
  if (nudgeBtn) {
    nudgeBtn.addEventListener("click", () => {
      quickSaveToCategory(nudge.key, 50, "Ingen utgifter i dag");
      renderHjemTodayTx();
      renderHjemFinance();
      renderBudget();
    });
  }
}

function renderHjemBodyToday() {
  const el = document.getElementById("hjem-body-today");
  if (!el) return;
  const ts = DATA.topStats || {};
  const steps = ts.steps || {};
  const stepsGoal = steps.goal || 8000;
  const stepsPct = stepsGoal ? Math.min(100, Math.round(100 * (steps.value || 0) / stepsGoal)) : 0;

  const activeCal = reportMetric("activeCalories").today;
  const calGoal = DATA.activeCalGoalDefault || 400;
  const calPct = calGoal ? Math.min(100, Math.round(100 * (activeCal || 0) / calGoal)) : 0;

  const sleep = ts.sleep || {};
  const stress = reportMetric("stress").today;
  const stressColor = stress == null ? null : stress <= 50 ? "green" : stress <= 75 ? "yellow" : "red";
  const bodyBattery = reportMetric("bodyBatteryLatest").today;

  el.innerHTML = `
    <div class="hjem-body-grid">
      <div class="hjem-body-group-label">Aktivitet i dag</div>
      <div class="hjem-card hjem-bigstat">
        <div class="hbs-label">Skritt</div>
        <div class="hbs-num">${steps.value != null ? steps.value.toLocaleString() : "–"}</div>
        <div class="hbs-bar"><div class="${stepsPct >= 100 ? "goalmet" : ""}" style="width:${stepsPct}%"></div></div>
      </div>
      <div class="hjem-card hjem-bigstat">
        <div class="hbs-label">Aktive kalorier</div>
        <div class="hbs-num">${activeCal != null ? Math.round(activeCal) : "–"}</div>
        <div class="hbs-bar"><div class="${calPct >= 100 ? "goalmet" : ""}" style="width:${calPct}%"></div></div>
      </div>
      <div class="hjem-body-group-label">Restitusjon i natt</div>
      <div class="hjem-minirow">
        <div class="hjem-card hjem-minicard">
          <div class="label">Søvn</div>
          <div class="value">${sleep.score != null ? sleep.score : "–"}</div>
          <div class="sub">${sleep.hours != null ? sleep.hours + " t" : ""}</div>
        </div>
        <div class="hjem-card hjem-minicard">
          <div class="label">Stress</div>
          <div class="value">${stressColor ? `<span class="stress-dot ${stressColor}"></span>` : ""}${stress != null ? Math.round(stress) : "–"}</div>
          <div class="sub"></div>
        </div>
        <div class="hjem-card hjem-minicard">
          <div class="label">Body Battery</div>
          <div class="value">${bodyBattery != null ? Math.round(bodyBattery) : "–"}</div>
          <div class="sub"></div>
        </div>
      </div>
    </div>
  `;
}

function loadInvestFundLog() { return loadLS(INVEST_FUND_KEY, []); }
function saveInvestFundLog(l) { saveLS(INVEST_FUND_KEY, l); }
function setInvestFundValue(date, value) {
  // quick single-field update (e.g. the Hjem-tab prompt) - carries the last known
  // contributed-capital figure forward, since that only changes on an actual deposit.
  const prior = loadInvestFundLog().filter(e => e.date < date).sort((a, b) => a.date.localeCompare(b.date));
  const contributed = prior.length ? prior[prior.length - 1].contributed : null;
  setInvestFundEntry(date, value, contributed);
}
function setInvestFundEntry(date, value, contributed) {
  const log = loadInvestFundLog().filter(e => e.date !== date);
  log.push({ date, value, contributed: contributed != null ? contributed : null });
  log.sort((a, b) => a.date.localeCompare(b.date));
  saveInvestFundLog(log);
}
function investFundStatus() {
  const log = loadInvestFundLog();
  if (!log.length) return { value: null, date: null, changeKr: null, changePct: null };
  const latest = log[log.length - 1];
  const prev = log.length > 1 ? log[log.length - 2] : null;
  const changeKr = prev ? latest.value - prev.value : null;
  const changePct = prev && prev.value ? (100 * changeKr / prev.value) : null;
  return { value: latest.value, date: latest.date, changeKr, changePct };
}

function renderHjemFinance() {
  const el = document.getElementById("hjem-finance");
  if (!el) return;
  const cfg = loadBudgetConfig();
  const emKey = emKeyForDate(todayISO());
  // faste utgifter (husleie, strøm, osv.) er penger hun betaler uansett - de skal ikke
  // telle som "brukt" her. Variable utgifter og sparing vises separat, siden penger satt
  // av til sparing fortsatt er hennes, bare lagt til side - ikke forbrukt på samme måte.
  const variableCats = cfg.categories.filter(c => c.type === "variable" && !c.savings);
  const savingsCats = cfg.categories.filter(c => c.savings);
  const variableKeys = variableCats.map(c => c.key);
  const savingsKeys = savingsCats.map(c => c.key);
  const variableBudget = variableCats.reduce((s, c) => s + getCategoryCap(c, emKey), 0);
  const savingsBudget = savingsCats.reduce((s, c) => s + getCategoryCap(c, emKey), 0);
  const start = emStart(emKey), end = emEnd(emKey);
  const tx = loadTransactions().filter(t => t.date >= start && t.date <= end);
  const variableSpent = tx.filter(t => variableKeys.includes(t.category)).reduce((s, t) => s + t.amount, 0);
  const savingsSpent = tx.filter(t => savingsKeys.includes(t.category)).reduce((s, t) => s + t.amount, 0);
  const pct = variableBudget ? Math.min(100, Math.round(100 * variableSpent / variableBudget)) : 0;
  const over = variableSpent > variableBudget;
  const savingsPct = savingsBudget ? Math.min(100, Math.round(100 * savingsSpent / savingsBudget)) : 0;
  const sparekrukkeBalance = savingsBalance(SPAREKRUKKE_KEY);

  el.innerHTML = `
    <div class="hjem-finance-row">
      <div class="hf-label"><span>Brukt på variable utgifter</span><span>${variableSpent.toLocaleString()} / ${variableBudget.toLocaleString()} kr</span></div>
      <div class="hjem-finance-bar"><div class="${over ? "over" : ""}" style="width:${pct}%"></div></div>
    </div>
    <div class="hjem-finance-row">
      <div class="hf-label"><span>Satt av til sparing</span><span>${savingsSpent.toLocaleString()} / ${savingsBudget.toLocaleString()} kr</span></div>
      <div class="hjem-finance-bar"><div class="savings" style="width:${savingsPct}%"></div></div>
    </div>
    <div class="hjem-finance-row">
      <div class="hf-label"><span>🫙 Sparekrukka - saldo</span></div>
      <div class="hf-val">${Math.round(sparekrukkeBalance).toLocaleString()} kr</div>
    </div>
    <button class="hjem-tx-nudge" id="hjem-finance-expense-btn">+ Logg utgift</button>
  `;
  document.getElementById("hjem-finance-expense-btn").addEventListener("click", openExpenseDrawer);
}

function openExpenseDrawer() {
  const cfg = loadBudgetConfig();
  openQuicklogDrawer("Logg utgift", `
    <input type="number" step="1" id="ql-expense-amount" placeholder="Beløp (kr)">
    <select id="ql-expense-category">${categoryOptionsHtml(cfg)}</select>
    <input type="text" id="ql-expense-name" placeholder="Hva var det? (valgfritt)">
    <button class="btn" id="ql-expense-save">Lagre</button>
  `);
  document.getElementById("ql-expense-save").addEventListener("click", () => {
    const amount = parseFloat(document.getElementById("ql-expense-amount").value);
    if (!amount) return;
    const category = document.getElementById("ql-expense-category").value;
    const name = document.getElementById("ql-expense-name").value.trim();
    addTransactionWithRoundUp(todayISO(), amount, category, name);
    closeQuicklogDrawer();
    renderBudget();
  });
}

function renderHjemReminder() {
  const el = document.getElementById("hjem-reminder");
  const p = DATA.program;
  if (!p || !el) { if (el) el.innerHTML = ""; return; }
  if (!loadSettings().personalityEnabled || isVacationActive()) { el.innerHTML = ""; return; }
  const overrides = loadPlanOverrides();
  const todayDay = p.week.find(d => d.isToday);
  if (!todayDay) { el.innerHTML = ""; return; }
  const resolved = resolvePlanDay(todayDay, overrides);
  const hour = new Date().getHours();
  const pending = resolved.type !== "rest" && !resolved.done;
  if (!pending || hour < 17) { el.innerHTML = ""; return; }

  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>⏰ Du har ikke logget ${resolved.label.toLowerCase()} ennå i dag.</span>
      <button id="hjem-reminder-link">Gå til økta</button>
    </div>
  `;
  document.getElementById("hjem-reminder-link").addEventListener("click", () => {
    showTab("trening");
    setTimeout(() => {
      const target = document.getElementById("plan-today");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }, 50);
  });
}

// Rekkefølgen her er bevisst: mest presserende/dagsaktuelt først, ren "hyggelig å vite"-info
// sist. arbitrateHjemBanners() viser bare den første som faktisk har noe å si - resten venter
// til neste besøk, i stedet for at alle stables oppå hverandre.
const HJEM_BANNER_PRIORITY = [
  "hjem-unplanned-cardio",
  "hjem-reminder",
  "hjem-aon-banner",
  "hjem-protein-pace",
  "hjem-weight-reminder",
  "hjem-freeze-notice",
  "hjem-backup-reminder",
  "hjem-monthly-insight-nudge",
];
function arbitrateHjemBanners() {
  let shown = false;
  HJEM_BANNER_PRIORITY.forEach(id => {
    const el = document.getElementById(id);
    if (!el || !el.innerHTML.trim()) return;
    if (shown) { el.innerHTML = ""; return; }
    shown = true;
  });
}

function renderHjem() {
  renderHjemWhy();
  renderHjemReminder();
  renderHjemUnplannedCardio();
  renderHjemWeightReminder();
  renderHjemBackupReminder();
  renderHjemAllOrNothing();
  renderHjemProteinPace();
  renderHjemMvdSunday();
  renderHjemNextWeekPreview();
  renderHjemFreezeNotice();
  renderHjemMonthlyInsightNudge();
  arbitrateHjemBanners();
  renderHjemDailyRoutine();
  renderHjemSocialBudget();
  renderHjemSession();
  renderHjemKcalRing();
  renderHjemTodayTx();
  renderHjemBodyToday();
  renderHjemFinance();
}

document.querySelectorAll(".hjem-shortcut-btn[data-goto-tab]").forEach(btn => {
  btn.addEventListener("click", () => showTab(btn.dataset.gotoTab));
});

// ---- quick-log bottom bar & drawer ----
function openQuicklogDrawer(title, bodyHtml) {
  document.getElementById("quicklog-drawer-title").textContent = title;
  document.getElementById("quicklog-drawer-body").innerHTML = bodyHtml;
  document.getElementById("quicklog-drawer").classList.add("open");
}
function closeQuicklogDrawer() {
  document.getElementById("quicklog-drawer").classList.remove("open");
}
document.getElementById("quicklog-drawer-close").addEventListener("click", closeQuicklogDrawer);

// ---- "Mer"-skuff - de mindre daglig-brukte fanene, samlet bak bunn-navigasjonens 5. knapp
// i stedet for at alle ni fanene skal med i selve navigasjonsraden ----
const MORE_TABS = [
  { tab: "budsjett", icon: "💰", label: "Budsjett" },
  { tab: "planlegg", icon: "📝", label: "Planlegg" },
  { tab: "fremgang", icon: "📏", label: "Fremgang" },
  { tab: "handleliste", icon: "🛒", label: "Handleliste" },
  { tab: "statistikk", icon: "🏆", label: "Statistikk" },
  { tab: "innstillinger", icon: "⚙️", label: "Innstillinger" },
];
document.getElementById("bottomnav-more").addEventListener("click", () => {
  const bodyHtml = `<div class="more-menu">${MORE_TABS.map(t => `
    <button class="more-menu-btn" data-more-tab="${t.tab}"><span class="ql-icon">${t.icon}</span> ${t.label}</button>
  `).join("")}</div>`;
  openQuicklogDrawer("Mer", bodyHtml);
  document.querySelectorAll("[data-more-tab]").forEach(btn => {
    btn.addEventListener("click", () => {
      gotoTab(btn.dataset.moreTab);
      closeQuicklogDrawer();
    });
  });
});

renderHjem();
renderNutritionCoach();
renderPlanlegg();

// ---- Hjem live refresh: re-fetch own published page for fresh Garmin data ----
async function refreshGarminData() {
  try {
    const res = await fetch(location.href, { cache: "no-store" });
    if (!res.ok) return false;
    const html = await res.text();
    const startTag = "const DATA = ";
    const marker = "// ---------------------------------------------------------------- settings";
    const startIdx = html.indexOf(startTag);
    const endIdx = html.indexOf(marker, startIdx);
    if (startIdx === -1 || endIdx === -1) return false;
    let jsonText = html.slice(startIdx + startTag.length, endIdx).trim();
    if (jsonText.endsWith(";")) jsonText = jsonText.slice(0, -1);
    const fresh = JSON.parse(jsonText);
    DATA.topStats = fresh.topStats;
    DATA.reportMetrics = fresh.reportMetrics;
    DATA.program = fresh.program;
    DATA.trainingHistory = fresh.trainingHistory;
    return true;
  } catch (e) {
    return false;
  }
}

function refreshHjemGarminSections() {
  renderHjemSession();
  renderHjemBodyToday();
  renderHjemReminder();
}

document.getElementById("hjem-refresh-btn").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  btn.classList.add("spinning");
  await refreshGarminData();
  renderHjem();
  setTimeout(() => btn.classList.remove("spinning"), 650);
});

setInterval(() => {
  refreshGarminData().then(ok => { if (ok) refreshHjemGarminSections(); });
}, 20 * 60 * 1000);

// ---------------------------------------------------------------- rapport (personlig coach)
function reportMetric(key) {
  return (DATA.reportMetrics && DATA.reportMetrics[key]) || { today: null, avg7: null, avg30: null };
}
function minToHM(min) {
  if (min == null) return null;
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return h > 0 ? `${h}t ${m}min` : `${m}min`;
}
function diffPhrase(latest, baseline, unit) {
  if (latest == null || baseline == null) return "";
  const diff = Math.round((latest - baseline) * 10) / 10;
  if (Math.abs(diff) < 0.3) return "på linje med snittet ditt";
  const word = diff > 0 ? "mer enn" : "mindre enn";
  return `${fmtNo(Math.abs(diff))}${unit} ${word} snittet ditt`;
}
function prsToday() {
  const log = loadSetLog();
  const todays = log.filter(s => s.date === todayISO()).sort((a, b) => a.id.localeCompare(b.id));
  const prior = log.filter(s => s.date !== todayISO());
  const priorBest = {};
  prior.forEach(s => { if (isBetterSet(s, priorBest[s.exercise])) priorBest[s.exercise] = s; });
  const prs = [];
  const seenBest = {};
  todays.forEach(s => {
    const cur = seenBest[s.exercise] || priorBest[s.exercise];
    if (isBetterSet(s, cur)) { prs.push(s); seenBest[s.exercise] = s; }
  });
  return prs;
}

// hvor hun ligger an på protein for DENNE uken (mandag-søndag, samme uke som treningsplanen),
// og hvor mye som må spises ekstra på resten av ukens dager for å ta igjen et etterslep -
// gir et konkret handlingstall i stedet for bare "du var under målet"
function weeklyProteinStatus(dateStr) {
  const n = DATA.nutritionPlan;
  const weekDates = (DATA.program.week || []).map(d => d.date);
  const idx = weekDates.indexOf(dateStr);
  if (!n || idx === -1) return null;
  const elapsed = weekDates.slice(0, idx + 1).filter(d => !isSickDay(d));
  const remaining = weekDates.slice(idx + 1);
  const actualSoFar = elapsed.reduce((s, d) => s + dayNutritionTotals(d).protein, 0);
  const goalSoFar = n.proteinMin * elapsed.length;
  return {
    deficit: Math.round(goalSoFar - actualSoFar),
    remainingDays: remaining.length,
  };
}
// gir en konkret, handlingsorientert setning for et protein-etterslep - "spis X g ekstra i
// morgen/i dag" - i stedet for bare å si at hun lå under målet
function proteinCatchupLine(dateStr, whenWord) {
  const status = weeklyProteinStatus(dateStr);
  if (!status || status.deficit <= 10) return null;
  if (status.remainingDays <= 0) {
    return `Du endte ${status.deficit} g under proteinmålet for uken totalt.`;
  }
  const perDay = Math.ceil(status.deficit / status.remainingDays);
  const spreadNote = status.remainingDays > 1 ? " (eller fordelt på resten av ukens dager)" : "";
  return `var du ${status.deficit} g under proteinmålet. Spis ca. ${perDay} g ekstra ${whenWord}${spreadNote} for å nå ukesmålet.`;
}

function renderEveningReport() {
  const out = document.getElementById("report-output");
  const vacation = isVacationActive();
  const todayStr = todayISO();
  const todayPlanDay = (DATA.program.week || []).find(d => d.isToday);

  const setsToday = loadSetLog().filter(s => s.date === todayStr);
  // en kondisjonsøkt vises aldri som "sett" (vekt×reps) - den telles som gjort via Garmin-matchet
  // aktivitet (samme logikk som ukeoversikten i Treningsplan bruker), ikke bare set-loggen
  const resolvedToday = todayPlanDay ? resolvePlanDay(todayPlanDay, loadPlanOverrides()) : null;
  const trained = (resolvedToday && resolvedToday.done) || setsToday.length > 0;
  let trainingLine;
  if (vacation) {
    trainingLine = "Du er i pause-modus - ingen treningskrav i dag, og det er helt greit.";
  } else if (!todayPlanDay) {
    trainingLine = "Fant ikke dagens plan.";
  } else if (todayPlanDay.sessionType === "rest") {
    trainingLine = "I dag var en hviledag - nyt den.";
  } else if (trained) {
    const activity = resolvedToday && resolvedToday.matchedActivity;
    trainingLine = setsToday.length
      ? `Du logget ${setsToday.length} sett på dagens økt (${todayPlanDay.sessionLabel}). Bra jobba!`
      : `Du fullførte dagens økt (${todayPlanDay.sessionLabel}${activity ? `: ${activity.name}${activity.minutes ? `, ${activity.minutes} min` : ""}` : ""}). Bra jobba!`;
  } else {
    trainingLine = `Dagens plan var «${todayPlanDay.sessionLabel}», men du har ikke logget noe ennå i dag - fortsatt tid til å få det inn, eller ta det igjen i morgen.`;
  }

  const totals = dayNutritionTotals(todayStr);
  const n = DATA.nutritionPlan;
  const kcalShown = withKcalMargin(totals.kcal);
  const overBudget = kcalShown > n.dailyKcal;
  let nutritionLine;
  if (totals.extras.length) {
    const names = totals.extras.map(e => e.name).join(", ");
    nutritionLine = overBudget
      ? `Du logget ${names} i dag utenom planen, og endte på ~${kcalShown} kcal (budsjett ${n.dailyKcal}). Litt over i dag - helt greit, juster i morgen og fortsett.`
      : `Du logget ${names} i dag, men holdt deg likevel innenfor kaloribudsjettet (~${kcalShown} / ${n.dailyKcal} kcal). Bra kontroll! 👏`;
  } else {
    nutritionLine = overBudget
      ? `Du endte på rundt ~${kcalShown} kcal i dag, litt over budsjettet på ${n.dailyKcal}. Ingen grunn til dårlig samvittighet - bare ta det med i morgen.`
      : `Du holdt deg fint innenfor kaloribudsjettet i dag (~${kcalShown} / ${n.dailyKcal} kcal).`;
  }

  const proteinCatchup = proteinCatchupLine(todayStr, "i morgen");
  const proteinLine = proteinCatchup ? `I dag ${proteinCatchup}` : "";

  const logHtml = `
    <div class="report-section">
      <h3>📒 Dagens logg vs. plan</h3>
      <p>${trainingLine}</p>
      <p>${nutritionLine}</p>
      ${proteinLine ? `<p>${proteinLine}</p>` : ""}
    </div>`;

  const prs = prsToday();
  const totalVolume = setsToday.reduce((s, x) => s + (x.weight || 0) * x.reps, 0);
  const txToday = loadTransactions().filter(t => t.date === todayStr);
  const savedToday = txToday.filter(t => t.category === DATA.dogFund.category).reduce((s, t) => s + t.amount, 0);
  const spentToday = txToday.filter(t => !isSavingsCategory(t.category)).reduce((s, t) => s + t.amount, 0);

  const progressBits = [];
  if (prs.length) progressBits.push(`🏆 Ny PR i dag: ${prs.map(p => `${p.label} (${p.weight != null ? p.weight + " kg × " + p.reps : p.reps + " reps"})`).join(", ")}!`);
  if (totalVolume > 0) progressBits.push(`Treningsvolum i dag: ca. ${Math.round(totalVolume)} kg totalt (vekt × reps).`);
  if (savedToday > 0) progressBits.push(`Du la ${Math.round(savedToday)} kr i hundefondet i dag. 🐶`);
  if (spentToday > 0) progressBits.push(`Du brukte ${Math.round(spentToday)} kr i dag.`);
  if (!progressBits.length) progressBits.push("Ingen ny aktivitet logget i dag - det er også helt ok.");

  const progressHtml = `
    <div class="report-section">
      <h3>📈 Fremgang</h3>
      <ul>${progressBits.map(b => `<li>${b}</li>`).join("")}</ul>
    </div>`;

  const tomorrowDate = isoAddDays(todayStr, 1);
  const tomorrowPlanDay = (DATA.program.week || []).find(d => d.date === tomorrowDate);
  const sleepM = reportMetric("sleepHours");

  // ---- bli bedre på i morgen - én konkret, prioritert ting ----
  let improveLine;
  if (sleepM.avg7 != null && sleepM.today != null && sleepM.today < sleepM.avg7 - 1) {
    improveLine = "Du sov mindre enn vanlig i natt - prøv å legge deg litt tidligere i kveld.";
  } else if (tomorrowPlanDay && tomorrowPlanDay.sessionType === "strength" && todayPlanDay && todayPlanDay.sessionType === "strength" && !trained) {
    improveLine = `I morgen er det «${tomorrowPlanDay.sessionLabel}» - sett av tid til den nå som du vet du har en treningsdag.`;
  } else if (overBudget) {
    improveLine = "Siden dagens kaloribudsjett ble sprengt litt, kan det være greit å planlegge et roligere måltid i morgen.";
  } else if (totals.extras.length >= 2) {
    improveLine = "Du logget flere ting utenom planen i dag - sjekk om «Eget forslag» under lunsj/middag kan dekke noen av favorittene dine faste, så blir det lettere å planlegge.";
  } else if (!vacation && todayPlanDay && todayPlanDay.sessionType !== "rest" && !trained) {
    improveLine = "Dagens økt er fortsatt ulogget - få den inn før du legger deg, eller ta den igjen i morgen tidlig.";
  } else {
    improveLine = "Ingenting som trenger justering i morgen - hold kursen.";
  }

  // ---- fortsett med - løftes fra samme fire områder som ukens/månedens innsikt dekker ----
  let continueLine;
  if (!vacation && todayPlanDay && todayPlanDay.sessionType !== "rest" && trained) {
    continueLine = "Du fulgte treningsplanen i dag - fortsett med det.";
  } else if (totals.protein > 0 && totals.protein >= n.proteinMin) {
    continueLine = "Du traff proteinmålet i dag - fortsett med det.";
  } else if (!overBudget && totals.kcal > 0) {
    continueLine = "Du holdt deg innenfor kaloribudsjettet i dag - fortsett med det.";
  } else if (sleepM.today != null && sleepM.avg7 != null && sleepM.today >= sleepM.avg7) {
    continueLine = "Du sov like mye eller mer enn vanlig i natt - fortsett med gode søvnrutiner.";
  } else {
    continueLine = "Du sjekket inn i appen i dag - det teller også.";
  }

  const tomorrowHtml = `
    <div class="report-section">
      <h3>✅ Fortsett med</h3>
      <p>${continueLine}</p>
    </div>
    <div class="report-section">
      <h3>🎯 Bli bedre på</h3>
      <p>${improveLine}</p>
    </div>`;

  out.innerHTML = `
    <div class="report-title">Kveldsrapport · ${fmtDate(todayStr)}</div>
    ${logHtml}${progressHtml}${tomorrowHtml}
  `;
}

// Finner sammenhenger på tvers av data hun ikke nødvendigvis ser selv - restitusjonsgjeld
// (HRV/hvilepuls/søvn samtidig dårligere enn vanlig, som ofte er "derfor jeg er sliten") og
// om proteinmålet faktisk er oppnåelig gitt hvor proteintett maten har vært i perioden, ikke
// bare "du lå under målet". Delt mellom ukens og månedens innsikt.
function buildDeepPatterns(startDate, endDate, periodWord) {
  const findings = [];
  const history = (DATA.dailyHistory || []).filter(d => d.date >= startDate && d.date <= endDate && !isSickDay(d.date));
  const baselineStart = isoAddDays(startDate, -60);
  const baselineEnd = isoAddDays(startDate, -1);
  const baseline = (DATA.dailyHistory || []).filter(d => d.date >= baselineStart && d.date <= baselineEnd && !isSickDay(d.date));

  function avg(arr, key) {
    const vals = arr.map(d => d[key]).filter(v => v != null);
    return vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
  }

  // ---- restitusjonsgjeld: HRV ned + hvilepuls opp + søvn ned samtidig, sammenlignet med
  // de siste 60 dagene før perioden - minst to av tre signaler må slå til ----
  const hrvNow = avg(history, "hrv"), hrvBase = avg(baseline, "hrv");
  const rhrNow = avg(history, "restingHR"), rhrBase = avg(baseline, "restingHR");
  const sleepNow = avg(history, "sleepHours"), sleepBase = avg(baseline, "sleepHours");
  if (hrvNow != null && hrvBase != null && rhrNow != null && rhrBase != null && sleepNow != null && sleepBase != null) {
    const hrvDown = hrvBase > 0 && (hrvBase - hrvNow) / hrvBase >= 0.08;
    const rhrUp = rhrNow - rhrBase >= 2;
    const sleepDown = sleepBase - sleepNow >= 0.5;
    const bits = [];
    if (hrvDown) bits.push(`HRV ${Math.round(hrvNow)} ms (vanligvis ${Math.round(hrvBase)})`);
    if (rhrUp) bits.push(`hvilepuls ${Math.round(rhrNow)} (vanligvis ${Math.round(rhrBase)})`);
    if (sleepDown) bits.push(`søvn ${sleepNow.toFixed(1)} t (vanligvis ${sleepBase.toFixed(1)} t)`);
    if (bits.length >= 2) {
      findings.push(`Kroppen din signaliserer restitusjonsgjeld ${periodWord}: ${bits.join(", ")}. Det er trolig derfor du kjenner deg sliten - ikke fordi du ikke gjør nok, men fordi kroppen bruker energien på å ta igjen, ikke bygge.`);
    }
  }

  // ---- protein-gjennomførbarhet: er målet realistisk gitt hvor proteintett maten faktisk
  // har vært, uttrykt som g protein per 100 kcal (samme mål som sorteringen i Måltidsbiblioteket
  // bruker) - i stedet for bare å gjenta at hun lå under målet ----
  const n = DATA.nutritionPlan;
  const loggedDays = history.filter(d => {
    const t = dayNutritionTotals(d.date);
    return t.fromLifesum || t.mealsLogged.length || t.extras.length;
  });
  if (n && loggedDays.length >= 3) {
    const totalKcal = loggedDays.reduce((s, d) => s + dayNutritionTotals(d.date).kcal, 0);
    const totalProtein = loggedDays.reduce((s, d) => s + dayNutritionTotals(d.date).protein, 0);
    const actualDensity = totalKcal > 0 ? totalProtein / totalKcal : 0;
    const requiredDensity = n.dailyKcal > 0 ? n.proteinMin / n.dailyKcal : 0;
    if (actualDensity > 0 && requiredDensity > 0 && actualDensity < requiredDensity * 0.85) {
      const avgProtein = Math.round(totalProtein / loggedDays.length);
      const neededPer100 = (requiredDensity * 100).toFixed(1);
      const actualPer100 = (actualDensity * 100).toFixed(1);
      findings.push(`Du traff i snitt ${avgProtein} g protein ${periodWord} - under målet på ${n.proteinMin} g. Trolig hvorfor: for å nå ${n.proteinMin} g protein innenfor ${n.dailyKcal} kcal trenger du ca. ${neededPer100} g protein per 100 kcal du spiser - maten din har i snitt ligget på ${actualPer100} g per 100 kcal. Det er ikke at du ikke prøver nok - målet krever at nesten alt du spiser er proteinrikt, ikke bare ett måltid. Måltidsbiblioteket sorterer forslagene etter nettopp denne tettheten.`);
    }
  }

  return findings;
}

// Bygger "fortsett med" / "bli bedre på" for et datointervall - delt mellom ukens og
// månedens innsikt siden de vurderer de samme fire områdene (trening, protein/kalorier,
// søvn, kroppsmål), bare med ulikt tidsvindu. Sykedager og ferie holdes helt utenfor,
// som om de ikke fantes - ingen av områdene skal telle dem som mislykket eller droppet.
function buildCoachingSummary(startDate, endDate, periodWord) {
  const continueItems = [];
  const improveItems = [];
  const activeDates = [];
  for (let d = startDate; d <= endDate; d = isoAddDays(d, 1)) {
    if (!isSickDay(d) && !inVacationRange(d)) activeDates.push(d);
  }

  // ---- trening: andel planlagte økter gjennomført ----
  const th = (DATA.trainingHistory || []).filter(d =>
    d.date >= startDate && d.date <= endDate && !isSickDay(d.date) && !inVacationRange(d.date));
  const plannedNonRest = th.filter(d => d.sessionType !== "rest");
  const sessionsDone = plannedNonRest.filter(d => d.loggedTypes.includes(d.sessionType)).length;
  if (plannedNonRest.length >= 2) {
    const ratio = sessionsDone / plannedNonRest.length;
    if (ratio >= 0.8) {
      continueItems.push(`Trening: du fullførte ${sessionsDone} av ${plannedNonRest.length} planlagte økter ${periodWord} - solid gjennomføring, fortsett sånn.`);
    } else if (ratio < 0.6) {
      const missedByWeekday = {};
      plannedNonRest.filter(d => !d.loggedTypes.includes(d.sessionType)).forEach(d => {
        const wd = new Date(d.date + "T00:00:00").getDay();
        missedByWeekday[wd] = (missedByWeekday[wd] || 0) + 1;
      });
      const topMissed = Object.entries(missedByWeekday).sort((a, b) => b[1] - a[1])[0];
      improveItems.push(topMissed && topMissed[1] >= 2
        ? `Trening: du fikk gjennomført ${sessionsDone} av ${plannedNonRest.length} planlagte økter ${periodWord} - ${NO_WEEKDAYS_FULL[topMissed[0]]} er dagen det oftest ikke blir noe av. Se om økten kan flyttes til et annet tidspunkt den dagen.`
        : `Trening: du fikk gjennomført ${sessionsDone} av ${plannedNonRest.length} planlagte økter ${periodWord} - prøv å finne ut hva som gjør det vanskelig å få til flere.`);
    }
  }

  // ---- protein og kalorier ----
  const n = DATA.nutritionPlan;
  const loggedActiveDates = activeDates.filter(d => {
    const t = dayNutritionTotals(d);
    return t.fromLifesum || t.mealsLogged.length || t.extras.length;
  });
  if (loggedActiveDates.length >= 3) {
    const lowProteinCount = loggedActiveDates.filter(d => dayNutritionTotals(d).protein < n.proteinMin * 0.8).length;
    const overKcalCount = loggedActiveDates.filter(d => withKcalMargin(dayNutritionTotals(d).kcal) > n.dailyKcal).length;
    const lowProteinRatio = lowProteinCount / loggedActiveDates.length;
    if (lowProteinRatio <= 0.2 && overKcalCount / loggedActiveDates.length <= 0.3) {
      continueItems.push(`Protein og kalorier: du traff proteinmålet ${loggedActiveDates.length - lowProteinCount} av ${loggedActiveDates.length} loggede dager ${periodWord} - bra jobbet, fortsett sånn.`);
    } else if (lowProteinRatio >= 0.4) {
      improveItems.push(`Protein og kalorier: du lå under proteinmålet ${lowProteinCount} av ${loggedActiveDates.length} loggede dager ${periodWord} - et proteinrikt valg tidlig på dagen gjør resten av dagen enklere.`);
    }
  }

  // ---- søvn og gjenoppbygging ----
  const sleepDates = (DATA.dailyHistory || []).filter(d =>
    d.date >= startDate && d.date <= endDate && d.sleepHours != null && !isSickDay(d.date) && !inVacationRange(d.date));
  if (sleepDates.length >= 3) {
    const goodNights = sleepDates.filter(d => d.sleepHours >= 7).length;
    const ratio = goodNights / sleepDates.length;
    const avgSleep = sleepDates.reduce((s, d) => s + d.sleepHours, 0) / sleepDates.length;
    if (ratio >= 0.7) {
      continueItems.push(`Søvn: du fikk 7+ timer ${goodNights} av ${sleepDates.length} netter ${periodWord} (snitt ${avgSleep.toFixed(1)} t) - god restitusjon, fortsett sånn.`);
    } else if (ratio <= 0.4) {
      improveItems.push(`Søvn: du fikk 7+ timer bare ${goodNights} av ${sleepDates.length} netter ${periodWord} (snitt ${avgSleep.toFixed(1)} t) - prøv å legge deg 20-30 min tidligere et par kvelder.`);
    }
  }

  // ---- kroppsmål og fettprosent-trend ----
  const weightLog = effectiveWeightLog().filter(e => e.date >= startDate && e.date <= endDate && !isSickDay(e.date)).sort((a, b) => a.date.localeCompare(b.date));
  const measureLog = loadMeasureLog().filter(e => e.date >= startDate && e.date <= endDate && e.waist != null && !isSickDay(e.date)).sort((a, b) => a.date.localeCompare(b.date));
  if (weightLog.length >= 2) {
    const avgSeries = weightRollingAvgSeries(weightLog);
    const weightDiff = avgSeries[avgSeries.length - 1] - avgSeries[0];
    let waistDiff = null;
    if (measureLog.length >= 2) waistDiff = measureLog[measureLog.length - 1].waist - measureLog[0].waist;

    if (weightDiff < -0.2 && (waistDiff == null || waistDiff <= 0.5)) {
      continueItems.push(`Kropp: vekten gikk ned ${Math.abs(weightDiff).toFixed(1)} kg ${periodWord} - fin fremgang, fortsett som nå.`);
    } else if (weightDiff > -0.2 && waistDiff != null && waistDiff <= -1) {
      continueItems.push(`Kropp: vekten sto nesten stille, men midjemålet gikk ned ${Math.abs(waistDiff).toFixed(1)} cm ${periodWord} - det betyr fett ned og muskler opp samtidig. Ikke endre noe, bare fortsett.`);
    } else if (weightDiff >= -0.2 && weightDiff <= 0.3 && (waistDiff == null || Math.abs(waistDiff) < 1)) {
      improveItems.push(`Kropp: vekt og mål har stått nokså stille ${periodWord} - sjekk at alt blir logget i Lifesum (spesielt olje, saus og drikke), eller juster underskuddet litt.`);
    }
  }

  return { continueItems: continueItems.slice(0, 3), improveItems: improveItems.slice(0, 2) };
}

function coachingSummaryHtml(coaching) {
  const continueList = coaching.continueItems.length
    ? coaching.continueItems
    : ["Ingenting som peker seg tydelig ut ennå - fortsett å logge, så får du klarere mønstre."];
  const improveList = coaching.improveItems.length
    ? coaching.improveItems
    : ["Ingenting som trenger justering akkurat nå - hold kursen."];
  return `
    <div class="report-section">
      <h3>✅ Fortsett med</h3>
      <ul>${continueList.map(c => `<li>${c}</li>`).join("")}</ul>
    </div>
    <div class="report-section">
      <h3>🎯 Bli bedre på</h3>
      <ul>${improveList.map(c => `<li>${c}</li>`).join("")}</ul>
    </div>`;
}

function renderWeeklyReport(targetId) {
  const out = document.getElementById(targetId || "report-output");
  if (!out) return;
  const todayStr = todayISO();
  const weekStart = isoAddDays(todayStr, -6);

  const history = (DATA.dailyHistory || []).filter(d => d.date >= weekStart && d.date <= todayStr && !isSickDay(d.date));
  const setLog = loadSetLog();
  const tx = loadTransactions();
  const extras = loadExtras();
  const coaching = buildCoachingSummary(weekStart, todayStr, "denne uken");

  function volumeOn(date) {
    return setLog.filter(s => s.date === date).reduce((s, x) => s + (x.weight || 0) * x.reps, 0);
  }

  const patterns = buildDeepPatterns(weekStart, todayStr, "denne uken");
  const lowSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours < 7);
  const okSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours >= 7);
  if (lowSleepDays.length >= 2 && okSleepDays.length >= 2) {
    const avgLow = lowSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / lowSleepDays.length;
    const avgOk = okSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / okSleepDays.length;
    if (avgOk > 0) {
      const pctDrop = Math.round(100 * (avgOk - avgLow) / avgOk);
      if (Math.abs(pctDrop) >= 10) {
        patterns.push(pctDrop > 0
          ? `På dager med under 7 timer søvn trente du i snitt ${pctDrop}% mindre volum enn på dager med mer søvn.`
          : "Du trente faktisk mer på dager med mindre søvn denne uken - gøy å se, men følg med at det ikke går på bekostning av restitusjonen over tid.");
      }
    }
  }

  const spendByWeekday = {};
  tx.filter(t => t.date >= weekStart && !isSavingsCategory(t.category)).forEach(t => {
    const wd = new Date(t.date + "T00:00:00").getDay();
    spendByWeekday[wd] = (spendByWeekday[wd] || 0) + t.amount;
  });
  const weekdayLabels = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
  const spendEntries = Object.entries(spendByWeekday).sort((a, b) => b[1] - a[1]);
  if (spendEntries.length && spendEntries[0][1] > 0) {
    patterns.push(`Du brukte mest penger på ${weekdayLabels[spendEntries[0][0]]} denne uken (${Math.round(spendEntries[0][1])} kr).`);
  }

  const extrasThisWeek = extras.filter(e => e.date >= weekStart);
  if (extrasThisWeek.length >= 5) {
    patterns.push(`Du logget noe utenom planen ${extrasThisWeek.length} ganger denne uken.`);
  }

  // cross-module: stress vs. variable spending
  const variableKeysForReport = loadBudgetConfig().categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
  const highStressDays = history.filter(d => d.stress != null && d.stress >= 40);
  const lowStressDays = history.filter(d => d.stress != null && d.stress < 40);
  if (highStressDays.length >= 2 && lowStressDays.length >= 2) {
    const spendOn = date => tx.filter(t => t.date === date && variableKeysForReport.includes(t.category)).reduce((s, t) => s + t.amount, 0);
    const avgHigh = highStressDays.reduce((s, d) => s + spendOn(d.date), 0) / highStressDays.length;
    const avgLow = lowStressDays.reduce((s, d) => s + spendOn(d.date), 0) / lowStressDays.length;
    if (avgLow > 0 && avgHigh > avgLow * 1.15) {
      const pctMore = Math.round(100 * (avgHigh - avgLow) / avgLow);
      patterns.push(`I dager med høyt stress brukte du i snitt ${Math.round(avgHigh)} kr på variable utgifter, mot ${Math.round(avgLow)} kr i roligere dager (${pctMore}% mer).`);
    }
  }

  // cross-module: steps vs. sleep the following night
  const stepSleepDays = history.filter(d => d.steps != null && d.sleepHours != null);
  if (stepSleepDays.length >= 4) {
    const sorted = [...stepSleepDays].sort((a, b) => a.steps - b.steps);
    const lowHalf = sorted.slice(0, Math.floor(sorted.length / 2));
    const highHalf = sorted.slice(Math.ceil(sorted.length / 2));
    const avgSleepLow = lowHalf.reduce((s, d) => s + d.sleepHours, 0) / lowHalf.length;
    const avgSleepHigh = highHalf.reduce((s, d) => s + d.sleepHours, 0) / highHalf.length;
    const sleepDiff = avgSleepHigh - avgSleepLow;
    if (Math.abs(sleepDiff) >= 0.4) {
      patterns.push(sleepDiff > 0
        ? `Du sover bedre i ukedager med mange skritt - i snitt ${sleepDiff.toFixed(1)} t mer søvn enn på de rolige dagene.`
        : `Dagene med flest skritt ga faktisk ${Math.abs(sleepDiff).toFixed(1)} t mindre søvn - følg med på at aktive dager ikke går på bekostning av søvnen.`);
    }
  }

  if (!patterns.length) {
    patterns.push("Ikke nok data til tydelige mønstre denne uken ennå - fortsett å logge, og du får dypere innsikt neste søndag.");
  }

  const patternsHtml = `
    <div class="report-section">
      <h3>🔍 Mønstre</h3>
      <ul>${patterns.map(p => `<li>${p}</li>`).join("")}</ul>
    </div>`;

  const highlights = [];
  const savedThisWeek = tx.filter(t => t.date >= weekStart && t.category === DATA.dogFund.category).reduce((s, t) => s + t.amount, 0);
  if (savedThisWeek > 0) highlights.push(`🐶 Du la ${Math.round(savedThisWeek)} kr i hundefondet denne uken.`);
  const bestSleepDay = history.filter(d => d.sleepScore != null).sort((a, b) => b.sleepScore - a.sleepScore)[0];
  if (bestSleepDay) highlights.push(`😴 Beste natt denne uken: ${fmtShort(bestSleepDay.date)} med søvnscore ${bestSleepDay.sleepScore}.`);
  const streak = computeStreak();
  if (streak >= 3) highlights.push(`🔥 Du har en streak på ${streak} dager akkurat nå.`);
  const weekDates = [];
  for (let d = weekStart; d <= todayStr; d = isoAddDays(d, 1)) { if (!isSickDay(d)) weekDates.push(d); }
  // uken totalt teller mer enn noen enkeltdag - vis snittet, ikke bare dagsfasiten på Hjem
  const weekKcalTotals = weekDates.map(d => withKcalMargin(dayNutritionTotals(d).kcal)).filter(k => k > 0);
  if (weekKcalTotals.length) {
    const avgKcal = Math.round(weekKcalTotals.reduce((s, k) => s + k, 0) / weekKcalTotals.length);
    const diff = avgKcal - DATA.nutritionPlan.dailyKcal;
    highlights.push(diff > 0
      ? `🍽️ Snitt denne uken: ${avgKcal} kcal/dag (mål ${DATA.nutritionPlan.dailyKcal}) - ${diff} over i snitt, men det er uken totalt som teller, ikke enkeltdager.`
      : `🍽️ Snitt denne uken: ${avgKcal} kcal/dag (mål ${DATA.nutritionPlan.dailyKcal}) - i snitt innenfor målet.`);
  }
  if (!highlights.length) highlights.push("En stille uke uten de store toppene - det er også en uke som teller.");

  const highlightsHtml = `
    <div class="report-section">
      <h3>🏆 Høydepunkter</h3>
      <ul>${highlights.map(h => `<li>${h}</li>`).join("")}</ul>
    </div>`;

  const lowProteinDays = history.filter(d => dayNutritionTotals(d.date).protein < DATA.nutritionPlan.proteinMin * 0.8).length;

  const why = loadWhy();
  const sessionsThisWeek = (DATA.trainingHistory || []).filter(d => d.date >= weekStart && d.date <= todayStr && d.sessionType !== "rest" && d.loggedTypes.includes(d.sessionType)).length;

  // ---- tips til neste uke - konkrete, handlingsorienterte forslag basert på denne ukens data ----
  const tips = [];
  const kcalOverDays = weekDates.filter(d => withKcalMargin(dayNutritionTotals(d).kcal) > DATA.nutritionPlan.dailyKcal).length;
  const plannedNonRestThisWeek = (DATA.trainingHistory || []).filter(d => d.date >= weekStart && d.date <= todayStr && d.sessionType !== "rest").length;
  const trainingGoodThisWeek = plannedNonRestThisWeek > 0 && sessionsThisWeek / plannedNonRestThisWeek >= 0.7;
  const matCatForTips = loadBudgetConfig().categories.find(c => c.key === "mat");
  const matCapWeekShare = matCatForTips ? getCategoryCap(matCatForTips, emKeyForDate(todayStr)) / 30 * 7 : null;
  const matSpentThisWeek = tx.filter(t => t.date >= weekStart && t.category === "mat").reduce((s, t) => s + t.amount, 0);

  if (lowSleepDays.length >= 2 && kcalOverDays >= 2) {
    tips.push("Neste uke: Prøv en proteinrik frokost for å holde deg mettere og mer stabil utover dagen, og legg inn en rolig tur en av kveldene du pleier å sove dårligst.");
  }
  if (trainingGoodThisWeek && matCapWeekShare != null && matSpentThisWeek > matCapWeekShare * 1.15) {
    tips.push(`Du har vært flink til å trene denne uken, men matbudsjettet sprakk litt. Neste uke: prøv å forberede lunsj eller middag hjemme et par dager (se mealprep-forslag i Planlegg-fanen) for å holde deg innenfor budsjettet.`);
  }
  if (!tips.length && lowProteinDays >= 3) {
    tips.push("Neste uke: Fokuser spesielt på proteinet til frokost - det er måltidet du oftest bommer på.");
  }
  if (!tips.length && extrasThisWeek.length >= 5) {
    tips.push("Neste uke: Ha et planlagt, proteinrikt mellommåltid klart i kjøleskapet - det gjør det lettere å styre unna impulsvalg.");
  }
  if (!tips.length) {
    tips.push("Ingen spesielle justeringer denne gangen - fortsett som nå, du er på god vei.");
  }

  const tipsHtml = `
    <div class="report-section">
      <h3>💡 Tips til neste uke</h3>
      <ul>${tips.slice(0, 2).map(t => `<li>${t}</li>`).join("")}</ul>
    </div>`;

  let conclusion = `Denne uken fikk du gjennomført ${sessionsThisWeek} treningsøkt${sessionsThisWeek === 1 ? "" : "er"}`;
  if (streak > 0) conclusion += ` og holder en streak på ${streak} dager`;
  conclusion += `. ${why ? `Husk hvorfor du gjør dette: ${why}. ` : ""}Du bygger noe som varer - fortsett sånn inn i neste uke! 💪`;

  const conclusionHtml = `
    <div class="report-section">
      <h3>💬 Konklusjon</h3>
      <p>${conclusion}</p>
    </div>`;

  const thisWeekMonday = (DATA.program && DATA.program.week && DATA.program.week[0]) ? DATA.program.week[0].date : null;
  const agendaNote = thisWeekMonday ? loadWeekAgenda()[thisWeekMonday] : null;
  const agendaHtml = agendaNote ? `<div class="report-section"><h3>📌 Det du planla for uken</h3><p>${agendaNote}</p></div>` : "";

  out.innerHTML = `
    <div class="report-title">Ukens innsikt · ${fmtShort(weekStart)} - ${fmtShort(todayStr)}</div>
    ${agendaHtml}${coachingSummaryHtml(coaching)}${patternsHtml}${highlightsHtml}${tipsHtml}${conclusionHtml}
  `;
}

// start/end (inclusive) of the calendar month `monthsAgo` months before today - used for
// training/kosthold/søvn, which don't follow the økonomimåned cycle
function calendarMonthRange(monthsAgo) {
  const d = new Date(todayISO() + "T00:00:00");
  const y = d.getFullYear(), m = d.getMonth() - monthsAgo;
  const start = new Date(y, m, 1);
  const end = new Date(y, m + 1, 0);
  const fmt = dt => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
  return { start: fmt(start), end: fmt(end) };
}

// Månedens innsikt: training/kosthold/søvn use the last full calendar month, budsjett uses
// the last fully completed økonomimåned (15.-14.) - she explicitly wanted these to follow
// their own natural cycles rather than being forced onto one shared date range. No PR section
// here (that's covered weekly already).
function renderMonthlyReport(targetId) {
  const out = document.getElementById(targetId || "report-output");
  if (!out) return;
  const todayStr = todayISO();
  const { start: calStart, end: calEnd } = calendarMonthRange(1);
  const emKeyNow = emKeyForDate(todayStr);
  const emKeyLast = emAddMonths(emKeyNow, -1);
  const emLastStart = emStart(emKeyLast), emLastEnd = emEnd(emKeyLast);

  const history = (DATA.dailyHistory || []).filter(d => d.date >= calStart && d.date <= calEnd && !isSickDay(d.date));
  const setLog = loadSetLog();
  const tx = loadTransactions();
  const extras = loadExtras();
  const coaching = buildCoachingSummary(calStart, calEnd, "denne måneden");

  function volumeOn(date) {
    return setLog.filter(s => s.date === date).reduce((s, x) => s + (x.weight || 0) * x.reps, 0);
  }

  const patterns = buildDeepPatterns(calStart, calEnd, "denne måneden");
  const lowSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours < 7);
  const okSleepDays = history.filter(d => d.sleepHours != null && d.sleepHours >= 7);
  if (lowSleepDays.length >= 4 && okSleepDays.length >= 4) {
    const avgLow = lowSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / lowSleepDays.length;
    const avgOk = okSleepDays.reduce((s, d) => s + volumeOn(d.date), 0) / okSleepDays.length;
    if (avgOk > 0) {
      const pctDrop = Math.round(100 * (avgOk - avgLow) / avgOk);
      if (Math.abs(pctDrop) >= 10) {
        patterns.push(pctDrop > 0
          ? `På dager med under 7 timer søvn trente du i snitt ${pctDrop}% mindre volum enn på dager med mer søvn.`
          : "Du trente faktisk mer på dager med mindre søvn denne måneden - gøy å se, men følg med at det ikke går på bekostning av restitusjonen over tid.");
      }
    }
  }

  const spendByWeekday = {};
  tx.filter(t => t.date >= emLastStart && t.date <= emLastEnd && !isSavingsCategory(t.category)).forEach(t => {
    const wd = new Date(t.date + "T00:00:00").getDay();
    spendByWeekday[wd] = (spendByWeekday[wd] || 0) + t.amount;
  });
  const weekdayLabels = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
  const spendEntries = Object.entries(spendByWeekday).sort((a, b) => b[1] - a[1]);
  if (spendEntries.length && spendEntries[0][1] > 0) {
    patterns.push(`Du brukte mest penger på ${weekdayLabels[spendEntries[0][0]]}er denne økonomimåneden (${Math.round(spendEntries[0][1])} kr totalt).`);
  }

  const extrasThisMonth = extras.filter(e => e.date >= calStart && e.date <= calEnd);
  if (extrasThisMonth.length >= 15) {
    patterns.push(`Du logget noe utenom planen ${extrasThisMonth.length} ganger denne måneden.`);
  }

  const highStressDays = history.filter(d => d.stress != null && d.stress >= 40);
  const lowStressDays = history.filter(d => d.stress != null && d.stress < 40);
  if (highStressDays.length >= 4 && lowStressDays.length >= 4) {
    const variableKeysForReport = loadBudgetConfig().categories.filter(c => c.type === "variable" && !c.savings).map(c => c.key);
    const spendOn = date => tx.filter(t => t.date === date && variableKeysForReport.includes(t.category)).reduce((s, t) => s + t.amount, 0);
    const avgHigh = highStressDays.reduce((s, d) => s + spendOn(d.date), 0) / highStressDays.length;
    const avgLow = lowStressDays.reduce((s, d) => s + spendOn(d.date), 0) / lowStressDays.length;
    if (avgLow > 0 && avgHigh > avgLow * 1.15) {
      const pctMore = Math.round(100 * (avgHigh - avgLow) / avgLow);
      patterns.push(`I dager med høyt stress brukte du i snitt ${Math.round(avgHigh)} kr på variable utgifter, mot ${Math.round(avgLow)} kr i roligere dager (${pctMore}% mer).`);
    }
  }

  const stepSleepDays = history.filter(d => d.steps != null && d.sleepHours != null);
  if (stepSleepDays.length >= 8) {
    const sorted = [...stepSleepDays].sort((a, b) => a.steps - b.steps);
    const lowHalf = sorted.slice(0, Math.floor(sorted.length / 2));
    const highHalf = sorted.slice(Math.ceil(sorted.length / 2));
    const avgSleepLow = lowHalf.reduce((s, d) => s + d.sleepHours, 0) / lowHalf.length;
    const avgSleepHigh = highHalf.reduce((s, d) => s + d.sleepHours, 0) / highHalf.length;
    const sleepDiff = avgSleepHigh - avgSleepLow;
    if (Math.abs(sleepDiff) >= 0.4) {
      patterns.push(sleepDiff > 0
        ? `I dager med mange skritt sov du i snitt ${sleepDiff.toFixed(1)} t mer enn på de rolige dagene.`
        : `Dagene med flest skritt ga faktisk ${Math.abs(sleepDiff).toFixed(1)} t mindre søvn i snitt - følg med på at aktive dager ikke går på bekostning av søvnen.`);
    }
  }

  if (!patterns.length) {
    patterns.push("Ikke nok data til tydelige mønstre denne måneden ennå - fortsett å logge, og du får dypere innsikt neste måned.");
  }

  const patternsHtml = `
    <div class="report-section">
      <h3>🔍 Mønstre</h3>
      <ul>${patterns.map(p => `<li>${p}</li>`).join("")}</ul>
    </div>`;

  const highlights = [];
  const savingsKeysForReport = loadBudgetConfig().categories.filter(c => c.savings).map(c => c.key);
  const savedThisMonth = tx.filter(t => t.date >= emLastStart && t.date <= emLastEnd && savingsKeysForReport.includes(t.category)).reduce((s, t) => s + t.amount, 0);
  if (savedThisMonth > 0) highlights.push(`🐶 Du la ${Math.round(savedThisMonth).toLocaleString()} kr i sparing denne økonomimåneden.`);
  const bestSleepDay = history.filter(d => d.sleepScore != null).sort((a, b) => b.sleepScore - a.sleepScore)[0];
  if (bestSleepDay) highlights.push(`😴 Beste natt denne måneden: ${fmtShort(bestSleepDay.date)} med søvnscore ${bestSleepDay.sleepScore}.`);
  const sessionsThisMonth = (DATA.trainingHistory || []).filter(d => d.date >= calStart && d.date <= calEnd && d.sessionType !== "rest" && d.loggedTypes.includes(d.sessionType)).length;
  if (sessionsThisMonth > 0) highlights.push(`🏋️ Du fullførte ${sessionsThisMonth} treningsøkt${sessionsThisMonth === 1 ? "" : "er"} denne måneden.`);
  const monthDates = [];
  for (let d = calStart; d <= calEnd; d = isoAddDays(d, 1)) { if (!isSickDay(d)) monthDates.push(d); }
  const monthKcalTotals = monthDates.map(d => withKcalMargin(dayNutritionTotals(d).kcal)).filter(k => k > 0);
  if (monthKcalTotals.length) {
    const avgKcal = Math.round(monthKcalTotals.reduce((s, k) => s + k, 0) / monthKcalTotals.length);
    const diff = avgKcal - DATA.nutritionPlan.dailyKcal;
    highlights.push(diff > 0
      ? `🍽️ Snitt denne måneden: ${avgKcal} kcal/dag (mål ${DATA.nutritionPlan.dailyKcal}) - ${diff} over i snitt, men det er måneden totalt som teller.`
      : `🍽️ Snitt denne måneden: ${avgKcal} kcal/dag (mål ${DATA.nutritionPlan.dailyKcal}) - i snitt innenfor målet.`);
  }
  if (!highlights.length) highlights.push("En stille måned uten de store toppene - det er også en måned som teller.");

  const highlightsHtml = `
    <div class="report-section">
      <h3>🏆 Høydepunkter</h3>
      <ul>${highlights.map(h => `<li>${h}</li>`).join("")}</ul>
    </div>`;

  const lowProteinDays = history.filter(d => dayNutritionTotals(d.date).protein < DATA.nutritionPlan.proteinMin * 0.8).length;

  // ---- tips til neste måned - konkrete, handlingsorienterte forslag basert på denne månedens data ----
  const tips = [];
  const kcalOverDays = monthDates.filter(d => withKcalMargin(dayNutritionTotals(d).kcal) > DATA.nutritionPlan.dailyKcal).length;
  const plannedNonRestThisMonth = (DATA.trainingHistory || []).filter(d => d.date >= calStart && d.date <= calEnd && d.sessionType !== "rest").length;
  const trainingGoodThisMonth = plannedNonRestThisMonth > 0 && sessionsThisMonth / plannedNonRestThisMonth >= 0.7;
  const matCatForTips = loadBudgetConfig().categories.find(c => c.key === "mat");
  const matCapLastMonth = matCatForTips ? getCategoryCap(matCatForTips, emKeyLast) : null;
  const matSpentLastMonth = tx.filter(t => t.date >= emLastStart && t.date <= emLastEnd && t.category === "mat").reduce((s, t) => s + t.amount, 0);

  if (lowSleepDays.length >= 4 && kcalOverDays >= 4) {
    tips.push("Neste måned: Prøv en proteinrik frokost på faste tider for å holde deg mettere og mer stabil utover dagen, og prioriter en rolig kveldstur de dagene søvnen pleier å svikte.");
  }
  if (trainingGoodThisMonth && matCapLastMonth != null && matSpentLastMonth > matCapLastMonth * 1.15) {
    tips.push("Du har vært flink til å trene, men matbudsjettet har vært utfordrende. Neste måned: prøv å forberede lunsj eller middag hjemme 2-3 dager i uken (se mealprep-forslag i Planlegg-fanen) for å holde deg innenfor budsjettet.");
  }
  if (!tips.length && lowProteinDays >= 10) {
    tips.push("Neste måned: Fokuser spesielt på proteinet til frokost - det er måltidet du oftest bommer på gjennom måneden.");
  }
  if (!tips.length && extrasThisMonth.length >= 15) {
    tips.push("Neste måned: Ha planlagte, proteinrike mellommåltider klare - det gjør det lettere å styre unna impulsvalg.");
  }
  if (!tips.length) {
    tips.push("Ingen spesielle justeringer denne gangen - fortsett som nå, du er på god vei.");
  }

  const tipsHtml = `
    <div class="report-section">
      <h3>💡 Tips til neste måned</h3>
      <ul>${tips.slice(0, 2).map(t => `<li>${t}</li>`).join("")}</ul>
    </div>`;

  const why = loadWhy();
  const streak = computeStreak();
  let conclusion = `Denne måneden fikk du gjennomført ${sessionsThisMonth} treningsøkt${sessionsThisMonth === 1 ? "" : "er"}`;
  if (streak > 0) conclusion += `, og holder en streak på ${streak} dager akkurat nå`;
  conclusion += `. ${why ? `Husk hvorfor du gjør dette: ${why}. ` : ""}Du bygger noe som varer - fortsett sånn inn i neste måned! 💪`;

  const conclusionHtml = `
    <div class="report-section">
      <h3>💬 Konklusjon</h3>
      <p>${conclusion}</p>
    </div>`;

  out.innerHTML = `
    <div class="report-title">Månedens innsikt · ${fmtShort(calStart)} - ${fmtShort(calEnd)} (trening/kosthold) · ${fmtShort(emLastStart)} - ${fmtShort(emLastEnd)} (økonomi)</div>
    ${coachingSummaryHtml(coaching)}${patternsHtml}${highlightsHtml}${tipsHtml}${conclusionHtml}
  `;
}

function showReport(key) {
  document.querySelectorAll(".report-tab-btn").forEach(b => b.classList.toggle("active", b.dataset.report === key));
  if (key === "monthly") renderMonthlyReport();
  else if (key === "weekly") renderWeeklyReport();
  else renderEveningReport();
}
document.querySelectorAll(".report-tab-btn").forEach(btn => {
  btn.addEventListener("click", () => showReport(btn.dataset.report));
});
showReport("evening");

// nudge toward the monthly report the first few days of a new month, since there's no
// real push notification to tell her it's ready - she has to be told inside the app
function renderHjemMonthlyInsightNudge() {
  const el = document.getElementById("hjem-monthly-insight-nudge");
  if (!el) return;
  if (new Date().getDate() > 3) { el.innerHTML = ""; return; }
  const { start: calStart } = calendarMonthRange(1);
  const monthName = NO_MONTHS_FULL[parseInt(calStart.slice(5, 7), 10) - 1];
  const monthLabel = monthName.charAt(0).toUpperCase() + monthName.slice(1);
  el.innerHTML = `
    <div class="hjem-reminder-banner">
      <span>📅 ${monthLabel}-oversikten din er klar.</span>
      <button id="hjem-monthly-insight-link">Se den</button>
    </div>
  `;
  document.getElementById("hjem-monthly-insight-link").addEventListener("click", () => {
    showTab("rapport");
    setTimeout(() => {
      showReport("monthly");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 50);
  });
}

// ---------------------------------------------------------------- daglig rutine (kne/hofte/nakke)
// Separat fra treningsplanen - en enkel sjekkliste, ikke koblet til sett-logg/PR-systemet.
// Nøkklet på dato, så den nullstilles automatisk hver dag. (DAILY_ROUTINE_LOG_KEY er deklarert
// tidlig i filen, sammen med SICK_DAY_KEY, siden renderHjem() kan kjøre før dette punktet.)
function loadDailyRoutineLog() { return loadLS(DAILY_ROUTINE_LOG_KEY, {}); }
function saveDailyRoutineLog(l) { saveLS(DAILY_ROUTINE_LOG_KEY, l); }
function isDailyRoutineChecked(date, key) {
  const log = loadDailyRoutineLog();
  return !!(log[date] && log[date].includes(key));
}
function toggleDailyRoutineItem(date, key) {
  const log = loadDailyRoutineLog();
  const done = log[date] || [];
  const i = done.indexOf(key);
  if (i === -1) done.push(key); else done.splice(i, 1);
  log[date] = done;
  saveDailyRoutineLog(log);
}
function renderHjemDailyRoutine() {
  const el = document.getElementById("hjem-daily-routine");
  const items = DATA.dailyRoutineItems;
  if (!el || !items || !items.length) return;
  const today = todayISO();
  const doneCount = items.filter(it => isDailyRoutineChecked(today, it.key)).length;
  const groups = [];
  items.forEach(it => {
    let g = groups.find(x => x.group === it.group);
    if (!g) { g = { group: it.group, items: [] }; groups.push(g); }
    g.items.push(it);
  });
  const groupsHtml = groups.map(g => `
    <div class="daily-routine-group">
      <div class="daily-routine-group-label">${g.group}</div>
      ${g.items.map(it => `
        <label class="daily-routine-item">
          <input type="checkbox" data-routine-key="${it.key}" ${isDailyRoutineChecked(today, it.key) ? "checked" : ""}>
          <span>${it.label}</span>
        </label>
      `).join("")}
    </div>
  `).join("");
  el.innerHTML = `
    <h3 style="margin:0 0 4px;font-size:15px;">📋 Daglig rutine (kne/hofte/nakke)</h3>
    <div class="section-sub" style="margin-bottom:8px;">Ca. 8-10 min · ${doneCount}/${items.length} gjort i dag</div>
    <div class="daily-routine-groups">${groupsHtml}</div>
  `;
  el.querySelectorAll("[data-routine-key]").forEach(cb => {
    cb.addEventListener("change", () => {
      toggleDailyRoutineItem(today, cb.dataset.routineKey);
      renderHjemDailyRoutine();
    });
  });
}

// ---------------------------------------------------------------- fremgang (long-term trends/goals)
document.querySelectorAll("#body-period-tabs .period-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#body-period-tabs .period-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    bodyChartPeriodMonths = parseInt(btn.dataset.period, 10);
    renderBodyGoalChart();
  });
});
document.querySelectorAll("#body-measure-tabs .measure-select-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#body-measure-tabs .measure-select-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    bodyChartMeasure = btn.dataset.measure;
    renderBodyGoalChart();
  });
});

document.getElementById("fund-log-date").value = todayISO();
document.getElementById("fund-log-add").addEventListener("click", () => {
  const date = document.getElementById("fund-log-date").value || todayISO();
  const contributedRaw = document.getElementById("fund-log-contributed").value;
  const value = parseFloat(document.getElementById("fund-log-value").value);
  if (Number.isNaN(value)) return;
  if (contributedRaw.trim() === "") {
    setInvestFundValue(date, value);
  } else {
    setInvestFundEntry(date, value, parseFloat(contributedRaw));
  }
  document.getElementById("fund-log-contributed").value = "";
  document.getElementById("fund-log-value").value = "";
  renderFundTrend();
  renderHjemFinance();
});

renderWeightGoalInput();
renderBodyGoalChart();
renderCalorieCalibration();
renderActivityTrends();
renderExpenseTrends();
renderSavingsGoals();
renderFundTrend();
renderWeeklyReport("fremgang-weekly-report");

// ---------------------------------------------------------------- settings toggles
const personalityToggle = document.getElementById("settings-personality-toggle");
personalityToggle.checked = loadSettings().personalityEnabled;
personalityToggle.addEventListener("change", () => {
  const s = loadSettings();
  s.personalityEnabled = personalityToggle.checked;
  saveSettings(s);
  renderHjemReminder();
});

const vacationToggle = document.getElementById("settings-vacation-toggle");
vacationToggle.checked = isVacationActive();
vacationToggle.addEventListener("change", () => {
  setVacationActive(vacationToggle.checked);
  renderHjem();
});

const focusModeToggle = document.getElementById("settings-focus-mode-toggle");
focusModeToggle.checked = loadSettings().kostholdFocusMode;
focusModeToggle.addEventListener("change", () => {
  const s = loadSettings();
  s.kostholdFocusMode = focusModeToggle.checked;
  saveSettings(s);
  renderNutrition();
});

(function initMvdSettingsForm() {
  const s = loadSettings();
  document.getElementById("mvd-protein-input").value = s.mvdProtein;
  document.getElementById("mvd-steps-input").value = s.mvdSteps;
  document.getElementById("mvd-minutes-input").value = s.mvdMinutes;
})();
document.getElementById("mvd-settings-save").addEventListener("click", () => {
  const protein = parseInt(document.getElementById("mvd-protein-input").value, 10);
  const steps = parseInt(document.getElementById("mvd-steps-input").value, 10);
  const minutes = parseInt(document.getElementById("mvd-minutes-input").value, 10);
  if (!protein || !steps || !minutes) {
    flashSaved("mvd-settings-saved-msg", "Fyll ut alle tre feltene");
    return;
  }
  const s = loadSettings();
  s.mvdProtein = protein;
  s.mvdSteps = steps;
  s.mvdMinutes = minutes;
  saveSettings(s);
  renderBadDayPanel();
  renderHjemMvdSunday();
  flashSaved("mvd-settings-saved-msg", "Lagret ✓");
});

// ---------------------------------------------------------------- backup / export / import
const BACKUP_KEYS = [
  WEIGHT_LOG_KEY, MEASURE_LOG_KEY, SHOP_LIST_KEY, TX_KEY,
  BUDGET_CONFIG_KEY, PLAN_OVERRIDES_KEY, SET_LOG_KEY, SEEN_KEY, REST_PREFS_KEY,
  FORGOTTEN_SAVINGS_KEY, BADDAY_LOG_KEY, EXTRAS_KEY, WATER_KEY, STREAK_BEST_KEY,
  SETTINGS_KEY, WHY_KEY, VACATION_KEY, CUSTOM_MEALS_KEY, MEAL_LOG_KEY, INVEST_FUND_KEY,
  SAVINGS_GOALS_KEY, CUSTOM_INGREDIENTS_KEY, MEAL_ING_OVERRIDES_KEY, MISSED_DAY_ACK_KEY, RPE_LOG_KEY,
  UNPLANNED_CARDIO_ACK_KEY, SOCIAL_BUDGET_KEY, FREEZE_CARDS_USED_KEY, FREEZE_NOTICE_ACK_KEY,
  SICK_DAY_KEY, DAILY_ROUTINE_LOG_KEY,
];
window.BACKUP_KEYS = BACKUP_KEYS;

document.getElementById("sync-now-btn").addEventListener("click", () => {
  if (!window.__cloudAuth) { setSyncStatus("Skylagring er ikke klar ennå - prøv igjen om et øyeblikk."); return; }
  setSyncStatus("Synkroniserer...");
  window.__cloudAuth.pullNow();
});
document.getElementById("sync-logout-btn").addEventListener("click", () => {
  if (!window.__cloudAuth) return;
  window.__cloudAuth.signOut();
});

document.getElementById("backup-export").addEventListener("click", () => {
  saveLS(LAST_BACKUP_KEY, todayISO());
  const dump = {};
  BACKUP_KEYS.forEach(k => {
    const v = localStorage.getItem(k);
    if (v !== null) dump[k] = JSON.parse(v);
  });
  const blob = new Blob([JSON.stringify(dump, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `dashboard-backup-${todayISO()}.json`;
  a.click();
  URL.revokeObjectURL(url);
  renderHjemBackupReminder();
});

document.getElementById("backup-import-btn").addEventListener("click", () => {
  document.getElementById("backup-import-file").click();
});

document.getElementById("backup-import-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const status = document.getElementById("backup-status");
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      let count = 0;
      BACKUP_KEYS.forEach(k => {
        if (data[k] !== undefined) {
          localStorage.setItem(k, JSON.stringify(data[k]));
          count++;
        }
      });
      status.textContent = `Gjenopprettet ${count} datasett. Laster siden på nytt...`;
      setTimeout(() => location.reload(), 1200);
    } catch (err) {
      status.textContent = "Kunne ikke lese filen - er det en gyldig sikkerhetskopi fra dashbordet?";
    }
  };
  reader.readAsText(file);
});

const VAPID_PUBLIC_KEY = "BIGWkavhmM-_3-ZKCKfvkvZT_vsnY09jFmW64MdACKPmW1Q53yOH-WwrMuACiYkaBKzEZWcvkvlpwj_b_2Bm5IA";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

function setPushStatus(msg) {
  const el = document.getElementById("push-status");
  if (el) el.textContent = msg;
}

function showPushSubscription(subscription) {
  const area = document.getElementById("push-subscription-area");
  const textEl = document.getElementById("push-subscription-text");
  if (!area || !textEl) return;
  textEl.value = JSON.stringify(subscription.toJSON ? subscription.toJSON() : subscription);
  area.style.display = "";
}

async function initPushUi() {
  const unsupportedEl = document.getElementById("push-unsupported-msg");
  const setupArea = document.getElementById("push-setup-area");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    if (unsupportedEl) {
      unsupportedEl.style.display = "";
      unsupportedEl.textContent = "Denne nettleseren støtter ikke push-varsler. På iPhone: åpne siden i Safari, legg den til på Hjem-skjermen, og åpne den derfra.";
    }
    if (setupArea) setupArea.style.display = "none";
    return;
  }
  try {
    const reg = await navigator.serviceWorker.register("sw.js");
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      setPushStatus("Varsler er aktivert på denne telefonen.");
      showPushSubscription(existing);
    }
  } catch (err) {
    setPushStatus("Kunne ikke sette opp varsler: " + err.message);
  }
}
initPushUi();

const pushEnableBtn = document.getElementById("push-enable-btn");
if (pushEnableBtn) {
  pushEnableBtn.addEventListener("click", async () => {
    setPushStatus("Setter opp varsler...");
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setPushStatus("Du må tillate varsler for at dette skal funke.");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      let subscription = await reg.pushManager.getSubscription();
      if (!subscription) {
        subscription = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }
      setPushStatus("Varsler er aktivert på denne telefonen.");
      showPushSubscription(subscription);
    } catch (err) {
      setPushStatus("Noe gikk feil: " + err.message);
    }
  });
}

const pushCopyBtn = document.getElementById("push-copy-btn");
if (pushCopyBtn) {
  pushCopyBtn.addEventListener("click", async () => {
    const textEl = document.getElementById("push-subscription-text");
    if (!textEl) return;
    try {
      await navigator.clipboard.writeText(textEl.value);
      setPushStatus("Kopiert! Send den til meg.");
    } catch (err) {
      textEl.select();
      setPushStatus("Marker teksten over og kopier manuelt.");
    }
  });
}

document.getElementById("footer-generated").textContent = `Generated ${new Date(DATA.meta.generated).toLocaleString()}`;

// ---------------------------------------------------------------- hidden debug page
// Not linked anywhere in the UI - visit dashboard.html#debug (after unlocking the gate)
// to dump DATA plus every localStorage key as raw JSON, for troubleshooting.
function renderDebugPage() {
  const ls = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    try { ls[k] = JSON.parse(localStorage.getItem(k)); } catch (e) { ls[k] = localStorage.getItem(k); }
  }
  document.body.innerHTML = "";
  const pre = document.createElement("pre");
  pre.style.cssText = "white-space:pre-wrap;word-break:break-word;padding:16px;font-size:12px;background:#0b0b0f;color:#8f8;min-height:100vh;margin:0;font-family:monospace;";
  pre.textContent = JSON.stringify({ DATA, localStorage: ls }, null, 2);
  document.body.appendChild(pre);
}
</script>

<script type="module">
  // Firebase needs its own module scope for these imports, so this talks to the classic
  // script above through window.__cloudAuth (calls into here) and window.__onAuthStateChanged /
  // window.__cloudSyncStatus (calls back out) rather than sharing scope directly. This script
  // is deferred (all type="module" scripts are), so the classic script above has always
  // already finished setting up those callbacks by the time any of this runs.
  import { initializeApp } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-app.js";
  import {
    getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut,
    setPersistence, browserLocalPersistence,
  } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-auth.js";
  import {
    getFirestore, doc, getDoc, setDoc,
  } from "https://www.gstatic.com/firebasejs/13.3.0/firebase-firestore.js";

  const firebaseConfig = {
    apiKey: "AIzaSyBPzs9R-3fq0yJy9GMGXQS5myayKhJNhNo",
    authDomain: "katrine-2027-dashboard.firebaseapp.com",
    projectId: "katrine-2027-dashboard",
    storageBucket: "katrine-2027-dashboard.firebasestorage.app",
    messagingSenderId: "208857107478",
    appId: "1:208857107478:web:d6318f950a993f577a7937",
  };
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);

  let currentUser = null;
  let lastSyncedAt = 0;
  let pushTimer = null;

  // persisted across page loads (per uid) - without this, every fresh page load would see
  // remote.updatedAt > 0 and think the cloud always has something newer, reloading forever.
  function syncMarkerKey(uid) { return "garminDashboardCloudSyncedAt_" + uid; }
  function loadLastSyncedAt(uid) { return parseInt(localStorage.getItem(syncMarkerKey(uid)) || "0", 10); }
  function saveLastSyncedAt(uid, ts) { localStorage.setItem(syncMarkerKey(uid), String(ts)); }

  function fmtTime(ms) {
    return new Date(ms).toLocaleTimeString("no-NO", { hour: "2-digit", minute: "2-digit" });
  }
  function dumpBackupData() {
    const dump = {};
    (window.BACKUP_KEYS || []).forEach(k => {
      const v = localStorage.getItem(k);
      if (v === null) return;
      try { dump[k] = JSON.parse(v); } catch (e) { /* skip unparsable value */ }
    });
    return dump;
  }
  function applyBackupData(data) {
    (window.BACKUP_KEYS || []).forEach(k => {
      if (data[k] !== undefined) localStorage.setItem(k, JSON.stringify(data[k]));
    });
  }

  async function cloudPush() {
    if (!currentUser) return;
    const now = Date.now();
    try {
      await setDoc(doc(db, "users", currentUser.uid), { updatedAt: now, data: dumpBackupData() });
      lastSyncedAt = now;
      saveLastSyncedAt(currentUser.uid, now);
      window.__cloudSyncStatus(`Synkronisert kl ${fmtTime(now)}`);
    } catch (e) {
      window.__cloudSyncStatus("Kunne ikke synke til skyen - sjekk internettforbindelsen");
    }
  }
  function schedulePush() {
    if (!currentUser) return;
    clearTimeout(pushTimer);
    pushTimer = setTimeout(cloudPush, 3000);
  }
  async function pullIfNewer() {
    if (!currentUser) return;
    try {
      const snap = await getDoc(doc(db, "users", currentUser.uid));
      if (!snap.exists()) { await cloudPush(); return; }
      const remote = snap.data();
      if (remote.updatedAt > lastSyncedAt) {
        applyBackupData(remote.data || {});
        lastSyncedAt = remote.updatedAt;
        saveLastSyncedAt(currentUser.uid, remote.updatedAt);
        window.__cloudSyncStatus(`Hentet nyere data fra skyen kl ${fmtTime(remote.updatedAt)} - laster siden på nytt...`);
        setTimeout(() => location.reload(), 1200);
      } else {
        window.__cloudSyncStatus(`Oppdatert - sist synket kl ${fmtTime(lastSyncedAt)}`);
      }
    } catch (e) {
      window.__cloudSyncStatus("Kunne ikke hente fra skyen - sjekk internettforbindelsen");
    }
  }

  window.__cloudAuth = {
    signIn: (email, password) => signInWithEmailAndPassword(auth, email, password),
    signOut: () => signOut(auth),
    schedulePush,
    pullNow: pullIfNewer,
  };

  setPersistence(auth, browserLocalPersistence).catch(() => {});
  onAuthStateChanged(auth, user => {
    currentUser = user;
    lastSyncedAt = user ? loadLastSyncedAt(user.uid) : 0;
    window.__onAuthStateChanged(user);
  });

  // A tab left open for hours (e.g. on a laptop) otherwise never learns about edits made
  // elsewhere until she reloads it or hits "Synk nå" - so every unrelated save on it kept
  // re-pushing its own stale snapshot and clobbering newer edits from another device. This
  // periodically pulls in the background to catch up before that can happen. Skipped while
  // the tab is focused, so it never yanks a reload out from under her mid-edit.
  setInterval(() => {
    if (currentUser && !document.hasFocus()) pullIfNewer();
  }, 60000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
