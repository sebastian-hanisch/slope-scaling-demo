# Slope Scaling – Fixkosten linearisieren – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-slope-scaling-demo.streamlit.app/)**

Zwölftes und letztes Stück der Hauptlinie der **Netzwerkfluss-Linie** der "Konzepte"-Reihe für die Website "Sebastian Hanisch – Operations Research und Machine Learning", drittes im Netzwerkdesign-Ast:
anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo **ein** Verfahren – die Matheuristik **Slope Scaling** für das Fixkosten-Netzdesign – an einem wachsenden Beispiel.
Die beiden Vorgänger lösen das Problem **exakt** (Schranke und Schnitte, Benders-Zerlegung). Slope Scaling verzichtet auf jeden Beweis: die Fixkosten $f_g$ einer Kante werden als **Stückkosten** auf ihren Fluss umgelegt, $c^k_e+f_g/s_g$, wobei die **Steigung** $s_g$ die Menge ist, die man über die Kante erwartet. Das ist ein LP ohne Entscheidungsvariablen. Ist die Erwartung richtig, kostet der Fluss genau die Fixkosten; also wird die Steigung nach jedem LP durch den gefundenen Fluss ersetzt (Kim/Pardalos 1999) und das LP erneut gelöst, bis sich nichts mehr ändert. Kanten ohne Fluss werden nie bezahlt: der Entwurf ergibt sich von selbst. Bausteine nach Crainic/Gendron/Hernu (2004): Dämpfung, Gedächtnis, Störung, dazu eine Politur.
Vehikel: das Distributionsnetz der Vorgänger (Standard, Seed 155), ein **Streckennetz** (Gitter) und drei feste Lehrnetze (Big-M-Falle, Rundungs-Falle, Bündelung).

