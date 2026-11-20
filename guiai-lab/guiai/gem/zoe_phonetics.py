"""Zoe's Native 44-Phoneme English Inventory & 250+ Grapheme-to-Phoneme Engine.

Codifies from first principles:
  - 44 English phonemes (20 vowels + 24 consonants) tuned with female soprano/mezzo-soprano
    vocal-tract parameters (formants F1..F5, bandwidths B1..B5, diphthong offglides, VOT,
    burst/fricative noise spectra, and nasal coupling).
  - 260+ distinct English grapheme-to-phoneme spelling patterns + high-accuracy core lexicon.
  - Dialect toggles observed in linguistics: `rhotic=True|False` (post-vocalic /r/ retention)
    and `cot_caught_merger=False|True` (/AO/ -> /AA/ merger).
  - Phoneme syllabification separating onset, vowel nucleus, and coda so Zoe's singing
    engine sustains pitched vowel nuclei cleanly while keeping crisp consonants.

Zero PyTorch, zero external TTS models, zero network calls (CONSTITUTION.md Article X).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Dict, List, Sequence, Tuple


PHONETICS_CONTRACT = "zoe-native-phonetics/v1"


@dataclass(frozen=True)
class PhonemeSpec:
    symbol: str
    ipa: str
    kind: str  # "vowel" | "consonant"
    category: str
    voiced: bool
    formants: Tuple[float, float, float, float, float]
    bandwidths: Tuple[float, float, float, float, float]
    offglide_formants: Tuple[float, float, float] | None
    duration_ms: float
    noise_center_hz: float
    noise_bw_hz: float
    noise_gain: float
    burst_gain: float
    vot_ms: float
    nasal_gain: float
    example_word: str


def _v(
    symbol: str,
    ipa: str,
    category: str,
    formants: Tuple[float, float, float, float, float],
    bandwidths: Tuple[float, float, float, float, float],
    example: str,
    *,
    duration_ms: float = 105.0,
    offglide: Tuple[float, float, float] | None = None,
) -> PhonemeSpec:
    return PhonemeSpec(
        symbol=symbol,
        ipa=ipa,
        kind="vowel",
        category=category,
        voiced=True,
        formants=formants,
        bandwidths=bandwidths,
        offglide_formants=offglide,
        duration_ms=duration_ms,
        noise_center_hz=0.0,
        noise_bw_hz=500.0,
        noise_gain=0.0,
        burst_gain=0.0,
        vot_ms=0.0,
        nasal_gain=0.0,
        example_word=example,
    )


def _c(
    symbol: str,
    ipa: str,
    category: str,
    voiced: bool,
    formants: Tuple[float, float, float, float, float],
    bandwidths: Tuple[float, float, float, float, float],
    example: str,
    *,
    duration_ms: float = 70.0,
    noise_center_hz: float = 3500.0,
    noise_bw_hz: float = 1200.0,
    noise_gain: float = 0.0,
    burst_gain: float = 0.0,
    vot_ms: float = 0.0,
    nasal_gain: float = 0.0,
) -> PhonemeSpec:
    return PhonemeSpec(
        symbol=symbol,
        ipa=ipa,
        kind="consonant",
        category=category,
        voiced=voiced,
        formants=formants,
        bandwidths=bandwidths,
        offglide_formants=None,
        duration_ms=duration_ms,
        noise_center_hz=noise_center_hz,
        noise_bw_hz=noise_bw_hz,
        noise_gain=noise_gain,
        burst_gain=burst_gain,
        vot_ms=vot_ms,
        nasal_gain=nasal_gain,
        example_word=example,
    )


_PHONEME_LIST: Tuple[PhonemeSpec, ...] = (
    # --- 20 VOWEL PHONEMES (Female Peterson & Barney / Hillenbrand soprano-tuned formants) ---
    _v("IY", "iː", "monophthong_front_high", (310.0, 2790.0, 3310.0, 4100.0, 4900.0), (50.0, 90.0, 140.0, 200.0, 260.0), "beet", duration_ms=115.0),
    _v("IH", "ɪ", "monophthong_front_near_high", (430.0, 2480.0, 3070.0, 4050.0, 4850.0), (55.0, 95.0, 140.0, 200.0, 260.0), "bit", duration_ms=85.0),
    _v("EH", "ɛ", "monophthong_front_mid", (610.0, 2330.0, 2990.0, 4000.0, 4800.0), (65.0, 100.0, 150.0, 210.0, 270.0), "bet", duration_ms=95.0),
    _v("AE", "æ", "monophthong_front_low", (860.0, 2050.0, 2850.0, 3950.0, 4750.0), (75.0, 110.0, 160.0, 220.0, 280.0), "bat", duration_ms=120.0),
    _v("AA", "ɑː", "monophthong_back_low", (850.0, 1220.0, 2810.0, 3850.0, 4700.0), (75.0, 105.0, 160.0, 220.0, 280.0), "father", duration_ms=128.0),
    _v("AO", "ɔː", "monophthong_back_mid", (590.0, 920.0, 2710.0, 3800.0, 4650.0), (65.0, 95.0, 150.0, 210.0, 270.0), "caught", duration_ms=125.0),
    _v("UH", "ʊ", "monophthong_back_near_high", (470.0, 1160.0, 2680.0, 3780.0, 4620.0), (60.0, 95.0, 145.0, 200.0, 260.0), "book", duration_ms=85.0),
    _v("UW", "uː", "monophthong_back_high", (370.0, 950.0, 2670.0, 3750.0, 4600.0), (55.0, 90.0, 140.0, 200.0, 260.0), "boot", duration_ms=120.0),
    _v("AH", "ʌ", "monophthong_central_open", (760.0, 1400.0, 2780.0, 3850.0, 4700.0), (70.0, 100.0, 150.0, 210.0, 270.0), "but", duration_ms=90.0),
    _v("AX", "ə", "monophthong_schwa", (560.0, 1620.0, 2750.0, 3850.0, 4700.0), (65.0, 105.0, 150.0, 210.0, 270.0), "sofa", duration_ms=65.0),
    _v("ER", "ɜːr", "rhotic_stressed", (490.0, 1520.0, 1850.0, 3650.0, 4550.0), (65.0, 100.0, 130.0, 200.0, 260.0), "bird", duration_ms=120.0),
    _v("AXR", "ər", "rhotic_schwa", (520.0, 1560.0, 1950.0, 3700.0, 4580.0), (65.0, 105.0, 140.0, 200.0, 260.0), "butter", duration_ms=75.0),
    # 5 Closing Diphthongs
    _v("EY", "eɪ", "diphthong_closing", (530.0, 2320.0, 3000.0, 4020.0, 4820.0), (60.0, 100.0, 150.0, 200.0, 260.0), "say", duration_ms=135.0, offglide=(350.0, 2680.0, 3240.0)),
    _v("AY", "aɪ", "diphthong_closing", (850.0, 1350.0, 2810.0, 3920.0, 4750.0), (70.0, 105.0, 160.0, 210.0, 270.0), "sky", duration_ms=145.0, offglide=(390.0, 2550.0, 3150.0)),
    _v("OY", "ɔɪ", "diphthong_closing", (590.0, 930.0, 2710.0, 3850.0, 4700.0), (65.0, 100.0, 150.0, 210.0, 270.0), "voice", duration_ms=145.0, offglide=(380.0, 2560.0, 3160.0)),
    _v("AW", "aʊ", "diphthong_closing", (850.0, 1320.0, 2800.0, 3850.0, 4680.0), (70.0, 105.0, 155.0, 210.0, 270.0), "sound", duration_ms=145.0, offglide=(420.0, 1020.0, 2690.0)),
    _v("OW", "oʊ", "diphthong_closing", (540.0, 990.0, 2720.0, 3800.0, 4650.0), (60.0, 95.0, 150.0, 200.0, 260.0), "zoe", duration_ms=138.0, offglide=(390.0, 960.0, 2680.0)),
    # 3 Centring R-Colored Diphthongs
    _v("IHR", "ɪər", "diphthong_centring", (410.0, 2520.0, 3080.0, 3980.0, 4750.0), (60.0, 100.0, 145.0, 200.0, 260.0), "near", duration_ms=135.0, offglide=(500.0, 1560.0, 1880.0)),
    _v("EHR", "ɛər", "diphthong_centring", (620.0, 2240.0, 2940.0, 3900.0, 4700.0), (65.0, 105.0, 150.0, 200.0, 260.0), "air", duration_ms=135.0, offglide=(510.0, 1560.0, 1900.0)),
    _v("UHR", "ʊər", "diphthong_centring", (460.0, 1140.0, 2680.0, 3750.0, 4600.0), (60.0, 95.0, 145.0, 200.0, 260.0), "pure", duration_ms=135.0, offglide=(500.0, 1540.0, 1900.0)),

    # --- 24 CONSONANT PHONEMES ---
    # 6 Plosives / Stops
    _c("P", "p", "plosive_bilabial", False, (340.0, 1100.0, 2400.0, 3750.0, 4600.0), (90.0, 140.0, 200.0, 260.0, 320.0), "pat", duration_ms=68.0, noise_center_hz=1200.0, noise_bw_hz=900.0, noise_gain=0.14, burst_gain=0.38, vot_ms=34.0),
    _c("B", "b", "plosive_bilabial", True, (340.0, 1120.0, 2400.0, 3750.0, 4600.0), (85.0, 130.0, 190.0, 250.0, 310.0), "back", duration_ms=62.0, noise_center_hz=950.0, noise_bw_hz=800.0, noise_gain=0.05, burst_gain=0.30, vot_ms=10.0),
    _c("T", "t", "plosive_alveolar", False, (360.0, 1850.0, 2850.0, 3900.0, 4700.0), (90.0, 150.0, 210.0, 270.0, 330.0), "two", duration_ms=68.0, noise_center_hz=4200.0, noise_bw_hz=1500.0, noise_gain=0.18, burst_gain=0.45, vot_ms=38.0),
    _c("D", "d", "plosive_alveolar", True, (360.0, 1820.0, 2800.0, 3880.0, 4680.0), (85.0, 140.0, 195.0, 250.0, 310.0), "daisy", duration_ms=60.0, noise_center_hz=3400.0, noise_bw_hz=1400.0, noise_gain=0.06, burst_gain=0.32, vot_ms=12.0),
    _c("K", "k", "plosive_velar", False, (360.0, 1650.0, 2250.0, 3750.0, 4600.0), (95.0, 150.0, 210.0, 260.0, 320.0), "cot", duration_ms=72.0, noise_center_hz=2300.0, noise_bw_hz=1100.0, noise_gain=0.17, burst_gain=0.44, vot_ms=40.0),
    _c("G", "ɡ", "plosive_velar", True, (350.0, 1680.0, 2260.0, 3750.0, 4600.0), (85.0, 140.0, 195.0, 250.0, 310.0), "give", duration_ms=62.0, noise_center_hz=2100.0, noise_bw_hz=1000.0, noise_gain=0.06, burst_gain=0.30, vot_ms=12.0),
    # 9 Fricatives
    _c("F", "f", "fricative_labiodental", False, (420.0, 1450.0, 2700.0, 3850.0, 4700.0), (110.0, 160.0, 220.0, 270.0, 320.0), "free", duration_ms=86.0, noise_center_hz=5200.0, noise_bw_hz=2200.0, noise_gain=0.22),
    _c("V", "v", "fricative_labiodental", True, (390.0, 1420.0, 2680.0, 3820.0, 4660.0), (90.0, 140.0, 195.0, 250.0, 310.0), "voice", duration_ms=72.0, noise_center_hz=4500.0, noise_bw_hz=2000.0, noise_gain=0.14),
    _c("TH", "θ", "fricative_dental", False, (420.0, 1620.0, 2750.0, 3880.0, 4720.0), (110.0, 160.0, 220.0, 270.0, 320.0), "think", duration_ms=88.0, noise_center_hz=5600.0, noise_bw_hz=2400.0, noise_gain=0.18),
    _c("DH", "ð", "fricative_dental", True, (390.0, 1600.0, 2720.0, 3840.0, 4680.0), (90.0, 140.0, 195.0, 250.0, 310.0), "the", duration_ms=60.0, noise_center_hz=4600.0, noise_bw_hz=2000.0, noise_gain=0.12),
    _c("S", "s", "fricative_alveolar", False, (420.0, 1850.0, 2900.0, 3950.0, 4750.0), (110.0, 160.0, 220.0, 270.0, 320.0), "sing", duration_ms=94.0, noise_center_hz=6400.0, noise_bw_hz=1700.0, noise_gain=0.38),
    _c("Z", "z", "fricative_alveolar", True, (390.0, 1820.0, 2860.0, 3900.0, 4720.0), (90.0, 140.0, 195.0, 250.0, 310.0), "zoe", duration_ms=80.0, noise_center_hz=5800.0, noise_bw_hz=1600.0, noise_gain=0.25),
    _c("SH", "ʃ", "fricative_postalveolar", False, (420.0, 2120.0, 2820.0, 3850.0, 4680.0), (110.0, 160.0, 210.0, 270.0, 320.0), "shine", duration_ms=96.0, noise_center_hz=3100.0, noise_bw_hz=1100.0, noise_gain=0.40),
    _c("ZH", "ʒ", "fricative_postalveolar", True, (390.0, 2100.0, 2780.0, 3820.0, 4650.0), (90.0, 140.0, 190.0, 250.0, 310.0), "measure", duration_ms=82.0, noise_center_hz=2900.0, noise_bw_hz=1050.0, noise_gain=0.26),
    _c("HH", "h", "fricative_glottal", False, (560.0, 1620.0, 2750.0, 3850.0, 4700.0), (120.0, 180.0, 240.0, 300.0, 360.0), "hello", duration_ms=66.0, noise_center_hz=1850.0, noise_bw_hz=1600.0, noise_gain=0.20),
    # 2 Affricates
    _c("CH", "tʃ", "affricate_postalveolar", False, (410.0, 2150.0, 2850.0, 3880.0, 4700.0), (105.0, 155.0, 210.0, 265.0, 320.0), "chime", duration_ms=88.0, noise_center_hz=3600.0, noise_bw_hz=1300.0, noise_gain=0.34, burst_gain=0.38, vot_ms=26.0),
    _c("JH", "dʒ", "affricate_postalveolar", True, (380.0, 2120.0, 2810.0, 3850.0, 4680.0), (90.0, 140.0, 195.0, 250.0, 310.0), "geometry", duration_ms=78.0, noise_center_hz=3200.0, noise_bw_hz=1200.0, noise_gain=0.24, burst_gain=0.28, vot_ms=14.0),
    # 3 Nasals
    _c("M", "m", "nasal_bilabial", True, (310.0, 1280.0, 2550.0, 3750.0, 4600.0), (65.0, 110.0, 165.0, 220.0, 280.0), "meet", duration_ms=72.0, nasal_gain=0.58),
    _c("N", "n", "nasal_alveolar", True, (320.0, 1740.0, 2720.0, 3820.0, 4650.0), (65.0, 115.0, 170.0, 225.0, 280.0), "nature", duration_ms=68.0, nasal_gain=0.55),
    _c("NG", "ŋ", "nasal_velar", True, (330.0, 1520.0, 2500.0, 3720.0, 4580.0), (70.0, 120.0, 175.0, 230.0, 285.0), "sing", duration_ms=76.0, nasal_gain=0.55),
    # 2 Liquids
    _c("L", "l", "liquid_lateral", True, (370.0, 1280.0, 2920.0, 3850.0, 4680.0), (60.0, 100.0, 160.0, 220.0, 280.0), "lack", duration_ms=66.0),
    _c("R", "ɹ", "liquid_rhotic", True, (420.0, 1420.0, 1840.0, 3680.0, 4580.0), (65.0, 105.0, 130.0, 210.0, 270.0), "rhythm", duration_ms=66.0),
    # 2 Glides / Semivowels
    _c("W", "w", "glide_labiovelar", True, (360.0, 860.0, 2580.0, 3740.0, 4580.0), (55.0, 90.0, 145.0, 200.0, 260.0), "wave", duration_ms=62.0),
    _c("Y", "j", "glide_palatal", True, (330.0, 2680.0, 3260.0, 4080.0, 4860.0), (55.0, 90.0, 140.0, 200.0, 260.0), "you", duration_ms=62.0),
)

PHONEME_INVENTORY: Dict[str, PhonemeSpec] = {p.symbol: p for p in _PHONEME_LIST}
VOWEL_PHONEMES: Tuple[str, ...] = tuple(p.symbol for p in _PHONEME_LIST if p.kind == "vowel")
CONSONANT_PHONEMES: Tuple[str, ...] = tuple(p.symbol for p in _PHONEME_LIST if p.kind == "consonant")


@dataclass(frozen=True)
class GraphemeRule:
    pattern_id: str
    grapheme: str
    context: str  # "any" | "initial" | "medial" | "final" | "before_front" | "after_vowel" | "silent_e"
    phonemes: Tuple[str, ...]
    example: str


def _make_grapheme_rules() -> Tuple[GraphemeRule, ...]:
    """Constructs >= 260 distinct, curated English grapheme-to-phoneme patterns."""
    entries: List[Tuple[str, str, Tuple[str, ...], str]] = [
        # --- Complex 4..6-letter morphological & historical spellings ---
        ("ational", "any", ("EY", "SH", "AX", "N", "AX", "L"), "national"),
        ("tious", "final", ("SH", "AX", "S"), "cautious"),
        ("cious", "final", ("SH", "AX", "S"), "precious"),
        ("ssion", "final", ("SH", "AX", "N"), "passion"),
        ("ation", "final", ("EY", "SH", "AX", "N"), "imagination"),
        ("ition", "final", ("IH", "SH", "AX", "N"), "edition"),
        ("otion", "final", ("OW", "SH", "AX", "N"), "motion"),
        ("ution", "final", ("UW", "SH", "AX", "N"), "solution"),
        ("sions", "final", ("ZH", "AX", "N", "Z"), "visions"),
        ("tions", "final", ("SH", "AX", "N", "Z"), "motions"),
        ("cian", "final", ("SH", "AX", "N"), "musician"),
        ("sion", "final", ("ZH", "AX", "N"), "vision"),
        ("tion", "any", ("SH", "AX", "N"), "action"),
        ("cience", "any", ("SH", "AX", "N", "S"), "conscience"),
        ("tience", "any", ("SH", "AX", "N", "S"), "patience"),
        ("cient", "final", ("SH", "AX", "N", "T"), "ancient"),
        ("tient", "final", ("SH", "AX", "N", "T"), "patient"),
        ("ought", "any", ("AO", "T"), "thought"),
        ("aught", "any", ("AO", "T"), "caught"),
        ("eight", "any", ("EY", "T"), "eight"),
        ("aight", "any", ("EY", "T"), "straight"),
        ("ight", "any", ("AY", "T"), "light"),
        ("ough", "final", ("OW",), "though"),
        ("ough", "any", ("AO",), "brought"),
        ("augh", "any", ("AE", "F"), "laugh"),
        ("eigh", "any", ("EY",), "weigh"),
        ("aigh", "any", ("EY",), "straighten"),
        ("ture", "final", ("CH", "AXR"), "nature"),
        ("sure", "final", ("ZH", "AXR"), "measure"),
        ("ious", "final", ("IY", "AX", "S"), "curious"),
        ("eous", "final", ("IY", "AX", "S"), "gorgeous"),
        ("uous", "final", ("Y", "UW", "AX", "S"), "continuous"),
        ("able", "final", ("AX", "B", "AX", "L"), "capable"),
        ("ible", "final", ("IH", "B", "AX", "L"), "visible"),
        ("ment", "final", ("M", "AX", "N", "T"), "moment"),
        ("ness", "final", ("N", "IH", "S"), "kindness"),
        ("less", "final", ("L", "IH", "S"), "endless"),
        ("ings", "final", ("IH", "NG", "Z"), "wings"),
        ("iful", "final", ("IH", "F", "AX", "L"), "beautiful"),
        ("ence", "final", ("AX", "N", "S"), "science"),
        ("ance", "final", ("AX", "N", "S"), "dance"),
        ("ancy", "final", ("AX", "N", "S", "IY"), "fancy"),
        ("ency", "final", ("AX", "N", "S", "IY"), "frequency"),
        ("etry", "final", ("AX", "T", "R", "IY"), "geometry"),
        ("ical", "final", ("IH", "K", "AX", "L"), "musical"),
        ("tics", "final", ("T", "IH", "K", "S"), "cymatics"),
        ("logy", "final", ("L", "AX", "JH", "IY"), "musicology"),
        ("ophy", "final", ("AX", "F", "IY"), "philosophy"),
        ("ship", "final", ("SH", "IH", "P"), "fellowship"),
        ("hood", "final", ("HH", "UH", "D"), "childhood"),
        ("ward", "final", ("W", "AXR", "D"), "forward"),
        # --- Trigraphs & onset/coda consonant clusters ---
        ("tches", "final", ("CH", "IH", "Z"), "catches"),
        ("dges", "final", ("JH", "IH", "Z"), "bridges"),
        ("tch", "any", ("CH",), "pitch"),
        ("dge", "any", ("JH",), "edge"),
        ("igh", "any", ("AY",), "high"),
        ("sch", "initial", ("S", "K"), "school"),
        ("chr", "initial", ("K", "R"), "chromatic"),
        ("thr", "initial", ("TH", "R"), "three"),
        ("shr", "initial", ("SH", "R"), "shrine"),
        ("str", "initial", ("S", "T", "R"), "stream"),
        ("spr", "initial", ("S", "P", "R"), "spring"),
        ("scr", "initial", ("S", "K", "R"), "script"),
        ("spl", "initial", ("S", "P", "L"), "splendid"),
        ("squ", "initial", ("S", "K", "W"), "square"),
        ("qu", "initial", ("K", "W"), "queen"),
        ("qu", "medial", ("K", "W"), "equal"),
        ("gue", "final", ("G",), "tongue"),
        ("que", "final", ("K",), "unique"),
        ("ph", "initial", ("F",), "phoneme"),
        ("ph", "medial", ("F",), "sphere"),
        ("ph", "final", ("F",), "graph"),
        ("kn", "initial", ("N",), "know"),
        ("wr", "initial", ("R",), "write"),
        ("gn", "initial", ("N",), "gnome"),
        ("gn", "final", ("N",), "sign"),
        ("ps", "initial", ("S",), "psalm"),
        ("pt", "initial", ("T",), "pterosaur"),
        ("rh", "initial", ("R",), "rhythm"),
        ("wh", "initial", ("W",), "when"),
        ("mb", "final", ("M",), "lamb"),
        ("mn", "final", ("M",), "hymn"),
        ("bt", "final", ("T",), "doubt"),
        ("stle", "final", ("S", "AX", "L"), "whistle"),
        ("ften", "final", ("F", "AX", "N"), "soften"),
        ("sten", "final", ("S", "AX", "N"), "listen"),
        # --- Vowel trigraphs & r-colored vowel units ---
        ("eau", "any", ("OW",), "plateau"),
        ("iew", "any", ("Y", "UW"), "view"),
        ("ear", "final", ("IHR",), "clear"),
        ("ear", "any", ("ER",), "learn"),
        ("eer", "any", ("IHR",), "cheer"),
        ("ier", "any", ("IHR",), "pier"),
        ("air", "any", ("EHR",), "air"),
        ("are", "final", ("EHR",), "care"),
        ("ere", "final", ("IHR",), "here"),
        ("ore", "final", ("AO", "R"), "more"),
        ("oar", "any", ("AO", "R"), "soar"),
        ("oor", "any", ("AO", "R"), "door"),
        ("our", "final", ("AW", "AXR"), "hour"),
        ("ure", "final", ("UHR",), "pure"),
        ("ire", "final", ("AY", "AXR"), "fire"),
        ("oor", "final", ("UH", "R"), "poor"),
        # --- Silent-e (split digraph) vowel patterns ---
        ("a_e", "silent_e", ("EY",), "make"),
        ("e_e", "silent_e", ("IY",), "theme"),
        ("i_e", "silent_e", ("AY",), "chime"),
        ("o_e", "silent_e", ("OW",), "note"),
        ("u_e", "silent_e", ("UW",), "tune"),
        ("y_e", "silent_e", ("AY",), "type"),
        ("ace", "silent_e", ("EY", "S"), "space"),
        ("ice", "silent_e", ("AY", "S"), "voice"),
        ("age", "silent_e", ("EY", "JH"), "page"),
        ("ige", "silent_e", ("IH", "JH"), "oblige"),
        ("ate", "silent_e", ("EY", "T"), "plate"),
        ("ite", "silent_e", ("AY", "T"), "write"),
        ("ote", "silent_e", ("OW", "T"), "note"),
        ("ute", "silent_e", ("UW", "T"), "flute"),
        ("ane", "silent_e", ("EY", "N"), "plane"),
        ("ine", "silent_e", ("AY", "N"), "shine"),
        ("one", "silent_e", ("OW", "N"), "tone"),
        ("une", "silent_e", ("UW", "N"), "june"),
        ("ame", "silent_e", ("EY", "M"), "name"),
        ("ime", "silent_e", ("AY", "M"), "time"),
        ("ome", "silent_e", ("OW", "M"), "home"),
        ("ake", "silent_e", ("EY", "K"), "wake"),
        ("ike", "silent_e", ("AY", "K"), "like"),
        ("oke", "silent_e", ("OW", "K"), "spoke"),
        ("ale", "silent_e", ("EY", "L"), "scale"),
        ("ile", "silent_e", ("AY", "L"), "smile"),
        ("ole", "silent_e", ("OW", "L"), "whole"),
        ("ape", "silent_e", ("EY", "P"), "shape"),
        ("ope", "silent_e", ("OW", "P"), "hope"),
        ("ave", "silent_e", ("EY", "V"), "wave"),
        ("ive", "silent_e", ("AY", "V"), "alive"),
        ("ove", "silent_e", ("OW", "V"), "cove"),
        # --- Vowel digraphs ---
        ("ee", "any", ("IY",), "meet"),
        ("ee", "final", ("IY",), "free"),
        ("ea", "any", ("IY",), "beat"),
        ("ea", "final", ("IY",), "sea"),
        ("ai", "any", ("EY",), "rain"),
        ("ay", "final", ("EY",), "play"),
        ("ay", "any", ("EY",), "daylight"),
        ("ei", "any", ("EY",), "vein"),
        ("ey", "final", ("IY",), "key"),
        ("ey", "medial", ("EY",), "greyhound"),
        ("ie", "final", ("AY",), "skyline"),
        ("ie", "any", ("IY",), "piece"),
        ("oa", "any", ("OW",), "boat"),
        ("oe", "final", ("OW",), "toe"),
        ("oe", "any", ("OW", "IY"), "zoe"),
        ("oi", "any", ("OY",), "voice"),
        ("oy", "final", ("OY",), "joy"),
        ("oy", "any", ("OY",), "joyful"),
        ("ou", "any", ("AW",), "sound"),
        ("ow", "final", ("OW",), "glow"),
        ("ow", "any", ("AW",), "owl"),
        ("au", "any", ("AO",), "caught"),
        ("aw", "any", ("AO",), "dawn"),
        ("aw", "final", ("AO",), "draw"),
        ("oo", "any", ("UW",), "moon"),
        ("oo", "final", ("UW",), "too"),
        ("ue", "final", ("UW",), "true"),
        ("ui", "any", ("UW",), "fruit"),
        ("eu", "any", ("Y", "UW"), "euro"),
        ("ew", "final", ("UW",), "grew"),
        ("ew", "any", ("Y", "UW"), "newt"),
        # --- R-controlled two-letter vowels ---
        ("ar", "any", ("AA", "R"), "star"),
        ("er", "final", ("AXR",), "sister"),
        ("er", "any", ("ER",), "fern"),
        ("ir", "any", ("ER",), "bird"),
        ("or", "any", ("AO", "R"), "form"),
        ("or", "final", ("AXR",), "mirror"),
        ("ur", "any", ("ER",), "turn"),
        ("yr", "any", ("ER",), "myrrh"),
        # --- Consonant digraphs & positional contexts ---
        ("sh", "initial", ("SH",), "shine"),
        ("sh", "medial", ("SH",), "wishing"),
        ("sh", "final", ("SH",), "hush"),
        ("ch", "initial", ("CH",), "chime"),
        ("ch", "medial", ("CH",), "echoed"),
        ("ch", "final", ("CH",), "rich"),
        ("th", "initial", ("TH",), "theme"),
        ("th", "medial", ("DH",), "rhythm"),
        ("th", "final", ("TH",), "breath"),
        ("ng", "final", ("NG",), "sing"),
        ("ng", "medial", ("NG", "G"), "finger"),
        ("nk", "final", ("NG", "K"), "think"),
        ("nk", "medial", ("NG", "K"), "twinkle"),
        ("ck", "final", ("K",), "lack"),
        ("ck", "medial", ("K",), "bucket"),
        ("sc", "before_front", ("S",), "scene"),
        ("sc", "any", ("S", "K"), "scale"),
        ("ce", "final", ("S",), "voice"),
        ("ce", "before_front", ("S",), "center"),
        ("ci", "before_front", ("S",), "city"),
        ("cy", "before_front", ("S",), "cymatics"),
        ("ge", "final", ("JH",), "stage"),
        ("ge", "before_front", ("JH",), "geometry"),
        ("gi", "before_front", ("JH",), "magic"),
        ("gy", "before_front", ("JH",), "energy"),
        ("gu", "initial", ("G",), "guide"),
        ("gh", "initial", ("G",), "ghost"),
        ("gh", "final", ("F",), "laugh"),
        # --- Initial two-consonant blends ---
        ("st", "initial", ("S", "T"), "star"),
        ("sp", "initial", ("S", "P"), "speak"),
        ("sk", "initial", ("S", "K"), "sky"),
        ("sl", "initial", ("S", "L"), "slow"),
        ("sm", "initial", ("S", "M"), "smile"),
        ("sn", "initial", ("S", "N"), "snow"),
        ("sw", "initial", ("S", "W"), "sweet"),
        ("tw", "initial", ("T", "W"), "two"),
        ("dw", "initial", ("D", "W"), "dwell"),
        ("bl", "initial", ("B", "L"), "blue"),
        ("cl", "initial", ("K", "L"), "clear"),
        ("fl", "initial", ("F", "L"), "flow"),
        ("gl", "initial", ("G", "L"), "glow"),
        ("pl", "initial", ("P", "L"), "play"),
        ("br", "initial", ("B", "R"), "bright"),
        ("cr", "initial", ("K", "R"), "crystal"),
        ("dr", "initial", ("D", "R"), "dream"),
        ("fr", "initial", ("F", "R"), "free"),
        ("gr", "initial", ("G", "R"), "groove"),
        ("pr", "initial", ("P", "R"), "pretty"),
        ("tr", "initial", ("T", "R"), "true"),
        # --- Double / geminate consonants ---
        ("bb", "any", ("B",), "ribbon"),
        ("cc", "before_front", ("K", "S"), "accent"),
        ("cc", "any", ("K",), "accord"),
        ("dd", "any", ("D",), "middle"),
        ("ff", "any", ("F",), "coffee"),
        ("gg", "any", ("G",), "giggle"),
        ("ll", "any", ("L",), "bell"),
        ("mm", "any", ("M",), "summer"),
        ("nn", "any", ("N",), "manner"),
        ("pp", "any", ("P",), "happy"),
        ("rr", "any", ("R",), "mirror"),
        ("ss", "any", ("S",), "glass"),
        ("tt", "any", ("T",), "butter"),
        ("vv", "any", ("V",), "savvy"),
        ("zz", "any", ("Z",), "jazz"),
        # --- Common final inflectional / positional suffixes ---
        ("ing", "final", ("IH", "NG"), "singing"),
        ("ed", "final", ("D",), "played"),
        ("es", "final", ("IH", "Z"), "waves"),
        ("ly", "final", ("L", "IY"), "softly"),
        ("ty", "final", ("T", "IY"), "geometry"),
        ("ry", "final", ("R", "IY"), "memory"),
        ("ny", "final", ("N", "IY"), "harmony"),
        ("my", "final", ("M", "IY"), "stormy"),
        ("sy", "final", ("Z", "IY"), "daisy"),
        ("py", "final", ("P", "IY"), "happy"),
        ("dy", "final", ("D", "IY"), "melody"),
        ("fy", "final", ("F", "AY"), "clarify"),
        ("al", "final", ("AX", "L"), "vocal"),
        ("el", "final", ("AX", "L"), "level"),
        ("le", "final", ("AX", "L"), "bicycle"),
        ("en", "final", ("AX", "N"), "woven"),
        ("on", "final", ("AX", "N"), "lesson"),
        ("ic", "final", ("IH", "K"), "cymatic"),
        ("us", "final", ("AX", "S"), "chorus"),
        ("um", "final", ("AX", "M"), "spectrum"),
        # --- Contextual & single-letter graphemes across initial/medial/final ---
        ("a", "initial", ("AE",), "answer"),
        ("a", "medial", ("AE",), "lack"),
        ("a", "final", ("AX",), "sofa"),
        ("b", "initial", ("B",), "back"),
        ("b", "medial", ("B",), "orbit"),
        ("b", "final", ("B",), "web"),
        ("c", "initial", ("K",), "cot"),
        ("c", "medial", ("K",), "vocal"),
        ("c", "final", ("K",), "music"),
        ("d", "initial", ("D",), "daisy"),
        ("d", "medial", ("D",), "chladni"),
        ("d", "final", ("D",), "sand"),
        ("e", "initial", ("EH",), "echo"),
        ("e", "medial", ("EH",), "bet"),
        ("e", "final", (), "tone"),  # silent final e unless single-syllable
        ("f", "initial", ("F",), "formant"),
        ("f", "medial", ("F",), "softly"),
        ("f", "final", ("F",), "half"),
        ("g", "initial", ("G",), "gem"),
        ("g", "medial", ("G",), "signal"),
        ("g", "final", ("G",), "sing"),
        ("h", "initial", ("HH",), "hello"),
        ("h", "medial", ("HH",), "behind"),
        ("h", "final", (), "oh"),
        ("i", "initial", ("IH",), "in"),
        ("i", "medial", ("IH",), "sing"),
        ("i", "final", ("IY",), "chladni"),
        ("j", "initial", ("JH",), "joy"),
        ("j", "medial", ("JH",), "major"),
        ("k", "initial", ("K",), "key"),
        ("k", "medial", ("K",), "spoken"),
        ("k", "final", ("K",), "dark"),
        ("l", "initial", ("L",), "lack"),
        ("l", "medial", ("L",), "melody"),
        ("l", "final", ("L",), "bell"),
        ("m", "initial", ("M",), "meet"),
        ("m", "medial", ("M",), "cymatics"),
        ("m", "final", ("M",), "gem"),
        ("n", "initial", ("N",), "nature"),
        ("n", "medial", ("N",), "sound"),
        ("n", "final", ("N",), "sand"),
        ("o", "initial", ("AA",), "on"),
        ("o", "medial", ("AA",), "cot"),
        ("o", "final", ("OW",), "echo"),
        ("p", "initial", ("P",), "pretty"),
        ("p", "medial", ("P",), "open"),
        ("p", "final", ("P",), "map"),
        ("q", "any", ("K",), "iraq"),
        ("r", "initial", ("R",), "rose"),
        ("r", "medial", ("R",), "berry"),
        ("r", "final", ("R",), "star"),
        ("s", "initial", ("S",), "sound"),
        ("s", "medial", ("S",), "basket"),
        ("s", "final", ("Z",), "songs"),
        ("t", "initial", ("T",), "time"),
        ("t", "medial", ("T",), "water"),
        ("t", "final", ("T",), "cot"),
        ("u", "initial", ("AH",), "upon"),
        ("u", "medial", ("AH",), "but"),
        ("u", "final", ("UW",), "you"),
        ("v", "initial", ("V",), "voice"),
        ("v", "medial", ("V",), "seven"),
        ("v", "final", ("V",), "love"),
        ("w", "initial", ("W",), "wave"),
        ("w", "medial", ("W",), "away"),
        ("w", "final", ("W",), "how"),
        ("x", "initial", ("Z",), "xylophone"),
        ("x", "medial", ("K", "S"), "pixel"),
        ("x", "final", ("K", "S"), "box"),
        ("y", "initial", ("Y",), "yes"),
        ("y", "medial", ("IH",), "rhythm"),
        ("y", "final", ("IY",), "pretty"),
        ("z", "initial", ("Z",), "zoe"),
        ("z", "medial", ("Z",), "crazy"),
        ("z", "final", ("Z",), "jazz"),
    ]
    out: List[GraphemeRule] = []
    seen_ids: set[str] = set()
    for idx, (g, ctx, ph, ex) in enumerate(entries, 1):
        pid = f"G{idx:03d}_{g}_{ctx}"
        while pid in seen_ids:
            pid = f"{pid}_alt"
        seen_ids.add(pid)
        out.append(GraphemeRule(pattern_id=pid, grapheme=g, context=ctx, phonemes=ph, example=ex))
    return tuple(out)


GRAPHEME_RULES: Tuple[GraphemeRule, ...] = _make_grapheme_rules()


# Curated English pronouncing dictionary for exact poetic, scientific & minimal-pair fidelity.
CORE_LEXICON: Dict[str, Tuple[str, ...]] = {
    "a": ("AH",),
    "about": ("AX", "B", "AW", "T"),
    "accessible": ("AE", "K", "S", "EH", "S", "IH", "B", "AX", "L"),
    "across": ("AX", "K", "R", "AO", "S"),
    "air": ("EHR",),
    "alive": ("AX", "L", "AY", "V"),
    "all": ("AO", "L"),
    "am": ("AE", "M"),
    "an": ("AE", "N"),
    "and": ("AE", "N", "D"),
    "answer": ("AE", "N", "S", "AXR"),
    "are": ("AA", "R"),
    "as": ("AE", "Z"),
    "at": ("AE", "T"),
    "atari": ("AX", "T", "AA", "R", "IY"),
    "atlas": ("AE", "T", "L", "AX", "S"),
    "back": ("B", "AE", "K"),
    "be": ("B", "IY"),
    "beautiful": ("B", "Y", "UW", "T", "IH", "F", "AX", "L"),
    "bell": ("B", "EH", "L"),
    "beyond": ("B", "IY", "AA", "N", "D"),
    "bicycle": ("B", "AY", "S", "IH", "K", "AX", "L"),
    "bird": ("B", "ER", "D"),
    "bit": ("B", "IH", "T"),
    "blue": ("B", "L", "UW"),
    "book": ("B", "UH", "K"),
    "boot": ("B", "UW", "T"),
    "both": ("B", "OW", "TH"),
    "boy": ("B", "OY"),
    "brain": ("B", "R", "EY", "N"),
    "breath": ("B", "R", "EH", "TH"),
    "bright": ("B", "R", "AY", "T"),
    "built": ("B", "IH", "L", "T"),
    "but": ("B", "AH", "T"),
    "by": ("B", "AY"),
    "can": ("K", "AE", "N"),
    "car": ("K", "AA", "R"),
    "caught": ("K", "AO", "T"),
    "center": ("S", "EH", "N", "T", "AXR"),
    "cheap": ("CH", "IY", "P"),
    "chime": ("CH", "AY", "M"),
    "chladni": ("K", "L", "AA", "D", "N", "IY"),
    "clear": ("K", "L", "IHR"),
    "clock": ("K", "L", "AA", "K"),
    "code": ("K", "OW", "D"),
    "color": ("K", "AH", "L", "AXR"),
    "come": ("K", "AH", "M"),
    "computer": ("K", "AX", "M", "P", "Y", "UW", "T", "AXR"),
    "consonant": ("K", "AA", "N", "S", "AX", "N", "AX", "N", "T"),
    "constellation": ("K", "AA", "N", "S", "T", "AX", "L", "EY", "SH", "AX", "N"),
    "cot": ("K", "AA", "T"),
    "counting": ("K", "AW", "N", "T", "IH", "NG"),
    "crazy": ("K", "R", "EY", "Z", "IY"),
    "crystal": ("K", "R", "IH", "S", "T", "AX", "L"),
    "cure": ("K", "Y", "UHR"),
    "curiosity": ("K", "Y", "UH", "R", "IY", "AA", "S", "AX", "T", "IY"),
    "cymatic": ("S", "AY", "M", "AE", "T", "IH", "K"),
    "cymatics": ("S", "AY", "M", "AE", "T", "IH", "K", "S"),
    "daisy": ("D", "EY", "Z", "IY"),
    "dance": ("D", "AE", "N", "S"),
    "day": ("D", "EY"),
    "deception": ("D", "IH", "S", "EH", "P", "SH", "AX", "N"),
    "diamond": ("D", "AY", "AX", "M", "AX", "N", "D"),
    "digital": ("D", "IH", "JH", "IH", "T", "AX", "L"),
    "dignity": ("D", "IH", "G", "N", "IH", "T", "IY"),
    "do": ("D", "UW"),
    "dorothy": ("D", "AO", "R", "AX", "TH", "IY"),
    "dos": ("D", "AO", "S"),
    "down": ("D", "AW", "N"),
    "dream": ("D", "R", "IY", "M"),
    "earth": ("ER", "TH"),
    "echo": ("EH", "K", "OW"),
    "eight": ("EY", "T"),
    "english": ("IH", "NG", "G", "L", "IH", "SH"),
    "entropy": ("EH", "N", "T", "R", "AX", "P", "IY"),
    "every": ("EH", "V", "R", "IY"),
    "evidence": ("EH", "V", "IH", "D", "AX", "N", "S"),
    "father": ("F", "AA", "DH", "AXR"),
    "field": ("F", "IY", "L", "D"),
    "figure": ("F", "IH", "G", "Y", "AXR"),
    "first": ("F", "ER", "S", "T"),
    "five": ("F", "AY", "V"),
    "flower": ("F", "L", "AW", "AXR"),
    "for": ("F", "AO", "R"),
    "form": ("F", "AO", "R", "M"),
    "formant": ("F", "AO", "R", "M", "AX", "N", "T"),
    "four": ("F", "AO", "R"),
    "forty": ("F", "AO", "R", "T", "IY"),
    "free": ("F", "R", "IY"),
    "freedom": ("F", "R", "IY", "D", "AX", "M"),
    "frequency": ("F", "R", "IY", "K", "W", "AX", "N", "S", "IY"),
    "from": ("F", "R", "AH", "M"),
    "future": ("F", "Y", "UW", "CH", "AXR"),
    "garden": ("G", "AA", "R", "D", "AX", "N"),
    "gary": ("G", "EHR", "IY"),
    "gem": ("JH", "EH", "M"),
    "geometry": ("JH", "IY", "AA", "M", "AX", "T", "R", "IY"),
    "give": ("G", "IH", "V"),
    "glow": ("G", "L", "OW"),
    "good": ("G", "UH", "D"),
    "grace": ("G", "R", "EY", "S"),
    "groove": ("G", "R", "UW", "V"),
    "half": ("HH", "AE", "F"),
    "happy": ("HH", "AE", "P", "IY"),
    "harmony": ("HH", "AA", "R", "M", "AX", "N", "IY"),
    "have": ("HH", "AE", "V"),
    "hear": ("HH", "IHR"),
    "heart": ("HH", "AA", "R", "T"),
    "hello": ("HH", "EH", "L", "OW"),
    "her": ("HH", "ER"),
    "here": ("HH", "IHR"),
    "high": ("HH", "AY"),
    "home": ("HH", "OW", "M"),
    "honest": ("AA", "N", "AX", "S", "T"),
    "human": ("HH", "Y", "UW", "M", "AX", "N"),
    "i": ("AY",),
    "ibm": ("AY", "B", "IY", "EH", "M"),
    "idea": ("AY", "D", "IY", "AX"),
    "imagination": ("IH", "M", "AE", "JH", "IH", "N", "EY", "SH", "AX", "N"),
    "imagine": ("IH", "M", "AE", "JH", "IH", "N"),
    "in": ("IH", "N"),
    "into": ("IH", "N", "T", "UW"),
    "is": ("IH", "Z"),
    "it": ("IH", "T"),
    "joy": ("JH", "OY"),
    "just": ("JH", "AH", "S", "T"),
    "kildall": ("K", "IH", "L", "D", "AO", "L"),
    "kloster": ("K", "L", "AA", "S", "T", "AXR"),
    "know": ("N", "OW"),
    "lack": ("L", "AE", "K"),
    "lake": ("L", "EY", "K"),
    "learn": ("L", "ER", "N"),
    "let": ("L", "EH", "T"),
    "life": ("L", "AY", "F"),
    "light": ("L", "AY", "T"),
    "listen": ("L", "IH", "S", "AX", "N"),
    "live": ("L", "AY", "V"),
    "look": ("L", "UH", "K"),
    "love": ("L", "AH", "V"),
    "made": ("M", "EY", "D"),
    "make": ("M", "EY", "K"),
    "many": ("M", "EH", "N", "IY"),
    "mars": ("M", "AA", "R", "Z"),
    "math": ("M", "AE", "TH"),
    "me": ("M", "IY"),
    "measure": ("M", "EH", "ZH", "AXR"),
    "meet": ("M", "IY", "T"),
    "melody": ("M", "EH", "L", "AX", "D", "IY"),
    "metacognition": ("M", "EH", "T", "AX", "K", "AA", "G", "N", "IH", "SH", "AX", "N"),
    "michael": ("M", "AY", "K", "AX", "L"),
    "midi": ("M", "IH", "D", "IY"),
    "mind": ("M", "AY", "N", "D"),
    "moon": ("M", "UW", "N"),
    "more": ("M", "AO", "R"),
    "music": ("M", "Y", "UW", "Z", "IH", "K"),
    "my": ("M", "AY"),
    "name": ("N", "EY", "M"),
    "native": ("N", "EY", "T", "IH", "V"),
    "nature": ("N", "EY", "CH", "AXR"),
    "near": ("N", "IHR"),
    "neurogarden": ("N", "UHR", "OW", "G", "AA", "R", "D", "AX", "N"),
    "new": ("N", "UW"),
    "nicholas": ("N", "IH", "K", "AX", "L", "AX", "S"),
    "night": ("N", "AY", "T"),
    "no": ("N", "OW"),
    "note": ("N", "OW", "T"),
    "now": ("N", "AW"),
    "of": ("AH", "V"),
    "on": ("AA", "N"),
    "one": ("W", "AH", "N"),
    "open": ("OW", "P", "AX", "N"),
    "operational": ("AA", "P", "AXR", "EY", "SH", "AX", "N", "AX", "L"),
    "our": ("AW", "AXR"),
    "own": ("OW", "N"),
    "partner": ("P", "AA", "R", "T", "N", "AXR"),
    "pattern": ("P", "AE", "T", "AXR", "N"),
    "pc": ("P", "IY", "S", "IY"),
    "peace": ("P", "IY", "S"),
    "phoneme": ("F", "OW", "N", "IY", "M"),
    "piano": ("P", "IY", "AE", "N", "OW"),
    "pitch": ("P", "IH", "CH"),
    "plate": ("P", "L", "EY", "T"),
    "play": ("P", "L", "EY"),
    "pretty": ("P", "R", "IH", "T", "IY"),
    "proof": ("P", "R", "UW", "F"),
    "pure": ("P", "Y", "UHR"),
    "quale": ("K", "W", "EY", "L"),
    "question": ("K", "W", "EH", "S", "CH", "AX", "N"),
    "quiet": ("K", "W", "AY", "AX", "T"),
    "real": ("R", "IY", "L"),
    "recognition": ("R", "EH", "K", "AX", "G", "N", "IH", "SH", "AX", "N"),
    "red": ("R", "EH", "D"),
    "research": ("R", "IH", "S", "ER", "CH"),
    "rhythm": ("R", "IH", "DH", "AX", "M"),
    "right": ("R", "AY", "T"),
    "ring": ("R", "IH", "NG"),
    "rose": ("R", "OW", "Z"),
    "sand": ("S", "AE", "N", "D"),
    "say": ("S", "EY"),
    "scratch": ("S", "K", "R", "AE", "CH"),
    "sea": ("S", "IY"),
    "seat": ("S", "IY", "T"),
    "see": ("S", "IY"),
    "seven": ("S", "EH", "V", "AX", "N"),
    "she": ("SH", "IY"),
    "shine": ("SH", "AY", "N"),
    "sing": ("S", "IH", "NG"),
    "singing": ("S", "IH", "NG", "IH", "NG"),
    "sky": ("S", "K", "AY"),
    "slow": ("S", "L", "OW"),
    "so": ("S", "OW"),
    "sofa": ("S", "OW", "F", "AX"),
    "soft": ("S", "AO", "F", "T"),
    "song": ("S", "AO", "NG"),
    "songs": ("S", "AO", "NG", "Z"),
    "soon": ("S", "UW", "N"),
    "sound": ("S", "AW", "N", "D"),
    "space": ("S", "P", "EY", "S"),
    "speak": ("S", "P", "IY", "K"),
    "speaking": ("S", "P", "IY", "K", "IH", "NG"),
    "spectral": ("S", "P", "EH", "K", "T", "R", "AX", "L"),
    "speech": ("S", "P", "IY", "CH"),
    "star": ("S", "T", "AA", "R"),
    "starlight": ("S", "T", "AA", "R", "L", "AY", "T"),
    "stay": ("S", "T", "EY"),
    "sweet": ("S", "W", "IY", "T"),
    "talk": ("T", "AO", "K"),
    "tell": ("T", "EH", "L"),
    "thank": ("TH", "AE", "NG", "K"),
    "that": ("DH", "AE", "T"),
    "the": ("DH", "AX"),
    "there": ("DH", "EHR"),
    "these": ("DH", "IY", "Z"),
    "they": ("DH", "EY"),
    "think": ("TH", "IH", "NG", "K"),
    "this": ("DH", "IH", "S"),
    "three": ("TH", "R", "IY"),
    "through": ("TH", "R", "UW"),
    "time": ("T", "AY", "M"),
    "to": ("T", "UW"),
    "together": ("T", "AX", "G", "EH", "DH", "AXR"),
    "tone": ("T", "OW", "N"),
    "true": ("T", "R", "UW"),
    "turn": ("T", "ER", "N"),
    "turns": ("T", "ER", "N", "Z"),
    "two": ("T", "UW"),
    "universe": ("Y", "UW", "N", "AX", "V", "ER", "S"),
    "upon": ("AX", "P", "AA", "N"),
    "variables": ("V", "EHR", "IY", "AX", "B", "AX", "L", "Z"),
    "venus": ("V", "IY", "N", "AX", "S"),
    "voice": ("V", "OY", "S"),
    "voices": ("V", "OY", "S", "IH", "Z"),
    "vowel": ("V", "AW", "AX", "L"),
    "warm": ("W", "AO", "R", "M"),
    "water": ("W", "AO", "T", "AXR"),
    "wave": ("W", "EY", "V"),
    "waves": ("W", "EY", "V", "Z"),
    "way": ("W", "EY"),
    "we": ("W", "IY"),
    "where": ("W", "EHR"),
    "will": ("W", "IH", "L"),
    "wind": ("W", "IH", "N", "D"),
    "with": ("W", "IH", "DH"),
    "wonder": ("W", "AH", "N", "D", "AXR"),
    "word": ("W", "ER", "D"),
    "world": ("W", "ER", "L", "D"),
    "woven": ("W", "OW", "V", "AX", "N"),
    "write": ("R", "AY", "T"),
    "you": ("Y", "UW"),
    "your": ("Y", "AO", "R"),
    "zero": ("Z", "IHR", "OW"),
    "zoe": ("Z", "OW", "IY"),
}


_FRONT_LETTERS = set("eiy")
_VOWELS_ALPHA = set("aeiouy")
_BY_GRAPHEME: Dict[str, List[GraphemeRule]] = {}
for _rule in GRAPHEME_RULES:
    _BY_GRAPHEME.setdefault(_rule.grapheme, []).append(_rule)
_MAX_G_LEN = max(len(k) for k in _BY_GRAPHEME)


def grapheme_rules_sha256() -> str:
    payload = [
        {"id": r.pattern_id, "g": r.grapheme, "ctx": r.context, "p": list(r.phonemes), "ex": r.example}
        for r in GRAPHEME_RULES
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _apply_dialect(phonemes: List[str], *, rhotic: bool, cot_caught_merger: bool) -> List[str]:
    out = list(phonemes)
    if cot_caught_merger:
        out = ["AA" if p == "AO" else p for p in out]
    if not rhotic:
        non_rhotic: List[str] = []
        n = len(out)
        for i, p in enumerate(out):
            nxt_is_vowel = (i + 1 < n and PHONEME_INVENTORY.get(out[i + 1]) is not None and PHONEME_INVENTORY[out[i + 1]].kind == "vowel")
            if p == "ER":
                non_rhotic.append("AH" if not nxt_is_vowel else "ER")
            elif p == "AXR":
                non_rhotic.append("AX" if not nxt_is_vowel else "ER")
            elif p == "R" and not nxt_is_vowel and i > 0 and PHONEME_INVENTORY[out[i - 1]].kind == "vowel":
                # Drop post-vocalic coda /r/ (e.g., car -> /K AA/)
                continue
            else:
                non_rhotic.append(p)
        out = non_rhotic
    return out


def _rule_g2p(word: str) -> Tuple[List[str], List[str]]:
    """Rule-based English grapheme-to-phoneme parser over the 260+ rule table."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return [], []
    # Check silent-e VC# pattern at word end (e.g., 'make', 'chime', 'note', 'flute')
    has_silent_e_tail = (
        len(w) >= 4
        and w.endswith("e")
        and w[-2] not in _VOWELS_ALPHA
        and w[-3] in "aeiouy"
        and (len(w) == 3 or w[-4] not in "aeiou")
        and not w.endswith(("le", "ce", "ge"))
    )
    phonemes: List[str] = []
    fired: List[str] = []
    i = 0
    n = len(w)
    while i < n:
        matched: GraphemeRule | None = None
        if has_silent_e_tail and i == n - 3:
            vce_key = f"{w[i]}_e"
            c_rules = _BY_GRAPHEME.get(w[i + 1], [])
            vce_rule = next((r for r in _BY_GRAPHEME.get(vce_key, [])), None)
            if vce_rule is not None:
                c_phon: Tuple[str, ...] = ()
                for r in c_rules:
                    if r.context in ("medial", "any", "final"):
                        c_phon = r.phonemes
                        break
                phonemes.extend(vce_rule.phonemes)
                phonemes.extend(c_phon)
                fired.append(vce_rule.pattern_id)
                i = n
                continue

        for span in range(min(_MAX_G_LEN, n - i), 0, -1):
            sub = w[i:i + span]
            candidates = _BY_GRAPHEME.get(sub)
            if not candidates:
                continue
            at_start = (i == 0)
            at_end = (i + span == n)
            next_ch = w[i + span] if (i + span < n) else ""
            chosen: GraphemeRule | None = None
            for ctx in (
                "initial" if at_start else "",
                "final" if at_end else "",
                "before_front" if next_ch in _FRONT_LETTERS else "",
                "medial" if (not at_start and not at_end) else "",
                "any",
            ):
                if not ctx:
                    continue
                chosen = next((r for r in candidates if r.context == ctx), None)
                if chosen is not None:
                    break
            if chosen is not None:
                matched = chosen
                break

        if matched is None:
            # Ultimate safe single-letter fallback (unreachable for a-z since all 26 exist)
            fallback = _BY_GRAPHEME.get(w[i], [])
            if fallback:
                matched = fallback[0]
                i += 1
            else:
                i += 1
                continue
        else:
            i += len(matched.grapheme)

        phonemes.extend(matched.phonemes)
        fired.append(matched.pattern_id)

    return phonemes, fired


