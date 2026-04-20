/**
 * Translation Bridge — Landing Page Scripts
 * Scroll reveal + Multi-language support
 */

// ═══ TRANSLATIONS ═══
const T = {
    ar: { dir: 'rtl', font: "'Tajawal', 'Inter', system-ui, sans-serif",
        badge: 'أداة مجانية ومفتوحة المصدر',
        heroTitle: 'ترجم <span class="text-gradient">بسرعة البرق</span><br>وأنت تلعب',
        heroSub: 'اكتب بلغتك، يرسل بأي لغة ثانية. بدون لاق، بدون تأخير، بدون أي تعقيد.<br>يدعم 14+ لغة — مصمم خصيصاً للقيمرز.',
        dlBtn: '⬇️ تحميل مجاني', howBtn: 'شوف كيف يشتغل ↓',
        statLang: 'لغة مدعومة', statTime: 'وقت الترجمة',
        featTitle: 'ليش <span class="text-gradient">Translation Bridge</span>؟',
        featSub: 'مو بس ترجمة — نظام كامل مصمم للقيمنق',
        f1t: 'Zero-Lag Hotkeys', f1d: 'اختصارات مربوطة مباشرة بنظام ويندوز. مافي hook بطيء، مافي drop بالفريمات.',
        f2t: '14+ لغة', f2d: 'مو بس عربي لإنجليزي — اختار أي لغة مصدر وأي لغة هدف. أي لغة لأي لغة.',
        f3t: 'AI يفهم السياق', f3d: 'يستخدم Grok 4.1 Fast — يفهم العامية والجنس من تصريف الفعل. مو ترجمة حرفية.',
        f4t: 'Game Presets', f4d: 'قواميس جاهزة لـ GTA RP، Valorant، FIFA، LoL، Fortnite وغيرها.',
        f5t: 'Ghost UX', f5d: 'نافذة الإدخال تدمر نفسها فوراً بعد الإرسال. ترجع للعبة بأجزاء من الثانية.',
        f6t: '4 أنماط ترجمة', f6d: 'Gamer عادي، Chill مريح، Formal رسمي، أو Rage Mode 🔥',
        howTitle: 'كيف يشتغل؟', howSub: 'ثلاث خطوات وبس',
        s1t: 'اضغط الاختصار', s1d: 'الافتراضي <kbd>Ctrl+Shift+T</kbd> — تطلع نافذة صغيرة شفافة.',
        s2t: 'اكتب بلغتك', s2d: 'اكتب جملتك بأي لغة — عربي، تركي، كوري، أو أي شي.',
        s3t: 'Enter وخلاص', s3d: 'يترجم ويلصق ويرسل بالشات تلقائياً.',
        gamesTitle: 'يدعم <span class="text-gradient">ألعابك المفضلة</span>',
        anyGame: '+ أي لعبة ثانية',
        ctaTitle: 'جاهز تبدأ؟', ctaSub: 'حمّل Translation Bridge مجاناً وابدأ تتكلم بأي لغة بالشات.', ctaBtn: '⬇️ تحميل الحين',
        footer: 'Translation Bridge — مشروع مفتوح المصدر', report: 'بلّغ عن مشكلة',
        navFeat: 'المميزات', navHow: 'طريقة العمل', navGames: 'الألعاب'
    },
    en: { dir: 'ltr', font: "'Inter', 'Tajawal', system-ui, sans-serif",
        badge: 'Free & Open Source Tool',
        heroTitle: 'Translate at <span class="text-gradient">Lightning Speed</span><br>While You Play',
        heroSub: 'Type in your language, sends in any other. Zero lag, zero delay, zero hassle.<br>Supports 14+ languages — built for gamers.',
        dlBtn: '⬇️ Free Download', howBtn: 'See How it Works ↓',
        statLang: 'Languages', statTime: 'Translation Time',
        featTitle: 'Why <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'Not just translation — a full system built for gaming',
        f1t: 'Zero-Lag Hotkeys', f1d: 'Hotkeys hooked directly to Windows OS. No slow hooks, no frame drops.',
        f2t: '14+ Languages', f2d: 'Not just one pair — pick any source and target language. Any language to any language.',
        f3t: 'Context-Aware AI', f3d: 'Powered by Grok 4.1 Fast — understands slang, detects gender, translates intent.',
        f4t: 'Game Presets', f4d: 'Built-in dictionaries for GTA RP, Valorant, FIFA, LoL, Fortnite and more.',
        f5t: 'Ghost UX', f5d: 'Input window self-destructs after sending. Back in game in milliseconds.',
        f6t: '4 Translation Tones', f6d: 'Standard Gamer, Chill, Formal, or Rage Mode 🔥',
        howTitle: 'How it Works?', howSub: 'Just three steps',
        s1t: 'Press the Hotkey', s1d: 'Default <kbd>Ctrl+Shift+T</kbd> — a small transparent window appears.',
        s2t: 'Type in Your Language', s2d: 'Type your message in any language — Arabic, Turkish, Korean, anything.',
        s3t: 'Hit Enter, Done', s3d: 'Translates, pastes, and sends in chat automatically.',
        gamesTitle: 'Supports <span class="text-gradient">Your Favorite Games</span>',
        anyGame: '+ Any Other Game',
        ctaTitle: 'Ready to Start?', ctaSub: 'Download Translation Bridge for free and start communicating in any language.', ctaBtn: '⬇️ Download Now',
        footer: 'Translation Bridge — Open Source Project', report: 'Report an Issue',
        navFeat: 'Features', navHow: 'How it Works', navGames: 'Games'
    },
    tr: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Ücretsiz ve Açık Kaynak',
        heroTitle: '<span class="text-gradient">Işık Hızında</span><br>Çeviri Yap',
        heroSub: 'Kendi dilinde yaz, başka bir dilde gönder. Sıfır gecikme, sıfır sorun.<br>14+ dil destekli — oyuncular için tasarlandı.',
        dlBtn: '⬇️ Ücretsiz İndir', howBtn: 'Nasıl Çalışır? ↓',
        statLang: 'Dil', statTime: 'Çeviri Süresi',
        featTitle: 'Neden <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'Sadece çeviri değil — oyun için tasarlanmış tam bir sistem',
        f1t: 'Sıfır Gecikme', f1d: 'Kısayollar doğrudan Windows\'a bağlı. Yavaş hook yok, FPS düşüşü yok.',
        f2t: '14+ Dil', f2d: 'Herhangi bir kaynak ve hedef dil seçin. Herhangi bir dilden herhangi bir dile.',
        f3t: 'Bağlam Farkında AI', f3d: 'Grok 4.1 Fast ile çalışır — argo anlar, cinsiyet algılar, niyeti çevirir.',
        f4t: 'Oyun Hazır Ayarları', f4d: 'GTA RP, Valorant, FIFA, LoL, Fortnite ve daha fazlası için sözlükler.',
        f5t: 'Ghost UX', f5d: 'Giriş penceresi gönderdikten sonra kendini yok eder.',
        f6t: '4 Çeviri Tonu', f6d: 'Gamer, Rahat, Resmi veya Öfke Modu 🔥',
        howTitle: 'Nasıl Çalışır?', howSub: 'Sadece üç adım',
        s1t: 'Kısayola Bas', s1d: 'Varsayılan <kbd>Ctrl+Shift+T</kbd> — küçük şeffaf bir pencere açılır.',
        s2t: 'Kendi Dilinde Yaz', s2d: 'Mesajını herhangi bir dilde yaz.',
        s3t: 'Enter ve Bitti', s3d: 'Otomatik olarak çevirir, yapıştırır ve sohbette gönderir.',
        gamesTitle: '<span class="text-gradient">Favori Oyunlarınızı</span> Destekler',
        anyGame: '+ Diğer Oyunlar',
        ctaTitle: 'Başlamaya Hazır mısın?', ctaSub: 'Translation Bridge\'i ücretsiz indir ve herhangi bir dilde iletişim kur.', ctaBtn: '⬇️ Şimdi İndir',
        footer: 'Translation Bridge — Açık Kaynak Proje', report: 'Sorun Bildir',
        navFeat: 'Özellikler', navHow: 'Nasıl Çalışır', navGames: 'Oyunlar'
    },
    es: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Herramienta Gratuita y Open Source',
        heroTitle: 'Traduce a <span class="text-gradient">Velocidad Luz</span><br>Mientras Juegas',
        heroSub: 'Escribe en tu idioma, envía en otro. Sin lag, sin retraso, sin complicaciones.<br>Soporta 14+ idiomas — hecho para gamers.',
        dlBtn: '⬇️ Descarga Gratis', howBtn: 'Cómo Funciona ↓',
        statLang: 'Idiomas', statTime: 'Tiempo de Traducción',
        featTitle: '¿Por qué <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'No es solo traducción — un sistema completo para gaming',
        f1t: 'Zero-Lag Hotkeys', f1d: 'Atajos conectados directamente a Windows. Sin hooks lentos, sin caídas de FPS.',
        f2t: '14+ Idiomas', f2d: 'Elige cualquier idioma de origen y destino. Cualquier idioma a cualquier idioma.',
        f3t: 'IA Contextual', f3d: 'Grok 4.1 Fast — entiende jerga, detecta género, traduce la intención.',
        f4t: 'Presets de Juegos', f4d: 'Diccionarios para GTA RP, Valorant, FIFA, LoL, Fortnite y más.',
        f5t: 'Ghost UX', f5d: 'La ventana se autodestruye al enviar. Vuelves al juego en milisegundos.',
        f6t: '4 Tonos de Traducción', f6d: 'Gamer, Chill, Formal o Modo Rabia 🔥',
        howTitle: '¿Cómo Funciona?', howSub: 'Solo tres pasos',
        s1t: 'Presiona el Atajo', s1d: 'Por defecto <kbd>Ctrl+Shift+T</kbd> — aparece una ventana transparente.',
        s2t: 'Escribe en Tu Idioma', s2d: 'Escribe tu mensaje en cualquier idioma.',
        s3t: 'Enter y Listo', s3d: 'Traduce, pega y envía en el chat automáticamente.',
        gamesTitle: 'Soporta <span class="text-gradient">Tus Juegos Favoritos</span>',
        anyGame: '+ Cualquier Otro Juego',
        ctaTitle: '¿Listo para Empezar?', ctaSub: 'Descarga Translation Bridge gratis y comunícate en cualquier idioma.', ctaBtn: '⬇️ Descargar Ahora',
        footer: 'Translation Bridge — Proyecto Open Source', report: 'Reportar Problema',
        navFeat: 'Características', navHow: 'Cómo Funciona', navGames: 'Juegos'
    },
    fr: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Outil Gratuit et Open Source',
        heroTitle: 'Traduisez à <span class="text-gradient">Vitesse Éclair</span><br>En Jouant',
        heroSub: 'Écrivez dans votre langue, envoyez dans une autre. Zéro lag, zéro délai.<br>14+ langues — conçu pour les gamers.',
        dlBtn: '⬇️ Télécharger Gratuitement', howBtn: 'Comment Ça Marche ↓',
        statLang: 'Langues', statTime: 'Temps de Traduction',
        featTitle: 'Pourquoi <span class="text-gradient">Translation Bridge</span> ?',
        featSub: 'Pas juste de la traduction — un système complet pour le gaming',
        f1t: 'Zero-Lag Hotkeys', f1d: 'Raccourcis connectés directement à Windows. Pas de hooks lents, pas de drops FPS.',
        f2t: '14+ Langues', f2d: 'Choisissez n\'importe quelle langue source et cible. N\'importe quelle langue.',
        f3t: 'IA Contextuelle', f3d: 'Grok 4.1 Fast — comprend l\'argot, détecte le genre, traduit l\'intention.',
        f4t: 'Presets de Jeux', f4d: 'Dictionnaires pour GTA RP, Valorant, FIFA, LoL, Fortnite et plus.',
        f5t: 'Ghost UX', f5d: 'La fenêtre s\'autodétruit après l\'envoi. Retour au jeu en millisecondes.',
        f6t: '4 Tons de Traduction', f6d: 'Gamer, Chill, Formel ou Mode Rage 🔥',
        howTitle: 'Comment Ça Marche ?', howSub: 'Trois étapes seulement',
        s1t: 'Appuyez sur le Raccourci', s1d: 'Par défaut <kbd>Ctrl+Shift+T</kbd> — une petite fenêtre transparente apparaît.',
        s2t: 'Écrivez dans Votre Langue', s2d: 'Écrivez votre message dans n\'importe quelle langue.',
        s3t: 'Enter et C\'est Fait', s3d: 'Traduit, colle et envoie dans le chat automatiquement.',
        gamesTitle: 'Supporte <span class="text-gradient">Vos Jeux Préférés</span>',
        anyGame: '+ Tout Autre Jeu',
        ctaTitle: 'Prêt à Commencer ?', ctaSub: 'Téléchargez Translation Bridge gratuitement et communiquez dans n\'importe quelle langue.', ctaBtn: '⬇️ Télécharger',
        footer: 'Translation Bridge — Projet Open Source', report: 'Signaler un Problème',
        navFeat: 'Fonctionnalités', navHow: 'Comment Ça Marche', navGames: 'Jeux'
    },
    pt: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Ferramenta Gratuita e Open Source',
        heroTitle: 'Traduza na <span class="text-gradient">Velocidade da Luz</span><br>Enquanto Joga',
        heroSub: 'Escreva no seu idioma, envie em outro. Sem lag, sem atraso.<br>14+ idiomas — feito para gamers.',
        dlBtn: '⬇️ Download Grátis', howBtn: 'Como Funciona ↓',
        statLang: 'Idiomas', statTime: 'Tempo de Tradução',
        featTitle: 'Por que <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'Não é só tradução — um sistema completo para gaming',
        f1t: 'Zero-Lag Hotkeys', f1d: 'Atalhos conectados diretamente ao Windows. Sem hooks lentos, sem queda de FPS.',
        f2t: '14+ Idiomas', f2d: 'Escolha qualquer idioma de origem e destino. Qualquer idioma para qualquer idioma.',
        f3t: 'IA Contextual', f3d: 'Grok 4.1 Fast — entende gírias, detecta gênero, traduz a intenção.',
        f4t: 'Presets de Jogos', f4d: 'Dicionários para GTA RP, Valorant, FIFA, LoL, Fortnite e mais.',
        f5t: 'Ghost UX', f5d: 'A janela se autodestrói após enviar. Volta ao jogo em milissegundos.',
        f6t: '4 Tons de Tradução', f6d: 'Gamer, Chill, Formal ou Modo Raiva 🔥',
        howTitle: 'Como Funciona?', howSub: 'Apenas três passos',
        s1t: 'Pressione o Atalho', s1d: 'Padrão <kbd>Ctrl+Shift+T</kbd> — uma pequena janela transparente aparece.',
        s2t: 'Escreva no Seu Idioma', s2d: 'Escreva sua mensagem em qualquer idioma.',
        s3t: 'Enter e Pronto', s3d: 'Traduz, cola e envia no chat automaticamente.',
        gamesTitle: 'Suporta <span class="text-gradient">Seus Jogos Favoritos</span>',
        anyGame: '+ Qualquer Outro Jogo',
        ctaTitle: 'Pronto para Começar?', ctaSub: 'Baixe o Translation Bridge de graça e se comunique em qualquer idioma.', ctaBtn: '⬇️ Baixar Agora',
        footer: 'Translation Bridge — Projeto Open Source', report: 'Reportar Problema',
        navFeat: 'Recursos', navHow: 'Como Funciona', navGames: 'Jogos'
    },
    ru: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Бесплатный инструмент с открытым кодом',
        heroTitle: 'Переводи <span class="text-gradient">Молниеносно</span><br>Прямо в Игре',
        heroSub: 'Пиши на своём языке, отправляй на любом другом. Без лагов, без задержек.<br>14+ языков — создан для геймеров.',
        dlBtn: '⬇️ Скачать Бесплатно', howBtn: 'Как Это Работает ↓',
        statLang: 'Языков', statTime: 'Время Перевода',
        featTitle: 'Почему <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'Не просто перевод — полная система для гейминга',
        f1t: 'Zero-Lag Хоткеи', f1d: 'Горячие клавиши напрямую через Windows. Без тормозов, без просадок FPS.',
        f2t: '14+ Языков', f2d: 'Выбери любой язык-источник и язык-цель. Любой язык на любой язык.',
        f3t: 'ИИ с Контекстом', f3d: 'Grok 4.1 Fast — понимает сленг, определяет пол, переводит смысл.',
        f4t: 'Пресеты Игр', f4d: 'Словари для GTA RP, Valorant, FIFA, LoL, Fortnite и других.',
        f5t: 'Ghost UX', f5d: 'Окно ввода самоуничтожается после отправки. Возврат в игру за мс.',
        f6t: '4 Тона Перевода', f6d: 'Gamer, Chill, Формальный или Режим Ярости 🔥',
        howTitle: 'Как Это Работает?', howSub: 'Всего три шага',
        s1t: 'Нажми Горячую Клавишу', s1d: 'По умолчанию <kbd>Ctrl+Shift+T</kbd> — появляется прозрачное окно.',
        s2t: 'Пиши на Своём Языке', s2d: 'Пиши сообщение на любом языке.',
        s3t: 'Enter и Готово', s3d: 'Переводит, вставляет и отправляет в чат автоматически.',
        gamesTitle: 'Поддерживает <span class="text-gradient">Твои Любимые Игры</span>',
        anyGame: '+ Любая Другая Игра',
        ctaTitle: 'Готов Начать?', ctaSub: 'Скачай Translation Bridge бесплатно и общайся на любом языке.', ctaBtn: '⬇️ Скачать Сейчас',
        footer: 'Translation Bridge — Проект с открытым кодом', report: 'Сообщить о Проблеме',
        navFeat: 'Функции', navHow: 'Как Работает', navGames: 'Игры'
    },
    de: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'Kostenlos & Open Source',
        heroTitle: 'Übersetze <span class="text-gradient">Blitzschnell</span><br>Während du Spielst',
        heroSub: 'Schreib in deiner Sprache, sende in einer anderen. Null Lag, null Verzögerung.<br>14+ Sprachen — für Gamer gemacht.',
        dlBtn: '⬇️ Kostenlos Herunterladen', howBtn: 'Wie es Funktioniert ↓',
        statLang: 'Sprachen', statTime: 'Übersetzungszeit',
        featTitle: 'Warum <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'Nicht nur Übersetzung — ein komplettes System für Gaming',
        f1t: 'Zero-Lag Hotkeys', f1d: 'Hotkeys direkt mit Windows verbunden. Keine langsamen Hooks, keine FPS-Drops.',
        f2t: '14+ Sprachen', f2d: 'Wähle jede Quell- und Zielsprache. Jede Sprache in jede Sprache.',
        f3t: 'Kontext-KI', f3d: 'Grok 4.1 Fast — versteht Slang, erkennt Geschlecht, übersetzt Absicht.',
        f4t: 'Spiel-Presets', f4d: 'Wörterbücher für GTA RP, Valorant, FIFA, LoL, Fortnite und mehr.',
        f5t: 'Ghost UX', f5d: 'Eingabefenster zerstört sich nach dem Senden. Zurück im Spiel in ms.',
        f6t: '4 Übersetzungstöne', f6d: 'Gamer, Chill, Formal oder Wutmodus 🔥',
        howTitle: 'Wie Funktioniert es?', howSub: 'Nur drei Schritte',
        s1t: 'Drücke den Hotkey', s1d: 'Standard <kbd>Ctrl+Shift+T</kbd> — ein kleines transparentes Fenster erscheint.',
        s2t: 'Schreib in Deiner Sprache', s2d: 'Schreib deine Nachricht in beliebiger Sprache.',
        s3t: 'Enter und Fertig', s3d: 'Übersetzt, fügt ein und sendet automatisch im Chat.',
        gamesTitle: 'Unterstützt <span class="text-gradient">Deine Lieblingsspiele</span>',
        anyGame: '+ Jedes Andere Spiel',
        ctaTitle: 'Bereit Loszulegen?', ctaSub: 'Lade Translation Bridge kostenlos herunter und kommuniziere in jeder Sprache.', ctaBtn: '⬇️ Jetzt Herunterladen',
        footer: 'Translation Bridge — Open Source Projekt', report: 'Problem Melden',
        navFeat: 'Features', navHow: 'Wie es Funktioniert', navGames: 'Spiele'
    },
    ko: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: '무료 & 오픈소스 도구',
        heroTitle: '<span class="text-gradient">번개처럼 빠르게</span><br>게임하면서 번역',
        heroSub: '당신의 언어로 입력하면, 다른 언어로 전송됩니다. 렉 없음, 딜레이 없음.<br>14개 이상의 언어 지원 — 게이머를 위해 제작.',
        dlBtn: '⬇️ 무료 다운로드', howBtn: '작동 방식 보기 ↓',
        statLang: '지원 언어', statTime: '번역 시간',
        featTitle: '왜 <span class="text-gradient">Translation Bridge</span>?',
        featSub: '단순 번역이 아닌 — 게이밍을 위한 완전한 시스템',
        f1t: 'Zero-Lag 단축키', f1d: 'Windows에 직접 연결된 단축키. 느린 훅 없음, FPS 드롭 없음.',
        f2t: '14+ 언어', f2d: '원하는 소스와 타겟 언어를 선택. 어떤 언어든 어떤 언어로든.',
        f3t: '맥락 이해 AI', f3d: 'Grok 4.1 Fast — 속어 이해, 성별 감지, 의도 번역.',
        f4t: '게임 프리셋', f4d: 'GTA RP, 발로란트, FIFA, LoL, 포트나이트 등 사전 내장.',
        f5t: 'Ghost UX', f5d: '입력 창이 전송 후 즉시 자폭. 밀리초 내에 게임 복귀.',
        f6t: '4가지 번역 톤', f6d: '게이머, 칠, 포멀, 또는 분노 모드 🔥',
        howTitle: '어떻게 작동하나요?', howSub: '단 세 단계',
        s1t: '단축키 누르기', s1d: '기본 <kbd>Ctrl+Shift+T</kbd> — 작은 투명 창이 나타남.',
        s2t: '당신의 언어로 입력', s2d: '어떤 언어로든 메시지를 입력하세요.',
        s3t: 'Enter 누르면 끝', s3d: '자동으로 번역, 붙여넣기, 채팅에 전송.',
        gamesTitle: '<span class="text-gradient">좋아하는 게임</span> 지원',
        anyGame: '+ 다른 모든 게임',
        ctaTitle: '시작할 준비 됐나요?', ctaSub: 'Translation Bridge를 무료 다운로드하고 어떤 언어로든 소통하세요.', ctaBtn: '⬇️ 지금 다운로드',
        footer: 'Translation Bridge — 오픈소스 프로젝트', report: '문제 신고',
        navFeat: '기능', navHow: '작동 방식', navGames: '게임'
    },
    ja: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: '無料＆オープンソース',
        heroTitle: '<span class="text-gradient">超高速</span>で翻訳<br>ゲーム中でも',
        heroSub: 'あなたの言語で入力、別の言語で送信。ラグなし、遅延なし。<br>14以上の言語対応 — ゲーマーのために設計。',
        dlBtn: '⬇️ 無料ダウンロード', howBtn: '使い方を見る ↓',
        statLang: '対応言語', statTime: '翻訳時間',
        featTitle: 'なぜ <span class="text-gradient">Translation Bridge</span>？',
        featSub: 'ただの翻訳ではない — ゲーミング用の完全システム',
        f1t: 'Zero-Lag ホットキー', f1d: 'Windows直結のショートカット。遅いフック無し、FPSドロップ無し。',
        f2t: '14+ 言語', f2d: '好きなソースとターゲット言語を選択。どの言語からでもどの言語へでも。',
        f3t: 'コンテキスト認識AI', f3d: 'Grok 4.1 Fast — スラング理解、性別検出、意図を翻訳。',
        f4t: 'ゲームプリセット', f4d: 'GTA RP、Valorant、FIFA、LoL、Fortnite等の辞書内蔵。',
        f5t: 'Ghost UX', f5d: '入力ウィンドウは送信後に即自己破壊。ミリ秒でゲームに復帰。',
        f6t: '4つの翻訳トーン', f6d: 'ゲーマー、チル、フォーマル、レイジモード 🔥',
        howTitle: 'どう動くの？', howSub: 'たった3ステップ',
        s1t: 'ホットキーを押す', s1d: 'デフォルト <kbd>Ctrl+Shift+T</kbd> — 小さな透明ウィンドウが出現。',
        s2t: 'あなたの言語で入力', s2d: 'どの言語でもメッセージを入力。',
        s3t: 'Enter で完了', s3d: '自動で翻訳、ペースト、チャットに送信。',
        gamesTitle: '<span class="text-gradient">お気に入りのゲーム</span>に対応',
        anyGame: '+ その他のゲーム',
        ctaTitle: '始める準備はOK？', ctaSub: 'Translation Bridgeを無料ダウンロードして、どの言語でもコミュニケーション。', ctaBtn: '⬇️ 今すぐダウンロード',
        footer: 'Translation Bridge — オープンソースプロジェクト', report: '問題を報告',
        navFeat: '機能', navHow: '使い方', navGames: 'ゲーム'
    },
    zh: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: '免费开源工具',
        heroTitle: '<span class="text-gradient">闪电般</span>翻译<br>边玩边用',
        heroSub: '用你的语言输入，用其他语言发送。零延迟，零卡顿。<br>支持14+种语言 — 专为玩家打造。',
        dlBtn: '⬇️ 免费下载', howBtn: '看看怎么用 ↓',
        statLang: '支持语言', statTime: '翻译时间',
        featTitle: '为什么选 <span class="text-gradient">Translation Bridge</span>？',
        featSub: '不只是翻译 — 专为游戏打造的完整系统',
        f1t: '零延迟热键', f1d: '热键直连Windows系统。无慢钩子，无帧率下降。',
        f2t: '14+ 语言', f2d: '任选源语言和目标语言。任何语言到任何语言。',
        f3t: '上下文感知AI', f3d: 'Grok 4.1 Fast — 理解俚语，检测性别，翻译意图。',
        f4t: '游戏预设', f4d: '内置GTA RP、Valorant、FIFA、LoL、Fortnite等词典。',
        f5t: 'Ghost UX', f5d: '输入窗口发送后自毁。毫秒级回到游戏。',
        f6t: '4种翻译语气', f6d: '玩家、休闲、正式或暴怒模式 🔥',
        howTitle: '怎么用？', howSub: '只需三步',
        s1t: '按下快捷键', s1d: '默认 <kbd>Ctrl+Shift+T</kbd> — 弹出小透明窗口。',
        s2t: '用你的语言输入', s2d: '用任何语言输入你的消息。',
        s3t: '回车搞定', s3d: '自动翻译、粘贴、在聊天中发送。',
        gamesTitle: '支持 <span class="text-gradient">你最爱的游戏</span>',
        anyGame: '+ 其他任何游戏',
        ctaTitle: '准备开始了吗？', ctaSub: '免费下载Translation Bridge，用任何语言交流。', ctaBtn: '⬇️ 立即下载',
        footer: 'Translation Bridge — 开源项目', report: '报告问题',
        navFeat: '功能', navHow: '使用方法', navGames: '游戏'
    },
    hi: { dir: 'ltr', font: "'Inter', system-ui, sans-serif",
        badge: 'मुफ्त और ओपन सोर्स टूल',
        heroTitle: '<span class="text-gradient">बिजली की रफ्तार</span> से<br>अनुवाद करो खेलते-खेलते',
        heroSub: 'अपनी भाषा में लिखो, किसी और भाषा में भेजो। जीरो लैग, जीरो डिले।<br>14+ भाषाएं — गेमर्स के लिए बनाया गया।',
        dlBtn: '⬇️ मुफ्त डाउनलोड', howBtn: 'कैसे काम करता है ↓',
        statLang: 'भाषाएं', statTime: 'अनुवाद समय',
        featTitle: 'क्यों <span class="text-gradient">Translation Bridge</span>?',
        featSub: 'सिर्फ अनुवाद नहीं — गेमिंग के लिए पूरा सिस्टम',
        f1t: 'Zero-Lag हॉटकी', f1d: 'हॉटकी सीधे Windows से जुड़ी। कोई स्लो हुक नहीं, कोई FPS ड्रॉप नहीं।',
        f2t: '14+ भाषाएं', f2d: 'कोई भी सोर्स और टारगेट भाषा चुनो। कोई भी भाषा से कोई भी भाषा में।',
        f3t: 'कॉन्टेक्स्ट-अवेयर AI', f3d: 'Grok 4.1 Fast — स्लैंग समझता है, जेंडर डिटेक्ट करता है।',
        f4t: 'गेम प्रीसेट', f4d: 'GTA RP, Valorant, FIFA, LoL, Fortnite आदि के लिए डिक्शनरी।',
        f5t: 'Ghost UX', f5d: 'इनपुट विंडो भेजने के बाद खुद नष्ट हो जाती है।',
        f6t: '4 अनुवाद टोन', f6d: 'गेमर, चिल, फॉर्मल, या रेज मोड 🔥',
        howTitle: 'कैसे काम करता है?', howSub: 'बस तीन कदम',
        s1t: 'हॉटकी दबाओ', s1d: 'डिफ़ॉल्ट <kbd>Ctrl+Shift+T</kbd> — एक छोटी ट्रांसपेरेंट विंडो आती है।',
        s2t: 'अपनी भाषा में लिखो', s2d: 'किसी भी भाषा में अपना मैसेज लिखो।',
        s3t: 'Enter और बस', s3d: 'ऑटोमैटिक ट्रांसलेट, पेस्ट और चैट में भेजता है।',
        gamesTitle: '<span class="text-gradient">आपके पसंदीदा गेम</span> सपोर्ट',
        anyGame: '+ कोई भी अन्य गेम',
        ctaTitle: 'शुरू करने के लिए तैयार?', ctaSub: 'Translation Bridge मुफ्त डाउनलोड करो और किसी भी भाषा में बात करो।', ctaBtn: '⬇️ अभी डाउनलोड करो',
        footer: 'Translation Bridge — ओपन सोर्स प्रोजेक्ट', report: 'समस्या रिपोर्ट करें',
        navFeat: 'फीचर्स', navHow: 'कैसे काम करता है', navGames: 'गेम्स'
    }
};

