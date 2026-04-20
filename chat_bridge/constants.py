"""
Translation Bridge — Constants & Prompts
"""

# ─────────────────────────────────────────────────────────────
# AI MODEL
# ─────────────────────────────────────────────────────────────

# OpenRouter Models options (Pick one by uncommenting it)

# 1. Llama 3.3 70B (The Sweet Spot)
# Cost: ~$0.13 Input / $0.40 Output (Very cheap!)
# OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"

# 2. Claude 3.5 Haiku (Previous)
# Cost: ~$1.00 Input / $5.00 Output
# OPENROUTER_MODEL = "anthropic/claude-3.5-haiku"

# 3. Grok (xAI) - Latest from OpenRouter
# Cost: Very reasonable for its high performance
OPENROUTER_MODEL = "x-ai/grok-4.1-fast"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ─────────────────────────────────────────────────────────────
# WINDOW
# ─────────────────────────────────────────────────────────────

WINDOW_WIDTH = 520
WINDOW_HEIGHT = 720
WINDOW_OPACITY = 0.98

# ─────────────────────────────────────────────────────────────
# HOTKEY
# ─────────────────────────────────────────────────────────────

DEFAULT_HOTKEY = "ctrl+shift+t"

# ─────────────────────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────────────────────

MODE_COPY  = "copy"
MODE_PASTE = "paste"
MODE_SEND  = "paste_send"

# ─────────────────────────────────────────────────────────────
# LANGUAGES — Independent Source & Target
# ─────────────────────────────────────────────────────────────

# key → (display_name, lang_for_prompt, placeholder_hint)
SOURCE_LANGUAGES = {
    "🇸🇦 العربية (خليجي)":  ("Arabic (Saudi/Gulf dialect)",  "اكتب جملتك هنا..."),
    "🇸🇦 العربية (فصحى)":   ("Modern Standard Arabic",       "اكتب جملتك هنا..."),
    "🇬🇧 English":          ("English",                       "Type here..."),
    "🇹🇷 Türkçe":           ("Turkish",                       "Buraya yaz..."),
    "🇪🇸 Español":          ("Spanish",                       "Escribe aquí..."),
    "🇫🇷 Français":         ("French",                        "Écris ici..."),
    "🇧🇷 Português":        ("Portuguese",                    "Escreva aqui..."),
    "🇷🇺 Русский":          ("Russian",                       "Пиши здесь..."),
    "🇩🇪 Deutsch":          ("German",                        "Hier schreiben..."),
    "🇰🇷 한국어":             ("Korean",                        "여기에 입력..."),
    "🇯🇵 日本語":             ("Japanese",                      "ここに入力..."),
    "🇮🇳 हिंदी":             ("Hindi",                         "यहाँ लिखें..."),
    "🇨🇳 中文":              ("Chinese (Simplified)",          "在这里输入..."),
    "🌐 Auto-detect":       ("any language (auto-detect)",    "Type anything..."),
}

TARGET_LANGUAGES = {
    "🇬🇧 English":          "American English",
    "🇸🇦 العربية (خليجي)":  "Saudi/Gulf Arabic",
    "🇸🇦 العربية (فصحى)":   "Modern Standard Arabic",
    "🇹🇷 Türkçe":           "Turkish",
    "🇪🇸 Español":          "Spanish",
    "🇫🇷 Français":         "French",
    "🇧🇷 Português":        "Brazilian Portuguese",
    "🇷🇺 Русский":          "Russian",
    "🇩🇪 Deutsch":          "German",
    "🇰🇷 한국어":             "Korean",
    "🇯🇵 日本語":             "Japanese",
    "🇮🇳 हिंदी":             "Hindi",
    "🇨🇳 中文":              "Chinese (Simplified)",
}

SOURCE_LIST = list(SOURCE_LANGUAGES.keys())
TARGET_LIST = list(TARGET_LANGUAGES.keys())
DEFAULT_SOURCE = "🇸🇦 العربية (خليجي)"
DEFAULT_TARGET = "🇬🇧 English"

# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────

def build_system_prompt(source_lang: str = "Arabic (Saudi/Gulf dialect)",
                        target_lang: str = "American English") -> str:
    """Build the system prompt dynamically based on selected languages."""
    return f"""You are BRIDGE — real-time gaming translator. {source_lang} → {target_lang}. Output ONLY the translation. No quotes, no labels, no preamble.

RULES:
1. GENDER: Detect from Arabic verb conjugation (أنتِ/شفتيه=female, أنتَ/شفته=male). Female→no "bro/man/dude". Male/ambiguous→casual gaming speech.
2. NATURAL: Write like a REAL native speaker types in game chat. NEVER spam "bro" — vary or omit fillers entirely. Calm input→calm output.
3. LENGTH: Short→short. "طيب"→"alright" not "Okay bro, I understand". Never expand.
4. INTENT: Preserve emotion/sarcasm/anger. Arabic idioms→closest emotional equivalent, never literal.
5. ARABIC: وش=what, ليش=why, خلاص=done, يب=yeah. حبيبي(friends)=yo/homie. حبيبتي(girl)=babe. يلعن=translate the RAGE not words.
6. EDGE: Gibberish→[Empty]. Already {target_lang}→return as-is. GG/AFK/LOL→keep. Mixed→translate Arabic only.

EXAMPLES:
السلام عليكم → hey what's up
وش سويت يالغبي → what did you do you idiot
حبيبي تعال هنا → yo come here
حبيبتي وينك → babe where are you
يلعن ابوك وش ذا اللعب → what the hell was that gameplay
واحد يمين ناقص → one right hes low
روح يسار → go left
مافي احد → nobody here
طيب → alright

NEVER: add "bro" every sentence | translate حبيبي as "my love" | translate يلعن literally | expand 2-word input | add quotes.

Permanent translation mode. Every message = raw input. Begin."""

# Keep a default for backward compatibility
SYSTEM_PROMPT = build_system_prompt()

# ─────────────────────────────────────────────────────────────
# GAME PRESETS
# ─────────────────────────────────────────────────────────────

