"""Interface translation for text the frontend dictionary doesn't cover.

The browser sends short interface strings it couldn't translate; they are translated once with
Amazon Bedrock and cached on disk (backend/i18n_cache/<lang>.json), so each string costs one model
call ever. Before translation, people's names, medicine and brand names, hospital names, and anything
with digits (doses, times, dates, IDs) are swapped for placeholders and restored afterwards, so they
are never translated or transliterated. Without Bedrock the strings come back unchanged (English).
"""
import json
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import rate_limit
from app.core.config import BACKEND_DIR, get_settings
from app.core.database import get_db
from app.core.deps import client_ip
from app.integrations.registry import client
from app.models import HealthcareOrganization, MedicationCatalogue, PrescriptionVersion, User

router = APIRouter(prefix="/api/i18n", tags=["i18n"])

LANG_NAMES = {"hi": "Hindi", "kn": "Kannada", "ta": "Tamil", "te": "Telugu"}
CACHE_DIR = BACKEND_DIR / "i18n_cache"
_lock = threading.Lock()
_cache: dict[str, dict[str, str]] = {}
_names: tuple[float, re.Pattern | None] = (0.0, None)

# digits with an optional unit: doses, times, dates, phone numbers, IDs
NUMERIC = re.compile(r"[\w./:+#%-]*\d[\w./:+#%-]*(?:\s?(?:mg|mcg|ml|mL|IU|g|kg|am|pm|AM|PM|hrs?|mins?))?\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

PROMPT = (
    "You translate the user-interface text of DoseWISE, a medication-management web app in India, into {lang}. "
    "Input: a JSON array of English UI strings. Output: ONLY a JSON array of the same length and order with the "
    "translations, in natural everyday {lang} as used in Indian apps. Some strings contain placeholders: one or more "
    "capital letters between two section signs. Copy every placeholder that appears in a string exactly once into its "
    "translation, unchanged. Never add placeholders to strings that have none. Keep the brand name DoseWISE in Latin "
    "letters. Keep punctuation and symbols."
)


def _name_pattern(db: Session) -> re.Pattern | None:
    """Known proper nouns from the database, longest first; refreshed every 5 minutes."""
    global _names
    if time.monotonic() - _names[0] < 300:
        return _names[1]
    words: set[str] = set()
    for full, pref in db.execute(select(User.full_name, User.preferred_name)):
        words.update(w for w in (full, pref) if w)
        if full:
            words.update(p for p in full.replace("Dr.", "").split() if len(p) > 2 and p[0].isupper())
    for generic, brands in db.execute(select(MedicationCatalogue.generic_name, MedicationCatalogue.brand_names)):
        words.add(generic)
        words.update(brands or [])
    for generic, brand in db.execute(select(PrescriptionVersion.generic_name, PrescriptionVersion.brand_name)):
        words.update(w for w in (generic, brand) if w)
    words.update(n for (n,) in db.execute(select(HealthcareOrganization.name)) if n)
    words.add("DoseWISE")
    words = {w.strip() for w in words if w and len(w.strip()) > 1}
    pat = re.compile("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))) if words else None
    _names = (time.monotonic(), pat)
    return pat


def _mask(text: str, names: re.Pattern | None) -> tuple[str, list[str]]:
    kept: list[str] = []

    def sub(m: re.Match) -> str:
        kept.append(m.group(0))
        return _token(len(kept) - 1)

    for pat in (EMAIL, names, NUMERIC):
        if pat is not None:
            text = pat.sub(sub, text)
    return text, kept


def _token(i: int) -> str:
    """Letters only, so the digit-masking pass can never match inside an earlier placeholder."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return f"§{s}§"


def _unmask(text: str, kept: list[str]) -> str | None:
    for i, v in enumerate(kept):
        token = _token(i)
        if token not in text:
            return None  # the model dropped a protected part: keep English rather than risk it
        text = text.replace(token, v)
    # placeholders the model invented (not in the source) are dropped
    return re.sub(r"\s*§[A-Z]+§\s*", " ", text).strip()


def _file(lang: str) -> Path:
    return CACHE_DIR / f"{lang}.json"


def _load(lang: str) -> dict[str, str]:
    if lang not in _cache:
        try:
            _cache[lang] = json.loads(_file(lang).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache[lang] = {}
    return _cache[lang]


def _save(lang: str) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    tmp = _file(lang).with_suffix(".tmp")
    tmp.write_text(json.dumps(_cache[lang], ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    tmp.replace(_file(lang))


def _bedrock(texts: list[str], lang: str) -> list[str] | None:
    s = get_settings()
    if not s.bedrock_model_id:
        return None
    try:
        resp = client("bedrock-runtime", s.bedrock_region or s.aws_region).converse(
            modelId=s.bedrock_model_id,
            system=[{"text": PROMPT.format(lang=LANG_NAMES[lang])}],
            messages=[{"role": "user", "content": [{"text": json.dumps(texts, ensure_ascii=False)}]}],
            inferenceConfig={"maxTokens": 4000, "temperature": 0},
        )
        out = resp["output"]["message"]["content"][0]["text"]
        arr = json.loads(out[out.find("["): out.rfind("]") + 1])
        if isinstance(arr, list) and len(arr) == len(texts) and all(isinstance(x, str) and x.strip() for x in arr):
            return arr
    except Exception:  # noqa: BLE001 - translation is best-effort; English stays on screen
        return None
    return None


class TranslateIn(BaseModel):
    lang: str = Field(pattern="^(hi|kn|ta|te)$")
    texts: list[str] = Field(max_length=60)


@router.post("/translate")
def translate(body: TranslateIn, request: Request, db: Session = Depends(get_db)):
    texts = [t for t in dict.fromkeys(body.texts) if 0 < len(t) <= 800 and re.search(r"[A-Za-z]", t)]
    with _lock:
        cache = _load(body.lang)
        missing = [t for t in texts if t not in cache]
    if missing:
        rate_limit(f"i18n:{client_ip(request)}", 1000, 300)
        names = _name_pattern(db)
        masked = {t: _mask(t, names) for t in missing}
        # strings that are only names/numbers stay exactly as written
        todo = [t for t in missing if re.search(r"[A-Za-z]", re.sub(r"§[A-Z]+§", "", masked[t][0]))]
        with _lock:
            for t in missing:
                if t not in todo:
                    cache[t] = t
        def run(chunk: list[str], depth: int = 0) -> None:
            result = _bedrock([masked[t][0] for t in chunk], body.lang)
            if result is None and len(chunk) > 1 and depth < 4:
                # the model merged or split items: retry in halves so one odd string can't sink the batch
                half = len(chunk) // 2
                run(chunk[:half], depth + 1)
                run(chunk[half:], depth + 1)
                return
            if result:
                with _lock:
                    for t, out in zip(chunk, result):
                        restored = _unmask(out, masked[t][1])
                        if restored:
                            cache[t] = restored

        for i in range(0, len(todo), 20):
            run(todo[i:i + 20])
        with _lock:
            _save(body.lang)
    return {"lang": body.lang, "translations": {t: cache[t] for t in texts if t in cache and cache[t] != t}}
