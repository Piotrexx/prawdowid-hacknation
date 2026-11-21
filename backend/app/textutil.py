import html
import re
import unicodedata
from urllib.parse import urlsplit

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
# Cudzysłowy i myślniki typograficzne ujednolicamy, żeby cytat modelu dało się
# dopasować do źródła mimo różnic w znakach.
_TYPOGRAPHY = str.maketrans(
    {"„": '"', "”": '"', "“": '"', "«": '"', "»": '"', "’": "'", "‘": "'", "–": "-", "—": "-", " ": " "}
)

# Końcówki, pod którymi instytucje rejestrują własne domeny (np. sejm.gov.pl, pravda.org.pl).
_SHARED_SUFFIXES = frozenset({"gov.pl", "org.pl", "com.pl", "net.pl", "edu.pl", "waw.pl"})

STOPWORDS = frozenset(
    """a aby ale albo anie az bardzo bez bo by byc byl byla bylo byly co czy czyli dla do
    gdy gdzie go i ich im ile ja jak jako je jego jej jest jeszcze juz ktora ktore ktory
    ktorzy lub ma maja mi mnie moze mozna na nad nam nas nie nich nim niz o od on ona one
    oni oraz po pod przez przy sa sie sobie ta tak takze tam te tego tej ten to tu tym tylko
    u w we wiec wszystko z za ze zeby""".split()
)


def strip_html(text: str) -> str:
    return collapse_ws(html.unescape(_TAG_RE.sub(" ", text or "")))


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def fold(text: str) -> str:
    """Małe litery bez znaków diakrytycznych (ł nie rozkłada się w NFKD, stąd replace)."""
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Tokeny do BM25. Polski jest silnie fleksyjny, więc długie słowa obcinamy do
    6 znaków – tani substytut stemmera, który łączy np. „szczepionki” i „szczepionek”."""
    out = []
    for tok in _TOKEN_RE.findall(fold(text)):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        out.append(tok if tok.isdigit() else tok[:6])
    return out


def normalize_for_match(text: str) -> str:
    return collapse_ws(text.translate(_TYPOGRAPHY)).lower()


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END_RE.split(text) if s.strip()]


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def jaccard(a: str, b: str) -> float:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def site_domain(url: str) -> str:
    """Domena serwisu bez poddomen, żeby np. cyfrowa.rp.pl i rp.pl liczyć jako jedno źródło."""
    labels = (urlsplit(url).hostname or "").lower().removeprefix("www.").split(".")
    keep = 3 if len(labels) > 2 and ".".join(labels[-2:]) in _SHARED_SUFFIXES else 2
    return ".".join(labels[-keep:])
