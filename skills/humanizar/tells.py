"""Find the tells of AI-generated writing in Spanish or English text, with file:line for each one.

Standard library only, so it runs anywhere:

    python tells.py docs/informe.md                 # one file, full report
    python tells.py docs/ --count                   # counts only (before/after comparison)
    python tells.py texto.md --lang en              # force the language (default: guessed per file)
    python tells.py docs/ --all                     # also list the weak tells that have no company
    python tells.py docs/ --ignore palanca,robusto  # words that are domain terms here, not tells

Three tiers, and the tier decides what the report does with a hit:

- STRONG: one hit is a candidate to rewrite (the contrast "not X, but Y", the one-line closer,
  the em dash, the summary closer, chat residue). Always listed.
- WEAK: a person may do any one of these on purpose (an intensifier, a soft verb, a hedge), so a
  weak hit is listed only when its paragraph holds at least one other hit of any tier
  ("weak tells need company"). `--all` lists them regardless.
- FORMAT: markdown/HTML habits (bold labels, title case, emoji, curly quotes). Counted; bold in
  prose is only counted, never listed, because each one is judged in its sentence by hand.

What decides a rewrite is not the hit but the test applied to it (see SKILL.md): does anyone
actually hold X, does Y add anything X did not say, does the sentence lose anything if the
first half goes, does the contrast close the paragraph.
"""

# ruff: noqa: E501  (the regex tables read better on one line each)
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from html import unescape
from pathlib import Path

# Letters including Spanish accents, for word boundaries that \b gets wrong.
_A = "A-Za-zÁÉÍÓÚÑÜáéíóúñü"
L = rf"(?<![{_A}])"
R = rf"(?![{_A}])"


def w(pat: str) -> str:
    return L + pat + R


STRONG, WEAK, FORMAT = "strong", "weak", "format"