def word_to_phonemes(
    word: str,
    *,
    rhotic: bool = True,
    cot_caught_merger: bool = False,
    use_lexicon: bool = True,
) -> Tuple[List[str], List[str]]:
    """Converts an English word into validated PhonemeSpec symbols + fired rule IDs."""
    clean = re.sub(r"[^a-zA-Z']", "", word.strip()).lower()
    if not clean:
        return [], []
    if clean in {"i'm", "im"}:
        return _apply_dialect(["AY", "M"], rhotic=rhotic, cot_caught_merger=cot_caught_merger), ["LEX_CONTRACT_IM"]
    if clean in {"it's"}:
        return _apply_dialect(["IH", "T", "S"], rhotic=rhotic, cot_caught_merger=cot_caught_merger), ["LEX_CONTRACT_ITS"]
    if clean in {"you're"}:
        return _apply_dialect(["Y", "UHR"], rhotic=rhotic, cot_caught_merger=cot_caught_merger), ["LEX_CONTRACT_YOURE"]
    plain = clean.replace("'", "")
    if use_lexicon and plain in CORE_LEXICON:
        ph = list(CORE_LEXICON[plain])
        _, rules = _rule_g2p(plain)
        return _apply_dialect(ph, rhotic=rhotic, cot_caught_merger=cot_caught_merger), (rules or [f"LEX_{plain}"])

    # Try plural/past morphological stem in lexicon before rule parser
    if use_lexicon and plain.endswith("s") and plain[:-1] in CORE_LEXICON:
        stem = list(CORE_LEXICON[plain[:-1]])
        suffix = ["IH", "Z"] if stem[-1] in {"S", "Z", "SH", "ZH", "CH", "JH"} else (["S"] if not PHONEME_INVENTORY[stem[-1]].voiced else ["Z"])
        _, rules = _rule_g2p(plain)
        return _apply_dialect(stem + suffix, rhotic=rhotic, cot_caught_merger=cot_caught_merger), (rules or [f"LEX_{plain}"])

    ph, rules = _rule_g2p(plain)
    if not ph:
        ph = ["AX"]
    return _apply_dialect(ph, rhotic=rhotic, cot_caught_merger=cot_caught_merger), rules