const LANG_LABELS = {
    ar: '🇸🇦 العربية', en: '🇬🇧 English', tr: '🇹🇷 Türkçe', es: '🇪🇸 Español',
    fr: '🇫🇷 Français', pt: '🇧🇷 Português', ru: '🇷🇺 Русский', de: '🇩🇪 Deutsch',
    ko: '🇰🇷 한국어', ja: '🇯🇵 日本語', zh: '🇨🇳 中文', hi: '🇮🇳 हिंदी'
};

let currentLang = 'ar';
let menuOpen = false;

function toggleLangMenu() {
    const menu = document.getElementById('lang-menu');
    menuOpen = !menuOpen;
    menu.style.display = menuOpen ? 'flex' : 'none';
}

function setLang(lang) {
    currentLang = lang;
    const t = T[lang];
    if (!t) return;
    const html = document.documentElement;
    html.setAttribute('lang', lang);
    html.setAttribute('dir', t.dir);
    document.body.style.fontFamily = t.font;

    // Map IDs to translation keys
    const map = {
        'tx-badge': 'badge', 'tx-hero-title': 'heroTitle', 'tx-hero-sub': 'heroSub',
        'tx-dl-btn': 'dlBtn', 'tx-how-btn': 'howBtn',
        'tx-stat-lang': 'statLang', 'tx-stat-time': 'statTime',
        'tx-feat-title': 'featTitle', 'tx-feat-sub': 'featSub',
        'tx-f1t': 'f1t', 'tx-f1d': 'f1d', 'tx-f2t': 'f2t', 'tx-f2d': 'f2d',
        'tx-f3t': 'f3t', 'tx-f3d': 'f3d', 'tx-f4t': 'f4t', 'tx-f4d': 'f4d',
        'tx-f5t': 'f5t', 'tx-f5d': 'f5d', 'tx-f6t': 'f6t', 'tx-f6d': 'f6d',
        'tx-how-title': 'howTitle', 'tx-how-sub': 'howSub',
        'tx-s1t': 's1t', 'tx-s1d': 's1d', 'tx-s2t': 's2t', 'tx-s2d': 's2d',
        'tx-s3t': 's3t', 'tx-s3d': 's3d',
        'tx-games-title': 'gamesTitle', 'tx-any-game': 'anyGame',
        'tx-cta-title': 'ctaTitle', 'tx-cta-sub': 'ctaSub', 'tx-cta-btn': 'ctaBtn',
        'tx-footer': 'footer', 'tx-report': 'report',
        'tx-nav-feat': 'navFeat', 'tx-nav-how': 'navHow', 'tx-nav-games': 'navGames'
    };

    for (const [id, key] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el && t[key]) el.innerHTML = t[key];
    }

    // Update toggle button label
    document.getElementById('lang-toggle').textContent = LANG_LABELS[lang] || lang.toUpperCase();

    // Close menu
    menuOpen = false;
    document.getElementById('lang-menu').style.display = 'none';
}

// Close menu on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.lang-selector')) {
        menuOpen = false;
        const menu = document.getElementById('lang-menu');
        if (menu) menu.style.display = 'none';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // ── Scroll Reveal ──
    const revealElements = document.querySelectorAll(
        '.feature-card, .step, .game-chip, .section-title, .section-subtitle'
    );
    revealElements.forEach(el => el.classList.add('reveal'));
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15, rootMargin: '0px 0px -50px 0px' }
    );
    revealElements.forEach(el => observer.observe(el));

    // ── Smooth scroll ──
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(anchor.getAttribute('href'));
            if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });

    // ── Navbar bg ──
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        navbar.style.background = window.scrollY > 50
            ? 'rgba(10, 10, 10, 0.95)'
            : 'rgba(10, 10, 10, 0.8)';
    });
});