# (key, tier, regex). Order inside a tier is the order of the report.
PATTERNS_ES: list[tuple[str, str, str]] = [
    # Staging instead of stating
    (
        "contraste: no es X, es Y",
        STRONG,
        w(
            r"[Nn]o (es|son|era|eran|está|están|hay|se trata de|tiene|tienen|fue|va de|consiste en)"
            r"[^.;:\n]{1,70}?, (es|son|sino|era|está|están|hay|tiene|tienen|fue|va de|consiste en)" + R
        ),
    ),
    ("contraste: no solo X, sino Y", STRONG, w(r"[Nn]o s[oó]lo[^.\n]{1,80}?" + L + r"sino" + R)),
    (
        "contraste disfrazado (lo que importa no es X / el problema real no es X / más que X, Y / menos X y más Y)",
        STRONG,
        w(
            r"([Ll]o (que importa|que cuenta|relevante|esencial|importante) no es|[Ee]l (problema|punto|reto|riesgo|tema|objetivo|error) (real|de verdad|de fondo) no (es|está)"
            r"|[Ll]a (cuestión|pregunta|clave|dificultad|diferencia) (real|de verdad|de fondo) no (es|está)|[Mm]ás que [^,.\n]{1,40}, |[Mm]enos [^,.\n]{1,30} y más )"
        ),
    ),
    (
        "contraste al cierre: X, no Y.",
        STRONG,
        rf", no (?:{L}(?:el|la|los|las|un|una|unos|unas|de|del|por|en|a|al|con|como|para|que|si){R} )?[{_A}][{_A} ]{{1,40}}[.!]\s*$",
    ),
    ("fragmento de 1 a 3 palabras como frase (cierre dramático)", STRONG, "__FRAGMENT__"),
    (
        "cierre que resume (en resumen, en definitiva, como se ve)",
        STRONG,
        w(
            r"([Ee]n (resumen|definitiva|conclusión|síntesis|última instancia|pocas palabras)|[Cc]omo (se ve|puede verse|hemos visto|vemos)"
            r"|[Pp]ara (resumir|concluir)|[Dd]icho de otro modo|[Ee]n otras palabras|[Tt]odo esto (para decir|significa))"
        ),
    ),
    (
        "arranque hueco (es importante señalar, cabe destacar, conviene recordar)",
        STRONG,
        w(
            r"([Ee]s (importante|fundamental|esencial|crucial|clave|necesario) (señalar|destacar|mencionar|entender|notar|tener en cuenta|recordar|subrayar|que)"
            r"|[Cc]onviene (señalar|destacar|recordar|notar|tener en cuenta|subrayar)|[Cc]abe (destacar|señalar|mencionar|recordar|subrayar)"
            r"|[Hh]ay que tener en cuenta que|[Vv]ale la pena (señalar|destacar|mencionar)|[Nn]ótese que|[Ee]n (un|el) mundo (donde|actual|cada vez)|[Cc]uando se trata de)"
        ),
    ),
    (
        "pregunta retórica con respuesta inmediata",
        STRONG,
        r"¿[^?\n]{2,60}\?\s+(Que|Porque|Sí|No|Ninguna|Ninguno|Nada|Todo|Todos|Depende|Sencillo|Fácil|Simple)"
        + R,
    ),
    (
        "residuo de chat (claro, aquí tienes, espero que sirva, si necesitas)",
        STRONG,
        w(
            r"([Cc]laro, aquí tienes|[Aa]quí tienes|[Ee]spero que (sirva|ayude|te sirva|sea útil)|[Cc]omo modelo de lenguaje|[Ss]i necesitas (algo|más|que)"
            r"|[Nn]o dudes en|[Gg]ran pregunta|[Bb]uena pregunta|[Pp]or supuesto[,!]|[Ee]n resumen, (espero|podemos))"
        ),
    ),
    (
        "marcador sin rellenar ([TODO], [insertar], XX)",
        STRONG,
        r"\[(TODO|TBD|insertar|pendiente|completar|cifra|dato)[^\]]*\]|" + w(r"XX+"),
    ),
    (
        "referencia a la versión anterior o al proceso de escritura",
        STRONG,
        w(
            r"(en la versión anterior|versión anterior de este documento|este documento (ha sido|fue) (actualizado|revisado|generado|redactado)|a diferencia de la versión)"
        ),
    ),
    # Rhythm and inflation, weak on their own
    (
        "intensificador (de verdad, realmente, en el fondo, literalmente)",
        WEAK,
        w(
            r"(de verdad|realmente|en el fondo|literalmente|sencillamente|genuinamente|verdaderamente|auténticamente)"
        ),
    ),
    (
        "frase escindida (es lo que, es donde, lo que hace es)",
        WEAK,
        w(r"((que )?es lo que|es donde|es cuando|lo que hace es|lo que pasa es que|es (ahí|aquí) donde)"),
    ),
    (
        "conector abriendo párrafo (Además, Asimismo, Por otro lado, Es decir, Sin embargo)",
        WEAK,
        r"(?m)^\s*(?:[-*] |\d+\. )?(Además|Asimismo|Adicionalmente|Por otro lado|Por otra parte|Sin embargo|Por lo tanto|Por tanto|De hecho|En consecuencia|Es más|Es decir|Igualmente|Del mismo modo|No obstante|Finalmente|Por último|En primer lugar|En segundo lugar|Dicho esto|En este sentido|En este contexto)"
        + R
        + r"[,:]?",
    ),
    (
        "gerundio de adorno (permitiendo, garantizando, asegurando, mejorando)",
        WEAK,
        w(
            r"(permitiendo|garantizando|asegurando|facilitando|mejorando|reflejando|destacando|fomentando|contribuyendo|reforzando|logrando|consiguiendo|maximizando|minimizando|optimizando|impulsando|potenciando)"
        ),
    ),
    (
        "adverbio en -mente de intensidad",
        WEAK,
        w(
            r"(especialmente|particularmente|significativamente|considerablemente|notablemente|claramente|efectivamente|simplemente|precisamente|fundamentalmente|básicamente|esencialmente|extremadamente|altamente|sumamente|profundamente|absolutamente|totalmente|completamente)"
        ),
    ),
    (
        "verbo blando (permite, proporciona, facilita, ofrece, brinda, cuenta con)",
        WEAK,
        w(
            r"(permite[n]?|proporciona[n]?|facilita[n]?|ofrece[n]?|brinda[n]?|cuenta[n]? con|dispone[n]? de|juega[n]? un papel|desempeña[n]? un papel|posibilita[n]?)"
        ),
    ),
    (
        "cópula evitada (actúa como, sirve como, funciona como, representa, constituye)",
        WEAK,
        w(
            r"(actúa[n]? como|sirve[n]? como|funciona[n]? como|representa[n]?|constituye[n]?|se erige[n]?|se configura[n]? como|se presenta[n]? como)"
        ),
    ),
    (
        "hedging (en muchos casos, hasta cierto punto, en general, potencialmente, probablemente)",
        WEAK,
        w(
            r"([Ee]n muchos casos|[Hh]asta cierto punto|[Ee]n cierto modo|[Ee]n cierta medida|[Ee]n general|potencialmente|posiblemente|probablemente|[Ee]n principio|[Ee]n teoría|podría (ser|decirse|considerarse)|[Ee]n la mayoría de los casos)"
        ),
    ),
    (
        "léxico inflado (crucial, fundamental, holístico, sinergia, potenciar, fomentar, garantizar, hoja de ruta, en aras de)",
        WEAK,
        w(
            r"(crucial(es)?|fundamental(es)?|esencial(es)?|holístic[oa]s?|sinergias?|paradigmas?|ecosistemas?|poner en valor|hoja de ruta|de cara a|en aras de|en el marco de"
            r"|potencia[rn]?|fomenta[rn]?|impulsa[rn]?|aborda[rn]?|garantiza[rn]?|integral(es)?|sin fisuras|vibrante|transformador[a]?s?|revolucionar|desafíos?|retos?|innovador[a]?s?|sólid[oa]s?|robust[oa]s?)"
        ),
    ),
    (
        "calco del inglés (corrida, hacer sentido, al final del día, asegúrate de, en términos de, básicamente)",
        WEAK,
        w(
            r"(corridas?|hacer sentido|hace sentido|al final del día|asegúrate de|en términos de|cuando se trata de|es importante de mencionar|de forma eficiente|customizar|setear|aplicar cambios|a día de hoy|en tiempo real)"
        ),
    ),
    (
        "significación inflada (un hito, un antes y un después, cambio radical, punto de inflexión)",
        WEAK,
        w(
            r"(un hito|un antes y un después|cambio (fundamental|radical|profundo)|punto de inflexión|salto cualitativo|clave para el éxito|marca (un|una) (diferencia|inflexión))"
        ),
    ),
    (
        "autoridad sin nombre (los expertos, la literatura, es sabido, estudios muestran)",
        WEAK,
        w(
            r"([Ll]os expertos|[Ll]a literatura (dice|muestra|indica|señala|sugiere)|[Ee]s sabido|[Ee]studios (muestran|demuestran|indican|sugieren)|[Ee]stá demostrado|[Aa]mpliamente (aceptado|reconocido|documentado)|[Cc]omo es bien sabido)"
        ),
    ),
    (
        "metáfora genérica (brújula, piedra angular, columna vertebral, viaje, un mar de)",
        WEAK,
        w(
            r"(brújula|bien engrasad[ao]|el viaje (de|hacia)|el camino hacia|piedra angular|columna vertebral|caja de herramientas|abanico de|arsenal|motor del cambio|un mar de|hoja en blanco)"
        ),
    ),
    ("tríada (A, B y C)", WEAK, rf"{L}[{_A}]+, [{_A}]+ y [{_A}]+{R}"),
    (
        "de forma / de manera + adjetivo",
        WEAK,
        w(
            r"[Dd]e (forma|manera) (eficiente|efectiva|adecuada|correcta|óptima|clara|significativa|consistente|coherente|robusta|automática|sistemática|transparente|precisa|natural|sencilla|fluida)"
        ),
    ),
    # Format
    ("negrita de etiqueta en viñeta (- **X:**)", FORMAT, r"(?m)^\s*[-*] \*\*[^*\n]{1,60}\*\*[:.]"),
    ("negrita en prosa", FORMAT, r"\*\*[^*\n]{2,80}\*\*"),
    (
        "título con mayúscula en cada palabra",
        FORMAT,
        rf"(?m)^#{{1,6}} (?:[A-ZÁÉÍÓÚÑ][{_A}]+ ){{2,}}[A-ZÁÉÍÓÚÑ][{_A}]+\s*$",
    ),
    ("emoji, flecha o símbolo en prosa", FORMAT, r"[←-⇿☀-➿\U0001F300-\U0001FAFF]|✅|❌|⚠️|→|⇒"),
    ("comillas curvas", FORMAT, r"[“”‘’]"),
    ("raya (—)", STRONG, "—"),
]