**Einordnung in die Reihe (die Kanten des Graphen):** Modell und Bausteine (Netze, MIP-Optimum, Aufrunden) stammen aus [fixkosten-netzdesign-demo](https://github.com/sebastian-hanisch/fixkosten-netzdesign-demo) und [benders-demo](https://github.com/sebastian-hanisch/benders-demo); das Verfahren ist das skalierbare Gegenstück: schnell, ohne Schranke, ohne Beweis. Die Bewertung läuft gegen das exakte Optimum (HiGHS) und gegen das Aufrunden aus dem Vorgängerstück. MIP-basierte Nachbarschaftssuchen (Local Branching, RINS) sind bewusst nicht Teil: sie gehören zur LNS-Linie (alns-demo). Mit diesem Stück ist die Hauptlinie vollständig; offen sind nur die Erweiterungen (Graph Cuts – als erstes Stück davon ist [projektauswahl-demo](https://github.com/sebastian-hanisch/projektauswahl-demo) gebaut –, Spannbaum/Steiner, Standortplanung, Verkehrsumlegung, Zeitexpansion). Bisher gebaut: alle zwölf Stücke der Hauptlinie.
```
edmonds-karp-demo (Wurzel: Restgraph, Rückkanten, Max-Flow = Min-Cut)                  [gebaut]
  ├─ dinic-demo (viele kürzeste Wege je Phase: Niveaugraph, blockierender Fluss)        [gebaut]
  ├─ push-relabel-demo (kein Weg: Überschüsse schieben, Höhen anheben)                 [gebaut]
  └─ ssp-demo (Kosten: der billigste Weg im Restgraphen, Potenziale)                    [gebaut]
       ├─ cycle-canceling-demo (negative Kreise löschen) → Netzwerksimplex               [gebaut]
       │    (network-flow-demo)                                                          [gebaut als Fall-Demo]
       ├─ cost-scaling-demo (Push-Relabel + ε-Skalierung, das nutzt OR-Tools)           [gebaut]
       └─ multicommodity-demo (mehrere Güter teilen Kapazität: Kanten-LP, Preise)       [gebaut]
            ├─ mcf-column-generation-demo (Pfade als Spalten, Pricing = Dijkstra)       [gebaut]
            ├─ garg-koenemann-demo (Näherung mit Preisen, ohne LP-Löser)                [gebaut]
            └─ fixkosten-netzdesign-demo (Fixkosten: Schranke und Schnitte)             [gebaut]
                 ├─ benders-demo (Entwurf im Master, Fluss im Teilproblem)              [gebaut]
                 └─ slope-scaling-demo (Fixkosten linearisieren, ohne Beweis)           [dieses Stück]
```

## Ergebnis (Zahlen aus den Tests)

Jede hier genannte Zahl ist in `tests/test_claims.py` belegt: Beispielnetze über ihre Seeds, Verteilungen über feste Netze (Seeds ab 100000, dieselben wie in den Vorgänger-Demos): 40 Netze für die Verteilung (34 lieferbar), 24 für die Varianten und Kontrollen (21 lieferbar), zwei je Größe. Standard: 3 Güter, 3 Werke, 3 Verteilzentren, 8 Filialen, Netzdichte 60 %, Streuung 50 %, Auslastung 50 %, Fixkosten-Basis 30, Startsteigung = Kapazität, **Dämpfung 0,5, Störung an, Politur an**, 30 Iterationen.
Slope Scaling ist deterministisch (fester Zufallsstrom für die Störung); das **Optimum** rechnet HiGHS (MIP). Zahlen stehen gerundet („etwa“), die Tests prüfen Bänder; Sekunden werden nur als grobes Verhältnis geprüft. Die Kopien aus den Vorgängern sind bewacht (`tests/test_copies.py`).

**Es findet gute Lösungen, sehr schnell.** Auf den 34 lieferbaren Distributionsnetzen liegt die Lösung im Mittel **0,7 % über dem Optimum** (Median 0,1 %, schlechtestes Netz 6,7 %), in **65 %** der Netze ist das Optimum getroffen (Lücke unter 0,5 %), nach im Mittel etwa 15 Iterationen (33 mal Fixpunkt, 1 mal Zyklus). Zum Vergleich: das **erste LP allein** (Steigung = Kapazität, ohne jede Anpassung) liegt 7,6 % über dem Optimum, das **Aufrunden** aus dem Vorgängerstück 5,1 % – Slope Scaling ist in 29 von 34 Netzen billiger. Im Beispielnetz (Seed 155): beste Iteration (Iteration 9 von 19) 1 797 gegen das Optimum 1 784 (0,7 %); die letzte Iteration liegt 4,5 % darüber.
**Streckennetz** (Gitter 4 × 3, drei Güter, Fixkosten 10, 30 von 40 Netzen lieferbar): Lücke im Mittel 1,6 % (Median 0), in 80 % das Optimum; das Aufrunden liegt hier bei 2,5 %, das erste LP bei 5,9 %. Preset-Netz (Seed 6): das erste LP trifft das Optimum 245, das Aufrunden liegt 12 % darüber.
Lehrnetze: **Big-M-Falle** – das erste LP wählt die breite Kante (Kosten 31), erst die Anpassung der Steigung an den Fluss 1 führt zum Optimum 15; **Rundungs-Falle** – schon das erste LP trifft 23; **Bündelung** ohne Dämpfung und Störung – 11 im ersten LP, Zyklus nach 3 Iterationen.

**Die letzte Iteration ist nicht die beste.** Die wahren Kosten schwanken von Iteration zu Iteration; in **62 %** der Netze ist die letzte Iteration schlechter als die beste (im Mittel 3,2 % gegen 1,1 %). Im Extremfall (Seed 38, reines Verfahren, Optimum 1 549) trifft das erste LP mit 1 554 fast das Optimum (0,3 %), danach wird es schlechter: nach 9 Iterationen liegt der Fixpunkt bei 1 909, **23 % darüber**. Deshalb wird die beste gefundene Lösung gemerkt.
**Was jede Zutat leistet** (Lücke im Mittel, 21 Netze): reines Slope Scaling 2,25 % · mit Politur 1,8 % · dazu Gedächtnis 1,55 % · Störung 1,4 % · Dämpfung 0,5 allein 1,7 % (aber 9 Zyklen) · Startsteigung Nachfrage 1,15 % · **Dämpfung + Störung 0,74 %** (Optimum in 15 von 21 Netzen). Negativkontrollen (ohne Politur und Störung): mit nur einem LP (Steigung nie angepasst) 7,6 % (Optimum in nur etwa 2 von 21), mit der letzten statt der besten Iteration 3,0 % gegen 2,25 %.

**Es lohnt sich erst bei großen Netzen – und die Lücke wächst.** Slope Scaling gegen das direkte MIP von HiGHS (Zeitlimit 20 s, je zwei feste Netze): bei etwa 68 Entwurfskanten Lücke 7 %, bei etwa 460 Kanten 10 % (1,5 gegen 3,5 Sekunden), bei etwa 1 200 Kanten 14 % (2,9 gegen 18 Sekunden; die Lücke gegen die beste Lösung, die HiGHS im Zeitlimit fand). Auf den kleinen Netzen der Vorgänger (27 Entwurfskanten) ist HiGHS **schneller** als Slope Scaling (etwa 0,02 gegen 0,05 Sekunden).

## Was nicht funktioniert hat / Vorab-Hypothesen

Vor dem Bau standen acht Vermutungen im Plan. Gemessen:

- **„Die Politur bringt am meisten“ – widerlegt.** Sie senkt die Lücke des reinen Verfahrens von 2,25 auf 1,8 %; die **Dämpfung zusammen mit der Störung** bringt deutlich mehr (0,74 %). Die Politur ist am wichtigsten, wenn das Verfahren früh abgebrochen wird (nur ein LP: 6,8 % → 3,4 %).
- **„Gedächtnis und Störung senken die Lücke deutlich“ – nur zum Teil.** Die Störung hilft (2,25 → 1,4 %, Zyklen von etwa 3 auf 1), das Gedächtnis wenig (1,55 %). Dämpfung allein erzeugt Zyklen (9 von 21 Netzen); erst mit der Störung wird daraus die beste Kombination. Die Unterschiede zwischen den Varianten sind auf 21 Netzen klein, die Rangfolge ist mit Vorsicht zu lesen.
- **„Die letzte Iteration ist oft schlechter als die beste“ – bestätigt, und stärker als gedacht:** in 62 % der Netze, im Extremfall 23 % gegen 0,3 %.
- **„Zyklen und Stagnation sind häufig“ – nur ohne Störung:** das reine Verfahren zyklt in 3 von 21 Netzen, mit Dämpfung allein in 9, mit Standardoptionen in 1 von 34.
- **„Besser als das Aufrunden“ – bestätigt für Distributionsnetze** (0,7 gegen 5,1 %), auf Streckennetzen nur knapp (1,6 gegen 2,5 %): dort ist das Aufrunden schon gut, weil die starke Kopplung die Schranke trägt.
- **„Slope Scaling gewinnt bei großen Netzen mit Zeitgrenze“ – nur mäßig.** HiGHS löst selbst Netze mit 460 Entwurfskanten in wenigen Sekunden und mit 1 200 in 18 Sekunden; Slope Scaling ist dort 2- bis 6-mal schneller, aber 10 bis 14 % über dem Optimum. Wer die exakte Lösung braucht, nimmt HiGHS; wer in Sekunden eine brauchbare will oder das MIP nicht mehr in den Speicher passt, Slope Scaling.
- **„Die Güte fällt mit der Größe“ – bestätigt:** 7 → 10 → 14 %.
- **Auf kleinen Netzen ist es langsamer als das exakte MIP** (27 Entwurfskanten: 0,05 gegen 0,02 Sekunden) – ein Verfahren für große Netze, nicht für die Demo-Netze.

## Was die Demo zeigt

- **Iteration für Iteration:** ein Regler durch die Iterationen; je Iteration die Netzkarte mit dem Fluss des Steigungs-LP (blau, Beschriftung s = Steigung), den gegenüber der vorigen Iteration geänderten Kanten (orange) und dem Optimum (rot), dazu die wahren Kosten je Iteration (sie schwanken) mit der besten bis dahin, dem Optimum und dem Aufrunden aus dem Vorgängerstück.
- **Verfahren wählbar:** Startsteigung, Dämpfung, Gedächtnis, Störung, Politur, Iterationsgrenze, Negativkontrollen.
- **Nicht nur dieses Netz:** Verteilung der Lücke über 40 feste Netze (erstes LP, beste Iteration, mit Politur, Aufrunden) mit der Marke „Ihre Ziehung“.
- **Experimente (auf Abruf):** Varianten (Lücke, Optimum getroffen, Iterationen, Zyklen), Negativkontrollen, Größe gegen HiGHS mit Zeitlimit.
- **Wo die Annahmen enden:** keine Schranke, Fixpunkte als lokale Optima, ein LP je Iteration, nur Fixkosten je Kante, Nachbarschaftssuche gehört zur LNS-Linie.

## Modell und Verfahren

- **Steigungs-LP:** $\min\sum_{k,e}\big(c^k_e+f_{g(e)}/s_{g(e)}\big)x^k_e$ mit Flusserhaltung je Gut, Kapazität $\sum_k x^k_e\le u_e$ und voller Nachfrage; HiGHS (`linprog`), die Matrizen werden einmal aufgebaut, je Iteration ändert sich nur der Kostenvektor.
- **Anpassen:** mit $F_g$ = Fluss auf der Gruppe (im Streckennetz beide Richtungen einer Strecke): $s_g\leftarrow\alpha s_g+(1-\alpha)F_g$ für Gruppen mit Fluss ($\alpha$ = Dämpfung), mit Gedächtnis das Mittel der positiven $F_g$; Kanten ohne Fluss behalten ihre Steigung; Steigungen sind mindestens 1.
- **Wahre Kosten:** Fixkosten der Gruppen mit Fluss plus Stückkosten; beste Iteration gemerkt. Stopp bei **Fixpunkt** (Entwurf und Fluss wiederholen sich unmittelbar), **Zyklus** (ein früherer Entwurf kehrt wieder; mit Störung höchstens dreimal ausgelenkt, Steigung × 0,5 bis 1,5 aus einem festen SplitMix64-Strom) oder Iterationsgrenze.
- **Politur:** Entwurf der besten Lösung festhalten, Fluss per LP neu wählen, dann Gruppen einzeln schließen (teuerste Fixkosten zuerst), solange die Gesamtkosten sinken.
- **Referenz:** Optimum aus dem MIP von HiGHS, Aufrunden (LP-Relaxation aufrunden, ungenutzte Kanten schließen) aus dem Vorgängerstück.

## Dateien

```
app.py                  Oberfläche (Streamlit)
ss_slope.py             Steigungs-LP, Schleife, Bausteine, Politur
ss_evaluation.py        Auswertung, Verteilung, Experiment-Tabellen
ss_visualization.py     Plotly-Abbildungen
ss_presets.py           Permalink, Presets, Zufalls-Seed
ss_constants.py         Konstanten, Regler-Grenzen, feste Seed-Mengen, Preset-Texte
ss_model.py             Entwurfsmodell und Netze (Kopie aus dem Vorgänger)
ss_formulation.py       LP-Stufen, MIP, Fluss bei festem Entwurf, Aufrunden (Kopie)
ss_scenario.py          Distributionsnetz und Zufallsgenerator (Kopie)
tests/                  Slope Scaling, Auswertung, Presets, Behauptungen, Kopien, App, Regler-Zustand
```

## Lokal starten

```bash
python -m venv venv
venv/Scripts/pip install -r requirements.txt
venv/Scripts/streamlit run app.py
```

## Tests ausführen

```bash
venv/Scripts/pip install -r requirements-dev.txt
venv/Scripts/python -m pytest tests/ -v
```

Die Tests laufen einige Minuten (die Behauptungen rechnen die festen Netze, die App-Tests durchlaufen jedes Preset und jede Kombination der Optionen).

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zur Reihe: [Netzwerkfluss: vom Max-Flow zum Netzdesign](https://sebastianhanisch.net/konzepte-netzwerkfluss.html).