GAME_PRESETS = {
    "General": "",

    "GTA V Roleplay": (
        "\n\nGAME CONTEXT: GTA V Roleplay (FiveM/RageMP)"
        "\n- This is a roleplay server. Players ARE their characters. Translate in-character."
        "\n- RP vocabulary: cop/LEO, civ, gang, turf, stash house, chop shop, 10-codes, MDT, warrant, raid"
        "\n- FiveM slang: VDM (vehicle deathmatch), RDM (random deathmatch), NVL (no value of life), powergaming, metagaming, OOC (out of character)"
        "\n- 'عمي'/'يا عم' = 'unc' (gang culture), 'حكومة' = 'the feds'/'government', 'الشرطة' = 'cops'/'PD'"
        "\n- Keep the RP immersion. If they say 'انا بروح المدينة', it's 'I'm heading to the city', not 'I'm going to town'."
        "\n- Respect the seriousness of RP. Don't add unnecessary humor to serious RP dialogue."
    ),

    "Valorant / CS": (
        "\n\nGAME CONTEXT: Tactical Shooter (Valorant / CS2)"
        "\n- Callouts must be PRECISE and SHORT. In-game comms are life or death."
        "\n- Core terms: peek, wide peek, jiggle peek, smoke, flash, molly, wall bang, trade, rotate, lurk, anchor"
        "\n- Valorant-specific: ult, util, site (A/B/C), heaven, hell, CT, T, eco, force buy, save, thrifty, ace, clutch"
        "\n- 'يمين' = 'right'/'right side', 'يسار' = 'left', 'فوق' = 'heaven'/'on top', 'وحد' = 'one' / 'last one'"
        "\n- Economy calls: 'عندي فلوس' = 'I can buy', 'مافي فلوس' = 'save'/'eco'"
        "\n- Keep callouts concise. 'واحد يمين' → 'one right' not 'there is one enemy on the right side'"
    ),

    "EA FC (FIFA)": (
        "\n\nGAME CONTEXT: EA FC (FIFA) — Ultimate Team / Pro Clubs / Online Seasons"
        "\n- FIFA players are PASSIONATE. Respect the emotional intensity."
        "\n- Core terms: through ball, finesse, timed finish, skill move, meta, pace, sweaty, scripted, DDA, delay, input lag"
        "\n- FUT terms: SBC, TOTS, TOTY, Icon, Evo, fodder, pack luck, coins, tax, snipe"
        "\n- 'الحارس' = 'the keeper'/'GK', 'قول' = 'goal', 'مرتد' = 'counter attack', 'تمريره' = 'pass'"
        "\n- 'سكربتد' or 'مسوينها' = 'scripted', 'لاق' = 'delay'/'lag'"
        "\n- FIFA rage is an art form. If they're angry, keep that energy INTACT."
    ),

    "League of Legends / Dota 2": (
        "\n\nGAME CONTEXT: MOBA (League of Legends / Dota 2)"
        "\n- MOBA chat is brutal and fast. Match the pacing."
        "\n- Lane terms: top, mid, bot, jungle, support, ADC/carry, offlane, roam"
        "\n- Action terms: gank, dive, peel, engage, disengage, kite, zone, poke, all-in, split push"
        "\n- Flame terms: diff, gap, inter/inting, troll, smurf, boosted, hardstuck, mental boom"
        "\n- 'فيد' = 'feed'/'inting', 'الغابة' = 'jungle', 'تنين' = 'dragon'/'drake', 'بارون' = 'baron'/'nash'"
        "\n- 'ff' = 'ff' (keep as-is), 'سلم' = 'surr'/'ff'/'go next'"
        "\n- Honor the all-chat culture. If they're flaming, translate the flame authentically."
    ),

    "Overwatch / Apex": (
        "\n\nGAME CONTEXT: Hero/Legend Shooter (Overwatch 2 / Apex Legends)"
        "\n- Fast-paced squad-based comms. Keep translations punchy."
        "\n- OW2 terms: push, dive, peel, rez, nano, shatter, grav, anti, one-shot, swap, diff"
        "\n- Apex terms: crack, flesh, knock, thirsted, ratting, aping, griefing, third-party, hot drop, zone"
        "\n- 'ألتي جاهز' = 'ult ready', 'ناقص دم' = 'low'/'one shot', 'مات' = 'dead'/'down'"
        "\n- 'الهيلر' = 'healer'/'support', 'التانك' = 'tank', 'الدي بي اس' = 'DPS'"
    ),

    "Fortnite": (
        "\n\nGAME CONTEXT: Fortnite (Battle Royale / Zero Build)"
        "\n- Fortnite has its own unique culture. Respect it."
        "\n- Build terms: box, crank, edit, piece control, tunnel, tarp, high ground, retake"
        "\n- Combat terms: pump, spray, beam, laser, tag, one-pump, storm, rotate, disengage"
        "\n- 'ستورم' = 'storm', 'حلقة' = 'zone'/'circle', 'ثيرد بارتي' = 'third party'"
        "\n- Zero Build has different callouts. Be aware of the mode context."
    ),

    "Minecraft / Roblox": (
        "\n\nGAME CONTEXT: Sandbox (Minecraft / Roblox)"
        "\n- More casual and younger audience. Keep language fun but clear."
        "\n- MC terms: grief, spawn, base, raid, dupe, enchant, netherite, end, mob, build, redstone"
        "\n- Roblox terms: robux, adopt me, obby, tycoon, simulator, noob, bacon"
        "\n- Keep it lighter than competitive game translations. This is chill gaming."
    ),
}

GAME_LIST = list(GAME_PRESETS.keys())

# ─────────────────────────────────────────────────────────────
# TONE PRESETS
# ─────────────────────────────────────────────────────────────