PATTERNS_EN: list[tuple[str, str, str]] = [
    (
        "contrast: not just/only X but Y",
        STRONG,
        r"\b[Nn]ot (just|only|merely|simply|about)\b[^.\n]{1,80}?\bbut\b",
    ),
    (
        "contrast: it's not X, it's Y",
        STRONG,
        r"\b(is|are|was|were)n'?t\b[^.\n]{1,60}?, (it's|it is|they're|they are|but|rather)\b|\b[Ii]t'?s not\b[^.\n]{1,60}?, it'?s\b|\b[Nn]o [a-z]+, no [a-z]+, just\b",
    ),
    (
        "contrast in disguise (the real X isn't, more than a, less about X and more about Y)",
        STRONG,
        r"\b([Tt]he real (issue|question|problem|point|value|win) (isn't|is not|was never)|[Tt]his (isn't|is not) (about|just|merely)|[Mm]ore than (a|just) [a-z]+, |[Ll]ess about [^,.\n]{1,30} and more about|[Rr]ead that again|[Tt]hat'?s the real)\b",
    ),
    (
        "contrast at the close: X, not Y.",
        STRONG,
        r", not (?:(?:the|a|an|of|in|by|for|to|as|with|on|just|merely) )?[A-Za-z][A-Za-z '\-]{1,40}[.!]\s*$",
    ),
    ("one- to three-word sentence (dramatic closer)", STRONG, "__FRAGMENT__"),
    (
        "summary closer (in summary, in conclusion, overall, ultimately, at the end of the day)",
        STRONG,
        r"\b(In summary|In conclusion|To sum up|To summarize|Overall|Ultimately|At the end of the day|In short|All in all|In essence|At its core|The bottom line)\b",
    ),
    (
        "filler opener (it's important to note, it is worth noting, notably, let's dive in)",
        STRONG,
        r"\b(It'?s (important|worth|essential|crucial|vital) to (note|mention|highlight|understand|remember|recognize)|It is (important|worth|essential|crucial|vital) to (note|mention|highlight|understand|remember|recognize)|Notably|Importantly|Crucially|Interestingly|Note that|Keep in mind|Bear in mind|Let'?s (dive|delve|explore|unpack)|Here'?s (what|the thing|where)|In today'?s (world|landscape|fast-paced)|When it comes to)\b",
    ),
    (
        "rhetorical question with immediate answer",
        STRONG,
        r"\?\s+(Because|Yes|No|Nothing|Everything|Simple|Easy|It depends|The answer|Exactly)\b|\b(The catch|The twist|The problem|The key|The truth)\?",
    ),
    (
        "chatbot residue (I hope this helps, let me know, great question, of course)",
        STRONG,
        r"\b(I hope this helps|Let me know if|Great question|Of course!|Feel free to|Happy to help|As an AI|As a language model|Certainly!|Absolutely!)\b",
    ),
    (
        "placeholder ([TODO], [insert], XX, lorem ipsum)",
        STRONG,
        r"\[(TODO|TBD|insert|placeholder|add|your)[^\]]*\]|\bXX+\b|lorem ipsum",
    ),
    (
        "knowledge-cutoff disclaimer",
        STRONG,
        r"\b(as of (my|the) (last|latest) (update|training)|my (knowledge|training) (cutoff|data)|I (do not|don't) have access to)\b",
    ),
    (
        "intensifier (actually, truly, really, genuinely, deeply)",
        WEAK,
        r"\b(actually|truly|really|genuinely|deeply|fundamentally|profoundly|incredibly|remarkably)\b",
    ),
    (
        "cleft (what really matters is, the thing is, this is where)",
        WEAK,
        r"\b([Ww]hat (really|truly|actually) matters|[Tt]he (thing|point|key) is|[Tt]his is where|[Tt]hat'?s where|[Ii]t'?s here that)\b",
    ),
    (
        "connector opening a paragraph (Additionally, Furthermore, Moreover, However, Therefore)",
        WEAK,
        r"(?m)^\s*(?:[-*] |\d+\. )?(Additionally|Furthermore|Moreover|However|Therefore|Thus|Consequently|Hence|Finally|Lastly|Firstly|Secondly|That said|In this context|In this sense)\b,?",
    ),
    (
        "-ing rider (highlighting, underscoring, ensuring, enabling, reflecting)",
        WEAK,
        r",\s(highlighting|underscoring|ensuring|enabling|allowing|reflecting|emphasizing|fostering|contributing to|resulting in|leading to|making it|providing|offering|helping|showcasing|demonstrating)\b",
    ),
    (
        "stacked qualifier (may potentially, could arguably, to some extent, in some cases)",
        WEAK,
        r"\b(may potentially|could potentially|might arguably|could arguably|to some extent|in some cases|generally speaking|in many cases|it could be argued|arguably|potentially)\b",
    ),
    (
        "soft verb (serves as, stands as, acts as, functions as, represents, boasts, features, offers)",
        WEAK,
        r"\b(serves? as|stands? as|acts? as|functions? as|represents?|constitutes?|boasts?|features?|offers?|provides?|enables?|empowers?|facilitates?)\b",
    ),
    (
        "AI vocabulary (delve, robust, leverage, crucial, pivotal, landscape, seamless, tapestry, testament, vibrant, holistic, comprehensive, streamline, unlock, journey, navigate, foster, meticulous, intricate, interplay, actionable, insights, ecosystem, paradigm, synergy, harness, underscore, showcase, enhance)",
        WEAK,
        r"\b(delve[sd]?|delving|robust(ly|ness)?|leverag(e[sd]?|ing)|crucial(ly)?|pivotal|landscape|seamless(ly)?|tapestry|testament|vibrant|holistic(ally)?|comprehensive(ly)?|cutting-edge|state-of-the-art|streamlin(e[sd]?|ing)|unlock(s|ed|ing)?|journey|navigat(e[sd]?|ing)|foster(s|ed|ing)?|bolster(s|ed|ing)?|meticulous(ly)?|intricate|intricacies|interplay|garner(s|ed)?|actionable|insights?|ecosystem|paradigm|synerg(y|ies)|game-?changer|harness(es|ed|ing)?|underscor(e[sd]?|ing)|showcas(e[sd]?|ing)|enhanc(e[sd]?|ing|ement)|elevat(e[sd]?|ing)|realm|multifaceted|nuanced|transformative|groundbreaking|innovative|powerful|utiliz(e[sd]?|ing)|embark(s|ed|ing)?)\b",
    ),
    (
        "key as adjective (key role, key factor, key takeaway)",
        WEAK,
        r"\bkey (role|factor|factors|driver|drivers|component|components|element|elements|aspect|aspects|point|points|takeaway|takeaways|insight|insights|question|questions|decision|decisions|metric|metrics|step|steps|area|areas)\b",
    ),
    (
        "inflated significance (game-changer, transformative, pivotal moment, a testament to, paves the way)",
        WEAK,
        r"\b(game-?changer|transformative|pivotal moment|a testament to|paves? the way|marks? a (shift|turning point|milestone)|sets? the stage|lasting (impact|legacy)|significant(ly)? (impact|improvement|change)|cannot be overstated)\b",
    ),
    (
        "vague authority (experts say, studies show, research suggests, best practices, widely recognized)",
        WEAK,
        r"\b(experts? (say|agree|argue|suggest|recommend)|studies (show|suggest|indicate)|research (shows|suggests|indicates)|industry (standard|best practice|leaders)|best practices?|widely (recognized|accepted|used|regarded)|it is (well )?known)\b",
    ),
    ("rule of three (A, B, and C)", WEAK, r"\b[A-Za-z]+, [A-Za-z]+,? and [A-Za-z]+\b"),
    (
        "bold label in a list (- **X:**)",
        FORMAT,
        r"(?m)^\s*[-*] \*\*[^*\n]{1,60}\*\*[:.]|<li>\s*<(?:strong|b)>[^<]{1,60}</(?:strong|b)>\s*[:.]",
    ),
    ("bold in prose", FORMAT, r"\*\*[^*\n]{2,80}\*\*|<(?:strong|b)>[^<]{2,80}</(?:strong|b)>"),
    ("Title Case heading", FORMAT, r"(?m)^#{1,6} (?:[A-Z][a-z]+ ){2,}[A-Z][a-z]+\s*$"),
    ("emoji or arrow in prose", FORMAT, r"[☀-➿\U0001F300-\U0001FAFF]|✅|❌|→|⇒"),
    ("curly quotes", FORMAT, r"[“”‘’]"),
    ("em dash (—)", STRONG, "—"),
]