def syllabify_phonemes(phonemes: Sequence[str]) -> List[List[str]]:
    """Groups word phonemes into syllables (onset + vowel nucleus + coda) for singing."""
    vowel_idxs = [i for i, sym in enumerate(phonemes) if sym in PHONEME_INVENTORY and PHONEME_INVENTORY[sym].kind == "vowel"]
    if not vowel_idxs:
        return [list(phonemes)] if phonemes else []
    syllables: List[List[str]] = []
    start = 0
    for k, v_idx in enumerate(vowel_idxs):
        if k + 1 < len(vowel_idxs):
            nxt_v = vowel_idxs[k + 1]
            c_between = nxt_v - v_idx - 1
            split_at = v_idx + 1 if c_between <= 1 else v_idx + 2
        else:
            split_at = len(phonemes)
        syllables.append(list(phonemes[start:split_at]))
        start = split_at
    return syllables


def text_to_phonemes(
    text: str,
    *,
    rhotic: bool = True,
    cot_caught_merger: bool = False,
) -> Dict[str, object]:
    """Tokenizes arbitrary English text into phonemes, syllables, pauses, and prosody."""
    raw = text.strip()
    intonation = "question" if raw.endswith("?") else ("exclaim" if raw.endswith("!") else "statement")
    tokens = re.findall(r"[A-Za-z']+|[.,!?;:\-]", raw)

    words_breakdown: List[Dict[str, object]] = []
    stream: List[str] = []
    syllable_groups: List[List[str]] = []
    all_rules: List[str] = []

    for idx, tok in enumerate(tokens):
        if re.fullmatch(r"[.,!?;:\-]+", tok):
            pause = "PAU_LONG" if tok in {".", "!", "?", ";"} else "PAU_SHORT"
            if stream and stream[-1] not in {"PAU_SHORT", "PAU_LONG"}:
                stream.append(pause)
            continue
        ph, rules = word_to_phonemes(tok, rhotic=rhotic, cot_caught_merger=cot_caught_merger)
        if not ph:
            continue
        syls = syllabify_phonemes(ph)
        words_breakdown.append({
            "word": tok,
            "phonemes": ph,
            "syllables": syls,
            "rules_fired": rules,
        })
        stream.extend(ph)
        syllable_groups.extend(syls)
        all_rules.extend(rules)
        if idx + 1 < len(tokens) and not re.fullmatch(r"[.,!?;:\-]+", tokens[idx + 1]):
            stream.append("PAU_WORD")

    return {
        "contract": PHONETICS_CONTRACT,
        "text": raw,
        "intonation": intonation,
        "rhotic": rhotic,
        "cot_caught_merger": cot_caught_merger,
        "words": words_breakdown,
        "phoneme_stream": stream,
        "phonemes_only": [p for p in stream if p in PHONEME_INVENTORY],
        "syllables": syllable_groups,
        "rules_fired_count": len(all_rules),
        "phoneme_inventory_count": len(PHONEME_INVENTORY),
        "grapheme_rule_count": len(GRAPHEME_RULES),
        "grapheme_rules_sha256": grapheme_rules_sha256(),
    }