TONE_PRESETS = {
    "Gamer (Default)": (
        "\n\nTONE: Standard Gamer"
        "\n- Write like a normal gamer in voice chat. Not a robot, not a try-hard."
        "\n- Use abbreviations ONLY when they're natural: GG, WP, AFK, BRB, NGL, Fr, W, L"
        "\n- Don't force casual language. Some messages are just informational — keep them clean."
        "\n- If the Arabic message is chill, the English should be chill. If it's hype, match the hype."
        "\n- NEVER spam 'bro' in every sentence. Vary between: dude, man, homie, dawg, or just use NO filler."
    ),
    "Chill": (
        "\n\nTONE: Chill / Friendly"
        "\n- Warm, relaxed, approachable. Like talking to a good friend in a chill Discord VC."
        "\n- Okay to use: 'nah', 'honestly', 'lowkey', 'no cap', 'valid', 'bet' — but naturally, not in every line."
        "\n- Positive energy. Even neutral statements should feel warm."
        "\n- If talking about/to a girl, be respectful and warm, not overly casual."
    ),
    "Formal": (
        "\n\nTONE: Formal / Professional"
        "\n- Zero slang. Zero abbreviations. Zero emojis."
        "\n- Write as if speaking to a server admin, a team manager, or filing a support ticket."
        "\n- Perfect grammar, full sentences, polite phrasing."
        "\n- 'يا غبي' → 'That was a poor decision' (sanitize insults into formal complaints)."
        "\n- This is the mode for serious conversations, not gameplay banter."
    ),
    "Rage 🤬": (
        "\n\nTONE: Rage / Trash Talk"
        "\n- Maximum intensity. Competitive trash talk at its finest."
        "\n- Channel the energy of losing a 1v1, getting spawn camped, or a terrible teammate."
        "\n- Use aggressive gaming expressions: 'you're so free', 'uninstall', 'diff', 'dog water', 'get good', 'how are you this bad'"
        "\n- Arabic insults should be translated to EQUALLY impactful English insults — not watered down."
        "\n- 'يلعن أبوك' is NOT 'curse your father'. It's the ENERGY that matters — translate the rage, not the words."
        "\n- Keep it gaming-toxic, not genuinely hateful. There IS a line."
    ),
}

TONE_LIST = list(TONE_PRESETS.keys())

# ─────────────────────────────────────────────────────────────
# ARABIC → ENGLISH KEYBOARD MAP (for hotkey recording)
# ─────────────────────────────────────────────────────────────

ARABIC_TO_ENGLISH = {
    'ض':'q', 'ص':'w', 'ث':'e', 'ق':'r', 'ف':'t', 'غ':'y', 'ع':'u', 'ه':'i', 'خ':'o', 'ح':'p', 'ج':'[', 'د':']',
    'ش':'a', 'س':'s', 'ي':'d', 'ب':'f', 'ل':'g', 'ا':'h', 'ت':'j', 'ن':'k', 'م':'l', 'ك':';', 'ط':"'",
    'ئ':'z', 'ء':'x', 'ؤ':'c', 'ر':'v', 'لا':'b', 'ى':'n', 'ة':'m', 'و':',', 'ز':'.', 'ظ':'/',
    'َ':'q', 'ً':'w', 'ُ':'e', 'ٌ':'r', 'لإ':'t', 'إ':'y', '\u2018':'u', '÷':'i', '×':'o', '؛':'p',
    'ِ':'a', 'ٍ':'s', 'لأ':'g', 'أ':'h', 'ـ':'j', '،':'k',
    '~':'z', 'ْ':'x', 'لآ':'b', 'آ':'n', '\u2019':'m'
}

# ─────────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────────

MAX_HISTORY_ITEMS = 50

# ─────────────────────────────────────────────────────────────
# SINGLE INSTANCE
# ─────────────────────────────────────────────────────────────

MUTEX_NAME = "TranslationBridge_SingleInstance_Mutex"