# A one- or two-word sentence anywhere after another sentence ("Sobreajuste.", "No es ruido."
# is three and only counts when it closes the paragraph), or a three-word one closing it.
FRAGMENT_ES = re.compile(
    rf"[.!?] ((?:No |Sin |Ni |Y |Nada |Nunca |Siempre )?[{_A}¡¿][{_A}]*(?: [{_A}]+)?)[.!](?= |$)"
    rf"|[.!?:;] ((?:No |Sin |Ni |Y |Nada |Nunca |Siempre )?[{_A}¡¿][{_A}]*(?: [{_A}]+){{0,2}})[.!]\s*$"
)
FRAGMENT_EN = re.compile(
    r"[.!?] ((?:No |Not |And |Just |Never |Always )?[A-Za-z][A-Za-z']*(?: [A-Za-z']+)?)[.!](?= |$)"
    r"|[.!?:;] ((?:No |Not |And |Just |Never |Always )?[A-Za-z][A-Za-z']*(?: [A-Za-z']+){0,2})[.!]\s*$"
)

ES_MARKERS = re.compile(
    r"\b(que|de|la|el|los|las|con|para|una|por|es|se|del|como|más|pero|sin|sobre)\b", re.I
)
EN_MARKERS = re.compile(r"\b(the|and|of|to|is|with|for|that|this|are|from|which|not|but|on|as|it|at)\b", re.I)

SKIP_LINE = re.compile(r"^\s*(```|~~~|\||#|<|\{|\}|\[|`)")  # code, tables, headings, html, yaml


@dataclass
class Hit:
    key: str
    tier: str
    line: int
    text: str
    match: str


def guess_lang(text: str) -> str:
    es = len(ES_MARKERS.findall(text))
    en = len(EN_MARKERS.findall(text))
    return "en" if en > es * 1.3 else "es"


def html_to_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"</(p|li|h[1-6]|div|tr|blockquote|section|article|dd|dt)>", "\n\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    return unescape(raw)


def paragraphs(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first_line, last_line, joined_text) for each prose paragraph; bullets split on their own."""
    out: list[tuple[int, int, str]] = []
    buf: list[str] = []
    start = 0
    in_code = False

    def flush(end: int) -> None:
        nonlocal buf
        if buf:
            out.append((start, end, " ".join(s.strip() for s in buf)))
        buf = []

    for i, line in enumerate(lines, 1):
        if line.strip().startswith(("```", "~~~")):
            in_code = not in_code
            flush(i - 1)
            continue
        if in_code:
            continue
        stripped = line.strip()
        is_bullet = bool(re.match(r"^([-*+]|\d+[.)])\s", stripped))
        if not stripped or SKIP_LINE.match(line) and not is_bullet:
            flush(i - 1)
            continue
        if is_bullet:
            flush(i - 1)
            start = i
            buf = [line]
            continue
        if not buf:
            start = i
        buf.append(line)
    flush(len(lines))
    return out


def scan(text: str, lang: str, ignore: set[str]) -> tuple[list[Hit], Counter]:
    patterns = PATTERNS_EN if lang == "en" else PATTERNS_ES
    fragment = FRAGMENT_EN if lang == "en" else FRAGMENT_ES
    lines = text.splitlines()
    paras = paragraphs(lines)
    hits: list[Hit] = []
    counts: Counter = Counter()

    # Prose patterns run paragraph by paragraph, so a hit never straddles a heading or a table.
    for key, tier, pat in patterns:
        if tier == FORMAT:
            rx = re.compile(pat)
            for m in rx.finditer(text):
                counts[key] += 1
                if key not in ("negrita en prosa", "bold in prose"):
                    ln = text.count("\n", 0, m.start()) + 1
                    hits.append(Hit(key, tier, ln, lines[ln - 1].strip(), m.group(0)))
            continue
        if pat == "__FRAGMENT__":
            for _first, last, ptext in paras:
                seen: set[str] = set()
                for m in fragment.finditer(ptext):
                    frag = m.group(1) or m.group(2)
                    if frag in seen or re.search(r"`|\d", frag):
                        continue
                    seen.add(frag)
                    counts[key] += 1
                    hits.append(
                        Hit(key, tier, last, ptext[max(0, m.start() - 110) : m.end() + 40], frag + ".")
                    )
            continue
        rx = re.compile(pat, re.M)
        for first, last, ptext in paras:
            for m in rx.finditer(ptext):
                found = m.group(0)
                if any(ig and ig.lower() in found.lower() for ig in ignore):
                    continue
                # Line of the hit: count how many of the paragraph's lines precede the offset.
                consumed = 0
                ln = first
                for k, line in enumerate(lines[first - 1 : last]):
                    consumed += len(line.strip()) + 1
                    if consumed > m.start():
                        ln = first + k
                        break
                counts[key] += 1
                hits.append(
                    Hit(key, tier, ln, lines[ln - 1].strip() if ln - 1 < len(lines) else ptext, found)
                )
    return hits, counts


def with_company(hits: list[Hit], text: str) -> list[Hit]:
    """Weak hits survive only when their paragraph holds another hit of any tier."""
    lines = text.splitlines()
    paras = paragraphs(lines)
    span_of: dict[int, tuple[int, int]] = {}
    for first, last, _ in paras:
        for ln in range(first, last + 1):
            span_of[ln] = (first, last)
    per_para: Counter = Counter(span_of.get(h.line, (h.line, h.line)) for h in hits if h.tier != FORMAT)
    return [h for h in hits if h.tier != WEAK or per_para[span_of.get(h.line, (h.line, h.line))] >= 2]


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files += sorted(
                q
                for q in path.rglob("*")
                if q.suffix.lower() in (".md", ".html", ".txt")
                and "archivo" not in q.parts
                and "node_modules" not in q.parts
            )
        elif path.exists():
            files.append(path)
        else:
            print(f"no existe: {p}", file=sys.stderr)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--lang", choices=["es", "en", "auto"], default="auto")
    ap.add_argument("--count", action="store_true", help="counts only, no candidate lines")
    ap.add_argument("--all", action="store_true", help="list weak hits even without company")
    ap.add_argument("--ignore", default="", help="comma-separated words that are domain terms, not tells")
    ap.add_argument("--json", action="store_true", help="counts as JSON, one object per file")
    args = ap.parse_args()
    ignore = {s.strip() for s in args.ignore.split(",") if s.strip()}

    total: Counter = Counter()
    report: dict[str, dict] = {}
    for f in collect(args.paths):
        raw = f.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(raw) if f.suffix.lower() == ".html" else raw
        lang = args.lang if args.lang != "auto" else guess_lang(text)
        hits, counts = scan(text, lang, ignore)
        if f.suffix.lower() == ".html":
            # Bold is only visible in the raw markup.
            key = "bold in prose" if lang == "en" else "negrita en prosa"
            counts[key] = len(re.findall(r"<(?:strong|b)>[^<]{2,80}</(?:strong|b)>", raw))
        total.update(counts)
        report[str(f)] = {"lang": lang, "counts": dict(counts)}
        if args.json:
            continue
        strong = sum(v for k, v in counts.items() if _tier(k, lang) == STRONG)
        weak = sum(v for k, v in counts.items() if _tier(k, lang) == WEAK)
        fmt = sum(v for k, v in counts.items() if _tier(k, lang) == FORMAT)
        print(f"\n== {f} ({lang})  fuertes={strong}  débiles={weak}  formato={fmt}")
        for key, n in sorted(counts.items(), key=lambda kv: (-_rank(_tier(kv[0], lang)), -kv[1])):
            print(f"   {n:4d}  [{_tier(key, lang)[0]}] {key}")
        if args.count:
            continue
        shown = hits if args.all else with_company(hits, text)
        listed = [
            h for h in shown if not (h.tier == FORMAT and h.key in ("negrita en prosa", "bold in prose"))
        ]
        if listed:
            print("   -- candidatos (fichero:línea, patrón, lo que ha saltado, la línea):")
        for h in sorted(listed, key=lambda h: (-_rank(h.tier), h.line)):
            print(f"   {f}:{h.line}  [{h.tier[0]}] {h.key.split(' (')[0]}  <{h.match.strip()}>")
            print(f"       {h.text[:200]}")
        hidden = len(hits) - len(shown)
        if hidden and not args.all:
            print(f"   ({hidden} débiles sin compañía, ocultos; --all los enseña)")

    if args.json:
        print(json.dumps({"files": report, "total": dict(total)}, ensure_ascii=False, indent=1))
    elif len(report) > 1:
        print("\n== TOTAL")
        for key, n in sorted(total.items(), key=lambda kv: -kv[1]):
            print(f"   {n:4d}  {key}")
    return 0


def _tier(key: str, lang: str) -> str:
    for k, tier, _ in PATTERNS_EN if lang == "en" else PATTERNS_ES:
        if k == key:
            return tier
    return FORMAT


def _rank(tier: str) -> int:
    return {STRONG: 2, WEAK: 1, FORMAT: 0}[tier]


if __name__ == "__main__":
    sys.exit(main())
