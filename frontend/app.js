
// API base:
// - local override: localStorage.apiBase
// - localhost dev:  http://127.0.0.1:5000
// - production:     https://api.<root-domain>
const _host = window.location.hostname || '';
const _isLocal = _host === 'localhost' || _host === '127.0.0.1';
const _rootHost = _host.replace(/^www\./, '');
const _savedApiBaseRaw = (localStorage.getItem('apiBase') || '').trim();
const _savedApiBase = _savedApiBaseRaw.replace(/\/+$/, '');
const _savedApiHost = (() => {
  if (!_savedApiBase) return '';
  try {
    return new URL(_savedApiBase).hostname.toLowerCase();
  } catch {
    return '';
  }
})();
const _savedApiAllowed = _isLocal
  ? /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(_savedApiBase)
  : false;
const _defaultApiBase = _isLocal
  ? 'http://127.0.0.1:5000'
  : `${window.location.protocol}//api.${_rootHost}`;
const API_BASE = _savedApiAllowed ? _savedApiBase : _defaultApiBase;
const SUPPORTED_LANGS = ['ru', 'en', 'es', 'de', 'fr', 'uk'];
const CONTENT_LANG_OPTIONS = [
  { value: 'ru', label: 'Русский' },
  { value: 'ua', label: 'Українська' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Espanol' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Francais' },
];
const LANGUAGE_LABELS = {
  ru: 'Русский',
  en: 'English',
  es: 'Espanol',
  de: 'Deutsch',
  fr: 'Francais',
  uk: 'Українська',
};
const DIRECTOR_NICHE_ENGINE = window.AutoSocialNiches || {};
const AUTOSOCIAL_RELEASE_MARKER_2026 = 'AUTOSOCIAL_RELEASE_MARKER_2026';
const AUTOSOCIAL_DASHBOARD_QUICKACTIONS_V1 = 'AUTOSOCIAL_DASHBOARD_QUICKACTIONS_V1';
const AUTOSOCIAL_CREATE_FLOW_V1 = 'AUTOSOCIAL_CREATE_FLOW_V1';
const DIRECTOR_TOPIC_IDEA_COUNT = 5;
const DIRECTOR_NICHE_OPTIONS = typeof DIRECTOR_NICHE_ENGINE.getNicheOptions === 'function'
  ? DIRECTOR_NICHE_ENGINE.getNicheOptions()
  : [{ value: 'smm_marketing', label: 'SMM и маркетинг' }];
const DEFAULT_DIRECTOR_NICHE = String(DIRECTOR_NICHE_ENGINE.DEFAULT_NICHE_ID || DIRECTOR_NICHE_OPTIONS[0]?.value || 'smm_marketing').trim();
const MARKETING_PRICING_PLANS = [
  { key: 'free', name: 'Free Trial 7 days', price: '€0', desc: 'Попробовать сценарий работы без карты и лишних расходов.', points: ['30 постов', '3 видео', '1 рабочее пространство'], cta: 'Начать trial' },
  { key: 'starter', name: 'Starter', price: '€29', desc: 'Для малого бизнеса, которому нужен стабильный контент и автопостинг.', points: ['150 постов/мес', '10 видео/мес', '2 рабочих пространства'], cta: 'Выбрать Starter' },
  { key: 'growth', name: 'Growth', price: '€79', desc: 'Основной тариф для регулярного контента, видео и роста без ручной рутины.', points: ['600 постов/мес', '40 видео/мес', '5 рабочих пространств'], cta: 'Выбрать Growth' },
  { key: 'agency', name: 'Agency', price: '€199', desc: 'Для агентств и multi-client работы с большим объёмом контента.', points: ['2000 постов/мес', '150 видео/мес', 'Безлимит рабочих пространств'], cta: 'Выбрать Agency' },
];
const DASHBOARD_QUICK_ACTIONS = [
  { key: 'weekly_plan', title: 'Контент-план на 7 дней', description: 'Быстрый недельный план публикаций для вашей ниши.', buttonLabel: 'Создать план', accent: '7D', size: 'large', contentType: 'post' },
  { key: 'monthly_plan', title: 'Контент-план на 30 дней', description: 'Полный контент-план на месяц с идеями и структурой.', buttonLabel: 'Создать план', accent: '30D', size: 'large', contentType: 'post' },
  { key: 'video_week_plan', title: 'Видео-посты на 7 дней', description: 'Недельный видеоплан с темами, слотами и CTA.', buttonLabel: 'Создать план', accent: 'V7', size: 'large', contentType: 'video' },
  { key: 'video_month_plan', title: 'Видео-посты на 30 дней', description: 'Месячный видеоплан для регулярного short-form контента.', buttonLabel: 'Создать план', accent: 'V30', size: 'large', contentType: 'video' },
  { key: 'post_series', title: 'Серия постов', description: 'Готовая серия постов под ваш бизнес и формат контента.', buttonLabel: 'Сгенерировать', accent: 'POST', size: 'large', contentType: 'post' },
  { key: 'video_series', title: 'Серия видео', description: 'Идеи и структура коротких видео для соцсетей.', buttonLabel: 'Сгенерировать', accent: 'VIDEO', size: 'large', contentType: 'video' },
  { key: 'hooks_pack', title: 'Hooks', description: 'Цепляющие начала для постов, Reels и Shorts.', buttonLabel: 'Создать hooks', accent: 'HOOK', size: 'small', contentType: 'post' },
  { key: 'cta_pack', title: 'CTA', description: 'Призывы к действию для вовлечения и заявок.', buttonLabel: 'Создать CTA', accent: 'CTA', size: 'small', contentType: 'post' },
];
const LOGIN_I18N = {
  ru: {
    language_label: 'Язык',
    form_title_register: 'Создать аккаунт',
    form_title_login: 'Войти',
    flow_title_register: 'Подтвердите регистрацию',
    flow_title_login: 'Подтвердите вход',
    submit_get_code: 'Получить код',
    submit_verify_code: 'Подтвердить код',
    switch_text_register: 'Уже есть аккаунт?',
    switch_text_login: 'Нет аккаунта?',
    switch_label_register: 'Войти',
    switch_label_login: 'Создать',
    auth_hint_default: 'Введите email и пароль. Отправим 4-значный код на почту.',
    auth_hint_code_prefix: 'Код отправлен на',
    hero_title: 'AutoSocial.tech — AI-ассистент для контента и автопостинга.',
    hero_subtitle: 'Создавайте контент, планируйте публикации и управляйте Facebook + Instagram из одного места — автоматически.',
    hero_cta: 'Начать бесплатно по email',
    hero_microcopy: 'Без привязки карт сейчас — начните с Free плана.',
    features_title: 'Всё, что нужно для SMM — в одной панели',
    features_1: 'Генерация уникального контента на основе AI',
    features_2: 'Автопостинг по расписанию в Facebook и Instagram',
    features_3: 'Интеллектуальные шаблоны для любых ниш',
    features_4: 'Планировщик, который думает за вас',
    features_5: 'Метрики и аналитика для роста',
    how_title: 'Как AutoSocial.tech помогает вашему бизнесу',
    how_1_title: 'Создавайте контент за секунды',
    how_1_text: 'Введите тему или ключевое сообщение — получите готовые посты с хештегами и CTA.',
    how_2_title: 'Планируйте. Автоматизируйте. Забывайте о ручной публикации',
    how_2_text: 'Настройте расписание — и система публикует сама.',
    how_3_title: 'Следите за эффективностью',
    how_3_text: 'Показы, вовлечённость, рост аудитории — всё в одной панели.',
    trust_title: 'Почему маркетологи выбирают AutoSocial.tech',
    trust_1: 'Экономит до 10 часов в неделю на публикациях',
    trust_2: 'Генерирует контент, основанный на бест-практиках SMM',
    trust_3: 'Интеграции с Facebook + Instagram Business',
    trust_4: 'SSL / GDPR-ready. Готово к оплате.',
    quote: '“AutoSocial.tech перевёл наши соцсети на автопилот — посты стали чаще, а вовлечённость выросла.” — Маркетолог, SMB',
    final_title: 'Готовы автоматизировать свои соцсети?',
    final_cta_account: 'Создать аккаунт по email',
    final_cta_pricing: 'Узнать тарифы',
    final_note: 'Начните с Free Trial. Перейти на Growth можно в любой момент.',
    footer_pricing: 'Тарифы',
    footer_privacy: 'Политика конфиденциальности',
    footer_support: 'Поддержка',
    field_email: 'Email',
    field_password: 'Пароль',
    field_code: 'Код из письма',
    placeholder_email: 'you@company.com',
    placeholder_password: 'Минимум 8 символов',
    placeholder_code: '4 цифры',
    resend_code: 'Отправить код повторно',
    back_to_auth: 'Изменить email/пароль',
  },
  en: {
    language_label: 'Language',
    form_title_register: 'Create account',
    form_title_login: 'Sign in',
    flow_title_register: 'Confirm registration',
    flow_title_login: 'Confirm sign-in',
    submit_get_code: 'Get code',
    submit_verify_code: 'Verify code',
    switch_text_register: 'Already have an account?',
    switch_text_login: "Don't have an account?",
    switch_label_register: 'Sign in',
    switch_label_login: 'Create',
    auth_hint_default: 'Enter email and password. We will send a 4-digit code.',
    auth_hint_code_prefix: 'Code sent to',
    hero_title: 'AutoSocial.tech — AI assistant for content and autoposting.',
    hero_subtitle: 'Create content, schedule posts, and manage Facebook + Instagram from one place automatically.',
    hero_cta: 'Start free with email',
    hero_microcopy: 'No card required now — start on the Free plan.',
    features_title: 'Everything you need for SMM in one panel',
    features_1: 'AI-powered unique content generation',
    features_2: 'Scheduled autoposting to Facebook and Instagram',
    features_3: 'Smart templates for any niche',
    features_4: 'A planner that thinks ahead for you',
    features_5: 'Metrics and analytics for growth',
    how_title: 'How AutoSocial.tech helps your business',
    how_1_title: 'Create content in seconds',
    how_1_text: 'Enter a topic or key message and get ready-to-post drafts with hashtags and CTA.',
    how_2_title: 'Plan. Automate. Stop manual posting',

    how_3_title: 'Track performance',
    how_3_text: 'Reach, engagement, and audience growth in one dashboard.',
    trust_title: 'Why marketers choose AutoSocial.tech',
    trust_1: 'Saves up to 10 hours per week on publishing',
    trust_2: 'Generates content based on SMM best practices',
    trust_3: 'Facebook + Instagram Business integrations',
    trust_4: 'SSL / GDPR-ready. Billing-ready.',
    quote: '"AutoSocial.tech put our social media on autopilot — posting got consistent and engagement grew." — SMB marketer',
    final_title: 'Ready to automate your social media?',
    final_cta_account: 'Create account with email',
    final_cta_pricing: 'See pricing',
    final_note: 'Start with Free Trial. Upgrade to Growth anytime.',
    footer_pricing: 'Pricing',
    footer_privacy: 'Privacy policy',
    footer_support: 'Support',
    field_email: 'Email',
    field_password: 'Password',
    field_code: 'Code from email',
    placeholder_email: 'you@company.com',
    placeholder_password: 'Minimum 8 characters',
    placeholder_code: '4 digits',
    resend_code: 'Resend code',
    back_to_auth: 'Change email/password',
  },
  es: {
    language_label: 'Idioma',
    form_title_register: 'Crear cuenta',
    form_title_login: 'Iniciar sesion',
    flow_title_register: 'Confirmar registro',
    flow_title_login: 'Confirmar inicio de sesion',
    submit_get_code: 'Obtener codigo',
    submit_verify_code: 'Confirmar codigo',
    switch_text_register: '?Ya tienes cuenta?',
    switch_text_login: '?No tienes cuenta?',
    switch_label_register: 'Entrar',
    switch_label_login: 'Crear',
    auth_hint_default: 'Introduce email y contrasena. Enviaremos un codigo de 4 digitos.',
    auth_hint_code_prefix: 'Codigo enviado a',
    hero_title: 'AutoSocial.tech — asistente de IA para contenido y autopublicacion.',
    hero_subtitle: 'Crea contenido, programa publicaciones y gestiona Facebook + Instagram desde un solo lugar automaticamente.',
    hero_cta: 'Empezar gratis con email',
    hero_microcopy: 'Sin tarjeta por ahora: empieza con el plan Free.',
    features_title: 'Todo lo que necesitas para SMM en un panel',
    features_1: 'Generacion de contenido unico con IA',
    features_2: 'Autopublicacion programada en Facebook e Instagram',
    features_3: 'Plantillas inteligentes para cualquier nicho',
    features_4: 'Planificador que piensa por ti',
    features_5: 'Metricas y analitica para crecer',
    how_title: 'Como AutoSocial.tech ayuda a tu negocio',
    how_1_title: 'Crea contenido en segundos',
    how_1_text: 'Introduce un tema o mensaje clave y obten borradores con hashtags y CTA.',
    how_2_title: 'Planifica. Automatiza. Olvida la publicacion manual',
    how_2_text: 'Configura un horario y la plataforma publica sola.',
    how_3_title: 'Mide resultados',
    how_3_text: 'Alcance, interaccion y crecimiento en un solo panel.',
    trust_title: 'Por que los marketers eligen AutoSocial.tech',
    trust_1: 'Ahorra hasta 10 horas por semana en publicaciones',
    trust_2: 'Genera contenido con buenas practicas de SMM',
    trust_3: 'Integraciones con Facebook + Instagram Business',
    trust_4: 'Listo para SSL / GDPR y pagos.',
    quote: '"AutoSocial.tech puso nuestras redes en piloto automatico: publicamos mas y mejoro la interaccion." — Marketer SMB',
    final_title: '?Listo para automatizar tus redes sociales?',
    final_cta_account: 'Crear cuenta con email',
    final_cta_pricing: 'Ver precios',
    final_note: 'Empieza con Free Trial. Cambia a Growth cuando quieras.',
    footer_pricing: 'Precios',
    footer_privacy: 'Politica de privacidad',
    footer_support: 'Soporte',
    field_email: 'Email',
    field_password: 'Contrasena',
    field_code: 'Codigo del correo',
    placeholder_email: 'you@company.com',
    placeholder_password: 'Minimo 8 caracteres',
    placeholder_code: '4 digitos',
    resend_code: 'Reenviar codigo',
    back_to_auth: 'Cambiar email/contrasena',
  },
  de: {
    language_label: 'Sprache',
    form_title_register: 'Konto erstellen',
    form_title_login: 'Anmelden',
    flow_title_register: 'Registrierung bestatigen',
    flow_title_login: 'Anmeldung bestatigen',
    submit_get_code: 'Code erhalten',
    submit_verify_code: 'Code bestatigen',
    switch_text_register: 'Schon ein Konto?',
    switch_text_login: 'Noch kein Konto?',
    switch_label_register: 'Anmelden',
    switch_label_login: 'Erstellen',
    auth_hint_default: 'E-Mail und Passwort eingeben. Wir senden einen 4-stelligen Code.',
    auth_hint_code_prefix: 'Code gesendet an',
    hero_title: 'AutoSocial.tech — KI-Assistent fur Content und Auto-Posting.',
    hero_subtitle: 'Inhalte erstellen, Beitrage planen und Facebook + Instagram automatisch an einem Ort verwalten.',
    hero_cta: 'Kostenlos mit E-Mail starten',
    hero_microcopy: 'Keine Karte notig — starte mit dem Free-Plan.',
    features_title: 'Alles fur SMM in einem Dashboard',
    features_1: 'Einzigartige Content-Erstellung mit KI',
    features_2: 'Geplantes Auto-Posting fur Facebook und Instagram',
    features_3: 'Intelligente Vorlagen fur jede Nische',
    features_4: 'Planer, der fur dich vorausdenkt',
    features_5: 'Metriken und Analysen fur Wachstum',
    how_title: 'So hilft AutoSocial.tech deinem Business',
    how_1_title: 'Content in Sekunden erstellen',
    how_1_text: 'Thema oder Kernbotschaft eingeben und fertige Entwurfe mit Hashtags und CTA erhalten.',
    how_2_title: 'Planen. Automatisieren. Manuelles Posten vergessen',
    how_2_text: 'Zeitplan festlegen und die Plattform veroffentlicht automatisch.',
    how_3_title: 'Leistung verfolgen',
    how_3_text: 'Reichweite, Engagement und Wachstum in einem Panel.',
    trust_title: 'Warum Marketer AutoSocial.tech wahlen',
    trust_1: 'Spart bis zu 10 Stunden pro Woche beim Publizieren',
    trust_2: 'Generiert Content nach SMM-Best-Practices',
    trust_3: 'Integrationen mit Facebook + Instagram Business',
    trust_4: 'SSL / DSGVO-ready. Zahlungsbereit.',
    quote: '"AutoSocial.tech hat unsere Socials auf Autopilot gebracht: mehr Konsistenz und hoheres Engagement." — SMB-Marketer',
    final_title: 'Bereit, deine Social Media zu automatisieren?',
    final_cta_account: 'Konto per E-Mail erstellen',
    final_cta_pricing: 'Preise ansehen',
    final_note: 'Mit Free Trial starten. Jederzeit auf Growth wechseln.',
    footer_pricing: 'Preise',
    footer_privacy: 'Datenschutz',
    footer_support: 'Support',
    field_email: 'E-Mail',
    field_password: 'Passwort',
    field_code: 'Code aus E-Mail',
    placeholder_email: 'you@company.com',
    placeholder_password: 'Mindestens 8 Zeichen',
    placeholder_code: '4 Ziffern',
    resend_code: 'Code erneut senden',
    back_to_auth: 'E-Mail/Passwort andern',
  },
  fr: {
    language_label: 'Langue',
    form_title_register: 'Creer un compte',
    form_title_login: 'Se connecter',
    flow_title_register: "Confirmer l'inscription",
    flow_title_login: 'Confirmer la connexion',
    submit_get_code: 'Obtenir le code',
    submit_verify_code: 'Confirmer le code',
    switch_text_register: 'Vous avez deja un compte ?',
    switch_text_login: "Vous n'avez pas de compte ?",
    switch_label_register: 'Se connecter',
    switch_label_login: 'Creer',
    auth_hint_default: 'Entrez e-mail et mot de passe. Nous enverrons un code a 4 chiffres.',
    auth_hint_code_prefix: 'Code envoye a',
    hero_title: "AutoSocial.tech — assistant IA pour le contenu et l'auto-publication.",
    hero_subtitle: 'Creez du contenu, planifiez des publications et gerez Facebook + Instagram automatiquement depuis un seul endroit.',
    hero_cta: 'Commencer gratuitement par e-mail',
    hero_microcopy: "Pas de carte requise pour l'instant — commencez avec Free.",
    features_title: 'Tout pour le SMM dans un seul panneau',
    features_1: 'Generation de contenu unique avec IA',
    features_2: 'Auto-publication planifiee sur Facebook et Instagram',
    features_3: 'Modeles intelligents pour tous les secteurs',
    features_4: 'Planificateur qui anticipe pour vous',
    features_5: 'Metriques et analyses pour la croissance',
    how_title: 'Comment AutoSocial.tech aide votre business',
    how_1_title: 'Creez du contenu en quelques secondes',
    how_1_text: 'Entrez un sujet ou un message cle et obtenez des brouillons avec hashtags et CTA.',
    how_2_title: 'Planifiez. Automatisez. Oubliez le manuel',
    how_2_text: 'Definissez un planning et la plateforme publie automatiquement.',
    how_3_title: 'Suivez les performances',
    how_3_text: "Portee, engagement et croissance dans un seul tableau de bord.",
    trust_title: 'Pourquoi les marketeurs choisissent AutoSocial.tech',
    trust_1: "Jusqu'a 10 heures gagnees par semaine",
    trust_2: 'Contenu base sur les bonnes pratiques SMM',
    trust_3: 'Integrations Facebook + Instagram Business',
    trust_4: 'Pret pour SSL / RGPD et paiement.',
    quote: '"AutoSocial.tech a mis nos reseaux en pilote automatique: plus de regularite et plus d engagement." — Marketeur SMB',
    final_title: 'Pret a automatiser vos reseaux sociaux ?',
    final_cta_account: 'Creer un compte par e-mail',
    final_cta_pricing: 'Voir les tarifs',
    final_note: 'Commencez avec Free Trial. Passez a Growth a tout moment.',
    footer_pricing: 'Tarifs',
    footer_privacy: 'Politique de confidentialite',
    footer_support: 'Support',
    field_email: 'E-mail',
    field_password: 'Mot de passe',
    field_code: 'Code recu par e-mail',
    placeholder_email: 'you@company.com',
    placeholder_password: '8 caracteres minimum',
    placeholder_code: '4 chiffres',
    resend_code: 'Renvoyer le code',
    back_to_auth: 'Changer e-mail/mot de passe',
  },
  uk: {
    language_label: 'Мова',
    form_title_register: 'Створити акаунт',
    form_title_login: 'Увійти',
    flow_title_register: 'Підтвердьте реєстрацію',
    flow_title_login: 'Підтвердьте вхід',
    submit_get_code: 'Отримати код',
    submit_verify_code: 'Підтвердити код',
    switch_text_register: 'Вже є акаунт?',
    switch_text_login: 'Немає акаунта?',
    switch_label_register: 'Увійти',
    switch_label_login: 'Створити',
    auth_hint_default: 'Введіть email і пароль. Ми надішлемо 4-значний код.',
    auth_hint_code_prefix: 'Код надіслано на',
    hero_title: 'AutoSocial.tech — AI-асистент для контенту й автопостингу.',
    hero_subtitle: 'Створюйте контент, плануйте публікації та керуйте Facebook + Instagram з одного місця автоматично.',
    hero_cta: 'Почати безкоштовно через email',
    hero_microcopy: 'Без прив?язки картки зараз — почніть із Free плану.',
    features_title: 'Усе для SMM в одній панелі',
    features_1: 'Генерація унікального контенту на базі AI',
    features_2: 'Автопостинг за розкладом у Facebook та Instagram',
    features_3: 'Розумні шаблони для будь-якої ніші',
    features_4: 'Планувальник, що думає за вас',
    features_5: 'Метрики та аналітика для зростання',
    how_title: 'Як AutoSocial.tech допомагає вашому бізнесу',
    how_1_title: 'Створюйте контент за секунди',
    how_1_text: 'Вкажіть тему або ключове повідомлення — отримайте готові пости з хештегами та CTA.',
    how_2_title: 'Плануйте. Автоматизуйте. Забудьте про ручні публікації',
    how_2_text: 'Налаштуйте графік — і система публікує сама.',
    how_3_title: 'Відстежуйте ефективність',
    how_3_text: 'Охоплення, залученість і зростання аудиторії — все в одній панелі.',
    trust_title: 'Чому маркетологи обирають AutoSocial.tech',
    trust_1: 'Економить до 10 годин на тиждень',
    trust_2: 'Генерує контент на основі найкращих SMM-практик',
    trust_3: 'Інтеграції з Facebook + Instagram Business',
    trust_4: 'SSL / GDPR-ready. Готово до оплати.',
    quote: '«AutoSocial.tech перевів наші соцмережі на автопілот — публікацій стало більше, а залученість зросла.» — Маркетолог, SMB',
    final_title: 'Готові автоматизувати свої соцмережі?',
    final_cta_account: 'Створити акаунт через email',
    final_cta_pricing: 'Дізнатися тарифи',
    final_note: 'Почніть з Free Trial. Перехід на Growth доступний у будь-який момент.',
    footer_pricing: 'Тарифи',
    footer_privacy: 'Політика конфіденційності',
    footer_support: 'Підтримка',
    field_email: 'Email',
    field_password: 'Пароль',
    field_code: 'Код з листа',
    placeholder_email: 'you@company.com',
    placeholder_password: 'Мінімум 8 символів',
    placeholder_code: '4 цифри',
    resend_code: 'Надіслати код повторно',
    back_to_auth: 'Змінити email/пароль',
  },
};
function normalizeLang(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  const simple = raw.split('-')[0];
  return SUPPORTED_LANGS.includes(simple) ? simple : '';
}
function detectBrowserLang() {
  const langs = Array.isArray(navigator.languages) && navigator.languages.length
    ? navigator.languages
    : [navigator.language || navigator.userLanguage || 'en'];
  for (const lang of langs) {
    const normalized = normalizeLang(lang);
    if (normalized) return normalized;
  }
  return 'en';
}
function loginText(key) {
  const lang = normalizeLang(state.lang) || 'en';
  const dict = LOGIN_I18N[lang] || LOGIN_I18N.en;
  if (Object.prototype.hasOwnProperty.call(dict, key)) return dict[key];
  return LOGIN_I18N.en[key] || key;
}
function setLanguage(lang, opts = {}) {
  const { persist = true } = opts;
  const normalized = normalizeLang(lang) || 'en';
  state.lang = normalized;
  document.documentElement.setAttribute('lang', normalized);
  if (persist) {
    localStorage.setItem('lang', normalized);
    localStorage.setItem('siteLang', normalized);
  }
}
function normalizeContentLanguage(value) {
  const normalized = normalizeLang(value);
  if (normalized === 'uk') return 'ua';
  if (normalized === 'ru' || normalized === 'ua' || normalized === 'en' || normalized === 'es' || normalized === 'de' || normalized === 'fr') return normalized;
  return 'ru';
}
const state = {
  token: localStorage.getItem('token') || '',
  theme: localStorage.getItem('theme') || 'light',
  lang: normalizeLang(localStorage.getItem('lang') || localStorage.getItem('siteLang')) || detectBrowserLang(),
  authMode: 'register',
  authChallenge: null,
  authProviders: null,
  user: null,
  billing: null,
  projects: [],
  connections: [],
  youtubeConnection: {
    connected: false,
    status: 'not_connected',
    channel_id: '',
    channel_name: '',
    updated_at: null,
  },
  connectionPicker: {
    open: false,
    connectionId: null,
    loading: false,
    pages: [],
    selectedPageId: '',
    error: '',
    filter: 'all', // all | with_ig | without_ig | not_connected
    query: '',
  },
  posts: [],
  dashboardMetrics: {
    loading: false,
    syncing: false,
    summary: null,
    timeseries: { points: [] },
    aiScore: { current: 0, delta_7d: 0, breakdown: null, timeseries: [] },
    forecast: { horizon_days: 7, confidence: { level: 'low', reasons: [] }, totals: { reach: 0, views: 0, engagement_rate_avg: 0 }, points: [], scenarios: { current: {}, plus30: {} } },
    forecastHorizon: 7,
    aiBreakdownOpen: false,
    insights: [],
    recent: [],
    chartMetric: 'reach',
    recentSort: 'engagement',
  },
  dashboardQuickStart: {
    nicheId: '',
    actionType: '',
    seed: 0,
  },
  plans: [],
  blog: [],
  adminUsers: [],
  adminRevenue: null,
  notice: null,
  historyCalendar: {
    monthKey: '',
    monthsSpan: 1,
    selectedDayKey: '',
  },
  createWizard: {
    step: 1,
    projectId: '',
    niche: 'services',
    category: 'business',
    topic: '',
    goal: 'sales',
    ctaAction: 'Записаться',
    hashtags: ['#бизнес', '#маркетинг'],
    finalCta: 'Напишите в директ, чтобы получить консультацию.',
    metaFormat: 'post',
    youtubeFormat: 'description',
    quickTopicsVersion: 0,
    tone: 'friendly',
    language: 'ru',
    previewText: '',
    generating: false,
    generatedAt: '',
    publishSuccess: null,
    mode: 'now',
    scheduleAt: '',
    platforms: { facebook: true, instagram: true, youtube: false },
    mediaUrl: '',
  },
  createCampaign: {
    step: 1,
    campaignId: null,
    mode: 'image',
    topic: '',
    offer: '',
    language: 'ru',
    projectId: '',
    objective: 'sales',
    platforms: { facebook: true, instagram: true, youtube: false },
    kinds: { facebook: 'image_post', instagram: 'image_post', youtube: 'shorts' },
    accountRefs: { facebook: '', instagram: '', youtube: '' },
    imageStyle: 'реалистично',
    noTextOnImage: true,
    videoDuration: 30,
    videoAspectRatio: '9:16',
    noFantasy: true,
    generateThumbnail: true,
    videoStylePackId: 'default_pro',
    stylePacks: [],
    stylePacksLoaded: false,
    caption: '',
    cta: 'Напишите в директ',
    hashtags: ['#бизнес', '#контент'],
    generation: { imageJobId: null, videoJobId: null, running: false, statusText: '' },
    assets: [],
    publishMode: 'now',
    scheduledAt: '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    deliveries: [],
    publishMessage: '',
    contentTone: 'friendly',
    contentGoal: 'engagement',
    contentVariants3: false,
    contentScheduleAt: '',
    studioMode: 'quick', // quick | pro
    audienceType: 'b2c',
    audienceSegment: '',
    contentFormat: 'post',
    forbiddenTopics: '',
    rewriteStyle: 'короче',
    previewPlatform: 'facebook',
    aiAssist: { loading: false, hook: '', angles: [], ctaVariants: [] },
    quality: { score: 0, checks: [], warnings: [] },
    templates: [],
    contentGeneration: {
      loading: false,
      stage: 'idle', // idle | strategy | drafts | ready | error
      error: '',
      retryable: false,
      briefId: null,
      strategy: null,
      drafts: [],
      activePlatform: 'facebook',
    },
    dirty: false,
  },
  createDirector: {
    mode: 'quick',
    generationMode: 'manual',
    contentType: 'post',
    topic: '',
    topicPreset: DEFAULT_DIRECTOR_NICHE,
    customTopicMode: false,
    customBaseTopicInput: '',
    goal: 'engagement',
    offer: '',
    language: 'ru',
    tone: 'friendly',
    audienceSegment: '',
    length: 'medium',
    style: 'short',
    brandRules: '',
    platforms: { facebook: true, instagram: true, youtube: false },
    loadingSuggest: false,
    loadingDrafts: false,
    suggestions: null,
    selectedSuggestedTopic: '',
    manualTopicInput: '',
    appliedManualTopic: '',
    selectedAngle: '',
    selectedHashtags: [],
    selectedCta: '',
    drafts: [],
    activeVariant: 1,
    activePlatform: 'facebook',
    quality: { score: 0, checks: [], warnings: [] },
    status: 'idle',
    warnings: [],
    debugCode: '',
    briefId: null,
    lastDraftTopic: '',
    lastDraftAngle: '',
    refreshCount: 0,
    hashtagsRefreshCount: 0,
    ctaRefreshCount: 0,
    approachesRefreshCount: 0,
    topicPool: [],
    refreshingTopics: false,
    refreshingHashtags: false,
    refreshingCta: false,
    refreshingApproaches: false,
    imageEnabled: false,
    imageUrl: '',
    videoCoverUrl: '',
    imageLoading: false,
    imageRefreshCount: 0,
    videoOrientation: 'vertical',
    videoDurationPreset: '30',
    videoSceneEvery4: true,
    videoShotSeconds: 4,
    videoMinimizeRepeats: true,
    videoRealisticOnly: true,
    videoVoiceGender: 'male',
    videoVoiceTone: 'neutral',
    previewVideoTab: 'meta',
    previewVideoMetaPlatform: 'facebook',
    previewExpanded: {},
    videoStructureExpanded: false,
    videoStructureLoading: false,
    videoStructure: null,
    videoRenderLoading: false,
    videoJobId: null,
    videoJobStatus: '',
    videoProgress: 0,
    videoStep: 'queued',
    videoMessage: '',
    videoPreviewUrl: '',
    videoFinalUrl: '',
    videoSrtUrl: '',
    videoDebug: null,
    videoRenderedVoiceGender: '',
    videoRenderedVoiceTone: '',
    videoRenderRequestedVoiceGender: '',
    videoRenderRequestedVoiceTone: '',
    videoWeekPostsPerDay: 1,
    videoWeekDurationPreset: '30',
    videoWeekTimeMode: 'ai',
    videoWeekManualTime: '12:00',
    videoWeekLoading: false,
    videoWeekApplying: false,
    videoWeekItems: [],
    videoWeekSelectedDate: '',
    videoMonthPostsPerDay: 1,
    videoMonthDurationPreset: '30',
    videoMonthTimeMode: 'ai',
    videoMonthManualTime: '12:00',
    videoMonthLoading: false,
    videoMonthApplying: false,
    videoMonthItems: [],
    videoMonthSelectedDate: '',
    postWeekPostsPerDay: 1,
    postWeekTimeMode: 'ai',
    postWeekManualTime: '12:00',
    postWeekLoading: false,
    postWeekApplying: false,
    postWeekScheduling: false,
    postWeekItems: [],
    postWeekSelectedDate: '',
    postMonthPostsPerDay: 1,
    postMonthTimeMode: 'ai',
    postMonthManualTime: '12:00',
    postMonthLoading: false,
    postMonthApplying: false,
    postMonthScheduling: false,
    postMonthItems: [],
    postMonthSelectedDate: '',
    quickActionType: '',
    quickActionNicheId: '',
    quickActionSeed: 0,
    quickActionPreviewOnly: false,
    scheduleAt: '',
    planHorizon: 'week',
    planLoading: false,
    planItems: [],
    planItemsAll: [],
    planLoaded: false,
    bestSlots: null,
    planFlowState: 'idle',
    planFlowError: '',
    planFlowItems: [],
    planFlowSelectedDay: 1,
    planFlowProgressStep: 0,
  },
  campaignDetails: null,
  campaignList: [],
  youtubeStudio: {
    projectId: '',
    topic: '',
    videoType: 'short',
    durationSeconds: 45,
    language: 'ru',
    tone: 'expert',
    style: 'educational',
    audience: 'Владельцы малого бизнеса',
    goal: 'engagement',
    postKind: 'community',
    loadingVideo: false,
    loadingPost: false,
    videoResult: null,
    postResult: null,
  },
  aiWizard: null,
};

const CP1251_EXTRA_MAP = {
  0x0402: 0x80, 0x0403: 0x81, 0x201A: 0x82, 0x0453: 0x83, 0x201E: 0x84, 0x2026: 0x85, 0x2020: 0x86, 0x2021: 0x87,
  0x20AC: 0x88, 0x2030: 0x89, 0x0409: 0x8A, 0x2039: 0x8B, 0x040A: 0x8C, 0x040C: 0x8D, 0x040B: 0x8E, 0x040F: 0x8F,
  0x0452: 0x90, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97,
  0x2122: 0x99, 0x0459: 0x9A, 0x203A: 0x9B, 0x045A: 0x9C, 0x045C: 0x9D, 0x045B: 0x9E, 0x045F: 0x9F, 0x00A0: 0xA0,
  0x040E: 0xA1, 0x045E: 0xA2, 0x0408: 0xA3, 0x00A4: 0xA4, 0x0490: 0xA5, 0x00A6: 0xA6, 0x00A7: 0xA7, 0x0401: 0xA8,
  0x00A9: 0xA9, 0x0404: 0xAA, 0x00AB: 0xAB, 0x00AC: 0xAC, 0x00AD: 0xAD, 0x00AE: 0xAE, 0x0407: 0xAF, 0x00B0: 0xB0,
  0x00B1: 0xB1, 0x0406: 0xB2, 0x0456: 0xB3, 0x0491: 0xB4, 0x00B5: 0xB5, 0x00B6: 0xB6, 0x00B7: 0xB7, 0x0451: 0xB8,
  0x2116: 0xB9, 0x0454: 0xBA, 0x00BB: 0xBB, 0x0458: 0xBC, 0x0405: 0xBD, 0x0455: 0xBE, 0x0457: 0xBF,
};
const UTF8_DECODER = new TextDecoder('utf-8', { fatal: true });

function cp1251ByteForChar(ch) {
  const code = ch.charCodeAt(0);
  // ASCII must stay untouched; decode only mojibake-like Cyrillic segments.
  if (code <= 0x7F) return null;
  // Preserve C1 controls that often appear in mojibake pairs like "\u0420\u0098".
  if (code >= 0x80 && code <= 0x9F) return code;
  if (code >= 0x0410 && code <= 0x044F) return code - 0x0350;
  if (Object.prototype.hasOwnProperty.call(CP1251_EXTRA_MAP, code)) return CP1251_EXTRA_MAP[code];
  return null;
}

function decodeMojibake(value) {
  const source = String(value ?? '');
  if (!source) return source;
  let out = '';
  let bufChars = '';
  let bufBytes = [];
  const flush = () => {
    if (!bufBytes.length) return;
    try {
      const decoded = UTF8_DECODER.decode(new Uint8Array(bufBytes));
      out += decoded.includes('\uFFFD') ? bufChars : decoded;
    } catch {
      out += bufChars;
    }
    bufChars = '';
    bufBytes = [];
  };

  for (const ch of source) {
    const b = cp1251ByteForChar(ch);
    if (b === null) {
      flush();
      out += ch;
      continue;
    }
    bufChars += ch;
    bufBytes.push(b);
  }
  flush();
  return out;
}

const esc = (v) => decodeMojibake(String(v ?? '')).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const safeText = (v, fallback = '—') => {
  const s = String(v ?? '').replace(/\uFFFD/g, '').trim();
  return s ? s : fallback;
};
const _pad2 = (n) => String(n).padStart(2, '0');
function localDateKey(value) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${_pad2(d.getMonth() + 1)}-${_pad2(d.getDate())}`;
}
function localMonthKey(value) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${_pad2(d.getMonth() + 1)}`;
}
function monthStartFromKey(key) {
  const m = String(key || '').match(/^(\d{4})-(\d{2})$/);
  if (!m) return new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  if (!Number.isFinite(y) || !Number.isFinite(mo)) return new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  return new Date(y, mo, 1);
}
function toLocalInputValue(value) {
  if (!value) return '';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${_pad2(d.getMonth() + 1)}-${_pad2(d.getDate())}T${_pad2(d.getHours())}:${_pad2(d.getMinutes())}`;
}
function toLocalIsoNoTz(value) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${_pad2(d.getMonth() + 1)}-${_pad2(d.getDate())}T${_pad2(d.getHours())}:${_pad2(d.getMinutes())}:${_pad2(d.getSeconds())}`;
}
function localInputToUtcIso(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toISOString();
}
function localInputToIsoNoTz(value) {
  // Legacy helper name preserved to keep existing scheduling callers stable.
  // The returned payload is now explicit UTC ISO instead of a naive local datetime string.
  return localInputToUtcIso(value);
}
const isAuthRoute = (p) => !['/login', '/blog'].includes(p);
let renderVersion = 0;

function setTheme(theme) {
  state.theme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', state.theme);
  localStorage.setItem('theme', state.theme);
}
setTheme(state.theme);
setLanguage(state.lang, { persist: false });

async function api(path, options = {}) {
  const { timeoutMs = 45000, ...fetchOptions } = options || {};
  const headers = { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const controller = new AbortController();
  const externalSignal = fetchOptions.signal;
  const signal = externalSignal || controller.signal;
  const timer = (!externalSignal && Number(timeoutMs) > 0)
    ? setTimeout(() => controller.abort(), Number(timeoutMs))
    : null;

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers, signal });
  } catch (err) {
    if (timer) clearTimeout(timer);
    if (err && err.name === 'AbortError') {
      const secs = Math.max(1, Math.round(Number(timeoutMs || 0) / 1000));
      throw new Error(`Сервер долго отвечает (${secs}с). Попробуйте снова.`);
    }
    throw err;
  }
  if (timer) clearTimeout(timer);

  const text = await res.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = text; }
  if (!res.ok) {
    const makeErr = (message) => {
      const err = new Error(message);
      err.status = res.status;
      err.path = path;
      err.payload = payload;
      return err;
    };
    if (typeof payload === 'string') {
      const htmlResponse = /<html|<!doctype/i.test(payload);
      if (htmlResponse) throw makeErr(`Ошибка сервера (${res.status}). Повторите позже.`);
      throw makeErr(payload || `Ошибка запроса (${res.status})`);
    }
    throw makeErr(payload.message || payload.error || `Ошибка запроса (${res.status})`);
  }
  return payload;
}

async function loadAuthProviders() {
  try {
    state.authProviders = await api('/api/auth/providers');
  } catch {
    state.authProviders = {
      google: { configured: false },
      facebook: { configured: false },
    };
  }
}

function nav(path, opts = {}) {
  const current = location.pathname.replace(/\/$/, '') || '/';
  const target = String(path || '').replace(/\/$/, '') || '/';
  if (current === target) return;
  history.pushState({}, '', path);
  if (!opts.keepNotice) state.notice = null;
  render();
}

function icon(name) {
  const icons = {
    dashboard: '<svg class="icon" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/></svg>',
    create: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M5 12h14"/></svg>',
    connections: '<svg class="icon" viewBox="0 0 24 24"><path d="M9 15l6-6"/><path d="M7 7h.01"/><path d="M17 17h.01"/><path d="M13 5h4a2 2 0 0 1 2 2v4"/><path d="M11 19H7a2 2 0 0 1-2-2v-4"/></svg>',
    history: '<svg class="icon" viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/><path d="M12 7v5l3 3"/></svg>',
    youtube: '<svg class="icon" viewBox="0 0 24 24"><rect x="2.5" y="6.2" width="19" height="11.6" rx="4.2"/><path d="M10 9.3v5.4l4.9-2.7-4.9-2.7z"/></svg>',
    billing: '<svg class="icon" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M2 10h20"/><path d="M7 15h4"/></svg>',
    settings: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.02.02a2 2 0 0 1-2.83 2.83l-.02-.02A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.56V21a2 2 0 0 1-4 0v-.04A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.02.02a2 2 0 0 1-2.83-2.83l.02-.02A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H3a2 2 0 0 1 0-4h.04A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.02-.02a2 2 0 0 1 2.83-2.83l.02.02A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 0 1 4 0v.04A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.02-.02a2 2 0 1 1 2.83 2.83l-.02.02A1.7 1.7 0 0 0 19.4 9c.13.32.46.53.81.53H21a2 2 0 0 1 0 4h-.79c-.35 0-.68.21-.81.53z"/></svg>',
    admin: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 3l8 4v6c0 5-3.5 7.5-8 8-4.5-.5-8-3-8-8V7l8-4z"/><path d="M9.5 12.5l1.7 1.7 3.6-3.6"/></svg>',
    blog: '<svg class="icon" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    contact: '<svg class="icon" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    support: '<svg class="icon" viewBox="0 0 24 24"><path d="M12 18h.01"/><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-2.9 2.5-2.9 4"/><circle cx="12" cy="12" r="9"/></svg>',
    logout: '<svg class="icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
  };
  return icons[name] || icons.dashboard;
}

function planBadge(plan) {
  const p = String(plan || 'free').toLowerCase();
  const labels = {
    free: 'Free Trial 7 days',
    starter: 'Starter',
    growth: 'Growth',
    agency: 'Agency',
    admin: 'Admin Unlimited',
  };
  const cls = p === 'admin'
    ? 'badge-agency'
    : p === 'growth'
      ? 'badge-growth'
      : p === 'agency'
        ? 'badge-agency'
        : p === 'starter'
          ? 'badge-starter'
          : 'badge-free';
  return `<span class="badge-plan ${cls}">${esc(labels[p] || p)}</span>`;
}

function statusBadge(status) {
  const key = String(status || '').toLowerCase();
  const map = {
    draft: { cls: 'queued', label: 'Черновик' },
    done: { cls: 'success', label: 'Готово' },
    published: { cls: 'success', label: 'Опубликовано' },
    connected: { cls: 'success', label: 'Подключено' },
    connected_ready: { cls: 'success', label: 'Готово' },
    connected_need_page: { cls: 'warning', label: 'Нужен выбор страницы' },
    not_connected: { cls: 'warning', label: 'Не подключено' },
    token_expired: { cls: 'warning', label: 'Требует переподключения' },
    permissions_missing: { cls: 'warning', label: 'Нужны права' },
    disconnected: { cls: 'error', label: 'Отключено' },
    error: { cls: 'error', label: 'Ошибка' },
    running: { cls: 'warning', label: 'В работе' },
    failed: { cls: 'error', label: 'Ошибка' },
    queued: { cls: 'queued', label: 'В очереди' },
    scheduled: { cls: 'scheduled', label: 'Запланировано' },
    hidden: { cls: 'warning', label: 'Скрыт' },
  };
  const item = map[key] || { cls: 'warning', label: status || 'неизвестно' };
  return `<span class="status ${item.cls}">${esc(item.label)}</span>`;
}

function isConnectionReady(c) {
  const key = String(c?.status || '').toLowerCase();
  return key === 'connected_ready' || key === 'connected';
}

function field(id, label, type = 'text', value = '', placeholder = '') {
  if (type === 'textarea') return `<div class="field"><label for="${id}">${esc(label)}</label><textarea id="${id}" placeholder="${esc(placeholder)}">${esc(value)}</textarea></div>`;
  return `<div class="field"><label for="${id}">${esc(label)}</label><input id="${id}" type="${esc(type)}" value="${esc(value)}" placeholder="${esc(placeholder)}"/></div>`;
}
function selectField(id, label, value, options) {
  return `<div class="field"><label for="${id}">${esc(label)}</label><select id="${id}">${options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(value) ? 'selected' : ''}>${esc(o.label)}</option>`).join('')}</select></div>`;
}
function normalizeCheckoutPlanCode(plan) {
  const key = normalizePublicPlan(plan);
  return ['starter', 'growth', 'agency'].includes(key) ? [key] : [];
}
function directorEffectiveTopic(d, fallback = '') {
  return String(d?.appliedManualTopic || '').trim()
    || String(d?.selectedSuggestedTopic || '').trim()
    || String(fallback || '').trim();
}
function directorBaseTopic(d, fallback = '') {
  const customEnabled = !!d?.customTopicMode;
  const customValue = String(d?.customBaseTopicInput || '').trim();
  const presetId = String(d?.topicPreset || fallback || DEFAULT_DIRECTOR_NICHE).trim();
  const presetMeta = typeof DIRECTOR_NICHE_ENGINE.getNicheTemplates === 'function'
    ? DIRECTOR_NICHE_ENGINE.getNicheTemplates(presetId)
    : null;
  const presetValue = String(presetMeta?.label || presetId || fallback || '').trim();
  return customEnabled ? customValue : presetValue;
}
function directorCurrentNicheId(d) {
  const customEnabled = !!d?.customTopicMode;
  if (customEnabled) return 'fallback';
  if (typeof DIRECTOR_NICHE_ENGINE.normalizeCategory === 'function') {
    return DIRECTOR_NICHE_ENGINE.normalizeCategory(d?.topicPreset || DEFAULT_DIRECTOR_NICHE);
  }
  return DEFAULT_DIRECTOR_NICHE;
}
function directorCurrentNicheMeta(d) {
  if (typeof DIRECTOR_NICHE_ENGINE.getNicheTemplates === 'function') {
    return DIRECTOR_NICHE_ENGINE.getNicheTemplates(directorCurrentNicheId(d));
  }
  return { id: DEFAULT_DIRECTOR_NICHE, label: 'SMM и маркетинг', contentAngles: [], topicTemplates: [], bannedCrossNicheWords: [] };
}
function buildDirectorHashtagToken(text) {
  const cleaned = String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '');
  return cleaned.length >= 3 ? `#${cleaned}` : '';
}
function directorNicheHashtagFallback(d, limit = 5) {
  const niche = directorCurrentNicheMeta(d);
  const out = [];
  const seen = new Set();
  const push = (value) => {
    const token = buildDirectorHashtagToken(value);
    if (!token || seen.has(token)) return;
    seen.add(token);
    out.push(token);
  };
  push(niche?.label || '');
  (Array.isArray(niche?.keywords) ? niche.keywords : []).forEach(push);
  return out.slice(0, Math.max(3, Math.min(Number(limit) || 5, 8)));
}
function directorPreferNicheHashtags(d, rawSet, limit = 8) {
  const nicheFallback = directorNicheHashtagFallback(d, 5);
  const normalized = normalizeHashtagSet(rawSet, nicheFallback);
  if (!nicheFallback.length) return normalized.slice(0, limit);
  const nicheKeys = new Set(nicheFallback.map((tag) => String(tag || '').trim().toLowerCase()));
  const hasNicheMatch = normalized.some((tag) => nicheKeys.has(String(tag || '').trim().toLowerCase()));
  if (!hasNicheMatch) return nicheFallback.slice(0, Math.min(limit, nicheFallback.length));
  return normalizeHashtagSet([...nicheFallback, ...normalized], nicheFallback).slice(0, limit);
}
function directorNicheAiContext(d) {
  if (!d || d.customTopicMode) return null;
  if (typeof DIRECTOR_NICHE_ENGINE.buildNicheAiContext === 'function') {
    return DIRECTOR_NICHE_ENGINE.buildNicheAiContext(directorCurrentNicheId(d));
  }
  return null;
}
function normalizePublicPlan(plan) {
  const key = String(plan || 'free').trim().toLowerCase();
  if (key === 'light') return 'starter';
  if (key === 'pro') return 'growth';
  return ['free', 'starter', 'growth', 'agency', 'admin'].includes(key) ? key : 'free';
}
function ensureDashboardQuickStartState() {
  if (!state.dashboardQuickStart || typeof state.dashboardQuickStart !== 'object') {
    state.dashboardQuickStart = { nicheId: '', actionType: '', seed: 0 };
  }
}
function savedDashboardNicheId() {
  const userId = String(state.user?.id || 'anon').trim() || 'anon';
  try {
    return String(localStorage.getItem(`dashboardQuickNiche:${userId}`) || '').trim();
  } catch {
    return '';
  }
}
function persistDashboardNicheId(nicheId) {
  const userId = String(state.user?.id || 'anon').trim() || 'anon';
  try {
    localStorage.setItem(`dashboardQuickNiche:${userId}`, String(nicheId || '').trim());
  } catch {}
}
function normalizeNicheIdSafe(value) {
  if (typeof DIRECTOR_NICHE_ENGINE.normalizeCategory === 'function') {
    return DIRECTOR_NICHE_ENGINE.normalizeCategory(value || '');
  }
  return String(value || '').trim();
}
function isExplicitDirectorNicheSelected() {
  const d = state.createDirector || {};
  if (d.customTopicMode) {
    const customId = normalizeNicheIdSafe(String(d.customBaseTopicInput || '').trim());
    return customId && customId !== 'fallback' ? customId : '';
  }
  const presetId = normalizeNicheIdSafe(String(d.topicPreset || '').trim());
  if (presetId && presetId !== DEFAULT_DIRECTOR_NICHE) return presetId;
  return '';
}
function resolveDashboardActiveNicheId() {
  ensureDashboardQuickStartState();
  const directorNicheId = isExplicitDirectorNicheSelected();
  if (directorNicheId) return directorNicheId;
  const savedId = normalizeNicheIdSafe(state.dashboardQuickStart.nicheId || savedDashboardNicheId());
  if (savedId && savedId !== 'fallback') return savedId;
  const wizardNicheId = normalizeNicheIdSafe(state.aiWizard?.niche || '');
  if (wizardNicheId && wizardNicheId !== 'fallback') return wizardNicheId;
  return '';
}
function dashboardQuickNicheMeta(nicheId) {
  if (typeof DIRECTOR_NICHE_ENGINE.getNicheTemplates === 'function') {
    return DIRECTOR_NICHE_ENGINE.getNicheTemplates(nicheId || '');
  }
  return { id: '', label: '', audience: '', keywords: [] };
}
function getQuickActionAccess(actionType, billing) {
  const plan = normalizePublicPlan(billing?.plan || 'free');
  const freeModes = {
    weekly_plan: { mode: 'full', limit: 7 },
    monthly_plan: { mode: 'locked', limit: 0 },
    video_week_plan: { mode: 'locked', limit: 0 },
    video_month_plan: { mode: 'locked', limit: 0 },
    post_series: { mode: 'preview', limit: 5 },
    video_series: { mode: 'locked', limit: 0 },
    hooks_pack: { mode: 'full', limit: 8 },
    cta_pack: { mode: 'full', limit: 6 },
  };
  const starterModes = {
    weekly_plan: { mode: 'full', limit: 7 },
    monthly_plan: { mode: 'full', limit: 30 },
    video_week_plan: { mode: 'full', limit: 7 },
    video_month_plan: { mode: 'full', limit: 30 },
    post_series: { mode: 'full', limit: 8 },
    video_series: { mode: 'full', limit: 6 },
    hooks_pack: { mode: 'full', limit: 10 },
    cta_pack: { mode: 'full', limit: 10 },
  };
  const growthModes = {
    weekly_plan: { mode: 'full', limit: 7 },
    monthly_plan: { mode: 'full', limit: 30 },
    video_week_plan: { mode: 'full', limit: 7 },
    video_month_plan: { mode: 'full', limit: 30 },
    post_series: { mode: 'full', limit: 10 },
    video_series: { mode: 'full', limit: 10 },
    hooks_pack: { mode: 'full', limit: 12 },
    cta_pack: { mode: 'full', limit: 12 },
  };
  const matrix = plan === 'free'
    ? freeModes
    : (plan === 'starter' ? starterModes : growthModes);
  const access = matrix[actionType] || { mode: 'full', limit: 7 };
  return {
    ...access,
    plan,
    isPreview: access.mode === 'preview',
    isLocked: access.mode === 'locked',
  };
}
function currentPlannerBillingPlan() {
  return normalizePublicPlan(state.billing?.plan || state.user?.plan || 'free');
}
function showPaywall(message) {
  state.notice = { type: 'error', text: String(message || '').trim() || '\u0424\u0443\u043d\u043a\u0446\u0438\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0442\u043e\u043b\u044c\u043a\u043e \u043d\u0430 \u043f\u043b\u0430\u0442\u043d\u043e\u043c \u0442\u0430\u0440\u0438\u0444\u0435.' };
  nav('/billing', { keepNotice: true });
}
function getPlannerMonetizationAccess(kind, days, plan = currentPlannerBillingPlan()) {
  const normalizedPlan = normalizePublicPlan(plan || 'free');
  const canAutopublish = ['growth', 'agency', 'admin'].includes(normalizedPlan);
  return {
    plan: normalizedPlan,
    canGenerate: !(normalizedPlan === 'free' && (Number(days) === 30 || String(kind || 'post') === 'video')),
    canAutopublish,
    generateMessage: Number(days) === 30 && normalizedPlan === 'free'
      ? '30 \u0434\u043d\u0435\u0439 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043e\u0442 \u20ac29'
      : (String(kind || 'post') === 'video' && normalizedPlan === 'free'
        ? '\u0412\u0438\u0434\u0435\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0432 Starter'
        : ''),
    autopublishMessage: '\u0410\u0432\u0442\u043e\u043f\u043e\u0441\u0442\u0438\u043d\u0433 \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u043d\u0430 Growth (\u20ac79)',
  };
}
function buildQuickActionResult(actionType, nicheId, billing, seed = 0) {
  const nicheMeta = dashboardQuickNicheMeta(nicheId);
  const access = getQuickActionAccess(actionType, billing);
  const result = {
    actionType,
    nicheId: nicheMeta.id,
    nicheLabel: nicheMeta.label,
    access,
    title: '',
    subtitle: '',
    items: [],
  };
  if (actionType === 'weekly_plan') {
    result.title = 'Контент-план на 7 дней';
    result.subtitle = '7 тем с форматом, углом подачи и CTA под выбранную нишу.';
    result.items = (DIRECTOR_NICHE_ENGINE.get7DayContentPlan?.(nicheId, 'post') || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'monthly_plan') {
    result.title = 'Контент-план на 30 дней';
    result.subtitle = access.isPreview
      ? 'Первые 7 тем с форматом, углом подачи и CTA под выбранную нишу. Полный месяц доступен после апгрейда.'
      : '30 тем с форматом, углом подачи и CTA под выбранную нишу.';
    result.items = (DIRECTOR_NICHE_ENGINE.get30DayContentPlan?.(nicheId, 'post') || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'video_week_plan') {
    result.title = 'Видео-посты на 7 дней';
    result.subtitle = '7 идей для short-form видео с hook, подачей и CTA под выбранную нишу.';
    result.items = (DIRECTOR_NICHE_ENGINE.get7DayContentPlan?.(nicheId, 'video') || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'video_month_plan') {
    result.title = 'Видео-посты на 30 дней';
    result.subtitle = access.isPreview
      ? 'Первые 7 видео-идей доступны сразу. Полный видеоплан на месяц открывается после апгрейда.'
      : '30 идей для видео-постов с hook, подачей и CTA на месяц.';
    result.items = (DIRECTOR_NICHE_ENGINE.get30DayContentPlan?.(nicheId, 'video') || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'post_series') {
    result.title = 'Серия постов';
    result.subtitle = access.isPreview
      ? 'Первые идеи серии доступны уже на текущем тарифе.'
      : 'Серия постов для регулярного контента по вашей нише.';
    result.items = (DIRECTOR_NICHE_ENGINE.getPostSeries?.(nicheId, Math.max(access.limit, 5)) || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'video_series') {
    result.title = 'Серия видео';
    result.subtitle = access.isPreview
      ? 'Preview short-form видео по вашей нише. Больше идей доступно после апгрейда.'
      : 'Идеи коротких видео с hook, углом подачи и CTA.';
    result.items = (DIRECTOR_NICHE_ENGINE.getVideoSeries?.(nicheId, Math.max(access.limit, 5)) || []).slice(0, access.limit);
    return result;
  }
  if (actionType === 'hooks_pack') {
    const hooks = (DIRECTOR_NICHE_ENGINE.getTopicHooks?.(nicheId) || []).slice();
    const shuffled = hooks.length ? hooks.slice(seed % Math.max(1, hooks.length)).concat(hooks.slice(0, seed % Math.max(1, hooks.length))) : [];
    result.title = 'Набор hooks';
    result.subtitle = 'Цепляющие начала для постов, Reels и Shorts по выбранной нише.';
    result.items = shuffled.slice(0, access.limit).map((text, idx) => ({ index: idx + 1, hook: text }));
    return result;
  }
  const ctas = (DIRECTOR_NICHE_ENGINE.getCtaTemplates?.(nicheId) || []).slice();
  const shuffled = ctas.length ? ctas.slice(seed % Math.max(1, ctas.length)).concat(ctas.slice(0, seed % Math.max(1, ctas.length))) : [];
  result.title = 'Набор CTA';
  result.subtitle = 'Призывы к действию для вовлечения, сообщений и заявок.';
  result.items = shuffled.slice(0, access.limit).map((text, idx) => ({ index: idx + 1, cta: text }));
  return result;
}
const PLAN_FORMAT_LABELS = {
  expert_post: 'Экспертный пост',
  checklist_post: 'Пост-чеклист',
  story_post: 'История / кейс',
  video_series: 'Видео',
  reels_idea: 'Идея для Reels',
  reel: 'Reels',
  post: 'Пост',
  carousel: 'Карусель',
  community: 'Пост для сообщества',
  short_video: 'Короткое видео',
  tutorial_post: 'Обучающий пост',
  sales_post: 'Продающий пост',
  behind_scenes: 'Закулисье',
  comparison_post: 'Сравнение',
};
function planFormatLabel(raw) {
  const key = String(raw || '').trim().toLowerCase();
  if (!key) return 'Публикация';
  if (PLAN_FORMAT_LABELS[key]) return PLAN_FORMAT_LABELS[key];
  if (key.includes('expert')) return 'Экспертный пост';
  if (key.includes('checklist')) return 'Пост-чеклист';
  if (key.includes('story') || key.includes('case')) return 'История / кейс';
  if (key.includes('reel')) return 'Идея для Reels';
  if (key.includes('video')) return 'Видео';
  if (key.includes('carousel')) return 'Карусель';
  if (key.includes('community')) return 'Пост для сообщества';
  if (key.includes('post')) return 'Пост';
  return key.replace(/_/g, ' ').replace(/\b\w/g, (s) => s.toUpperCase());
}
function planGoalLabel(raw) {
  const key = String(raw || '').trim().toLowerCase();
  if (['sales', 'lead', 'leads'].includes(key)) return 'Продажи';
  if (key === 'awareness') return 'Охват';
  if (key === 'engagement') return 'Вовлечение';
  return 'Вовлечение';
}
function planDayPreview(item) {
  if (!item || typeof item !== 'object') return '';
  const topic = String(item.topic || '').trim();
  const formatHint = String(item.format_hint || '').trim();
  const angle = String(item.angle || '').trim();
  const focusHint = String(item.focus_hint || '').trim();
  const endingHint = String(item.ending_hint || '').trim();
  const cta = String(item.cta || '').trim();
  const scheduledAt = String(item.scheduled_at || '').trim();
  const scheduleLabel = (() => {
    if (!scheduledAt) return '';
    try {
      return new Date(scheduledAt).toLocaleString('ru-RU', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  })();
  const parts = [];
  if (scheduleLabel) parts.push(`Публикация: ${scheduleLabel}`);
  if (topic) parts.push(`Тема: ${topic}`);
  if (formatHint) parts.push(`Формат: ${formatHint}`);
  if (angle) parts.push(`Угол подачи: ${angle}`);
  if (focusHint) parts.push(`Фокус: ${focusHint}`);
  if (endingHint) parts.push(`Финал: ${endingHint}`);
  if (cta) parts.push(`CTA: ${cta}`);
  if (parts.length) return parts.join('. ');
  return topic ? `Идея на тему «${topic}» с акцентом на пользу для клиента.` : '';
}
function groupPlanItemsByWeek(items) {
  const grouped = [];
  const list = Array.isArray(items) ? items : [];
  for (let index = 0; index < list.length; index += 7) {
    grouped.push({
      index: Math.floor(index / 7) + 1,
      items: list.slice(index, index + 7),
    });
  }
  return grouped;
}
function normalizePlannerKind(value) {
  return String(value || '').trim().toLowerCase() === 'video' ? 'video' : 'post';
}
function normalizePlannerDays(value) {
  return String(value || '').trim() === '30' || Number(value) === 30 ? 30 : 7;
}
function plannerUrl(kind = 'post', days = 7, extras = {}) {
  const query = new URLSearchParams();
  query.set('mode', 'plan');
  query.set('kind', normalizePlannerKind(kind));
  query.set('days', String(normalizePlannerDays(days)));
  Object.entries(extras || {}).forEach(([key, value]) => {
    if (value == null || value === '') return;
    query.set(key, String(value));
  });
  return `/create?${query.toString()}`;
}
function getCreatePlannerRoute(path = location.pathname.replace(/\/$/, '') || '/') {
  if (path === '/create') {
    try {
      const params = new URLSearchParams(location.search);
      if (String(params.get('mode') || '').trim() !== 'plan') return null;
      return {
        kind: normalizePlannerKind(params.get('kind') || 'post'),
        days: normalizePlannerDays(params.get('days') || 7),
        legacy: false,
      };
    } catch {
      return null;
    }
  }
  if (path === '/create/post-week') return { kind: 'post', days: 7, legacy: true };
  if (path === '/create/video-week') return { kind: 'video', days: 7, legacy: true };
  if (path === '/create/video-month') return { kind: 'video', days: 30, legacy: true };
  return null;
}
function getPlannerStateConfig(kind, days) {
  const normalizedKind = normalizePlannerKind(kind);
  const normalizedDays = normalizePlannerDays(days);
  const baseKey = normalizedKind === 'video'
    ? (normalizedDays === 30 ? 'videoMonth' : 'videoWeek')
    : (normalizedDays === 30 ? 'postMonth' : 'postWeek');
  return {
    kind: normalizedKind,
    days: normalizedDays,
    baseKey,
    itemsKey: `${baseKey}Items`,
    selectedDateKey: `${baseKey}SelectedDate`,
    postsPerDayKey: `${baseKey}PostsPerDay`,
    timeModeKey: `${baseKey}TimeMode`,
    manualTimeKey: `${baseKey}ManualTime`,
    loadingKey: `${baseKey}Loading`,
    applyingKey: `${baseKey}Applying`,
    schedulingKey: `${baseKey}Scheduling`,
    title: normalizedKind === 'video'
      ? (normalizedDays === 30 ? 'Видео-посты на 30 дней' : 'Видео-посты на 7 дней')
      : (normalizedDays === 30 ? 'Контент-план постов на 30 дней' : 'Контент-план постов на 7 дней'),
    subtitle: normalizedKind === 'video'
      ? 'Единый planner для short-form видео: темы, слоты публикации, CTA и превью по дням.'
      : 'Единый planner для постов: темы, слоты публикации, платформы и подготовка к автопостингу.',
    backUrl: `/create?type=${normalizedKind}`,
  };
}
function groupPlannerDays(dayKeys) {
  const list = Array.isArray(dayKeys) ? dayKeys : [];
  if (list.length <= 7) return [{ index: 1, from: 1, to: list.length || 7, days: list }];
  const groups = [];
  for (let index = 0; index < list.length; index += 7) {
    const isFinalThirtyDayGroup = list.length >= 30 && index >= 21;
    const slice = isFinalThirtyDayGroup ? list.slice(index) : list.slice(index, index + 7);
    groups.push({
      index: Math.floor(index / 7) + 1,
      from: index + 1,
      to: index + slice.length,
      days: slice,
    });
    if (isFinalThirtyDayGroup) break;
  }
  return groups;
}
function getPlannerDayState(items, selectedDate) {
  const dayMap = {};
  (Array.isArray(items) ? items : []).forEach((item) => {
    const iso = String(item?.scheduled_at || '').trim();
    if (!iso) return;
    const day = iso.slice(0, 10);
    if (!dayMap[day]) dayMap[day] = [];
    dayMap[day].push(item);
  });
  const dayKeys = Object.keys(dayMap).sort();
  const effectiveSelectedDate = String(selectedDate || '').trim() || dayKeys[0] || '';
  const selectedDayItems = effectiveSelectedDate ? (dayMap[effectiveSelectedDate] || []) : [];
  return {
    dayMap,
    dayKeys,
    effectiveSelectedDate,
    selectedDayItems,
    selectedPreviewItem: selectedDayItems[0] || (Array.isArray(items) ? items[0] : null) || null,
  };
}
function renderPostPlannerPreview(item, d) {
  const timeLabel = new Date(item.scheduled_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  const captionText = String(item.caption_text || item.post_text || item.caption || '').trim();
  const captionParagraphs = captionText
    ? captionText.split(/\r?\n\s*\r?\n/).map((part) => String(part || '').trim()).filter(Boolean)
    : [];
  const ctaText = String(item.cta || '').trim();
  const hashtagsText = String(item.hashtags || '').trim();
  return `<article class="card" style="padding:12px;border:1px solid rgba(148,163,184,.18);">
    <div class="row" style="justify-content:space-between;align-items:flex-start;gap:8px;">
      <strong>${esc(timeLabel)}</strong>
      <span class="small">Формат: ${esc(planFormatLabel(item.format_hint || 'post'))} · Изображение: ${d.imageEnabled ? 'AI-картинка' : 'Без картинки'}</span>
    </div>
    <p class="small" style="margin:8px 0 8px 0;"><strong>${esc(item.topic || '—')}</strong></p>
    ${captionParagraphs.length
      ? captionParagraphs.map((part) => `<p class="small" style="margin:0 0 8px 0;white-space:pre-wrap;">${esc(part)}</p>`).join('')
      : '<p class="small" style="margin:0 0 8px 0;">—</p>'}
    ${ctaText ? `<p class="small" style="margin:0 0 8px 0;">${esc(ctaText)}</p>` : ''}
    ${hashtagsText ? `<p class="small" style="margin:0;white-space:pre-wrap;">${esc(hashtagsText)}</p>` : ''}
  </article>`;
}
function renderVideoPlannerPreview(item, d) {
  const timeLabel = new Date(item.scheduled_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  return `<article class="card" style="padding:12px;border:1px solid rgba(148,163,184,.18);">
    <div class="row" style="justify-content:space-between;align-items:flex-start;gap:8px;">
      <strong>${esc(timeLabel)}</strong>
      <span class="small">Длительность: ${esc(String(item.duration_sec || d.videoDurationPreset || '30'))} сек · Формат: ${esc(String(item.format || item.orientation || d.videoOrientation || 'vertical'))}</span>
    </div>
    <p class="small" style="margin:8px 0 4px 0;"><strong>Тема:</strong> ${esc(item.topic || '—')}</p>
    <p class="small" style="margin:0 0 4px 0;"><strong>Hook:</strong> ${esc(item.hook || '—')}</p>
    <p class="small" style="margin:0 0 4px 0;"><strong>Script:</strong> ${esc(item.script || '—')}</p>
    <p class="small" style="margin:0;"><strong>CTA:</strong> ${esc(item.cta || '—')}</p>
  </article>`;
}
function renderPlannerPreview(data, config) {
  const rows = data.selectedDayItems
    .slice()
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .map((item) => config.previewType === 'video' ? renderVideoPlannerPreview(item, data.d) : renderPostPlannerPreview(item, data.d))
    .join('');
  return rows || '<p class="small">Выберите день, чтобы увидеть детали.</p>';
}
function getPlannerRenderConfig(kind, d) {
  if (normalizePlannerKind(kind) === 'video') {
    return {
      previewType: 'video',
      panelLabel: 'Видео-план',
      fieldConfig: {
        secondaryField: selectField('plannerOrientation', 'Формат видео', String(d.videoOrientation || 'vertical'), [{ value: 'vertical', label: 'Shorts/Reels (9:16)' }, { value: 'horizontal', label: 'Обычное (16:9)' }]),
        tertiaryField: selectField('plannerDuration', 'Длительность', String(d.videoDurationPreset || d.videoWeekDurationPreset || '30'), String(d.videoOrientation || 'vertical') === 'horizontal'
          ? [{ value: '120', label: '120 сек' }, { value: '180', label: '180 сек' }, { value: '240', label: '240 сек' }, { value: '300', label: '300 сек' }, { value: '360', label: '360 сек' }, { value: '420', label: '420 сек' }, { value: '480', label: '480 сек' }]
          : [{ value: '20', label: '20 сек' }, { value: '30', label: '30 сек' }, { value: '40', label: '40 сек' }, { value: '60', label: '60 сек' }]),
        postsPerDayLabel: 'Видео в день',
        topicPlaceholder: 'Например: короткие видео для салона красоты',
        platformsMarkup: `<label class="create-toggle"><input id="plannerPlatformFacebook" type="checkbox" ${d.platforms?.facebook ? 'checked' : ''}/> Facebook</label>
              <label class="create-toggle"><input id="plannerPlatformInstagram" type="checkbox" ${d.platforms?.instagram ? 'checked' : ''}/> Instagram</label>
              <label class="create-toggle"><input id="plannerPlatformYouTube" type="checkbox" ${d.platforms?.youtube ? 'checked' : ''}/> YouTube</label>`,
      },
    };
  }
  return {
    previewType: 'post',
    panelLabel: 'План постов',
    fieldConfig: {
      secondaryField: '<div></div>',
      tertiaryField: `<div class="field"><label>Медиа</label><label class="create-toggle"><input id="plannerImageEnabled" type="checkbox" ${d.imageEnabled ? 'checked' : ''} /> С картинкой</label></div>`,
      postsPerDayLabel: 'Постов в день',
      topicPlaceholder: 'Если нужно сузить тему внутри выбранной ниши',
      platformsMarkup: `<label class="create-toggle"><input id="plannerPlatformFacebook" type="checkbox" ${d.platforms?.facebook ? 'checked' : ''}/> Facebook</label>
              <label class="create-toggle"><input id="plannerPlatformInstagram" type="checkbox" ${d.platforms?.instagram ? 'checked' : ''}/> Instagram</label>`,
    },
  };
}
function renderPlanner(data, config) {
  const cardTitle = (day) => {
    const dt = new Date(`${day}T00:00:00`);
    return Number.isFinite(dt.getTime())
      ? dt.toLocaleDateString('ru-RU', { weekday: 'long', day: '2-digit', month: '2-digit' })
      : day;
  };
  const cardSubtitle = (rows) => {
    const count = Array.isArray(rows) ? rows.length : 0;
    if (!count) return 'Публикаций пока нет';
    return count === 1 ? '1 слот публикации' : `${count} слота публикации`;
  };
  const renderDayCard = (day, rows) => {
    const previewItem = Array.isArray(rows) && rows.length ? rows[0] : null;
    const active = data.effectiveSelectedDate === day;
    return `<button type="button" class="card create-planner-day-card ${active ? 'is-active' : ''}" data-planner-day="${esc(day)}" style="text-align:left;padding:14px;border:1px solid ${active ? 'rgba(59,130,246,.45)' : 'rgba(148,163,184,.18)'};">
      <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;">
        <div>
          <h4 style="margin:0 0 4px 0;">${esc(cardTitle(day))}</h4>
          <p class="small" style="margin:0;">${esc(cardSubtitle(rows))}</p>
        </div>
        <span class="pill">${esc(String((Array.isArray(rows) ? rows.length : 0) || 0))}</span>
      </div>
      <p class="small" style="margin:10px 0 0 0;">${esc(planDayPreview(previewItem) || 'Откройте день, чтобы увидеть детали.')}</p>
    </button>`;
  };
  const sections = !data.dayKeys.length
    ? '<p class="small">После генерации здесь появятся карточки по дням.</p>'
    : (data.cfg.days === 7
      ? `<div style="display:grid;gap:10px;">${data.dayKeys.map((day) => renderDayCard(day, data.dayMap[day] || [])).join('')}</div>`
      : `<div style="display:grid;gap:12px;">
          ${groupPlannerDays(data.dayKeys).map((group, index) => {
            const open = index === 0 ? 'open' : '';
            return `<details class="card" ${open} style="padding:12px;">
              <summary style="cursor:pointer;font-weight:600;">Неделя ${group.index}: дни ${group.from}-${group.to}</summary>
              <div style="display:grid;gap:10px;margin-top:12px;">
                ${group.days.map((day) => renderDayCard(day, data.dayMap[day] || [])).join('')}
              </div>
            </details>`;
          }).join('')}
        </div>`);
  return {
    sections,
    preview: renderPlannerPreview(data, config),
    previewTitle: data.effectiveSelectedDate ? cardTitle(data.effectiveSelectedDate) : (data.selectedTopic || data.cfg.title),
  };
}
function directorLocalTopicIdeas(d, count = DIRECTOR_TOPIC_IDEA_COUNT, seed = 0) {
  if (d?.customTopicMode) return [];
  if (typeof DIRECTOR_NICHE_ENGINE.getRandomTopicIdeas === 'function') {
    return DIRECTOR_NICHE_ENGINE.getRandomTopicIdeas(directorCurrentNicheId(d), count, seed);
  }
  return [];
}
function directorLocalAngles(d) {
  if (typeof DIRECTOR_NICHE_ENGINE.getContentAngles === 'function') {
    return DIRECTOR_NICHE_ENGINE.getContentAngles(directorCurrentNicheId(d));
  }
  return [];
}
function directorTopicBelongsToNiche(topic, d) {
  const text = String(topic || '').trim().toLowerCase();
  if (!text) return false;
  const nicheMeta = directorCurrentNicheMeta(d);
  const banned = Array.isArray(nicheMeta?.bannedCrossNicheWords) ? nicheMeta.bannedCrossNicheWords : [];
  return !banned.some((word) => String(word || '').trim() && text.includes(String(word).trim().toLowerCase()));
}
function directorAngleHeadlineHint(angle) {
  const raw = String(angle || '').trim();
  if (!raw) return '';
  const colonPart = raw.includes(':') ? raw.split(':').slice(1).join(':').trim() : raw;
  const cleaned = String(colonPart || raw)
    .replace(/^через\s+/i, '')
    .replace(/^подход\s+/i, '')
    .replace(/^фокус\s+/i, '')
    .replace(/\.$/, '')
    .trim();
  return cleaned.length > 56 ? `${cleaned.slice(0, 53).trim()}...` : cleaned;
}
function directorHeadlineByAngle(topic, angle) {
  const base = String(topic || '').trim();
  if (!base) return '';
  return base;
}
function directorHeadlineItems(topics, angle) {
  return (Array.isArray(topics) ? topics : [])
    .map((topic, idx) => {
      const rawTopic = String(topic || '').trim();
      if (!rawTopic) return null;
      return {
        index: idx,
        rawTopic,
        title: directorHeadlineByAngle(rawTopic, angle),
      };
    })
    .filter(Boolean);
}
function directorIdeasButtonLabel(directorState, loading = false) {
  if (loading) return 'Подбираем заголовки…';
  const hasTopics = Array.isArray(directorState?.topicPool) && directorState.topicPool.length > 0;
  return hasTopics ? `Обновить ${DIRECTOR_TOPIC_IDEA_COUNT} заголовков` : 'Сгенерировать темы';
}
function progressBar(value, max) {
  const pct = max > 0 ? Math.max(2, Math.min(100, Math.round((value / max) * 100))) : 0;
  return `<div class="progress"><span style="width:${pct}%;"></span></div>`;
}
function emptyState(title, text, buttonLabel, path) {
  return `<div class="empty"><h3>${esc(title)}</h3><p class="small">${esc(text)}</p>${buttonLabel ? `<button class="btn btn-primary" data-link="${esc(path)}">${esc(buttonLabel)}</button>` : ''}</div>`;
}

function blogSelectedSlug() {
  try {
    return new URLSearchParams(location.search).get('slug') || '';
  } catch {
    return '';
  }
}

function blogContentToHtml(content, articleTitle = '') {
  const normalizeTitle = (v) => String(v || '')
    .toLowerCase()
    .replace(/^#+\s*/, '')
    .replace(/[^\p{L}\p{N}\s]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const titleNorm = normalizeTitle(articleTitle);
  let droppedTitleLines = 0;
  const lines = String(content || '').split('\n');
  return lines.map((line) => {
    const t = line.trim();
    if (!t) return '<p class="small">&nbsp;</p>';
    const lineNorm = normalizeTitle(t);
    const isTitleDuplicate = titleNorm && lineNorm === titleNorm;
    if (isTitleDuplicate && droppedTitleLines < 3) {
      droppedTitleLines += 1;
      return '';
    }
    if (t.startsWith('### ')) return `<h4>${esc(t.slice(4))}</h4>`;
    if (t.startsWith('## ')) return `<h3>${esc(t.slice(3))}</h3>`;
    if (t.startsWith('# ')) return `<h2>${esc(t.slice(2))}</h2>`;
    if (/^\d+\.\s+/.test(t) || t.startsWith('- ')) return `<p class="small">${esc(t)}</p>`;
    return `<p>${esc(t)}</p>`;
  }).join('');
}

const WizardUtils = (typeof window !== 'undefined' && window.WizardUtils) ? window.WizardUtils : {};
const WIZARD_BUSINESS_TYPES = [
  'SaaS / IT',
  'Салон красоты',
  'Интернет-магазин',
  'Эксперт / консалтинг',
  'Другое',
];
const WIZARD_GOALS = ['Лиды', 'Продажи', 'Охваты', 'Бренд'];
const WIZARD_TONES = ['Экспертный', 'Дружелюбный', 'Продающий', 'Провокационный'];
const WIZARD_NICHE_HINTS = [
  'SMM и маркетинг', 'Косметология', 'Барбершоп', 'Автосервис', 'Детейлинг', 'Ремонт квартир',
  'Психология', 'Консалтинг', 'Онлайн-курсы', 'Фитнес', 'Стоматология', 'Ресторан', 'Кафе',
  'Интернет-магазин одежды', 'Недвижимость', 'Юридические услуги',
];
const WIZARD_OUTPUT_OPTIONS = [
  { key: 'plan7', label: 'Контент-план на 7 дней' },
  { key: 'posts10', label: '10 готовых постов' },
  { key: 'reels5', label: '5 идей для Reels/Shorts' },
  { key: 'funnel', label: 'Воронка прогрева (серия тем)' },
  { key: 'hashtags', label: 'Хештеги и CTA' },
  { key: 'bio', label: 'Описание профиля' },
];
const CREATE_QUICK_TOPIC_POOL_BY_CATEGORY = {
  business: [
    '3 ошибки, из-за которых клиент переплачивает за услугу',
    'Чек-лист: что спросить у подрядчика до оплаты',
    'Кейс: как сократили срок услуги без потери качества',
    'Сравнение: разовая услуга или долгосрочное сопровождение',
    '5 признаков, что услуга вам действительно подходит',
    'Как проверить компетентность исполнителя за 10 минут',
    'Почему "дешево" часто выходит дороже: разбор на примере',
    'Что должно быть в договоре, чтобы не потерять деньги',
  ],
  marketing: [
    '3 ошибки в продвижении, которые сливают бюджет',
    'Чек-лист запуска рекламы: от оффера до аналитики',
    'Кейс: как подняли заявки без увеличения бюджета',
    'Сравнение: органический контент vs таргет в 2026',
    '5 рабочих форматов контента для стабильных лидов',
    'Почему охваты есть, а продаж нет: что проверить',
    'Как быстро понять, что креатив не работает',
    'План контента на неделю для малого бизнеса',
  ],
  fitness: [
    '3 ошибки новичков, которые тормозят прогресс',
    'Чек-лист: как безопасно начать тренировки после паузы',
    'Кейс: как выйти на результат за 30 дней без перегруза',
    'Сравнение: домашние тренировки или зал',
    '5 привычек, которые ускоряют прогресс в форме',
    'Почему вес стоит: главные причины и решения',
    'Как составить реалистичный план тренировок на неделю',
    'Что важнее для результата: питание или тренировки',
  ],
  ecommerce: [
    '3 ошибки карточки товара, из-за которых нет продаж',
    'Чек-лист: как оформить карточку, чтобы росла конверсия',
    'Кейс: как подняли средний чек в интернет-магазине',
    'Сравнение: скидка или бонус - что продает лучше',
    '5 элементов, которые повышают доверие к магазину',
    'Как сократить брошенные корзины без агрессивных скидок',
    'Почему товар смотрят, но не покупают: разбор',
    'Как написать описание товара, которое продает',
  ],
  beauty: [
    '3 ошибки в уходе, которые портят результат процедур',
    'Чек-лист подготовки к процедуре: что важно сделать заранее',
    'Кейс: как получили заметный эффект за короткий курс',
    'Сравнение: две популярные процедуры и кому что подходит',
    '5 советов по уходу, чтобы продлить результат',
    'Как выбрать мастера и не пожалеть после первого визита',
    'Почему результат "не держится": основные причины',
    'Что нельзя делать после процедуры: памятка клиенту',
  ],
  auto: [
    '3 ошибки автовладельцев при выборе сервиса',
    'Чек-лист перед визитом в СТО: что подготовить',
    'Кейс: как предотвратили дорогой ремонт вовремя',
    'Сравнение: оригинальные запчасти или качественный аналог',
    '5 признаков, что машине нужна срочная диагностика',
    'Как говорить с мастером, чтобы не навязали лишнее',
    'Почему "дотяну до потом" приводит к большим тратам',
    'Что проверить после ремонта перед оплатой',
  ],
  fallback: [
    '3 частые ошибки клиентов при выборе решения',
    'Чек-лист: как подготовиться перед обращением',
    'Кейс: как получили измеримый результат за короткий срок',
    'Сравнение: 2 подхода и какой выбрать',
    '5 практических советов, которые экономят бюджет',
    'Как оценить качество услуги до старта работы',
    'Что чаще всего упускают на старте проекта',
    'Какие вопросы задавать, чтобы избежать рисков',
  ],
};

function buildCreateQuickTopics(category, version = 0) {
  const normalizedNicheId = normalizeNicheIdSafe(category || '');
  if (
    normalizedNicheId
    && normalizedNicheId !== 'fallback'
    && typeof DIRECTOR_NICHE_ENGINE.getRandomTopicIdeas === 'function'
  ) {
    return DIRECTOR_NICHE_ENGINE.getRandomTopicIdeas(normalizedNicheId, 5, version);
  }
  const key = String(category || 'fallback');
  const pool = CREATE_QUICK_TOPIC_POOL_BY_CATEGORY[key] || CREATE_QUICK_TOPIC_POOL_BY_CATEGORY.fallback;
  const count = Math.min(5, pool.length);
  const seedBase = Array.from(`${key}:${Number(version) || 0}`).reduce((acc, ch) => acc + ch.charCodeAt(0), 0) || 1;
  let seed = seedBase;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const shuffled = [...pool].sort(() => rnd() - 0.5);
  return shuffled.slice(0, count);
}

function defaultAiWizardState() {
  return {
    step: 1,
    status: 'idle', // idle | typing | analyzing | submitting
    project_id: '',
    business_type: '',
    niche: '',
    product_summary: '',
    goal: '',
    tone: '',
    language: 'ru',
    platforms: { facebook: true, instagram: true },
    outputs: {
      plan7: true,
      posts10: true,
      reels5: false,
      funnel: false,
      hashtags: true,
      bio: false,
    },
  };
}

function wizardSelectedPlatforms(w) {
  const src = w?.platforms || {};
  const out = [
    src.facebook ? 'facebook' : null,
    src.instagram ? 'instagram' : null,
  ].filter(Boolean);
  return out.length ? out : ['facebook', 'instagram'];
}

function ensureAiWizardState() {
  if (!state.aiWizard) state.aiWizard = defaultAiWizardState();
}

function loadAiWizardDraft() {
  ensureAiWizardState();
  try {
    const raw = localStorage.getItem('aiWizardDraftV2');
    if (!raw) return;
    const parsed = JSON.parse(raw);
    state.aiWizard = {
      ...defaultAiWizardState(),
      ...parsed,
      platforms: { ...defaultAiWizardState().platforms, ...(parsed.platforms || {}) },
      outputs: { ...defaultAiWizardState().outputs, ...(parsed.outputs || {}) },
    };
  } catch {}
}

function saveAiWizardDraft() {
  try {
    ensureAiWizardState();
    localStorage.setItem('aiWizardDraftV2', JSON.stringify(state.aiWizard));
  } catch {}
}

function mapWizardStateToExistingPayload(w) {
  const mapper = WizardUtils.mapWizardStateToExistingPayload;
  const mapped = typeof mapper === 'function' ? mapper(w) : {
    project_id: w.project_id ? Number(w.project_id) : null,
    business_type: String(w.business_type || '').trim(),
    niche: String(w.niche || '').trim(),
    goal: String(w.goal || '').trim(),
    language: String(w.language || 'ru').trim(),
  };
  return {
    ...mapped,
    platforms: Array.isArray(mapped?.platforms) && mapped.platforms.length ? mapped.platforms : wizardSelectedPlatforms(w),
  };
}

function buildPreviewFromWizard(w) {
  const fn = WizardUtils.generateWizardPreview;
  if (typeof fn === 'function') return fn(w);
  const niche = (w.niche || 'ваша ниша').trim();
  const tone = (w.tone || 'Дружелюбный').toLowerCase();
  const goal = (w.goal || 'Охваты').toLowerCase();
  return {
    weeklyTopic: `Неделя 1: «${niche} — практические советы и кейсы»`,

    strategyMix: { expert: 50, nurture: 30, sales: 20 },
    focusHint: `Фокус: ${goal}. Тон: ${tone}. Давайте 1 конкретную пользу в каждом посте.`,
  };
}

function getWizardValidationErrors(w, step) {
  const errors = {};
  if (step >= 1) {
    if (!String(w.business_type || '').trim()) errors.business_type = 'Выберите тип бизнеса';
    if (!String(w.niche || '').trim()) errors.niche = 'Укажите нишу';
    if (!String(w.product_summary || '').trim()) errors.product_summary = 'Кратко опишите продукт/услугу';
  }
  if (step >= 2) {
    if (!String(w.goal || '').trim()) errors.goal = 'Выберите цель';
    if (!String(w.tone || '').trim()) errors.tone = 'Выберите стиль';
    if (!wizardSelectedPlatforms(w).length) errors.platforms = 'Выберите хотя бы одну платформу';
  }
  if (step >= 3) {
    const selected = Object.values(w.outputs || {}).filter(Boolean).length;
    if (!selected) errors.outputs = 'Выберите минимум один результат генерации';
  }
  return errors;
}

function wizardStatusLabel(status) {
  const map = {
    idle: 'Готово к запуску',
    typing: 'Заполняем контекст',
    analyzing: 'AI анализирует ввод',
    submitting: 'Генерируем…',
  };
  return map[String(status || 'idle')] || 'Готово к запуску';
}

function chipsGroup(id, ariaLabel, values, selected, dataAttr) {
  return `
    <div id="${id}" class="wizard-chips" role="group" aria-label="${esc(ariaLabel)}">
      ${values.map((v) => `<button type="button" class="wizard-chip ${String(v) === String(selected) ? 'active' : ''}" ${dataAttr}="${esc(v)}" aria-pressed="${String(v) === String(selected) ? 'true' : 'false'}">${esc(v)}</button>`).join('')}
    </div>
  `;
}

function Step1Business(w, projectOptions, errors) {
  return `
    <div class="wizard-step-block">
      <h3>О бизнесе</h3>
      ${selectField('wizardProject', 'Проект', w.project_id, projectOptions)}
      <div class="field">
        <label>Тип бизнеса</label>
        ${chipsGroup('wizardBusinessType', 'Тип бизнеса', WIZARD_BUSINESS_TYPES, w.business_type, 'data-wizard-business')}
        ${errors.business_type ? `<p class="small wizard-error">${esc(errors.business_type)}</p>` : ''}
      </div>
      <div class="field">
        <label for="wizardNiche">Ниша</label>
        <input id="wizardNiche" list="wizardNicheHints" value="${esc(w.niche)}" placeholder="Например, косметология, автосервис, онлайн-курсы" aria-describedby="wizardNicheHelp" />
        <datalist id="wizardNicheHints">${WIZARD_NICHE_HINTS.map((i) => `<option value="${esc(i)}"></option>`).join('')}</datalist>
        <p id="wizardNicheHelp" class="small wizard-inline-help">Можно выбрать подсказку или ввести вручную.</p>
        ${errors.niche ? `<p class="small wizard-error">${esc(errors.niche)}</p>` : ''}
      </div>
      ${field('wizardProductSummary', 'Коротко о продукте/услуге', 'textarea', w.product_summary || '', '1–2 предложения: что продаёте и чем полезны клиенту')}
      ${errors.product_summary ? `<p class="small wizard-error">${esc(errors.product_summary)}</p>` : ''}
      <p class="small wizard-inline-help">AI использует это, чтобы настроить тон и темы контента.</p>
    </div>
  `;
}

function Step2GoalTone(w, errors) {
  const preview = buildPreviewFromWizard(w);
  return `
    <div class="wizard-step-block">
      <h3>Цель и стиль</h3>
      <div class="field">
        <label>Цель</label>
        ${chipsGroup('wizardGoal', 'Цель', WIZARD_GOALS, w.goal, 'data-wizard-goal')}
        ${errors.goal ? `<p class="small wizard-error">${esc(errors.goal)}</p>` : ''}
      </div>
      <div class="field">
        <label>Стиль (тон)</label>
        ${chipsGroup('wizardTone', 'Стиль', WIZARD_TONES, w.tone, 'data-wizard-tone')}
        ${errors.tone ? `<p class="small wizard-error">${esc(errors.tone)}</p>` : ''}
      </div>
      <div class="field">
        <label>Платформы контент-плана</label>
        <div class="row" style="gap:12px;flex-wrap:wrap;">
          <label class="create-toggle"><input id="wizardPlatformFacebook" type="checkbox" ${w.platforms?.facebook ? 'checked' : ''}/> Facebook</label>
          <label class="create-toggle"><input id="wizardPlatformInstagram" type="checkbox" ${w.platforms?.instagram ? 'checked' : ''}/> Instagram</label>
        </div>
        ${errors.platforms ? `<p class="small wizard-error">${esc(errors.platforms)}</p>` : ''}
        <p class="small">Если выбрать обе сети, для контент-плана будут создаваться отдельные публикации на каждую платформу.</p>
      </div>
      ${selectField('wizardLang', 'Язык', w.language || 'ru', [{ value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' }])}
      <article class="wizard-ai-hint" aria-live="polite">
        <h4>AI подсказка</h4>
        <p class="small">${esc(preview.focusHint)}</p>
      </article>
    </div>
  `;
}

function PreviewCard(w) {
  const p = buildPreviewFromWizard(w);
  return `
    <article class="wizard-preview card" aria-live="polite">
      <h4>AI уже подготовил черновик</h4>
      <div class="small"><strong>Тема недели:</strong> ${esc(p.weeklyTopic)}</div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        <strong>Стратегия:</strong> экспертный ${Number(p.strategyMix.expert) || 0}% · прогрев ${Number(p.strategyMix.nurture) || 0}% · продажи ${Number(p.strategyMix.sales) || 0}%
      </div>
      <button id="wizardRefreshPreviewBtn" type="button" class="btn btn-ghost" style="margin-top:10px;">Обновить предпросмотр</button>
    </article>
  `;
}

function Step3GeneratePreview(w, errors) {
  return `
    <div class="wizard-step-block">
      <h3>Генерация и предпросмотр</h3>
      <p class="small">Вы получите план и черновики. Можно будет отредактировать перед публикацией.</p>
      <div class="wizard-checks" role="group" aria-label="Что сгенерировать">
        ${WIZARD_OUTPUT_OPTIONS.map((item) => `
          <label class="wizard-check-item">
            <input type="checkbox" data-wizard-output="${esc(item.key)}" ${w.outputs?.[item.key] ? 'checked' : ''} />
            <span>${esc(item.label)}</span>
          </label>
        `).join('')}
      </div>
      ${errors.outputs ? `<p class="small wizard-error">${esc(errors.outputs)}</p>` : ''}
      <div class="small wizard-plan-note">В Free Trial доступны базовые лимиты. В Growth открываются расширенные лимиты и автопостинг.</div>
    </div>
  `;
}

// AI SMM Wizard v2: 3-step + preview
// Files touched: frontend/app.js, frontend/styles.css, frontend/wizard_utils.js, tests/unit/wizard_utils.test.js
// Why: replace long form with step-by-step UX while preserving legacy backend payload contract on submit.
function WizardContainer(params) {
  ensureAiWizardState();
  const w = state.aiWizard;
  const step = Number(w.step || 1);
  const stepErrors = getWizardValidationErrors(w, step);
  const canGoNext = Object.keys(getWizardValidationErrors(w, step)).length === 0;
  const projectOptions = params.projectOptions.length ? params.projectOptions : [{ value: '', label: 'Проект по умолчанию' }];

  let stepHtml = '';
  if (step === 1) stepHtml = Step1Business(w, projectOptions, stepErrors);
  if (step === 2) stepHtml = Step2GoalTone(w, stepErrors);
  if (step === 3) stepHtml = Step3GeneratePreview(w, stepErrors);

  return `
    <section id="aiWizardBlock" class="card" style="margin-top:18px;">
      <div class="wizard-head">
        <h2>Создать стратегию и контент</h2>
        <p class="small">3 шага — и AI подготовит план и примеры постов. Можно отредактировать перед запуском.</p>
        <div class="wizard-meta-row">
          <span class="small"><strong>Шаг ${step} из 3</strong></span>
          <span class="small">${esc(wizardStatusLabel(w.status || 'idle'))}</span>
        </div>
        ${progressBar(step, 3)}
      </div>

      <div class="stepper wizard-stepper-3">
        <div class="step ${step === 1 ? 'active' : ''}">1. О бизнесе</div>
        <div class="step ${step === 2 ? 'active' : ''}">2. Цель и стиль</div>
        <div class="step ${step === 3 ? 'active' : ''}">3. Генерация и предпросмотр</div>
      </div>

      <div class="wizard-grid">
        <div>${stepHtml}</div>
        ${step === 3 ? `<div>${PreviewCard(w)}</div>` : ''}
      </div>

      <div class="wizard-actions">
        <button id="wizardPrevBtn" type="button" class="btn btn-ghost" ${step === 1 || w.status === 'submitting' ? 'disabled' : ''}>Назад</button>
        ${step < 3
          ? `<button id="wizardNextBtn" type="button" class="btn btn-secondary" ${(!canGoNext || w.status === 'submitting') ? 'disabled' : ''}>Далее</button>`
          : `<button id="wizardSubmitBtn" type="button" class="btn btn-primary" ${(Object.keys(stepErrors).length > 0 || w.status === 'submitting') ? 'disabled' : ''}>${w.status === 'submitting' ? 'Генерируем…' : 'Создать план и черновики'}</button>`
        }
      </div>
    </section>
  `;
}

function appLayout(path, title, body) {
  const isAdminArea = path.startsWith('/admin');
  const links = isAdminArea
    ? [['/admin', 'Админ', 'admin']]
    : [
        ['/dashboard', 'Панель', 'dashboard'],
        ['/create', 'Создать', 'create'],
        ['/calendar', 'Календарь', 'history'],
        ['/connections', 'Подключения', 'connections'],
        ['/history', 'История', 'history'],
        ['/settings', 'Настройки бренда', 'settings'],
        ['/billing', 'Биллинг', 'billing'],
        ['/support', 'Поддержка', 'support'],
      ];
  const navHtml = links.map(([p, l, i]) => `<button type="button" data-link="${p}" class="nav-link ${path === p ? 'active' : ''}">${icon(i)}<span>${esc(l)}</span></button>`).join('');
  const logoutNav = !isAdminArea ? `<button type="button" id="sidebarLogoutBtn" class="nav-link nav-link-logout">${icon('logout')}<span>Выйти</span></button>` : '';
  const footer = `<div class="footer-note"><div class="small">Без скрытых платежей. Прозрачные тарифы. Лимиты считаются в постах.</div><div class="small">Stripe защищенные платежи · SSL защищено · GDPR совместимо</div></div>`;
  return `<div class="layout page"><aside class="sidebar"><div class="brand-row"><img class="brand-logo" src="/assets/brand/logo-icon.svg?v=brand-mark-2026-03-06-01" alt="AutoSocial.tech"/><div><div class="brand-name">AutoSocial.tech</div><div class="small">AI SMM менеджер</div></div></div>${navHtml}${logoutNav}<div class="trust-row" style="margin-top:16px;"><span class="trust-chip">Stripe</span><span class="trust-chip">SSL</span><span class="trust-chip">GDPR</span></div></aside><div><header class="topbar"><div><strong>${esc(title)}</strong><div class="small">${esc(state.user?.email || '')} В· ${planBadge(state.user?.role === 'admin' ? 'admin' : (state.user?.plan || 'free'))}</div></div><div class="topbar-actions"><button id="themeToggleBtn" class="btn btn-ghost">${state.theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}</button></div></header><main class="content">${state.notice ? `<div class="notice ${state.notice.type === 'error' ? 'error' : 'ok'}">${esc(state.notice.text)}</div>` : ''}${body}${footer}</main></div></div>`;
}
function pageLogin() {
  const t = loginText;
  const isRegister = state.authMode !== 'login';
  const codeStep = !!state.authChallenge;
  const challengeFlow = state.authChallenge?.flow || (isRegister ? 'register' : 'login');
  const flowTitle = challengeFlow === 'register' ? t('flow_title_register') : t('flow_title_login');
  const showSocialLogin = false;
  const formTitle = codeStep ? flowTitle : (isRegister ? t('form_title_register') : t('form_title_login'));
  const submitLabel = codeStep ? t('submit_verify_code') : t('submit_get_code');
  const switchText = isRegister ? t('switch_text_register') : t('switch_text_login');
  const switchLabel = isRegister ? t('switch_label_register') : t('switch_label_login');
  const socialBlock = showSocialLogin ? `<div class="social-auth-row"></div>` : '';
  const authHint = codeStep
    ? `${t('auth_hint_code_prefix')} ${esc(state.authChallenge.email || '')}.`
    : t('auth_hint_default');
  const painCards = [
    {
      title: 'Контент забирает часы каждую неделю',
      text: 'Идеи, тексты, согласования и публикация вручную съедают время владельца или маркетолога.',
      icon: '<svg viewBox="0 0 24 24" class="icon"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>',
    },
    {
      title: 'Постинг идёт нерегулярно',
      text: 'Когда публикации зависят от ручного режима, соцсети быстро становятся хаотичными и нестабильными.',
      icon: '<svg viewBox="0 0 24 24" class="icon"><rect x="3.5" y="4.5" width="17" height="16" rx="2.4"></rect><path d="M8 3v3.5M16 3v3.5M3.5 9h17"></path></svg>',
    },
    {
      title: 'Посты не приводят к заявкам',
      text: 'Без понятной структуры, оффера и CTA контент набирает просмотры, но не помогает продавать.',
      icon: '<svg viewBox="0 0 24 24" class="icon"><path d="M4 18h16M7 14l3-3 3 2 4-5"></path><circle cx="17" cy="8" r="1.1"></circle></svg>',
    },
    {
      title: 'Рост упирается в операционку',
      text: 'Чтобы вести больше аккаунтов и кампаний, приходится нанимать людей вместо масштабирования процесса.',
      icon: '<svg viewBox="0 0 24 24" class="icon"><rect x="3" y="4" width="7" height="7" rx="1.4"></rect><rect x="14" y="4" width="7" height="7" rx="1.4"></rect><rect x="8.5" y="13" width="7" height="7" rx="1.4"></rect></svg>',
    },
  ];
  const features = [
    ['Готовые темы и идеи', 'Сервис подсказывает темы, углы подачи и форматы, чтобы не начинать с пустого листа.'],
    ['Посты и видео в одном сервисе', 'Генерируйте тексты, сценарии, структуры и материалы для регулярного контент-потока.'],
    ['Автопостинг по расписанию', 'Публикуйте в нужное время без ручной рутины и потери ритма.'],
    ['Контент-календарь', 'Планируйте неделю и месяц вперёд, чтобы видеть весь поток публикаций в одном месте.'],
    ['Понятно для малого бизнеса', 'Не нужен отдельный контент-отдел: владелец, маркетолог или SMM могут запустить процесс сами.'],
    ['Рост без хаоса', 'Больше проектов, клиентов и каналов без роста операционной нагрузки на команду.'],
  ];
  const pricing = MARKETING_PRICING_PLANS;

  return `<div class="landing-2026 page">
    <header class="landing-2026-topbar">
      <img src="/assets/brand/logo-full-light.svg" alt="AutoSocial.tech"/>
      <div class="landing-2026-top-actions">
        <button class="btn btn-link" data-link="/billing" type="button">${t('footer_pricing')}</button>
        <a class="btn btn-link" href="https://docs.google.com/document/d/1d7yV-Nxcunz4_DC9VHnCv136o1fnkUidyDhkYFhryPg" target="_blank" rel="noreferrer">${t('footer_privacy')}</a>
        <button class="btn btn-link" data-link="/contact" type="button">${t('footer_support')}</button>
      </div>
    </header>

    <section class="landing-2026-hero reveal">
      <div class="landing-2026-hero-copy">
        <span class="landing-2026-chip">Для малого бизнеса, маркетолога и in-house SMM без отдельной контент-команды</span>
        <h1>Генерируйте посты и видео для соцсетей и запускайте автопостинг из одного сервиса.</h1>
        <p>AutoSocial.tech помогает малому бизнесу быстрее вести соцсети: подсказывает темы, собирает контент, формирует календарь и публикует в Meta и YouTube без ручной рутины.</p>
        <div class="cta-row">
          <button id="heroRegisterBtn" class="btn btn-primary cta__button">Попробовать 7 дней бесплатно</button>
          <a class="btn btn-secondary cta__button" href="#landingPricing">Посмотреть тарифы</a>
        </div>
        <div class="landing-2026-cta-proof">
          <span class="landing-2026-cta-pill">7 дней бесплатно</span>
          <span class="landing-2026-cta-pill">Без карты</span>
          <span class="landing-2026-cta-pill">30 постов и 3 видео в trial</span>
        </div>
      </div>
      <div class="landing-2026-hero-visual">
        <div class="landing-2026-mockup">
          <div class="landing-2026-mock-head">
            <span></span><span></span><span></span>
          </div>
          <div class="landing-2026-mock-grid">
            <div class="landing-2026-skeleton lg"></div>
            <div class="landing-2026-skeleton"></div>
            <div class="landing-2026-skeleton"></div>
            <div class="landing-2026-skeleton wide"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="landing-2026-section">
      <h2>Почему малому бизнесу сложно вести соцсети стабильно</h2>
      <div class="landing-2026-grid-4">
        ${painCards.map((c) => `<article class="landing-2026-card"><div class="landing-2026-icon">${c.icon}</div><h3>${c.title}</h3><p>${c.text}</p></article>`).join('')}
      </div>
    </section>

    <section id="landingHow" class="landing-2026-section">
      <h2>Как AutoSocial.tech экономит время каждую неделю</h2>
      <div class="landing-2026-steps">
        <article class="landing-2026-card"><span class="landing-2026-step">01</span><h3>Выберите тему или получите идеи</h3><p>Сервис предлагает темы, форматы и углы подачи под ваш бизнес.</p></article>
        <article class="landing-2026-card"><span class="landing-2026-step">02</span><h3>Сгенерируйте посты и видео</h3><p>Получите текст, структуру, CTA и материалы для контента без долгой ручной подготовки.</p></article>
        <article class="landing-2026-card"><span class="landing-2026-step">03</span><h3>Запланируйте и публикуйте</h3><p>Соберите контент-календарь и поддерживайте регулярный постинг без хаоса.</p></article>
      </div>
    </section>

    <section class="landing-2026-demo">
      <h2>Что получает бизнес на выходе</h2>
      <p>Вместо ручного цикла "придумать -> написать -> согласовать -> опубликовать" вы получаете один рабочий процесс для идей, контента и автопостинга.</p>
      <div class="landing-2026-demo-box">
        <strong>В одном окне:</strong><br/>
        идеи и темы -> генерация постов и видео -> календарь -> публикация по расписанию
      </div>
    </section>

    <section class="landing-2026-section">
      <h2>Что получает малый бизнес вместо ручного SMM</h2>
      <div class="landing-2026-grid-3">
        ${features.map(([title, text]) => `<article class="landing-2026-card landing-2026-feature"><h3>${title}</h3><p>${text}</p></article>`).join('')}
      </div>
    </section>

    <section id="landingPricing" class="landing-2026-section">
      <div class="row" style="justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap;">
        <h2 style="margin:0;">Тарифы без перегруза и скрытых условий</h2>
        <button id="finalPricingBtn" class="btn btn-ghost" type="button">${t('footer_pricing')}</button>
      </div>
      <div class="landing-2026-pricing">
        ${pricing.map((p) => `<article class="landing-2026-card landing-2026-price ${p.key === 'growth' ? 'is-featured' : ''}">
          ${p.key === 'growth' ? '<span class="landing-2026-popular">Recommended</span>' : ''}
          <h3>${p.name}</h3>
          <p class="landing-2026-price-value">${p.price}<span>/month</span></p>
          <p class="small">${p.desc}</p>
          <ul>${p.points.map((pt) => `<li>${pt}</li>`).join('')}</ul>
          <button class="btn ${p.key === 'growth' ? 'btn-primary' : 'btn-secondary'} connection-btn-sm" type="button" data-pricing-cta="${p.key}">${p.cta}</button>
        </article>`).join('')}
      </div>
    </section>

    <section class="landing-2026-trust">
      <span class="landing-2026-trust-pill">GDPR compliant</span>
      <span class="landing-2026-trust-pill">Secure API</span>
      <span class="landing-2026-trust-pill">Encrypted data</span>
      <span class="landing-2026-trust-pill">Hosted in EU</span>
    </section>

    <section class="landing-2026-final">
      <h2>Попробуйте AutoSocial.tech на своём контенте в течение 7 дней</h2>
      <p>Free Trial показывает сценарий работы без риска: темы, генерация постов и видео, календарь и базовые лимиты без привязки карты.</p>
      <button id="finalRegisterBtn" class="btn btn-primary cta__button">Запустить Free Trial</button>
      <div class="landing-2026-cta-proof" style="justify-content:center;">
        <span class="landing-2026-cta-pill">7 дней бесплатно</span>
        <span class="landing-2026-cta-pill">Без карты</span>
        <span class="landing-2026-cta-pill">Отмена в любой момент</span>
      </div>
    </section>

    <section class="landing-2026-auth-wrap">
      <article class="landing-2026-auth-info landing-2026-card">
        <h3>Создайте аккаунт за минуту</h3>
        <p>Подтверждение по email, без карты на старте. После входа вы сразу попадете в мастер создания контента и сможете использовать 7-дневный trial с лимитом 30 постов, 3 видео и 1 проекта.</p>
        <div class="trust-row">
          <span class="trust-chip">SSL</span>
          <span class="trust-chip">GDPR</span>
          <span class="trust-chip">Stripe</span>
        </div>
      </article>
      <section class="auth-panel auth-form-panel landing-2026-auth-form">
        ${state.notice ? `<div class="notice ${state.notice.type === 'error' ? 'error' : 'ok'}">${esc(state.notice.text)}</div>` : ''}
        <h2>${formTitle}</h2>
        <p class="small mobile-microcopy">${authHint}</p>
        ${socialBlock}
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
        ${codeStep ? field('authCode', t('field_code'), 'text', '', t('placeholder_code')) : ''}
        ${codeStep ? '' : '<input id="authWebsite" type="text" autocomplete="off" tabindex="-1" style="position:absolute;left:-10000px;opacity:0;pointer-events:none;" />'}
        <button id="authSubmitBtn" class="btn btn-primary auth-submit">${submitLabel}</button>
        ${codeStep ? `<button id="authResendBtn" class="btn btn-ghost auth-submit" type="button" style="margin-top:10px;">${t('resend_code')}</button>` : ''}
        ${codeStep ? `<button id="authBackBtn" class="btn btn-link" type="button">${t('back_to_auth')}</button>` : ''}
        <div class="auth-switch-row">
          <span class="small">${switchText}</span>
          <button id="authSwitchBtn" class="btn btn-link" type="button" ${codeStep ? 'disabled' : ''}>${switchLabel}</button>
        </div>
      </section>
    </section>
  </div>`;
}

function pageDashboard() {
  const billing = state.billing || { plan: 'free', usage: {}, limits: {}, remaining: {} };
  const stats = state.dashboardMetrics || {};
  const dashboardUserId = String(state.user?.id || 'anon').trim() || 'anon';
  const onboardingDismissKey = `dashboardOnboardingDismissed:${dashboardUserId}`;
  const summary = stats.summary || { reach: 0, views: 0, likes: 0, comments: 0, shares: 0, items: 0, by_platform: {} };
  const current = summary.current || summary;
  const prev = summary.prev || { reach: 0, views: 0, clicks: 0, likes: 0, comments: 0, shares: 0, items: 0, engagement_rate: 0 };
  const delta = summary.delta || {};
  const aiScore = stats.aiScore || { current: 0, delta_7d: 0, delta_vs_prev_period: 0, breakdown: null, timeseries: [] };
  const forecast = stats.forecast || { horizon_days: 7, confidence: { level: 'low', reasons: ['недостаточно данных'] }, totals: { reach: 0, views: 0, engagement_rate_avg: 0 }, scenarios: { current: {}, plus30: {} }, points: [] };
  const byPlatform = summary.by_platform || current.by_platform || {
    facebook: { reach: 0, views: 0, items: 0 },
    instagram: { reach: 0, views: 0, items: 0 },
    youtube: { reach: 0, views: 0, items: 0 },
  };
  const points = Array.isArray(stats?.timeseries?.points) ? stats.timeseries.points : [];
  const aiPoints = Array.isArray(aiScore.timeseries) ? aiScore.timeseries : [];
  const insights = Array.isArray(stats.insights) ? stats.insights : [];
  const recent = Array.isArray(stats.recent) ? stats.recent : [];
  const chartMetric = stats.chartMetric || 'reach';
  const recentSort = stats.recentSort || 'engagement';
  const fmt = (n) => Number(n || 0).toLocaleString('ru-RU');
  const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`;
  const deltaFmt = (v) => `${Number(v || 0) >= 0 ? '+' : ''}${Number(v || 0).toFixed(1)}`;
  const deltaLabel = (obj) => {
    const abs = Number(obj?.abs || 0);
    const p = Number(obj?.pct || 0) * 100;
    return `${abs >= 0 ? '+' : ''}${abs.toFixed(1)} (${p >= 0 ? '+' : ''}${p.toFixed(1)}%)`;
  };

  const statusLabel = (kind) => kind === 'connected' ? 'подключено' : (kind === 'expiring' ? 'токен скоро истечет' : 'требует внимания');
  const statusClass = (kind) => kind === 'connected' ? 'is-ok' : (kind === 'expiring' ? 'is-warn' : 'is-bad');
  const tokenExpiring = (iso) => {
    if (!iso) return false;
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return false;
    return (t - Date.now()) <= 1000 * 60 * 60 * 24 * 3;
  };
  const metaReady = (state.connections || []).filter((c) => isConnectionReady(c));
  const fbStatus = !metaReady.length ? 'needs' : (metaReady.some((c) => tokenExpiring(c.token_expires_at)) ? 'expiring' : 'connected');
  const igReady = metaReady.filter((c) => String(c?.ig_user_id || '').trim());
  const igStatus = !igReady.length ? 'needs' : (igReady.some((c) => tokenExpiring(c.token_expires_at)) ? 'expiring' : 'connected');
  const ytConnected = !!state.youtubeConnection?.connected;
  const ytStatus = ytConnected ? 'connected' : 'needs';
  const hasConnectedChannels = fbStatus === 'connected' || igStatus === 'connected' || ytStatus === 'connected';
  const hasGeneratedContent = Number(billing?.usage?.posts_per_month || 0) > 0 || Number(billing?.usage?.videos_per_month || 0) > 0;
  const hasAnalyticsData = Number(current?.items || 0) > 0
    || recent.length > 0
    || points.some((p) => Number(p?.reach || 0) > 0 || Number(p?.views || 0) > 0 || Number(p?.engagement_rate || 0) > 0)
    || ['facebook', 'instagram', 'youtube'].some((key) => Number(byPlatform?.[key]?.items || 0) > 0 || Number(byPlatform?.[key]?.reach || 0) > 0 || Number(byPlatform?.[key]?.views || 0) > 0);
  const onboardingDismissed = localStorage.getItem(onboardingDismissKey) === '1';
  const shouldShowOnboardingHero = !stats.loading && !hasAnalyticsData && !onboardingDismissed;
  const shouldShowAnalyticsEmptyState = !stats.loading && !hasAnalyticsData;

  const fbSeries = points.map((p) => Number(p.facebook_reach || 0) + Number(p.facebook_views || 0));
  const igSeries = points.map((p) => Number(p.instagram_reach || 0) + Number(p.instagram_views || 0));
  const ytSeries = points.map((p) => Number(p.youtube_reach || 0) + Number(p.youtube_views || 0));
  const buildSpark = (vals, css) => {
    if (!vals.length) return `<div class="dash-sparkline ${css}"></div>`;
    const width = 220;
    const height = 46;
    const pad = 3;
    const maxV = Math.max(1, ...vals);
    const minV = Math.min(...vals, 0);
    const spread = Math.max(1, maxV - minV);
    const xAt = (i) => pad + (vals.length <= 1 ? 0 : (i * (width - pad * 2)) / (vals.length - 1));
    const yAt = (v) => pad + (height - pad * 2) - ((v - minV) / spread) * (height - pad * 2);
    const d = vals.map((v, i) => `${i ? 'L' : 'M'}${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).join(' ');
    return `<svg viewBox="0 0 ${width} ${height}" class="dash-sparkline ${css}" role="img" aria-label="sparkline"><path d="${d}"></path></svg>`;
  };

  const resolveSeries = () => {
    if (chartMetric === 'ai_score') {
      return aiPoints.map((p) => ({ day: p.day, value: Number(p.ai_score || 0) }));
    }
    if (chartMetric === 'engagement') {
      return points.map((p) => ({ day: p.day, value: Number(p.engagement_rate || 0) * 100 }));
    }
    return points.map((p) => ({ day: p.day, value: Number(p[chartMetric] || 0) }));
  };
  const chartSeries = resolveSeries();
  const chartStat = (() => {
    if (!chartSeries.length) return { avg: 0, peak: 0, worst: 0, peakDay: '—', worstDay: '—' };
    let sum = 0;
    let peak = -1;
    let worst = Number.POSITIVE_INFINITY;
    let peakDay = '';
    let worstDay = '';
    chartSeries.forEach((p) => {
      sum += Number(p.value || 0);

      if (p.value < worst) { worst = Number(p.value || 0); worstDay = p.day || ''; }
    });
    return { avg: sum / chartSeries.length, peak, worst, peakDay, worstDay };
  })();
  const chartUnit = chartMetric === 'engagement' ? 'percent' : (chartMetric === 'ai_score' ? 'score' : 'number');
  const chartValue = (v) => chartUnit === 'number' ? fmt(Math.round(v)) : `${Number(v || 0).toFixed(1)}${chartUnit === 'score' ? '' : '%'}`;
  const chartTitle = { reach: 'Охват аудитории', views: 'Просмотры контента', engagement: 'Уровень вовлечённости', ai_score: 'AI-Score' }[chartMetric] || 'Охват аудитории';
  const chartDescription = {
    reach: 'Показывает, сколько людей увидели ваш контент по дням за последние 30 дней.',
    views: 'Показывает, сколько просмотров набрал контент по дням за последние 30 дней.',
    engagement: 'Показывает, как менялась вовлечённость: лайки, комментарии и репосты относительно охвата.',
    ai_score: 'Показывает, как менялся AI-Score аккаунта на основе регулярности, вовлечённости и роста.',
  }[chartMetric] || 'Показывает динамику результатов по дням за последние 30 дней.';

  const mainChartHtml = (() => {
    if (stats.loading) return '<div class="dash-skeleton dash-skeleton-chart"></div>';
    if (!chartSeries.length) return '<p class="small">Нет данных. Нажмите «Синхронизировать».</p>';
    const width = 980;
    const height = 280;
    const padX = 28;
    const padY = 16;
    const chartW = width - padX * 2;
    const chartH = height - padY * 2;
    const maxValue = Math.max(1, ...chartSeries.map((p) => Number(p.value || 0)));

    const xAt = (i) => padX + (chartSeries.length <= 1 ? 0 : (i * chartW) / (chartSeries.length - 1));
    const yAt = (v) => padY + chartH - (Number(v || 0) / maxValue) * chartH;
    const d = chartSeries.map((p, i) => `${i ? 'L' : 'M'}${xAt(i).toFixed(2)} ${yAt(p.value).toFixed(2)}`).join(' ');
    const xLabels = [0, Math.floor((chartSeries.length - 1) / 2), chartSeries.length - 1]
      .filter((v, i, arr) => arr.indexOf(v) === i)
      .map((idx) => `<text x="${xAt(idx).toFixed(1)}" y="${height - 3}" text-anchor="middle">${esc((chartSeries[idx].day || '').slice(5))}</text>`)
      .join('');
    return `<div class="dash-chart-wrap">
      <svg viewBox="0 0 ${width} ${height}" class="dash-chart-svg dash-chart-svg-single" role="img" aria-label="${esc(chartTitle)}">
        <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" class="dash-chart-axis"></line>
        <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}" class="dash-chart-axis"></line>
        <path d="${d}" class="dash-chart-line dash-chart-line-primary"></path>
        ${xLabels}
      </svg>
      <div class="dash-chart-stats">
        <div><span>среднее</span><strong>${chartValue(chartStat.avg)}</strong></div>
        <div><span>пик</span><strong>${chartValue(chartStat.peak)}</strong><small>${esc((chartStat.peakDay || '').slice(5))}</small></div>
        <div><span>худший день</span><strong>${chartValue(chartStat.worst)}</strong><small>${esc((chartStat.worstDay || '').slice(5))}</small></div>
      </div>
    </div>`;
  })();

  const insightCards = (insights.slice(0, 4).map((item, idx) => {
    const title = String(item.title || '').toLowerCase();
    let cta = 'Открыть топ-контент';
    let action = 'open-top-content';
    if (title.includes('день')) {
      cta = 'Запланировать на лучший день';
      action = 'schedule-best-day';
    } else if (title.includes('формат')) {
      cta = 'Создать пост в этом формате';
      action = 'create-format-post';
    } else if (title.includes('регуляр')) {
      cta = 'Запланировать на лучший день';
      action = 'schedule-best-day';
    }
    const impact = String(item.impact || 'low').toLowerCase();
    return `<article class="dash-insight-card glass-card">
      <span class="dash-impact dash-impact-${esc(impact)}">${esc(impact.toUpperCase())}</span>
      <h4>${esc(item.title || 'Инсайт')}</h4>
      <p>${esc(item.text || '')}</p>
      <button type="button" class="btn btn-ghost dash-insight-cta" data-dash-insight-action="${esc(action)}" data-dash-insight-index="${idx}">${esc(cta)}</button>
    </article>`;
  }).join('')) || '<p class="small">Недостаточно данных для инсайтов.</p>';

  const sortedRecent = [...recent].sort((a, b) => {
    const ma = a?.metrics || {};
    const mb = b?.metrics || {};
    if (recentSort === 'reach') return Number(mb.reach || 0) - Number(ma.reach || 0);
    if (recentSort === 'views') return Number(mb.views || 0) - Number(ma.views || 0);
    return Number(b.engagement_rate || 0) - Number(a.engagement_rate || 0);
  });
  const recentRows = stats.loading
    ? '<tr><td colspan="6"><div class="dash-skeleton dash-skeleton-row"></div></td></tr>'
    : (sortedRecent.length
      ? sortedRecent.map((item) => {
        const m = item.metrics || {};
        const rate = Number(item.engagement_rate || 0) * 100;
        const rateClass = rate >= 6 ? 'high' : (rate >= 3 ? 'medium' : 'low');
        const published = item.published_at ? new Date(item.published_at).toLocaleDateString() : '—';
        const title = item.title || 'Публикация';
        const platform = (item.platform || '').toUpperCase();
        return `<tr class="dash-row-link" data-dash-item-url="${esc(item.url || '')}">
          <td><strong>${esc(title)}</strong><div class="small">${esc(platform)} · ${esc(item.content_type || 'post')}</div></td>
          <td>${fmt(m.reach)}</td>
          <td>${fmt(m.views)}</td>
          <td><span class="dash-er-indicator ${rateClass}"></span>${rate.toFixed(2)}%</td>
          <td>${esc(published)}</td>
          <td><button type="button" class="btn btn-ghost dash-delete-btn" data-dash-recent-delete="${item.id}">Удалить</button></td>
        </tr>`;
      }).join('')
      : '<tr><td colspan="6" class="small">Нет материалов за период.</td></tr>');

  const skeletonCards = '<div class="dash-skeleton-grid"><div class="dash-skeleton"></div><div class="dash-skeleton"></div><div class="dash-skeleton"></div><div class="dash-skeleton"></div></div>';
  const projectLimitLabel = Number(billing?.limits?.projects || 0) >= 999999 ? 'Без ограничений' : String(billing?.limits?.projects || '—');
  const accountLimitLabel = Number(billing?.limits?.accounts_connected || 0) >= 999999 ? '\u0411\u0435\u0437 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0439' : String(billing?.limits?.accounts_connected || '\u2014');
  const postsRemaining = Math.max(0, Number(billing?.remaining?.posts_generated ?? ((billing?.limits?.posts_per_month || 0) - (billing?.usage?.posts_per_month || 0))));
  const videosRemaining = Math.max(0, Number(billing?.remaining?.videos_generated ?? ((billing?.limits?.videos_per_month || 0) - (billing?.usage?.videos_per_month || 0))));
  const projectsRemaining = Number(billing?.limits?.projects || 0) >= 999999
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
    : String(Math.max(0, Number(billing?.remaining?.projects ?? ((billing?.limits?.projects || 0) - (billing?.usage?.projects || 0)))));
  const trialLine = billing.plan === 'free'
    ? `<div class="small">Пробный период: <strong>${Number(billing.trial_days_left || 0)} дн.</strong>${billing.trial_ends_at ? ` · до ${esc(new Date(billing.trial_ends_at).toLocaleDateString('ru-RU'))}` : ''}</div>`
    : '<div class="small">Платный тариф активен. Лимиты синхронизированы с backend.</div>';
  const lockedItems = [];
  if (!billing?.limits?.can_autopublish) lockedItems.push('Автопостинг');
  if (String(billing?.limits?.analytics_level || 'none') === 'none') lockedItems.push('Аналитика');
  const lockText = lockedItems.length ? lockedItems.join(', ') : 'Все ключевые функции доступны';
  const trialExpiringSoon = billing.plan === 'free' && Number(billing.trial_days_left || 0) <= 2;
  const nextBestStep = hasGeneratedContent
    ? (hasConnectedChannels ? 'Синхронизируйте метрики или опубликуйте следующий материал.' : 'Подключите соцсети позже, а пока продолжайте генерировать контент.')
    : 'Начните с первой темы и получите пост или структуру видео меньше чем за минуту.';
  ensureDashboardQuickStartState();
  const resolvedQuickNicheId = resolveDashboardActiveNicheId();
  if (resolvedQuickNicheId && state.dashboardQuickStart.nicheId !== resolvedQuickNicheId) {
    state.dashboardQuickStart.nicheId = resolvedQuickNicheId;
  }
  const dashboardNicheId = String(state.dashboardQuickStart.nicheId || '').trim();
  const dashboardNicheMeta = dashboardNicheId ? dashboardQuickNicheMeta(dashboardNicheId) : null;
  const quickActionCardsHtml = dashboardNicheId
    ? DASHBOARD_QUICK_ACTIONS.map((action) => {
      const access = getQuickActionAccess(action.key, billing);
      const stateLabel = access.isLocked ? 'Locked' : (access.isPreview ? 'Preview' : 'Доступно');
      const accessText = access.isPreview
        ? 'Preview на вашем тарифе'
        : (access.isLocked ? 'Недоступно на текущем тарифе' : 'Доступно на вашем тарифе');
      const buttonLabel = access.isLocked ? 'Обновить тариф' : action.buttonLabel;
      return `<article class="dash-quick-card glass-card dash-quick-card-${esc(action.size)} ${access.isLocked ? 'is-locked' : ''} ${access.isPreview ? 'is-preview' : ''}">
        <div class="dash-quick-accent">${esc(action.accent)}</div>
        <div class="dash-quick-topline">
          <div class="dash-quick-meta">${esc(accessText)}</div>
          <span class="dash-quick-status">${esc(stateLabel)}</span>
        </div>
        <h3>${esc(action.title)}</h3>
        <p>${esc(action.description)}</p>
        <div class="small">Ниша: <strong>${esc(dashboardNicheMeta?.label || '—')}</strong></div>
        ${access.isLocked ? '<div class="small">На текущем тарифе действие закрыто. Откроется после апгрейда.</div>' : ''}
        <button type="button" class="btn ${access.isLocked ? 'btn-ghost' : 'btn-primary'}" data-dash-quick-action="${esc(action.key)}">${esc(buttonLabel)}</button>
      </article>`;
    }).join('')
    : '';
  const quickStartShell = dashboardNicheId
    ? `<section class="dash-card dash-quick-shell glass-card">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;">
          <div style="max-width:760px;">
            <div class="dash-hero-topline">Быстрый старт</div>
            <h2 style="margin:10px 0 8px 0;">Что хотите создать?</h2>
            <p class="small" style="margin:0;">Выберите действие и получите результат за пару кликов. На основе ниши <strong>${esc(dashboardNicheMeta?.label || '—')}</strong> AI подготовит идеи, структуру и готовые заготовки.</p>
          </div>
          <div class="dash-quick-controls">
            ${selectField('dashQuickNiche', 'Ниша', dashboardNicheId, DIRECTOR_NICHE_OPTIONS)}
          </div>
        </div>
        <div class="dash-quick-grid">${quickActionCardsHtml}</div>
      </section>`
    : `<section class="dash-card dash-quick-shell glass-card">
        <div class="dash-quick-empty">
          <div class="dash-hero-topline">Быстрый старт</div>
          <h2 style="margin:10px 0 8px 0;">Сначала выберите нишу</h2>
          <p class="small">Ниша нужна, чтобы контент-планы, серии постов, видео, hooks и CTA были релевантны именно вашему бизнесу.</p>
          <div class="dash-quick-empty-controls">
            ${selectField('dashQuickNiche', 'Ниша', '', [{ value: '', label: 'Выберите нишу' }].concat(DIRECTOR_NICHE_OPTIONS))}
            <button id="dashQuickPickNicheBtn" class="btn btn-primary" type="button">Выбрать нишу</button>
          </div>
        </div>
      </section>`;
  const onboardingHero = shouldShowOnboardingHero ? `
      <section class="card glass-card" style="margin-bottom:18px;border:1px solid rgba(54,102,255,.18);box-shadow:0 18px 48px rgba(15,26,61,.08);">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
          <div style="max-width:720px;">
            <div class="pill active" style="margin-bottom:10px;">Добро пожаловать в AutoSocial</div>
            <h2 style="margin:0 0 8px 0;">Начните с первого результата, а не с пустой аналитики</h2>
            <p class="small" style="margin:0 0 12px 0;">Ваш план: <strong>${esc(billing.plan_title || planBadge(billing.plan || 'free').replace(/<[^>]+>/g, ''))}</strong>. Осталось: <strong>${postsRemaining}</strong> постов, <strong>${videosRemaining}</strong> видео, <strong>${esc(projectsRemaining)}</strong> рабочего пространства. ${trialExpiringSoon ? 'Trial скоро закончится, поэтому лучше получить первый результат сейчас.' : 'Первый результат можно получить меньше чем за минуту.'}</p>
            <div class="cta-row">
              <button id="dashFirstPostBtn" class="btn btn-primary" type="button">Создать первый пост</button>
              <button id="dashFirstVideoBtn" class="btn btn-secondary" type="button">Создать первое видео</button>
              <button id="dashConnectChannelsBtn" class="btn btn-ghost" type="button">Подключить соцсети</button>
            </div>
            <div class="small" style="margin-top:10px;">${hasConnectedChannels ? 'Каналы уже можно использовать для публикации и синхронизации.' : 'Сначала можно сгенерировать контент, а подключить каналы позже для автопостинга и аналитики.'}</div>
          </div>
          <button id="dashDismissOnboardingBtn" class="btn btn-ghost" type="button">Скрыть</button>
        </div>
        <div class="grid-3" style="margin-top:16px;">

          <article class="card" style="padding:14px;"><div class="small" style="opacity:.7;">Шаг 2</div><strong>Сгенерируйте пост или структуру видео</strong><p class="small" style="margin:8px 0 0 0;">Получите первый черновик сразу и отредактируйте его при необходимости.</p></article>
          <article class="card" style="padding:14px;"><div class="small" style="opacity:.7;">Шаг 3</div><strong>Опубликуйте сейчас или подключите каналы позже</strong><p class="small" style="margin:8px 0 0 0;">Контент можно подготовить заранее, а автопостинг включить после подключения соцсетей.</p></article>
        </div>
      </section>` : '';
  const analyticsEmptyState = shouldShowAnalyticsEmptyState ? `
        <section class="card glass-card" style="margin-bottom:18px;">
          <h3 style="margin-top:0;">Аналитика появится после первых публикаций</h3>
          <p class="small">Сейчас панель не пустая и не сломана: данные подтянутся после публикаций и синхронизации. Пока главный путь к value - создать первый пост или первое видео.</p>
          <div class="cta-row">
            <button id="dashEmptyCreateBtn" class="btn btn-primary" type="button">Начать с контента</button>
            <button id="dashEmptySyncBtn" class="btn btn-ghost" type="button">Понятно</button>
          </div>
        </section>` : '';
  const analyticsHeader = shouldShowAnalyticsEmptyState ? 'Первые данные появятся после публикаций' : 'Ваш рост за 30 дней';
  const analyticsBadge = shouldShowAnalyticsEmptyState ? 'Пока нет данных для графиков - сначала создайте и опубликуйте контент' : 'данные: Facebook + Instagram + YouTube / период: 30 дней';
  const analyticsHeroButton = shouldShowAnalyticsEmptyState
    ? '<button id="dashOpenCreateBtn" class="btn btn-primary" type="button">Начать с контента</button>'
    : '<button id="dashAiBreakdownBtn" class="btn btn-ghost" type="button">Из чего складывается</button>';
  const analyticsHeroKpis = shouldShowAnalyticsEmptyState
    ? `<article class="dash-kpi-card glass-card"><p>Следующий шаг</p><strong>Создать</strong><small>${esc(nextBestStep)}</small></article>
       <article class="dash-kpi-card glass-card"><p>Каналы</p><strong>${hasConnectedChannels ? 'Есть' : 'Пока нет'}</strong><small>${hasConnectedChannels ? 'Можно публиковать и синхронизировать.' : 'Сначала можно работать без подключений.'}</small></article>
       <article class="dash-kpi-card glass-card"><p>Trial</p><strong>${billing.plan === 'free' ? `${Number(billing.trial_days_left || 0)} дн.` : 'Активен'}</strong><small>${billing.plan === 'free' ? 'Покажите первую ценность до конца пробного периода.' : 'Лимиты и доступ уже активны.'}</small></article>
       <article class="dash-kpi-card glass-card"><p>Лимиты</p><strong>${postsRemaining}/${videosRemaining}</strong><small>Осталось постов / видео в текущем периоде.</small></article>`
    : (stats.loading ? skeletonCards : `
            <article class="dash-kpi-card glass-card"><p>Охват</p><strong>${fmt(current.reach)}</strong><small class="${Number(delta?.reach?.abs || 0) >= 0 ? 'is-positive' : 'is-negative'}">vs prev 30d: ${deltaLabel(delta.reach)}</small></article>
            <article class="dash-kpi-card glass-card"><p>Просмотры</p><strong>${fmt(current.views)}</strong><small class="${Number(delta?.views?.abs || 0) >= 0 ? 'is-positive' : 'is-negative'}">vs prev 30d: ${deltaLabel(delta.views)}</small></article>
            <article class="dash-kpi-card glass-card"><p>Уровень вовлеченности</p><strong>${pct(current.engagement_rate || 0)}</strong><small class="${Number(delta?.engagement_rate?.abs || 0) >= 0 ? 'is-positive' : 'is-negative'}">vs prev 30d: ${deltaLabel(delta.engagement_rate)}</small></article>
            <article class="dash-kpi-card glass-card"><p>Количество постов</p><strong>${fmt(current.items)}</strong><small class="${Number(delta?.items?.abs || 0) >= 0 ? 'is-positive' : 'is-negative'}">vs prev 30d: ${deltaLabel(delta.items)}</small></article>
          `);

  return appLayout('/dashboard', 'Панель управления', `
    <section class="dash-client-shell dash-v2-shell">
      ${onboardingHero}
      ${quickStartShell}
      <header class="dash-card dash-hero glass-card">
        <div>
          <div class="dash-hero-topline">${analyticsHeader}</div>
          <div class="dash-hero-score-row">
            ${shouldShowAnalyticsEmptyState
              ? `<div class="dash-hero-score">1</div>
                 <div class="dash-hero-score-meta">
                   <span>Лучший следующий шаг</span>

                 </div>`
              : `<div class="dash-hero-score">${Number(aiScore.current || 0).toFixed(1)}</div>
                 <div class="dash-hero-score-meta">
                   <span>AI-Score / 100</span>

                 </div>`}
          </div>
          <div class="dash-hero-badge">${analyticsBadge}</div>
          ${analyticsHeroButton}
        </div>
        <div class="dash-hero-kpis">
          ${analyticsHeroKpis}
          <div class="cta-row">
            <button id="dashSyncMetricsBtn" class="btn btn-primary" ${stats.syncing ? 'disabled' : ''}>${stats.syncing ? 'Синхронизирую...' : (shouldShowAnalyticsEmptyState ? 'Синхронизировать позже' : 'Синхронизировать')}</button>
            <button id="dashCreatePostBtn" class="btn btn-secondary">${shouldShowAnalyticsEmptyState ? 'Создать первый пост' : 'Создать пост'}</button>
          </div>
        </div>
      </header>
      <main class="dash-client-content">
        <section class="grid-2" style="margin-bottom:18px;">
          <article class="card glass-card">
            <h3 style="margin-top:0;">Текущий план</h3>
            <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
              <div>
                <div class="small">План</div>
                <div style="margin-top:6px;">${planBadge(billing.plan || 'free')}</div>
              </div>
              <button type="button" class="btn btn-primary" data-link="/billing">Апгрейд</button>
            </div>
            <div class="small" style="margin-top:12px;">Посты: <strong>${Number(billing?.usage?.posts_per_month || 0)}</strong> / <strong>${Number(billing?.limits?.posts_per_month || 0)}</strong></div>
            <div class="small" style="margin-top:6px;">Видео: <strong>${Number(billing?.usage?.videos_per_month || 0)}</strong> / <strong>${Number(billing?.limits?.videos_per_month || 0)}</strong></div>
            <div class="small" style="margin-top:6px;">Рабочие пространства: <strong>${Number(billing?.usage?.projects || 0)}</strong> / <strong>${esc(projectLimitLabel)}</strong></div>
            <div class="small" style="margin-top:6px;">Каналы: <strong>${Number(billing?.usage?.accounts_connected || 0)}</strong> / <strong>${esc(accountLimitLabel)}</strong></div>
            <div class="small" style="margin-top:6px;">Locked / недоступно: <strong>${esc(lockText)}</strong></div>
            <div style="margin-top:10px;">${trialLine}</div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
          </article>
          <article class="card glass-card">
            <h3 style="margin-top:0;">Что доступно сейчас</h3>
            <ul class="small">
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
              <li>Аналитика: <strong>${esc(String(billing?.limits?.analytics_level || 'none'))}</strong></li>
              <li>Шаблоны по нишам: <strong>${esc(String(billing?.limits?.niche_templates || 'limited'))}</strong></li>
            </ul>
            <p class="small">${Number(billing?.usage?.posts_per_month || 0) <= 0 && Number(billing?.usage?.videos_per_month || 0) <= 0
              ? 'Следующий шаг: откройте «Создать», выберите тему и получите первый пост или структуру видео за несколько минут.'
              : 'Если лимит закончится или функция недоступна, paywall должен вести на страницу тарифа без ложных кнопок и пустых действий.'}</p>
          </article>
        </section>
        ${analyticsEmptyState}
        ${shouldShowAnalyticsEmptyState ? '' : `<section class="dash-platform-grid">
          <article class="dash-platform-card glass-card">
            <div class="dash-platform-head"><h4>Facebook</h4><span class="dash-status-chip ${statusClass(fbStatus)}">${statusLabel(fbStatus)}</span></div>
            <p>Охват: <strong>${fmt(byPlatform.facebook?.reach)}</strong></p>
            <p>Просмотры: <strong>${fmt(byPlatform.facebook?.views)}</strong></p>
            <p class="small">Контент-единиц: ${fmt(byPlatform.facebook?.items)}</p>
            ${buildSpark(fbSeries, 'facebook')}
          </article>
          <article class="dash-platform-card glass-card">
            <div class="dash-platform-head"><h4>Instagram</h4><span class="dash-status-chip ${statusClass(igStatus)}">${statusLabel(igStatus)}</span></div>
            <p>Охват: <strong>${fmt(byPlatform.instagram?.reach)}</strong></p>
            <p>Просмотры: <strong>${fmt(byPlatform.instagram?.views)}</strong></p>
            <p class="small">Контент-единиц: ${fmt(byPlatform.instagram?.items)}</p>
            ${buildSpark(igSeries, 'instagram')}
          </article>
          <article class="dash-platform-card glass-card">
            <div class="dash-platform-head"><h4>YouTube</h4><span class="dash-status-chip ${statusClass(ytStatus)}">${statusLabel(ytStatus)}</span></div>
            <p>Охват: <strong>${fmt(byPlatform.youtube?.reach)}</strong></p>
            <p>Просмотры: <strong>${fmt(byPlatform.youtube?.views)}</strong></p>
            <p class="small">Контент-единиц: ${fmt(byPlatform.youtube?.items)}</p>
            ${buildSpark(ytSeries, 'youtube')}
          </article>
        </section>`}
        ${shouldShowAnalyticsEmptyState ? '' : `<section class="dash-card glass-card">
          <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <div>
              <h3>График результатов за 30 дней</h3>
              <p class="small">${esc(chartDescription)}</p>
            </div>
            <div class="dash-metric-switch" role="tablist" aria-label="Metric switch">
              <button type="button" data-dash-metric="reach" class="${chartMetric === 'reach' ? 'active' : ''}">Охват аудитории</button>
              <button type="button" data-dash-metric="views" class="${chartMetric === 'views' ? 'active' : ''}">Просмотры</button>
              <button type="button" data-dash-metric="engagement" class="${chartMetric === 'engagement' ? 'active' : ''}">Вовлечённость</button>
              <button type="button" data-dash-metric="ai_score" class="${chartMetric === 'ai_score' ? 'active' : ''}">AI-Score</button>
            </div>
          </div>
          ${mainChartHtml}
        </section>`}
        ${shouldShowAnalyticsEmptyState ? '' : `<section class="dash-card glass-card">
          <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <div>
              <h3>Прогноз</h3>
              <p class="small">На ${Number(forecast.horizon_days || 7)} дней · confidence: <strong>${esc(forecast?.confidence?.level || 'low')}</strong> · ${esc((forecast?.confidence?.reasons || []).join(', ') || 'недостаточно данных')}</p>
            </div>
            <div class="dash-sort-row">
              <button type="button" data-dash-forecast-horizon="7" class="${Number(stats.forecastHorizon || 7) === 7 ? 'active' : ''}">7 дней</button>

            </div>
          </div>
          <div class="dash-forecast-grid">
            <article class="dash-kpi-card glass-card"><p>Прогноз Reach</p><strong>${fmt(forecast?.totals?.reach || 0)}</strong></article>
            <article class="dash-kpi-card glass-card"><p>Прогноз Views</p><strong>${fmt(forecast?.totals?.views || 0)}</strong></article>
            <article class="dash-kpi-card glass-card"><p>Прогноз Engagement</p><strong>${pct(forecast?.totals?.engagement_rate_avg || 0)}</strong></article>
          </div>
          <div class="dash-forecast-scenarios">
            <div><strong>Текущий темп</strong><p class="small">${Number(forecast?.scenarios?.current?.posts_per_week || 0).toFixed(1)} поста/нед · Reach ${fmt(forecast?.scenarios?.current?.reach || 0)}</p></div>
            <div><strong>+30% частоты</strong><p class="small">${Number(forecast?.scenarios?.plus30?.posts_per_week || 0).toFixed(1)} поста/нед · Reach ${fmt(forecast?.scenarios?.plus30?.reach || 0)}</p></div>
          </div>
        </section>`}
        ${shouldShowAnalyticsEmptyState ? '' : `<section class="dash-card dash-ai-card glass-card">
          <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <div>
              <h3>AI-инсайты</h3>
              <p class="small">Лучшие точки роста на основе фактических метрик.</p>
            </div>
            <div class="cta-row">
              <button id="dashApplyRecommendationsBtn" class="btn btn-secondary">Применить рекомендации</button>
              <button id="dashOpenCalendarBtn" class="btn btn-ghost">Открыть календарь</button>
            </div>
          </div>
          <div class="dash-insights-grid">${stats.loading ? skeletonCards : insightCards}</div>
        </section>`}
        ${shouldShowAnalyticsEmptyState ? '' : `<section class="dash-card glass-card">
          <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <h3>Опубликованные посты</h3>
            <div class="dash-sort-row">
              <button type="button" class="${recentSort === 'reach' ? 'active' : ''}" data-dash-sort="reach">Сортировка по охвату</button>
              <button type="button" class="${recentSort === 'views' ? 'active' : ''}" data-dash-sort="views">Сортировка по просмотрам</button>
              <button type="button" class="${recentSort === 'engagement' ? 'active' : ''}" data-dash-sort="engagement">Сортировка по вовлеченности</button>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Контент</th>
                  <th>Охват</th>
                  <th>Просмотры</th>
                  <th>Уровень вовлеченности</th>
                  <th>Дата</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>${recentRows}</tbody>
            </table>
          </div>
        </section>`}
      </main>
      ${stats.aiBreakdownOpen ? `<div class="dash-modal-backdrop" id="dashAiModalBackdrop">
        <div class="dash-modal glass-card">
          <div class="row" style="justify-content:space-between;align-items:center;">
            <h3 style="margin:0;">Из чего складывается AI-Score</h3>
            <button id="dashAiBreakdownClose" type="button" class="btn btn-ghost">Закрыть</button>
          </div>
          <p class="small">Период: ${esc(aiScore?.breakdown?.period?.from || '—')} > ${esc(aiScore?.breakdown?.period?.to || '—')}</p>
          <div class="dash-breakdown-list">
            ${(Array.isArray(aiScore?.breakdown?.factors) && aiScore.breakdown.factors.length)
              ? aiScore.breakdown.factors.map((f) => {

                const weight = Math.max(Number(f?.weight || 1), 1);

                const conf = String(f?.confidence || 'low');
                const confText = conf === 'high' ? 'Высокая' : (conf === 'medium' ? 'Средняя' : 'Низкая');
                const actionPath = String(f?.key || '').includes('timing') ? '/calendar' : '/create';
                return `<article class="dash-breakdown-item">
                  <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
                    <strong>${esc(f?.title || 'Фактор')}</strong>
                    <span class="dash-confidence ${esc(conf)}">${esc(confText)}</span>
                  </div>
                  <div class="small">Вес ${weight} · ${score.toFixed(1)} балла</div>
                  <div class="dash-mini-progress"><span style="width:${ratio.toFixed(1)}%"></span></div>
                  <p class="small">${esc(f?.how_to_improve || '—')}</p>
                  <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
                    <small>Ожидаемый эффект: ${esc(f?.expected_gain || '—')}</small>

                  </div>
                </article>`;
              }).join('')
              : '<p class="small">Недостаточно данных. Нажмите «Синхронизировать».</p>'
            }
          </div>
        </div>
      </div>` : ''}
    </section>
  `);
}

function pageCreate() {
  const w = state.createWizard;
  const projectOptions = state.projects.map((p) => ({ value: p.id, label: p.name }));
  const nicheOptions = DIRECTOR_NICHE_OPTIONS;
  const toneOptions = [
    { value: 'friendly', label: 'Дружелюбный' },
    { value: 'expert', label: 'Экспертный' },
    { value: 'sales', label: 'Продающий' },
    { value: 'neutral', label: 'Нейтральный' },
  ];
  const goalOptions = [
    { value: 'sales', label: 'Продажи' },
    { value: 'warmup', label: 'Прогрев' },
    { value: 'expert', label: 'Экспертность' },
    { value: 'announce', label: 'Анонс' },
  ];
  const platformMetaSelected = !!(w.platforms?.facebook || w.platforms?.instagram);
  const platformYoutubeSelected = !!w.platforms?.youtube;
  const selectedPlatforms = [platformMetaSelected ? 'Meta' : null, platformYoutubeSelected ? 'YouTube' : null].filter(Boolean).join(' + ') || 'Не выбрано';
  const metaConnected = (state.connections || []).some((c) => isConnectionReady(c));
  const youtubeConnected = !!state.youtubeConnection?.connected;
  const stepDurations = { 1: 4, 2: 3, 3: 2, 4: 1, 5: 1 };
  const minutesLeft = stepDurations[w.step] || 2;
  const hashtags = Array.isArray(w.hashtags) && w.hashtags.length ? w.hashtags : ['#контент', '#бизнес'];
  const goalLabel = (goalOptions.find((g) => g.value === w.goal) || goalOptions[0]).label;
  const ctaText = (w.finalCta || '').trim() || `CTA: ${w.ctaAction || 'Написать'}`;
  const projectName = (state.projects.find((p) => String(p.id) === String(w.projectId)) || state.projects[0] || { name: 'Новый проект' }).name;
  const fallbackPreviewText = ((w.topic || '').trim()
    ? `${w.topic}\n\nСфокусируйтесь на выгоде клиента, добавьте один конкретный шаг и завершите понятным действием.\n\n${ctaText}`
    : 'Текст поста появится здесь после ввода темы или генерации AI.');
  const previewText = ((w.previewText || '').trim() || fallbackPreviewText).trim();
  const activeBadge = platformYoutubeSelected && !platformMetaSelected ? 'YouTube' : 'Meta';
  const stepTitles = {
    1: 'Проект',
    2: 'Платформы',
    3: 'Контент',
    4: 'Предпросмотр',
    5: 'Публикация',
  };
  const submitLabel = w.mode === 'schedule' ? 'Запланировать' : (w.mode === 'draft' ? 'Сохранить как черновик' : 'Опубликовать');
  if (!w.niche) w.niche = DEFAULT_DIRECTOR_NICHE;
  w.niche = normalizeNicheIdSafe(w.niche || DEFAULT_DIRECTOR_NICHE) || DEFAULT_DIRECTOR_NICHE;
  if (!w.goal) w.goal = 'sales';
  if (!w.ctaAction) w.ctaAction = 'Записаться';
  if (!w.finalCta) w.finalCta = 'Напишите в директ, чтобы получить консультацию.';
  w.category = w.niche;
  const topicTemplates = buildCreateQuickTopics(w.niche, w.quickTopicsVersion || 0);

  const step1 = `
    <div class="wizard-step-note">Проект хранит стиль, нишу и настройки бренда.</div>
    ${selectField('wProject', 'Проект (бренд/клиент)', w.projectId, projectOptions.length ? projectOptions : [{ value: '', label: 'Нет проектов' }])}
    <div class="field">
      <label for="wNewProject">Новый проект</label>
      <div class="cta-row">
        <input id="wNewProject" type="text" placeholder="Например: Салон Glow Studio" />
        <button id="createProjectFromCreateBtn" class="btn btn-secondary" type="button">Сохранить проект</button>
      </div>
      <p class="small">Проект создается сразу и автоматически выбирается в мастере.</p>
    </div>
    <div class="create-grid-compact">
      ${selectField('wNiche', 'Ниша', w.niche, nicheOptions)}
      ${selectField('wTone', 'Тон', w.tone, toneOptions)}
    </div>
  `;

  const step2 = `
    <div class="wizard-step-note">Выберите, где публиковать контент и в каком формате его готовить.</div>
    <div class="create-platform-grid">
      <article class="create-platform-card ${platformMetaSelected ? 'active' : ''}">
        <div class="row" style="justify-content:space-between;align-items:center;">
          <div class="row" style="align-items:center;gap:8px;">
            <span class="create-platform-icon">M</span>
            <strong>Meta (Facebook/Instagram)</strong>
          </div>
          <label class="create-toggle"><input id="wMeta" type="checkbox" ${platformMetaSelected ? 'checked' : ''}/> Выбрать</label>
        </div>
        <div class="small">Статус: ${metaConnected ? '<span class="status success">Подключено</span>' : '<span class="status warning">Не подключено</span>'}</div>
        ${!metaConnected ? '<button id="wConnectMeta" class="btn btn-ghost connection-btn-sm" type="button">Подключить</button>' : ''}
        ${selectField('wMetaFormat', 'Формат контента', w.metaFormat || 'post', [{ value: 'post', label: 'Пост' }, { value: 'story', label: 'Текст для сторис' }])}
      </article>
      <article class="create-platform-card ${platformYoutubeSelected ? 'active' : ''}">
        <div class="row" style="justify-content:space-between;align-items:center;">
          <div class="row" style="align-items:center;gap:8px;">
            <span class="create-platform-icon yt">YT</span>
            <strong>YouTube</strong>
          </div>
          <label class="create-toggle"><input id="wYoutube" type="checkbox" ${platformYoutubeSelected ? 'checked' : ''}/> Выбрать</label>
        </div>
        <div class="small">Статус: ${youtubeConnected ? '<span class="status success">Подключено</span>' : '<span class="status warning">Не подключено</span>'}</div>
        ${!youtubeConnected ? '<button id="wConnectYoutube" class="btn btn-ghost connection-btn-sm" type="button">Подключить</button>' : ''}
        ${selectField('wYoutubeFormat', 'Формат контента', w.youtubeFormat || 'description', [{ value: 'description', label: 'Описание ролика' }, { value: 'community', label: 'Текст для Community' }, { value: 'shorts', label: 'Описание для Shorts' }])}
      </article>
    </div>
  `;

  const step3 = `
    <div class="wizard-step-note">Сформулируйте задачу. AI соберет черновик поста за несколько секунд.</div>
    <div class="field">
      <label>Цель публикации</label>
      <div class="create-goal-grid">
        ${goalOptions.map((g) => `<label class="create-goal-item"><input type="radio" name="wGoal" value="${esc(g.value)}" ${w.goal === g.value ? 'checked' : ''} /> ${esc(g.label)}</label>`).join('')}
      </div>
    </div>
    ${field('wTopic', 'О чём пост?', 'text', w.topic, 'Например: 5 ошибок в продвижении локального бизнеса')}
    ${field('wCtaAction', 'Что должен сделать клиент?', 'text', w.ctaAction, 'Записаться / Написать / Купить / Позвонить')}
    <div class="field">
      <label style="margin:0 0 8px;">AI подсказки</label>
      <div class="topic-template-row">
        <button type="button" class="btn btn-ghost btn-topic-template" data-ai-prompt="sales">Сделай продающий пост</button>
        <button type="button" class="btn btn-ghost btn-topic-template" data-ai-prompt="expert">Сделай экспертный пост</button>
        <button type="button" class="btn btn-ghost btn-topic-template" data-ai-prompt="announce">Сделай анонс</button>
        <button type="button" class="btn btn-ghost btn-topic-template" data-ai-prompt="warmup">Сделай прогрев</button>
      </div>
    </div>
    <div class="field">
      <div class="row" style="justify-content:space-between;align-items:center;">
        <label style="margin:0;">Быстрые темы</label>
        <button id="wRefreshTopics" type="button" class="btn btn-ghost">Обновить</button>
      </div>
      <div id="wTopicTemplates" class="topic-template-row">
        ${topicTemplates.map((t) => `<button type="button" class="btn btn-ghost btn-topic-template" data-topic-template="${esc(t)}">${esc(t)}</button>`).join('')}
      </div>
    </div>
    <div class="row" style="align-items:center;gap:10px;">
      <button id="wGenerateBtn" class="btn btn-primary" type="button">${w.generating ? 'AI готовит пост…' : 'Сгенерировать'}</button>
      ${w.generating ? '<span class="create-ai-status"><span class="create-ai-dot"></span> AI готовит пост…</span>' : ''}
    </div>
  `;

  const step4 = `
    <div class="wizard-step-note">Финальная правка перед публикацией. Справа вы сразу видите итоговый вид поста.</div>
    ${field('wPreviewText', 'Итоговый текст поста', 'textarea', previewText, 'Введите текст публикации')}
    ${field('wHashtags', 'Хэштеги (через пробел)', 'textarea', hashtags.join(' '), '#бизнес #продажи #маркетинг')}
    ${field('wFinalCta', 'CTA (призыв к действию)', 'text', w.finalCta, 'Напишите в директ, чтобы получить консультацию')}
  `;

  const step5 = w.publishSuccess ? `
    <article class="wizard-help">
      <h3>Готово</h3>
      <p class="small">${esc(w.publishSuccess)}</p>
      <div class="cta-row">
        <button id="wCreateMoreBtn" class="btn btn-secondary" type="button">Создать ещё</button>
        <button id="wOpenCalendarBtn" class="btn btn-ghost" type="button">Открыть календарь</button>
      </div>
    </article>
  ` : `
    <div class="wizard-step-note">Выберите формат публикации и подтвердите запуск.</div>
    ${selectField('wMode', 'Публикация', w.mode, [{ value: 'now', label: 'Опубликовать сейчас' }, { value: 'schedule', label: 'Запланировать' }, { value: 'draft', label: 'Сохранить как черновик' }])}
    ${w.mode === 'schedule' ? field('wSchedule', 'Дата и время', 'datetime-local', w.scheduleAt) : ''}
    <article class="wizard-help">
      <h3>Подтверждение</h3>
      <p class="small">Проект: <strong>${esc(projectName)}</strong></p>
      <p class="small">Платформы: <strong>${esc(selectedPlatforms)}</strong></p>
      <p class="small">Цель: <strong>${esc(goalLabel)}</strong></p>
      <p class="small">Тема: <strong>${esc(w.topic || '—')}</strong></p>
    </article>
  `;

  const stepContent = [step1, step2, step3, step4, step5][w.step - 1] || step1;
  const previewCard = `
    <article class="create-preview-card">
      <div class="row" style="justify-content:space-between;align-items:center;">
        <span class="pill">${esc(activeBadge)}</span>
        <span class="small">${esc(projectName)}</span>
      </div>
      <h3>${esc(w.topic || 'Ваш будущий пост')}</h3>
      <div class="create-preview-text">${esc(previewText)}</div>
      <div class="create-preview-tags">${hashtags.map((h) => `<span class="pill">${esc(h)}</span>`).join('')}</div>
      <button class="btn btn-secondary create-preview-cta" type="button">${esc((w.ctaAction || 'Написать').trim() || 'Написать')}</button>
    </article>
  `;
  const infoCard = `
    <article class="create-info-card">
      <h3>Что вы получите</h3>
      <ul class="check-list">
        <li class="done">Готовый текст</li>
        <li class="done">Сильный CTA</li>
        <li class="done">Хэштеги</li>
        <li class="done">План публикации</li>
      </ul>
    </article>
  `;

  return appLayout('/create', 'Создать', `
    <section class="create-wizard-shell">
      <div class="create-wizard-grid">
        <article class="card create-main-col">
          <h2>Мастер создания поста</h2>
          <p class="small">Заполните шаги слева, а справа сразу смотрите итог поста.</p>
          <div class="create-progress-badge">Шаг ${w.step} из 5 · ~${minutesLeft} минут до готового поста</div>
          <div class="stepper">
            <div class="step ${w.step===1?'active':''}">1. Проект</div>
            <div class="step ${w.step===2?'active':''}">2. Платформы</div>
            <div class="step ${w.step===3?'active':''}">3. Контент</div>
            <div class="step ${w.step===4?'active':''}">4. Предпросмотр</div>
            <div class="step ${w.step===5?'active':''}">5. Публикация</div>
          </div>
          <h3 class="create-step-title">${esc(stepTitles[w.step] || 'Шаг')}</h3>
          ${stepContent}
          ${!w.publishSuccess ? `<div class="cta-row create-wizard-actions">${w.step>1?'<button id="wPrev" type="button" class="btn btn-ghost">Назад</button>':''}${w.step<5?'<button id="wNext" type="button" class="btn btn-primary">Далее</button>':`<button id="wSubmit" type="button" class="btn btn-primary">${esc(submitLabel)}</button>`}</div>` : ''}
          <details class="create-mobile-preview">
            <summary>Предпросмотр</summary>
            <div class="create-mobile-preview-content">${previewCard}${infoCard}</div>
          </details>
        </article>
        <aside class="create-preview-col">
          ${previewCard}
          ${infoCard}
        </aside>
      </div>
    </section>
  `);
}
function pageConnections() {
  const query = new URLSearchParams(location.search);
  const err = query.get('error');
  const msg = query.get('message');
  if (err) {
    const map = {
      oauth_denied: 'Вы отменили подключение Facebook.',
      token_exchange_failed: 'Не удалось обменять код на токен. Проверьте App ID/Secret и Redirect URI.',
      state_invalid: 'Сессия OAuth устарела. Запустите подключение заново.',
      meta_api_error: 'Meta API вернул ошибку при получении страниц/Instagram.',
      no_pages: 'У этого Facebook-аккаунта нет доступных страниц для подключения.',
      no_ig_business: 'На выбранной странице нет Instagram Business, привязанного к странице.',
      youtube_oauth_denied: 'Вы отменили подключение Google/YouTube.',
      youtube_state_invalid: 'Сессия подключения YouTube устарела. Нажмите "Подключить YouTube" снова.',
      youtube_token_exchange_failed: 'Не удалось получить токен Google для YouTube.',
      youtube_no_channel: 'Не удалось найти канал YouTube в выбранном Google-аккаунте.',
      youtube_api_not_enabled: 'YouTube Data API не включен в Google Cloud проекте для этого OAuth клиента.',
      youtube_api_failed: 'YouTube API вернул ошибку при чтении канала.',
      youtube_not_configured: 'Google OAuth для YouTube не настроен.',
    };
    state.notice = { type: 'error', text: (map[err] || 'Ошибка подключения.') + (msg ? ` ${msg}` : '') };
  } else if (query.get('connected')) {
    state.notice = { type: 'ok', text: 'Facebook/Instagram аккаунт подключён.' };
  }

  const primaryByStatus = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'not_connected') return { action: 'connect', label: 'Подключить Facebook' };
    if (s === 'connected_need_page') return { action: 'pick_page', label: 'Выбрать страницу' };
    if (s === 'connected_ready' || s === 'connected') return { action: 'test', label: 'Тест публикации' };
    if (s === 'token_expired' || s === 'permissions_missing' || s === 'disconnected') return { action: 'reconnect', label: 'Переподключить' };
    return { action: 'retry', label: 'Повторить' };
  };
  const renderConnectionAvatar = (imageUrl, fallbackText, extraClass = '') => {
    const cls = `avatar connection-brand-avatar ${extraClass}`.trim();
    if (imageUrl) return `<span class="${cls}"><img src="${esc(imageUrl)}" alt="" loading="lazy" /></span>`;
    return `<span class="${cls}">${esc((safeText(fallbackText, 'A')[0] || 'A').toUpperCase())}</span>`;
  };
  const platformIcons = {
    facebook: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 21v-7h2.8l.4-3h-3.2V9.1c0-.9.3-1.6 1.7-1.6H17V4.8c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.5-4 4.3V11H8v3h2.2v7h3.3z" fill="currentColor"/></svg>',
    instagram: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.2" y="3.2" width="17.6" height="17.6" rx="5.2" ry="5.2" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="4.1" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17.2" cy="6.8" r="1.2" fill="currentColor"/></svg>',

  };
  const renderPlatformMini = (label, kind) => `<span class="connection-platform-mini connection-platform-mini-${esc(kind)}">${platformIcons[kind] || ''}<span>${esc(label)}</span></span>`;

  const visibleMetaConnections = (() => {
    const base = (state.connections || []).filter((c) => {
      const status = String(c?.status || '').toLowerCase();
      if (status !== 'not_connected' && status !== 'disconnected') return true;
      return !!(c?.facebook_page_id || c?.facebook_page_name || c?.instagram_business_id || c?.page_id || c?.token_expires_at);
    });
    const seen = new Set();
    return base.filter((c) => {
      const dedupeKey = [
        String(c?.facebook_page_id || c?.page_id || '').trim().toLowerCase(),
        String(c?.instagram_business_id || c?.ig_user_id || '').trim().toLowerCase(),
        String(c?.facebook_page_name || c?.page_name || '').trim().toLowerCase(),
      ].join('|');
      if (!dedupeKey.replace(/\|/g, '')) return true;
      if (seen.has(dedupeKey)) return false;
      seen.add(dedupeKey);
      return true;
    });
  })();

  const metaCards = visibleMetaConnections.length
    ? `${visibleMetaConnections.map((c) => {
        const status = String(c.status || 'not_connected').toLowerCase();
        const primary = primaryByStatus(status);
        const avatar = renderConnectionAvatar(c.facebook_page_picture_url, c.facebook_page_name || 'Facebook', 'connection-brand-avatar-meta');
        const brandTitle = safeText(c.facebook_page_name, 'Страница Facebook');
        const pageLine = c.facebook_page_name
          ? `${esc(c.facebook_page_name)}`
          : `<span class="small">Страница не выбрана</span>`;
        const igLine = c.instagram_business_id
          ? `${esc(safeText(c.instagram_username, '')) ? `@${esc(c.instagram_username)}` : 'Instagram Business подключен'}`
          : `<span class="small">Instagram Business не выбран</span>`;
        const howToFix = c.status_help_text || 'Проверьте детали подключения.';
        const canRefresh = status === 'connected_ready' || status === 'connected' || status === 'token_expired';
        const canAddPage = status === 'connected_ready' || status === 'connected' || status === 'connected_need_page';
        const statusText = status === 'connected_ready' || status === 'connected' ? 'Готово' : 'Нужно действие';
        const syncText = canRefresh ? 'Синхронизация OK' : 'Ограничено';
        const pageHealth = c.facebook_page_name ? 'Страница привязана' : 'Страница не выбрана';
        const igHealth = c.instagram_business_id ? 'IG business активен' : 'IG business не найден';
        return `<article class="card connection-card">
          <div class="row connection-head">
            <div>
              <div class="row connection-chip-row" style="align-items:center;gap:10px;"><span class="pill">Meta</span><span class="connection-caption">Автопостинг</span></div>
              <div class="row connection-title-row">${avatar}<div><h3 class="connection-title">${esc(brandTitle)}</h3><div class="connection-platform-stack">${renderPlatformMini('Facebook', 'facebook')}${renderPlatformMini('Instagram', 'instagram')}</div></div></div>
              <div class="small connection-subtitle">Подключённый бренд-аккаунт для публикации в Facebook и Instagram.</div>
            </div>
            <div>${statusBadge(status)}</div>
          </div>
          <div class="grid-2 connection-grid-info">
            <div class="connection-identity"><span class="connection-label">Facebook Page</span><div class="connection-main-text">${pageLine}</div></div>
            <div class="connection-identity"><span class="connection-label">Instagram Business</span><div class="connection-main-text">${igLine}</div></div>
          </div>
          <div class="connection-kpis connection-kpis-compact">
            <div class="connection-kpi"><strong>${esc(statusText)}</strong><span>Состояние публикации</span></div>
            <div class="connection-kpi"><strong>${esc(syncText)}</strong><span>Статус синхронизации</span></div>
          </div>
          <div class="connection-hint-wrap">
            <div class="small connection-hint">${esc(howToFix)}</div>
            <div class="small connection-hint" style="margin-top:4px;">${esc(pageHealth)} · ${esc(igHealth)}</div>
          </div>
          <div class="cta-row connection-actions">
            <button class="btn btn-primary connection-btn-sm" data-primary-action="${esc(primary.action)}" data-connection-id="${c.id}">${esc(primary.label)}</button>
            ${canAddPage ? `<button class="btn btn-ghost connection-btn-sm" data-add-page="${c.id}">Добавить страницу</button>` : ''}
            ${canRefresh ? `<button class="btn btn-secondary connection-btn-sm" data-refresh="${c.id}">Обновить токен</button>` : ''}
            <button class="btn btn-danger connection-btn-sm" data-disconnect="${c.id}">Отключить</button>
          </div>
        </article>`;
      }).join('')}`
    : `<article class="card connection-card">${emptyState('Нет подключенных Meta-аккаунтов', 'Подключите Facebook Page и Instagram Business, чтобы начать публикацию.', 'Подключить Facebook', '/connections')}</article>`;

  const y = state.youtubeConnection || {};
  const youtubeConnected = !!y.connected;
  const youtubeCard = youtubeConnected ? `
    <article class="card connection-card yt-connection-card">
      <div class="row connection-head">
        <div>
          <div class="row connection-chip-row" style="align-items:center;gap:10px;"><span class="pill">YouTube</span><span class="connection-caption">Видео и Shorts</span></div>
          <div class="row connection-title-row">${renderConnectionAvatar(y.channel_picture_url, y.channel_name || 'YouTube', 'connection-brand-avatar-youtube')}<div><h3 class="connection-title">${esc(safeText(y.channel_name, 'YouTube канал'))}</h3><div class="connection-platform-stack">${renderPlatformMini('YouTube', 'youtube')}</div></div></div>
          <div class="small connection-subtitle">Подключённый канал для роликов, Shorts и постов сообщества.</div>
        </div>
        <div>${statusBadge(y.status || 'connected_ready')}</div>
      </div>
      <div class="connection-features">
        <span class="pill">Shorts 15-70с</span>
        <span class="pill">Long 120-480с</span>
        <span class="pill">AI Script + Post</span>
      </div>
      <div class="connection-grid-info">
        <div class="connection-identity"><span class="connection-label">Канал</span><div class="connection-main-text">${esc(safeText(y.channel_name, 'YouTube канал'))}</div></div>
      </div>
      <div class="connection-kpis connection-kpis-compact">
        <div class="connection-kpi"><strong>Готово</strong><span>Контент-пайплайн</span></div>
        <div class="connection-kpi"><strong>Мультиформат</strong><span>Shorts и long-form</span></div>
      </div>
      <div class="connection-hint-wrap">
        <div class="small connection-hint">Откройте YouTube Studio и выберите тему, формат и длительность.</div>
      </div>
      <div class="cta-row connection-actions">
        <button class="btn btn-primary connection-btn-sm" type="button" data-link="/youtube">Открыть студию</button>
        <button type="button" class="btn btn-danger connection-btn-sm" data-youtube-disconnect="1">Отключить YouTube</button>
      </div>
    </article>
  ` : '';

  const cards = `<div class="grid-2 connections-grid">${metaCards}${youtubeCard}</div>`;

  const picker = state.connectionPicker || { open: false, loading: false, pages: [], selectedPageId: '', error: '' };
  const pageMatches = (p) => {
    const q = String(picker.query || '').trim().toLowerCase();
    if (!q) return true;
    return String(p.page_name || '').toLowerCase().includes(q) || String(p.page_id || '').includes(q) || String(p.ig_username || '').toLowerCase().includes(q);
  };
  const pageInFilter = (p) => {
    if (picker.filter === 'with_ig') return !!p.has_ig;
    if (picker.filter === 'without_ig') return !p.has_ig;
    if (picker.filter === 'not_connected') return !p.already_connected;
    return true;
  };
  const visiblePages = (picker.pages || []).filter((p) => pageInFilter(p) && pageMatches(p));

  const pickerList = picker.loading
    ? `<p class="small">Загружаю список страниц…</p>`
    : (picker.error
        ? `<p class="small" style="color:var(--error);">${esc(picker.error)}</p>`
        : (picker.pages.length
            ? (visiblePages.length
                ? `<div class="list">${visiblePages.map((p) => {
                const pic = p.page_picture_url ? `<span class="avatar"><img src="${esc(p.page_picture_url)}" alt="" /></span>` : `<span class="avatar">${esc((safeText(p.page_name,'P')[0] || 'P').toUpperCase())}</span>`;
                const ig = p.has_ig ? `<span class="pill ok">IG привязан</span>` : `<span class="pill warn">Без IG</span>`;



              }).join('')}</div>`
                : `<p class="small">Неподключенных страниц не найдено. Все доступные страницы уже добавлены.</p>`)
            : `<p class="small">Страницы не найдены. Проверьте, что у аккаунта есть роль на Facebook Page и выданы permissions (pages_show_list).</p>`));

  const modal = `<div id="connectionPickerBackdrop" class="modal-backdrop ${picker.open ? 'open' : ''}"><div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h3>Выбор Facebook Page</h3><button id="closePickerBtn" class="btn btn-ghost">Закрыть</button></div><div class="modal-body"><p class="small">Покажем все страницы, к которым у вашего токена есть доступ. Выберите нужную для публикаций.</p><div class="row" style="justify-content:space-between;align-items:center;margin:10px 0;"><div class="cta-row"><button id="filterAllBtn" class="btn btn-ghost">Все</button><button id="filterNotConnectedBtn" class="btn btn-ghost">Неподключенные</button><button id="filterWithIgBtn" class="btn btn-ghost">С IG</button><button id="filterWithoutIgBtn" class="btn btn-ghost">Без IG</button></div><input id="pageSearchInput" style="max-width:320px;" placeholder="Поиск: название / Page ID / @IG" /></div>${pickerList}</div><div class="cta-row" style="margin-top:12px;justify-content:flex-end;"><button id="refreshPagesBtn" class="btn btn-secondary">Обновить список</button><button id="savePickedPageBtn" class="btn btn-primary" ${picker.selectedPageId ? '' : 'disabled'}>Использовать</button><button id="addPickedPageBtn" class="btn btn-secondary" ${picker.selectedPageId ? '' : 'disabled'}>Добавить как отдельное</button></div></div></div>`;

  const connectYoutubeBtn = youtubeConnected
    ? '<button id="connectYoutubeBtn" class="btn btn-secondary connection-btn-sm" type="button" disabled>YouTube подключён</button>'
    : '<button id="connectYoutubeBtn" class="btn btn-secondary connection-btn-sm" type="button">Подключить YouTube</button>';
  return appLayout('/connections', 'Подключения', `<section class="card connection-shell"><h2>Подключенные аккаунты</h2><p class="small">Подключите Meta и YouTube. В карточке показывается реальное лого подключённой страницы или канала.</p><div class="cta-row connections-toolbar"><button id="connectMetaBtn" data-testid="connect-meta-btn" class="btn btn-primary connection-btn-sm">Подключить Meta</button>${connectYoutubeBtn}</div>${cards}</section>${modal}`);
}

function plansTable() {
  const planMap = {};
  (state.plans || []).forEach((p) => { planMap[p.name] = p; });
  const marketingMap = Object.fromEntries(MARKETING_PRICING_PLANS.map((p) => [p.key, p]));
  const f = (name, key, fallback) => {
    const v = planMap[name]?.[key];
    return v === undefined || v === null || String(v).trim() === '' ? fallback : v;
  };
  const yesNo = (v) => (v ? '\u0414\u0430' : '\u041d\u0435\u0442');
  const price = (name) => {
    if (marketingMap[name]?.price) return marketingMap[name].price;
    const v = planMap[name]?.price_eur_month;
    if (v === undefined || v === null) return '\u2014';
    const n = Number(v) || 0;
    return n <= 0 ? '\u20ac0' : `\u20ac${n}`;
  };
  const workspaces = (name) => {
    const v = planMap[name]?.max_projects;
    if (Number(v || 0) >= 999999 || String(name) === 'agency') return '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430';
    return v ?? '\u2014';
  };
  const channels = (name) => {
    const v = planMap[name]?.accounts_connected;
    if (Number(v || 0) >= 999999 || String(name) === 'agency') return '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430';
    return v ?? '\u2014';
  };
  const analytics = (name) => {
    const key = String(planMap[name]?.analytics_level || 'none').toLowerCase();
    return key === 'advanced' ? '\u0440\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f' : (key === 'basic' ? '\u0431\u0430\u0437\u043e\u0432\u0430\u044f' : '\u043d\u0435\u0442');
  };
  return `<div class="table-wrap"><table class="pricing-table"><thead><tr><th>\u0424\u0443\u043d\u043a\u0446\u0438\u044f</th><th>Free Trial</th><th>Starter</th><th>Growth</th><th>Agency</th></tr></thead><tbody>
    <tr><td>\u0426\u0435\u043d\u0430 / \u043c\u0435\u0441\u044f\u0446</td><td>${price('free')}</td><td>${price('starter')}</td><td>${price('growth')}</td><td>${price('agency')}</td></tr>
    <tr><td>\u041f\u0440\u043e\u0431\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434</td><td>7 \u0434\u043d\u0435\u0439</td><td>\u2014</td><td>\u2014</td><td>\u2014</td></tr>
    <tr><td>\u041f\u043e\u0441\u0442\u044b / \u043c\u0435\u0441\u044f\u0446</td><td>${f('free','max_posts_month',30)}</td><td>${f('starter','max_posts_month',150)}</td><td>${f('growth','max_posts_month',600)}</td><td>${f('agency','max_posts_month',2000)}</td></tr>
    <tr><td>\u0412\u0438\u0434\u0435\u043e / \u043c\u0435\u0441\u044f\u0446</td><td>${f('free','max_videos_period',3)}</td><td>${f('starter','max_videos_period',10)}</td><td>${f('growth','max_videos_period',40)}</td><td>${f('agency','max_videos_period',150)}</td></tr>
    <tr><td>\u0420\u0430\u0431\u043e\u0447\u0438\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u0430</td><td>${workspaces('free')}</td><td>${workspaces('starter')}</td><td>${workspaces('growth')}</td><td>${workspaces('agency')}</td></tr>
    <tr><td>\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d\u043d\u044b\u0435 \u043a\u0430\u043d\u0430\u043b\u044b</td><td>${channels('free')}</td><td>${channels('starter')}</td><td>${channels('growth')}</td><td>${channels('agency')}</td></tr>
    <tr><td>\u0410\u0432\u0442\u043e\u043f\u043e\u0441\u0442\u0438\u043d\u0433</td><td>${yesNo(f('free','can_autopublish',false))}</td><td>${yesNo(f('starter','can_autopublish',true))}</td><td>${yesNo(f('growth','can_autopublish',true))}</td><td>${yesNo(f('agency','can_autopublish',true))}</td></tr>
    <tr><td>\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430</td><td>${analytics('free')}</td><td>${analytics('starter')}</td><td>${analytics('growth')}</td><td>${analytics('agency')}</td></tr>
  </tbody></table></div>`;
}

function pricingCards() {
  const planMap = {};
  (state.plans || []).forEach((p) => { planMap[p.name] = p; });
  const marketingMap = Object.fromEntries(MARKETING_PRICING_PLANS.map((p) => [p.key, p]));
  const marketingFeatures = {
    free: { posts: '30', videos: '3', workspaces: '1', channels: '1', autopublish: false, analytics: 'none' },
    starter: { posts: '150', videos: '10', workspaces: '2', channels: '2', autopublish: true, analytics: 'basic' },
    growth: { posts: '600', videos: '40', workspaces: '5', channels: '5', autopublish: true, analytics: 'advanced' },
    agency: { posts: '2000', videos: '150', workspaces: '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430', channels: '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430', autopublish: true, analytics: 'advanced' },
  };

  const stripe = state.billing?.stripe || {};
  const stripeReady = !!stripe.subscriptions_ready;
  const planPaymentAvailable = (name) => !!(planMap[name]?.payment_available && stripe.prices?.[name]);
  const current = String(state.billing?.plan || state.user?.plan || 'free').toLowerCase();
  const order = ['free', 'starter', 'growth', 'agency'];
  const meta = {
    free: { title: marketingMap.free?.name || 'Free Trial 7 days', desc: '\u041f\u043e\u043f\u0440\u043e\u0431\u043e\u0432\u0430\u0442\u044c \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439 \u0440\u0430\u0431\u043e\u0442\u044b \u0431\u0435\u0437 \u043a\u0430\u0440\u0442\u044b \u0438 \u043b\u0438\u0448\u043d\u0438\u0445 \u0440\u0430\u0441\u0445\u043e\u0434\u043e\u0432.' },
    starter: { title: marketingMap.starter?.name || 'Starter', desc: '\u0414\u043b\u044f \u043c\u0430\u043b\u043e\u0433\u043e \u0431\u0438\u0437\u043d\u0435\u0441\u0430.' },
    growth: { title: marketingMap.growth?.name || 'Growth', desc: '\u0414\u043b\u044f \u0440\u0435\u0433\u0443\u043b\u044f\u0440\u043d\u043e\u0433\u043e \u043a\u043e\u043d\u0442\u0435\u043d\u0442-\u043f\u043e\u0442\u043e\u043a\u0430, \u0432\u0438\u0434\u0435\u043e \u0438 \u0430\u0432\u0442\u043e\u043f\u043e\u0441\u0442\u0438\u043d\u0433\u0430.', highlight: true },
    agency: { title: marketingMap.agency?.name || 'Agency', desc: '\u0414\u043b\u044f \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u0438\u0445 \u0431\u0440\u0435\u043d\u0434\u043e\u0432 \u0438 \u043a\u043b\u0438\u0435\u043d\u0442\u0441\u043a\u0438\u0445 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u043e\u0432.' },
    admin: { title: 'Admin Unlimited', desc: '\u0412\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0438\u0439 \u0441\u043b\u0443\u0436\u0435\u0431\u043d\u044b\u0439 \u0442\u0430\u0440\u0438\u0444 \u0441 \u043f\u043e\u043b\u043d\u044b\u043c \u0434\u043e\u0441\u0442\u0443\u043f\u043e\u043c.' },
  };
  const price = (name) => {
    if (marketingMap[name]?.price) return marketingMap[name].price;
    const v = planMap[name]?.price_eur_month;
    const n = Number(v) || 0;
    return n <= 0 ? '\u20ac0' : `\u20ac${n}`;
  };
  const workspaces = (name) => {
    const live = planMap[name]?.max_projects;
    if (Number(live || 0) >= 999999 || name === 'agency') return '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430';
    if (live !== undefined && live !== null && String(live).trim() !== '') return live;
    return marketingFeatures[name]?.workspaces ?? '\u2014';
  };
  const channels = (name) => {
    const live = planMap[name]?.accounts_connected;
    if (Number(live || 0) >= 999999 || name === 'agency') return '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430';
    if (live !== undefined && live !== null && String(live).trim() !== '') return live;
    return marketingFeatures[name]?.channels ?? '\u2014';
  };
  const posts = (name) => {
    const live = planMap[name]?.max_posts_month;
    if (live !== undefined && live !== null && String(live).trim() !== '') return live;
    return marketingFeatures[name]?.posts ?? '\u2014';
  };
  const videos = (name) => {
    const live = planMap[name]?.max_videos_period;
    if (live !== undefined && live !== null && String(live).trim() !== '') return live;
    return marketingFeatures[name]?.videos ?? '\u2014';
  };
  const autopublish = (name) => {
    if (typeof planMap[name]?.can_autopublish === 'boolean') return !!planMap[name].can_autopublish;
    return !!marketingFeatures[name]?.autopublish;
  };
  const analytics = (name) => {
    const key = String(planMap[name]?.analytics_level || marketingFeatures[name]?.analytics || 'none').toLowerCase();
    return key === 'advanced' ? 'advanced' : (key === 'basic' ? 'basic' : 'none');
  };
  const analyticsLabel = (name) => {
    const key = analytics(name);
    return key === 'advanced' ? '\u0440\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f' : (key === 'basic' ? '\u0431\u0430\u0437\u043e\u0432\u0430\u044f' : '\u043d\u0435\u0442');
  };
  const yesNo = (v) => (v ? '\u0434\u0430' : '\u043d\u0435\u0442');
  const adminCard = current === 'admin'
    ? `<article class="card plan-card highlight">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <div class="plan-title">${esc(meta.admin.title)}</div>
            <div class="plan-price">\u221e<span class="plan-price-suffix">/internal</span></div>
            <div class="small muted" style="margin-top:6px;">${esc(meta.admin.desc)}</div>
          </div>
          <div>${planBadge('admin')}</div>
        </div>
        <div class="plan-features">
          <div class="small"><strong>\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430</strong> \u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432</div>
          <div class="small"><strong>\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430</strong> \u043f\u043e\u0441\u0442\u043e\u0432/\u043c\u0435\u0441</div>
          <div class="small"><strong>\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430</strong> \u0432\u0438\u0434\u0435\u043e/\u043c\u0435\u0441</div>
          <div class="small"><strong>\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430</strong> \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d\u043d\u044b\u0445 \u043a\u0430\u043d\u0430\u043b\u043e\u0432</div>
          <div class="small">\u0410\u0432\u0442\u043e\u043f\u043e\u0441\u0442\u0438\u043d\u0433: <strong>\u0434\u0430</strong></div>
          <div class="small">\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430: <strong>\u0440\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f</strong></div>
        </div>
        <div class="cta-row" style="margin-top:12px;justify-content:space-between;gap:10px;">
          <button class="btn btn-secondary" disabled>\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u0441\u043b\u0443\u0436\u0435\u0431\u043d\u044b\u0439 \u0442\u0430\u0440\u0438\u0444</button>
          <span class="hint-pill">Admin</span>
        </div>
      </article>`
    : '';

  return `<div class="pricing-grid">
    ${adminCard}
    ${order.map((name) => {
      const m = meta[name] || { title: name, desc: '' };
      const isCurrent = current === name;
      const canUpgrade = name !== 'free' && stripeReady && planPaymentAvailable(name);
      const btn = isCurrent
        ? `<button class="btn btn-secondary" disabled>\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u043f\u043b\u0430\u043d</button>`
        : canUpgrade
          ? `<button class="btn ${m.highlight ? 'btn-primary' : 'btn-secondary'}" data-upgrade="${esc(name)}">\u041f\u0435\u0440\u0435\u0439\u0442\u0438 \u043d\u0430 ${esc(m.title)}</button>`
          : name === 'free'
            ? `<button class="btn btn-ghost" disabled>\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043f\u043e \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u0438</button>`
            : `<button class="btn btn-ghost" disabled title="\u041f\u043b\u0430\u0442\u043d\u044b\u0435 \u043f\u043b\u0430\u043d\u044b \u0443\u0436\u0435 \u0443\u0447\u0430\u0441\u0442\u0432\u0443\u044e\u0442 \u0432 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u043e\u0432\u043e\u0439 \u043b\u043e\u0433\u0438\u043a\u0435, \u043d\u043e checkout \u0435\u0449\u0451 \u043d\u0435 \u0432\u043a\u043b\u044e\u0447\u0451\u043d">\u0421\u043a\u043e\u0440\u043e \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e</button>`;
      return `<article class="card plan-card ${m.highlight ? 'highlight' : ''}">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;">
          <div>
            <div class="plan-title">${esc(m.title)}</div>
            <div class="plan-price">${price(name)}<span class="plan-price-suffix">/\u043c\u0435\u0441</span></div>
            <div class="small muted" style="margin-top:6px;">${esc(m.desc)}</div>
          </div>
          <div>${planBadge(name)}</div>
        </div>
        <div class="plan-features">
          <div class="small"><strong>${workspaces(name)}</strong> \u0440\u0430\u0431\u043e\u0447\u0438\u0445 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432</div>
          <div class="small"><strong>${posts(name)}</strong> \u043f\u043e\u0441\u0442\u043e\u0432/\u043c\u0435\u0441</div>
          <div class="small"><strong>${videos(name)}</strong> \u0432\u0438\u0434\u0435\u043e/\u043c\u0435\u0441</div>
          <div class="small"><strong>${channels(name)}</strong> \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d\u043d\u044b\u0445 \u043a\u0430\u043d\u0430\u043b\u043e\u0432</div>
          <div class="small">\u0410\u0432\u0442\u043e\u043f\u043e\u0441\u0442\u0438\u043d\u0433: <strong>${yesNo(autopublish(name))}</strong></div>
          <div class="small">\u0410\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430: <strong>${esc(analyticsLabel(name))}</strong></div>
        </div>
        <div class="cta-row" style="margin-top:12px;justify-content:space-between;gap:10px;">
          ${btn}
          ${m.highlight ? `<span class="hint-pill">\u041f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0439</span>` : `<span></span>`}
        </div>
      </article>`;
    }).join('')}
  </div>`;
}

function pageHistory(showCalendar = false) {
  const viewer = state.postViewer || { open: false, loading: false, post: null, error: '' };
  const editor = state.postEditor || { open: false, saving: false, post: null, error: '' };
  const today = new Date();
  const calendarState = state.historyCalendar || { monthKey: '', monthsSpan: 1, selectedDayKey: '' };
  const currentMonthKey = localMonthKey(today);
  if (!calendarState.monthKey) calendarState.monthKey = currentMonthKey;
  calendarState.monthsSpan = 1;
  const start = monthStartFromKey(calendarState.monthKey);
  const end = new Date(start.getFullYear(), start.getMonth() + 1, 1);
  const dayMs = 24 * 60 * 60 * 1000;
  const dayKeys = [];
  for (let cursor = new Date(start.getTime()); cursor < end; cursor = new Date(cursor.getTime() + dayMs)) {
    dayKeys.push(localDateKey(cursor));
  }
  const rangeLabel = start.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  const dateToKey = (value) => {
    if (!value) return '';
    return localDateKey(value);
  };
  const isPublishedPost = (p) => {
    if (!p) return false;
    const status = String(p.status || '').toLowerCase();
    return Boolean(p.published_at) || Boolean(p.remote_id) || status === 'published';
  };
  const plannerStatus = (p) => (isPublishedPost(p) ? 'published' : 'draft');
  const grouped = Object.fromEntries(dayKeys.map((k) => [k, []]));
  grouped.draft = [];
  const dayKeySet = new Set(dayKeys);
  for (const p of (state.posts || [])) {
    const published = plannerStatus(p) === 'published';
    const calendarDate = published ? (p.published_at || p.schedule_at || p.created_at) : p.schedule_at;
    const calendarKey = dateToKey(calendarDate);
    const key = calendarKey && dayKeySet.has(calendarKey) ? calendarKey : 'draft';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(p);
  }
  for (const key of Object.keys(grouped)) {
    grouped[key].sort((a, b) => {
      const da = new Date(a.published_at || a.schedule_at || a.created_at).getTime();
      const db = new Date(b.published_at || b.schedule_at || b.created_at).getTime();
      return da - db;
    });
  }
  const defaultSelectedKey = dayKeySet.has(dateToKey(today)) ? dateToKey(today) : dayKeys[0];
  const selectedDayKey = dayKeySet.has(calendarState.selectedDayKey) ? calendarState.selectedDayKey : defaultSelectedKey;
  calendarState.selectedDayKey = selectedDayKey;
  state.historyCalendar = { ...(state.historyCalendar || {}), monthKey: calendarState.monthKey, monthsSpan: 1, selectedDayKey };

  const selectedDayPosts = grouped[selectedDayKey] || [];
  const selectedDate = new Date(`${selectedDayKey}T00:00:00`);
  const selectedDateLabel = selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
  const postsInMonth = dayKeys.reduce((acc, k) => acc + (grouped[k]?.length || 0), 0);
  const publishedInMonth = dayKeys.reduce((acc, k) => acc + (grouped[k] || []).filter((p) => plannerStatus(p) === 'published').length, 0);
  const draftsWithoutDay = grouped.draft.length;

  const weekDayLabels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const leadingEmpty = (start.getDay() + 6) % 7;
  const monthCells = [];
  for (let i = 0; i < leadingEmpty; i += 1) monthCells.push('<div class="phone-day-blank"></div>');
  for (const key of dayKeys) {
    const d = new Date(`${key}T00:00:00`);
    const count = (grouped[key] || []).length;
    const isToday = key === dateToKey(today);
    const isSelected = key === selectedDayKey;
    monthCells.push(`<button class="phone-day ${count > 0 ? 'has-posts' : 'no-posts'} ${isToday ? 'is-today' : ''} ${isSelected ? 'is-selected' : ''}" data-calendar-day="${key}">
      <span class="phone-day-number">${d.getDate()}</span>
      <span class="phone-day-dot">${count > 0 ? `${count}` : '0'}</span>
    </button>`);
  }

  const selectedPostsHtml = selectedDayPosts.map((p) => {
    const status = plannerStatus(p);
    const title = p.topic || p.title_preview || `Пост #${p.id}`;
    const when = p.published_at ? `Опубликовано: ${new Date(p.published_at).toLocaleString()}` : (p.schedule_at ? `План: ${new Date(p.schedule_at).toLocaleString()}` : 'Без даты');
    return `<article class="phone-post-row">
      <div class="phone-post-main">
        <strong class="truncate" title="${esc(title)}">${esc(title)}</strong>
        <div class="small">${esc(p.platform || '—')} · ${esc(when)} · ${status === 'published' ? 'Опубликован' : 'Черновик'}</div>
      </div>
    </article>`;
  }).join('');

  const plannerBoard = `<section class="card planner-card phone-calendar">
    <div class="phone-cal-toolbar">
      <button class="btn btn-ghost phone-nav-btn" id="calendarPrevMonthBtn"><</button>
      <h3 class="phone-cal-title">${esc(rangeLabel)}</h3>
      <button class="btn btn-ghost phone-nav-btn" id="calendarNextMonthBtn">></button>
    </div>
    <div class="phone-cal-subline">
      <button class="btn btn-ghost" id="calendarTodayBtn">Сегодня</button>
      <span class="small">Постов в месяце: ${postsInMonth} · Опубликовано: ${publishedInMonth} · Вне месяца/без даты: ${draftsWithoutDay}</span>
    </div>
    <div class="phone-weekdays">${weekDayLabels.map((w) => `<span>${w}</span>`).join('')}</div>
    <div class="phone-days">${monthCells.join('')}</div>
    <div class="phone-selected-panel">
      <h4 id="historySelectedDayLabel" style="margin:0;">${esc(selectedDateLabel)}</h4>
      <div id="historySelectedDayPosts">
        ${selectedPostsHtml || `<div class="small muted">На этот день постов нет</div>`}
      </div>
    </div>
  </section>`;

  const table = state.posts.length
    ? `<div class="table-wrap"><table>
        <thead><tr>
          <th>Дата</th>
          <th>Платформа</th>
          <th>Тема</th>
          <th>Статус</th>
          <th>Публикация</th>
          <th>Действия</th>
        </tr></thead>
        <tbody>
          ${state.posts.map((p) => {
            const pub = p.published_at ? `Опубликовано: ${new Date(p.published_at).toLocaleString()}` : (p.schedule_at ? `Запланировано: ${new Date(p.schedule_at).toLocaleString()}` : '—');
            const retryDisabled = (p.status === 'queued' || p.status === 'running') ? 'disabled' : '';
            const title = ((p.topic || '').trim() && (p.topic || '').includes('?') && (p.title_preview || '').trim())
              ? p.title_preview
              : (p.topic || p.title_preview || '—');
            const isPublished = plannerStatus(p) === 'published';
            const isYoutube = String(p.platform || '').toLowerCase() === 'youtube';
            const publishDisabled = (isPublished || p.status === 'failed' || isYoutube) ? 'disabled' : '';
            return `<tr>
              <td>${new Date(p.created_at).toLocaleString()}</td>
              <td>${esc(p.platform)}</td>
              <td class="truncate" title="${esc(title)}">${esc(title)}</td>
              <td>${statusBadge(plannerStatus(p))}</td>
              <td class="small">${esc(pub)}</td>
              <td>
                <div class="cta-row" style="justify-content:flex-end;">
                  <button class="btn btn-ghost" data-edit-post="${p.id}">Редактировать</button>
                  ${isPublished ? `<button class="btn btn-ghost" data-hide-post="${p.id}">Убрать с сайта</button>` : `<button class="btn btn-secondary" data-publish-now="${p.id}" ${publishDisabled}>Опубликовать</button>`}
                  ${isPublished ? '' : `<button class="btn btn-danger" data-delete-post="${p.id}">Удалить</button>`}
                  <button class="btn btn-ghost" data-view-post="${p.id}">Открыть</button>
                  <button class="btn btn-ghost" data-retry="${p.id}" ${retryDisabled}>Повтор</button>
                </div>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table></div>`
    : emptyState('Календарь пуст', 'Создайте первый пост и опубликуйте его.', 'Создать пост', '/create');

  const modalBody = viewer.loading
    ? `<p class="small">Загружаю пост…</p>`
    : (viewer.error
        ? `<p class="small" style="color:var(--error);">${esc(viewer.error)}</p>`
        : (viewer.post
            ? (() => {
                const p = viewer.post;
                const meta = [
                  p.platform ? `Платформа: <strong>${esc(p.platform)}</strong>` : '',
                  p.status ? `Статус: ${statusBadge(p.status)}` : '',
                  p.schedule_at ? `План: <strong>${esc(new Date(p.schedule_at).toLocaleString())}</strong>` : '',
                  p.published_at ? `Публикация: <strong>${esc(new Date(p.published_at).toLocaleString())}</strong>` : '',
                ].filter(Boolean).join(' • ');
                const text = (p.generated_text || '').trim();
                const mediaUrl = String(p.media_url || '').trim();
                const mediaPreview = mediaUrl
                  ? `<div style="margin:12px 0 14px 0;">
                      <p class="small" style="margin:0 0 8px 0;"><strong>Изображение</strong></p>
                      <a href="${esc(mediaUrl)}" target="_blank" rel="noopener noreferrer" style="display:block;">
                        <img
                          src="${esc(mediaUrl)}"
                          alt="Post image"
                          onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='block';"
                          style="width:100%;max-height:360px;object-fit:contain;border-radius:14px;border:1px solid rgba(99,102,241,.16);background:rgba(255,255,255,.75);display:block;"
                        />

                      </a>
                    </div>`
                  : '';
                const body = text
                  ? `<div class="post-preview" style="white-space:pre-wrap;line-height:1.45;">${esc(text)}</div>`
                  : `<p class="small muted">Текст еще не готов. Если статус “queued/running”, подождите 10–30 секунд и откройте снова.</p>`;
                const err = p.error_message ? `<p class="small" style="color:var(--error);margin-top:10px;">Ошибка: ${esc(p.error_message)}</p>` : '';
                const prompt = (p.prompt_text || '').trim();

                return `<div>
                  <div class="small muted">${meta || ''}</div>
                  <h3 style="margin-top:10px;">${esc(p.topic || 'Пост')}</h3>
                  ${mediaPreview}
                  ${body}
                  ${err}
                  ${details}
                </div>`;
              })()
            : `<p class="small muted">Выберите пост в таблице.</p>`));

  const modal = `<div id="postViewerBackdrop" class="modal-backdrop ${viewer.open ? 'open' : ''}">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Пост</h3>
        <button id="closePostViewerBtn" class="btn btn-ghost">Закрыть</button>
      </div>
      <div class="modal-body">
        ${modalBody}
      </div>
    </div>
  </div>`;

  const editorPlatforms = editor.platforms || { facebook: String(editor.post?.platform || '').toLowerCase() === 'facebook', instagram: String(editor.post?.platform || '').toLowerCase() === 'instagram' };
  const editorBody = editor.post ? `<div>
    ${editor.error ? `<p class="small" style="color:var(--error);">${esc(editor.error)}</p>` : ''}
    ${field('editTopic', 'Тема', 'text', editor.post.topic || '')}
    ${field('editText', 'Текст', 'textarea', editor.post.generated_text || '')}
    <div class="field">
      <label>Платформы</label>
      <div class="row" style="gap:12px;align-items:center;flex-wrap:wrap;">
        <label class="create-toggle"><input id="editPlatformFacebook" type="checkbox" ${editorPlatforms.facebook ? 'checked' : ''}/> Facebook</label>
        <label class="create-toggle"><input id="editPlatformInstagram" type="checkbox" ${editorPlatforms.instagram ? 'checked' : ''}/> Instagram</label>
      </div>
      <p class="small" style="margin-top:6px;">Для каждой выбранной платформы будет сохранена отдельная запись публикации.</p>
    </div>
    ${field('editMedia', 'Ссылка на изображение (опц.)', 'text', editor.post.media_url || '', 'https://...')}
    ${String(editor.post.media_url || '').trim()
      ? `<div style="margin:10px 0 4px 0;">
          <p class="small" style="margin:0 0 8px 0;"><strong>Превью изображения</strong></p>
          <a href="${esc(String(editor.post.media_url || '').trim())}" target="_blank" rel="noopener noreferrer" style="display:block;">
            <img
              src="${esc(String(editor.post.media_url || '').trim())}"
              alt="Post image preview"
              onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='block';"
              style="width:100%;max-height:320px;object-fit:contain;border-radius:14px;border:1px solid rgba(99,102,241,.16);background:rgba(255,255,255,.75);display:block;"
            />
            <div style="display:none;padding:14px;border:1px solid rgba(99,102,241,.16);border-radius:14px;background:rgba(255,255,255,.75);color:var(--muted);">Изображение недоступно</div>
          </a>
        </div>`
      : ''}
    ${field('editSchedule', 'Дата и время публикации (опц.)', 'datetime-local', toLocalInputValue(editor.post.schedule_at))}
    <div class="cta-row" style="justify-content:flex-end;margin-top:12px;">
      <button id="clearScheduleBtn" class="btn btn-ghost" ${editor.saving ? 'disabled' : ''}>Снять с расписания</button>
      <button id="savePostEditBtn" class="btn btn-primary" ${editor.saving ? 'disabled' : ''}>${editor.saving ? 'Сохраняю…' : 'Сохранить'}</button>
    </div>
  </div>` : `<p class="small muted">Пост не выбран.</p>`;

  const editModal = `<div id="postEditBackdrop" class="modal-backdrop ${editor.open ? 'open' : ''}">
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Редактирование перед публикацией</h3>
        <button id="closePostEditBtn" class="btn btn-ghost">Закрыть</button>
      </div>
      <div class="modal-body">${editorBody}</div>
    </div>
  </div>`;

  const calendarSection = showCalendar ? plannerBoard : '';
  return appLayout(showCalendar ? '/calendar' : '/history', showCalendar ? 'Календарь' : 'История', `${calendarSection}<section class="card"><h2>Архив публикаций</h2>${table}</section>${modal}${editModal}`);
}

function pageCalendar() {
  return pageHistory(true);
}

function pageBilling() {
  const b = state.billing || { plan: 'free', usage: {}, limits: {} };
  const stripe = b.stripe || {};
  const usedMonth = b.usage.posts_per_month || 0;
  const limitMonth = b.limits.posts_per_month || 0;
  const usedVideos = b.usage.videos_per_month || 0;
  const limitVideos = b.limits.videos_per_month || 0;
  const usedProjects = b.usage.projects || 0;
  const limitProjects = b.limits.projects || 0;
  const usedDaily = b.usage.daily_posts || 0;
  const limitDaily = b.limits.daily_posts || 0;
  const monthlyUnlimited = Number(limitMonth) >= 1000000000;
  const videosUnlimited = Number(limitVideos) >= 1000000000;
  const projectsUnlimited = Number(limitProjects) >= 999999;
  const dailyUnlimited = Number(limitDaily) >= 1000000000;
  const monthMax = monthlyUnlimited ? Math.max(Number(usedMonth) || 0, 1) : Math.max(Number(limitMonth) || 0, 1);
  const videoMax = videosUnlimited ? Math.max(Number(usedVideos) || 0, 1) : Math.max(Number(limitVideos) || 0, 1);
  const projectsMax = projectsUnlimited ? Math.max(Number(usedProjects) || 0, 1) : Math.max(Number(limitProjects) || 0, 1);
  const dayMax = dailyUnlimited ? Math.max(Number(usedDaily) || 0, 1) : Math.max(Number(limitDaily) || 0, 1);
  const stripeHint = stripe.subscriptions_ready
    ? ''
    : `<section class="card" style="margin-bottom:18px;">
         <h3>Оплата временно недоступна</h3>
         <p class="small">${b.plan === 'admin' ? 'Для администратора checkout не нужен: активен внутренний безлимитный тариф.' : 'Тарифы Starter, Growth и Agency уже участвуют в логике продукта, но их checkout пока выключен.'}</p>
       </section>`;
  const analyticsLevelLabel = (() => {
    const key = String(b.limits.analytics_level || 'none').toLowerCase();
    return key === 'advanced' ? 'Расширенная' : (key === 'basic' ? 'Базовая' : 'Нет');
  })();

  const billingInfo = `<section class="grid-2" style="margin-bottom:18px;">
    <article class="card">
      <h2 style="margin-bottom:6px;">Тарифы и биллинг</h2>
      <p class="small">Текущий план: <strong>${esc(b.plan_title || planBadge(b.plan || 'free').replace(/<[^>]+>/g, ''))}</strong></p>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
      <div class="cta-row" style="margin-top:12px;">
        <button class="btn btn-ghost" data-portal="1" ${stripe.portal_ready ? '' : 'disabled'} title="${stripe.portal_ready ? '' : (b.plan === 'admin' ? 'Для admin-плана управление подпиской не требуется' : 'Портал подписки станет доступен после включения оплаты')}">Управление подпиской</button>
      </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
    </article>
    <article class="card">
      <h3>Использование</h3>
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
      ${progressBar(usedMonth, monthMax)}
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
      ${progressBar(usedVideos, videoMax)}
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
      ${progressBar(usedProjects, projectsMax)}
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
      ${progressBar(usedDaily, dayMax)}
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
    </article>
  </section>`;

  return appLayout(
    '/billing',
    'Тарифы',
    `${stripeHint}${billingInfo}
     ${pricingCards()}
     <section class="card" style="margin-top:18px;">
       <h3>Сравнение тарифов</h3>
       ${plansTable()}
       <div class="small muted" style="margin-top:10px;">Growth - основной тариф для регулярного контента, видео и автопостинга.</div>
     </section>`
  );
}

function pageSettings() {
  if (!state.dashboardBrand) {
    try {
      const raw = localStorage.getItem('dashboardBrandSettings');
      state.dashboardBrand = raw ? JSON.parse(raw) : { description: '', audience: '', ctaStyle: 'value' };
    } catch {
      state.dashboardBrand = { description: '', audience: '', ctaStyle: 'value' };
    }
  }
  const brand = state.dashboardBrand || { description: '', audience: '', ctaStyle: 'value' };
  return appLayout('/settings', 'Настройки бренда', `<section class="dash-card">
    <h3>Параметры бренда</h3>
    ${field('dashBrandDescription', 'Описание бренда', 'textarea', brand.description || '', 'Чем вы полезны клиентам и какой стиль нужно держать в публикациях')}
    ${field('dashBrandAudience', 'Целевая аудитория', 'text', brand.audience || '', 'Например: владельцы малого бизнеса 25-45')}
    ${selectField('dashBrandCtaStyle', 'Стиль CTA', brand.ctaStyle || 'value', [
      { value: 'value', label: 'Через пользу' },
      { value: 'direct', label: 'Прямой оффер' },
      { value: 'soft', label: 'Мягкий призыв' },
    ])}
    <div class="cta-row">
      <button id="dashSaveBrandBtn" class="btn btn-primary">Сохранить настройки</button>
    </div>
  </section>`);
}

function pageBlog() {
  const selectedSlug = blogSelectedSlug();
  const selected = selectedSlug ? state.blog.find((b) => String(b.slug || '') === selectedSlug) : null;
  if (selected) {
    const detail = `
      <article class="card">
        <div class="cta-row" style="justify-content:space-between;align-items:center;">
          <h2 style="margin:0;">${esc(selected.title)}</h2>
          <button id="blogBackBtn" class="btn btn-ghost">К списку</button>
        </div>
        <div class="small" style="margin-top:10px;">${new Date(selected.published_at).toLocaleDateString()}</div>
        <hr style="margin:14px 0;border:none;border-top:1px solid rgba(128,128,128,.25);" />
        <div class="blog-content">${blogContentToHtml(selected.content, selected.title)}</div>
      </article>`;
    return appLayout('/blog', 'Блог', detail);
  }

  const items = state.blog.length
    ? `<div class="grid-2">${state.blog.map((b)=>`
      <article class="card">
        <h3>${esc(b.title)}</h3>
        <div class="small">${new Date(b.published_at).toLocaleDateString()}</div>
        <p class="small">${esc((b.meta_description || '').slice(0,220))}</p>
        <div class="cta-row" style="margin-top:10px;">
          <button class="btn btn-primary" data-blog-open="${esc(b.slug)}">Открыть статью</button>
        </div>
      </article>`).join('')}</div>`
    : emptyState('Блог пока пуст', 'Ежедневные SEO-статьи будут появляться здесь автоматически.', '', '');
  return appLayout('/blog', 'Блог', `<section class="card"><h2>SEO блог-движок</h2>${items}</section>`);
}

function pageYouTubeStudio() {
  const y = state.youtubeStudio || {};
  const options = state.projects.map((p) => ({ value: p.id, label: p.name }));
  const typeOptions = [
    { value: 'short', label: 'Short (15-70 сек)' },
    { value: 'long', label: 'Long (120-480 сек)' },
  ];
  const postKindOptions = [
    { value: 'community', label: 'Community post' },
    { value: 'announcement', label: 'Announcement' },
    { value: 'poll', label: 'Poll idea' },
  ];
  const videoResult = y.videoResult || null;
  const postResult = y.postResult || null;

  const resultHtml = !videoResult ? '<p class="small">Сгенерируйте пакет видео, чтобы увидеть структуру ролика, заголовки и описание.</p>' : `
    <div class="wizard-summary">
      <span class="pill">Тип: ${esc(videoResult.video_type || '—')}</span>
      <span class="pill">Длительность: ${esc(String(videoResult.duration_seconds || '—'))} сек</span>
      <span class="pill">Ожидание: ~${esc(String(videoResult.estimated_wait_seconds || '—'))} сек</span>
    </div>
    <p class="small">${esc(videoResult.server_capacity_note || '')}</p>
    <h3 style="margin-top:10px;">Варианты заголовка</h3>
    <ul class="small">${(videoResult.title_options || []).map((t) => `<li>${esc(t)}</li>`).join('') || '<li>—</li>'}</ul>
    <h3 style="margin-top:10px;">Хук</h3>
    <p class="small">${esc(videoResult.hook || '—')}</p>
    <h3 style="margin-top:10px;">Описание</h3>
    <p class="small">${esc(videoResult.description || '—')}</p>
    <h3 style="margin-top:10px;">Таймлайн</h3>
    <div class="table-wrap"><table><thead><tr><th>Время</th><th>Сегмент</th><th>Озвучка</th><th>Визуал</th></tr></thead><tbody>
      ${(videoResult.timeline || []).map((s) => `<tr><td>${esc(s.t || '—')}</td><td>${esc(s.segment || '—')}</td><td>${esc(s.voiceover || '—')}</td><td>${esc(s.visual || '—')}</td></tr>`).join('') || '<tr><td colspan="4">—</td></tr>'}
    </tbody></table></div>
    <h3 style="margin-top:10px;">CTA и пост</h3>
    <p class="small"><strong>CTA:</strong> ${esc(videoResult.cta || '—')}</p>
    <p class="small"><strong>Community post:</strong> ${esc(videoResult.community_post || '—')}</p>
    <p class="small"><strong>Хештеги:</strong> ${esc((videoResult.hashtags || []).join(' ') || '—')}</p>
  `;

  return appLayout('/youtube', 'YouTube Studio', `
    <section class="grid-2">
      <article class="card">
        <h2>Генерация ролика для YouTube</h2>
        <p class="small">Настройте тип ролика, длительность и тему. Для стабильной генерации на сервере long ограничен до 480 секунд.</p>
        ${selectField('ytProject', 'Проект', y.projectId || options[0]?.value || '', options.length ? options : [{ value: '', label: 'Нет проектов' }])}
        ${field('ytTopic', 'Тема ролика', 'text', y.topic || '', 'Например: Как малому бизнесу получать заявки из YouTube')}
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
        ${field('ytDuration', 'Длительность (сек)', 'number', String(y.durationSeconds || 45), '45')}
        ${selectField('ytLang', 'Язык', y.language || 'ru', [{ value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' }])}
        ${selectField('ytTone', 'Тон', y.tone || 'expert', [{ value: 'expert', label: 'Экспертный' }, { value: 'friendly', label: 'Дружелюбный' }, { value: 'sales', label: 'Продающий' }])}
        ${field('ytStyle', 'Стиль', 'text', y.style || 'educational', 'educational / storytelling / analytical')}
        ${field('ytAudience', 'Целевая аудитория', 'text', y.audience || '', 'Владельцы бизнеса, маркетологи, эксперты')}
        ${field('ytGoal', 'Цель ролика', 'text', y.goal || 'engagement', 'engagement / leads / views')}
        <div class="cta-row">
          <button id="ytGenerateVideoBtn" type="button" class="btn btn-primary" ${y.loadingVideo ? 'disabled' : ''}>${y.loadingVideo ? 'Генерирую…' : 'Сгенерировать ролик'}</button>
        </div>
        <hr style="margin:14px 0;border:none;border-top:1px solid var(--border);" />
        <h3>YouTube пост</h3>
        ${selectField('ytPostKind', 'Тип поста', y.postKind || 'community', postKindOptions)}
        <div class="cta-row">
          <button id="ytGeneratePostBtn" type="button" class="btn btn-secondary" ${y.loadingPost ? 'disabled' : ''}>${y.loadingPost ? 'Генерирую…' : 'Сгенерировать YouTube пост'}</button>
        </div>
        ${postResult ? `<p class="small" style="margin-top:10px;">Пост создан: #${esc(String(postResult.id || '—'))} (${esc(postResult.status || '—')}). Откройте раздел "Календарь".</p>` : ''}
      </article>
      <article class="card">
        <h2>Результат генерации</h2>
        ${resultHtml}
      </article>
    </section>
  `);
}

function pageContact() {
  return appLayout('/contact','РљРѕРЅС‚Р°РєС‚С‹',`<section class="grid-2"><article class="card"><h2>РљРѕРЅС‚Р°РєС‚С‹</h2><p class="small">РќСѓР¶РЅР° РїРѕРјРѕС‰СЊ СЃ РѕРЅР±РѕСЂРґРёРЅРіРѕРј, РЅР°СЃС‚СЂРѕР№РєРѕР№ Meta РёР»Рё Р±РёР»Р»РёРЅРіРѕРј?</p><p><strong>Email:</strong> support@autosocial-gpt.local</p><p><strong>РљРѕРјРїР°РЅРёСЏ:</strong> AutoSocial.tech SaaS</p><p><strong>Р’СЂРµРјСЏ СЂР°Р±РѕС‚С‹:</strong> РџРЅ-РџС‚ 09:00-18:00 UTC</p></article><article class="card"><h2>Р‘РµР·РѕРїР°СЃРЅРѕСЃС‚СЊ Рё СЃРѕРѕС‚РІРµС‚СЃС‚РІРёРµ</h2><ul class="small"><li>Р‘РµР·РѕРїР°СЃРЅС‹Рµ РїР»Р°С‚РµР¶Рё Stripe</li><li>SSL-С€РёС„СЂРѕРІР°РЅРёРµ СЃРѕРµРґРёРЅРµРЅРёР№</li><li>РЎРѕРѕС‚РІРµС‚СЃС‚РІРёРµ GDPR</li><li>Р‘РµР· СЃРєСЂС‹С‚С‹С… РїР»Р°С‚РµР¶РµР№</li></ul></article></section>`);
}

function pageSupport() {
  return appLayout('/support', 'Поддержка', `<section class="grid-2">
    <article class="card">
      <h2>Поддержка</h2>
      <p class="small">Поможем с подключением Meta, YouTube и настройкой публикаций.</p>
      <p><strong>Email:</strong> support@autosocial.tech</p>
      <p><strong>Часы поддержки:</strong> Пн-Пт 09:00-18:00 UTC</p>
    </article>
    <article class="card">
      <h2>Безопасность</h2>
      <ul class="small">
        <li>Безопасные платежи Stripe</li>
        <li>SSL-шифрование</li>
        <li>Соответствие GDPR</li>
        <li>Без скрытых платежей</li>
      </ul>
    </article>
  </section>`);
}

const CREATE_DRAFT_KEY = 'createCampaignDraftV1';
const CREATE_DIRECTOR_TYPE_KEY = 'createDirectorContentTypeV1';
const DIRECTOR_FIXED_NICHES = [
  { id: 'smm_auto', title: 'Автоматизация SMM' },
  { id: 'content_plan', title: 'Контент-план для бизнеса' },
  { id: 'autoposting', title: 'Автопостинг в соцсетях' },
  { id: 'leads_social', title: 'Лиды из Facebook/Instagram' },
  { id: 'youtube_shorts', title: 'YouTube Shorts для бренда' },
  { id: 'analytics', title: 'Аналитика и рост метрик' },
  { id: 'brand_voice', title: 'Бренд и коммуникация' },
  { id: 'local_business', title: 'Локальный бизнес в соцсетях' },
  { id: 'small_business', title: 'SMM для малого бизнеса' },
  { id: 'agency_mode', title: 'Агентский режим и мультиаккаунт' },
];

function normalizeDirectorContentType(value) {
  return String(value || '').trim().toLowerCase() === 'video' ? 'video' : 'post';
}

function parseCampaignHashtags(raw) {
  return [...new Set(String(raw || '')
    .split(/\s+/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((x) => (x.startsWith('#') ? x : `#${x}`))
  )].slice(0, 30);
}

function normalizeHashtagSet(rawSet, fallback = ['#контент', '#маркетинг', '#smm']) {
  const src = Array.isArray(rawSet) ? rawSet : [];
  const tags = [];
  const seen = new Set();
  for (const item of src) {
    let tag = String(item || '').trim();
    if (!tag) continue;
    if (!tag.startsWith('#')) tag = `#${tag}`;
    const low = tag.toLowerCase();
    if (seen.has(low)) continue;
    seen.add(low);
    tags.push(tag);
    if (tags.length >= 20) break;
  }
  for (const item of fallback) {
    if (tags.length >= 3) break;
    let tag = String(item || '').trim();
    if (!tag) continue;
    if (!tag.startsWith('#')) tag = `#${tag}`;
    const low = tag.toLowerCase();
    if (seen.has(low)) continue;
    seen.add(low);
    tags.push(tag);
  }
  return tags.slice(0, 20);
}

function buildVideoPublicationText(directorState, platform = 'facebook') {
  const d = directorState || {};
  const p = String(platform || 'facebook').trim().toLowerCase();
  const durationSec = Math.max(20, Math.min(480, Number(d.videoDurationPreset || 30) || 30));
  const cta = String(d.selectedCta || d.videoStructure?.cta || '').trim();
  const ytDescription = String(d.videoStructure?.description || '').trim();
  const rawLines = Array.isArray(d.videoStructure?.subtitles?.lines)
    ? d.videoStructure.subtitles.lines
    : (Array.isArray(d.videoStructure?.scenes) ? d.videoStructure.scenes.map((x) => x?.text).filter(Boolean) : []);
  const base = (p === 'youtube' && ytDescription)
    ? ytDescription
    : String(rawLines.join(' ').replace(/\s+/g, ' ').trim() || '');
  if (!base) return 'Сначала сгенерируйте структуру, затем соберите видео.';
  const sentenceParts = String(base)
    .replace(/\s+/g, ' ')
    .match(/[^.!?]+[.!?]?/g) || [String(base).trim()];
  const skipBoilerplateRe = /(покажем один|короткий пример|добавим конкретик|фиксируем ожидаемый эффект|плавно подводим|простыми словами|без лишней сложности|на простой метрике)/i;
  const seen = new Set();
  const cleaned = [];
  for (const raw of sentenceParts) {
    const sentence = String(raw || '').replace(/\s+/g, ' ').trim();
    if (!sentence) continue;
    if (skipBoilerplateRe.test(sentence)) continue;
    const key = sentence
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    cleaned.push(sentence);
  }
  const fallback = cleaned.length ? cleaned : sentenceParts.map((s) => String(s || '').trim()).filter(Boolean);
  const targetChars = p === 'youtube'
    ? Math.max(360, Math.min(1600, Math.round(durationSec * 5.2)))
    : Math.max(220, Math.min(760, Math.round(durationSec * 3.0)));
  const targetSentences = p === 'youtube'
    ? Math.max(3, Math.min(10, Math.round(durationSec / 35)))
    : Math.max(2, Math.min(6, Math.round(durationSec / 25)));
  const picked = [];
  let acc = 0;
  for (const sentence of fallback) {
    if (picked.length >= targetSentences && acc >= targetChars) break;
    const nextLen = acc + sentence.length + 1;
    if (picked.length >= 2 && nextLen > targetChars) break;
    picked.push(sentence);
    acc = nextLen;
  }
  let out = picked.join(' ').replace(/\s+/g, ' ').trim();
  if (!out) out = fallback.slice(0, targetSentences).join(' ').replace(/\s+/g, ' ').trim();
  if (cta) {
    const lowOut = out.toLowerCase();
    if (!lowOut.includes(cta.toLowerCase())) {
      out = `${out}\n\n${cta}`.trim();
    }
  }
  return out || 'Сначала сгенерируйте структуру, затем соберите видео.';
}

function getVideoPreviewTextState(directorState, platform = 'facebook') {
  const d = directorState || {};
  if (!d.previewExpanded || typeof d.previewExpanded !== 'object') d.previewExpanded = {};
  const p = String(platform || 'facebook').trim().toLowerCase();
  const fullText = buildVideoPublicationText(d, p);
  const limits = { facebook: 300, instagram: 280, youtube: 420 };
  const limit = limits[p] || 300;
  const expanded = !!d.previewExpanded[p];
  const shortText = fullText.length > limit
    ? `${fullText.slice(0, Math.max(0, limit - 1)).trimEnd()}…`
    : fullText;
  return {
    fullText,
    text: expanded ? fullText : shortText,
    canExpand: fullText.length > limit,
    expanded,
  };
}

function resolveDirectorPostPreviewText({ draft, draftMatchesSelection, loadingDrafts, selectedThemePreviewText, hasSelection }) {
  const generatedText = String(draft?.post_text || '').trim();
  if (generatedText) return generatedText;
  if (loadingDrafts) return selectedThemePreviewText || 'Генерируем текст по выбранной теме и подходу...';
  if (draftMatchesSelection) return 'Сгенерируйте контент, чтобы увидеть результат.';
  if (hasSelection) return selectedThemePreviewText || 'Генерируем текст по выбранной теме и подходу...';
  return 'Сгенерируйте контент, чтобы увидеть результат.';
}

function loadCampaignDraftLocal() {
  try {
    const raw = localStorage.getItem(CREATE_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    return data;
  } catch {
    return null;
  }
}

function saveCampaignDraftLocal() {
  try {
    const snapshot = { ...state.createCampaign, dirty: false };
    localStorage.setItem(CREATE_DRAFT_KEY, JSON.stringify(snapshot));
  } catch {}
}

function hydrateCampaignDefaults() {
  const c = state.createCampaign;
  if (!c.projectId && state.projects?.[0]?.id) c.projectId = String(state.projects[0].id);
  if (!Array.isArray(c.hashtags)) c.hashtags = ['#бизнес', '#контент'];
  if (!c.platforms) c.platforms = { facebook: true, instagram: true, youtube: false };
  if (!c.kinds) c.kinds = { facebook: 'image_post', instagram: 'image_post', youtube: 'shorts' };
  if (!c.accountRefs) c.accountRefs = { facebook: '', instagram: '', youtube: '' };
  if (!c.contentTone) c.contentTone = 'friendly';
  if (!c.contentGoal) c.contentGoal = 'engagement';
  if (typeof c.contentVariants3 !== 'boolean') c.contentVariants3 = false;
  if (typeof c.contentScheduleAt !== 'string') c.contentScheduleAt = '';
  if (!c.studioMode) c.studioMode = 'quick';
  if (!c.audienceType) c.audienceType = 'b2c';
  if (typeof c.audienceSegment !== 'string') c.audienceSegment = '';
  if (!c.contentFormat) c.contentFormat = 'post';
  if (typeof c.forbiddenTopics !== 'string') c.forbiddenTopics = '';
  if (!c.rewriteStyle) c.rewriteStyle = 'короче';
  if (!c.previewPlatform) c.previewPlatform = 'facebook';
  if (!c.activeVariant) c.activeVariant = 1;
  if (!c.aiAssist || typeof c.aiAssist !== 'object') c.aiAssist = { loading: false, hook: '', angles: [], ctaVariants: [] };
  if (!c.quality || typeof c.quality !== 'object') c.quality = { score: 0, checks: [], warnings: [] };
  if (!Array.isArray(c.templates)) c.templates = [];
  if (typeof c.templatesLoaded !== 'boolean') c.templatesLoaded = false;
  if (!c.contentGeneration || typeof c.contentGeneration !== 'object') {
    c.contentGeneration = {
      loading: false,
      stage: 'idle',
      error: '',
      retryable: false,
      briefId: null,
      strategy: null,
      drafts: [],
      activePlatform: 'facebook',
    };
  }
  if (!c.contentGeneration.activePlatform) c.contentGeneration.activePlatform = 'facebook';
}

function syncCampaignKindsByMode() {
  const c = state.createCampaign;
  if (c.mode === 'image') {
    c.kinds.facebook = 'image_post';
    c.kinds.instagram = 'image_post';
    c.platforms.youtube = false;
  } else if (c.mode === 'video') {
    c.kinds.facebook = 'video';
    c.kinds.instagram = 'reel';
  } else {
    if (!['image_post', 'video'].includes(c.kinds.facebook)) c.kinds.facebook = 'image_post';
    if (!['image_post', 'reel'].includes(c.kinds.instagram)) c.kinds.instagram = 'image_post';
  }
  if (c.videoDuration <= 60 && c.videoAspectRatio === '9:16') c.kinds.youtube = 'shorts';
  if (c.videoDuration > 60 || c.videoAspectRatio !== '9:16') c.kinds.youtube = 'video';
}

function selectedCampaignPlatforms() {
  const c = state.createCampaign;
  return ['facebook', 'instagram', 'youtube'].filter((platform) => !!c.platforms?.[platform]);
}

async function ensureCampaignSaved() {
  hydrateCampaignDefaults();
  const c = state.createCampaign;
  const payload = {
    project_id: Number(c.projectId || state.projects?.[0]?.id || 0) || null,
    mode: c.mode || 'image',
    topic: String(c.topic || '').trim() || 'Новая кампания',
    offer: String(c.offer || '').trim(),
    objective: c.objective || 'sales',
    caption_master: String(c.caption || '').trim(),
    cta: String(c.cta || '').trim(),
    hashtags_master: Array.isArray(c.hashtags) ? c.hashtags : [],
    language: c.language || 'ru',
    status: 'draft',
  };
  if (!c.campaignId) {
    const created = await api('/api/campaigns', { method: 'POST', body: JSON.stringify(payload) });
    c.campaignId = created?.campaign?.id || null;
  } else {
    await api(`/api/campaigns/${c.campaignId}`, { method: 'PATCH', body: JSON.stringify(payload) });
  }
  c.dirty = false;
  saveCampaignDraftLocal();
  return c.campaignId;
}

async function loadCampaignDetails(campaignId) {
  if (!campaignId) return;
  const details = await api(`/api/campaigns/${campaignId}`);
  const c = state.createCampaign;
  c.assets = details?.assets || [];
  c.deliveries = details?.deliveries || [];
  state.campaignDetails = details;
  saveCampaignDraftLocal();
}

function directorQualityLocal({ caption, cta, hashtags, goal, platform }) {
  const text = String(caption || '').trim();
  const tags = Array.isArray(hashtags) ? hashtags.map((t) => String(t || '').trim()).filter(Boolean) : [];
  const g = String(goal || 'engagement').toLowerCase();
  const p = String(platform || 'facebook').toLowerCase();
  const firstLine = (text.split('\n')[0] || '').trim();
  const hasHook = text.length > 40 && (
    /[!?]/.test(text.slice(0, 180))
    || firstLine.length >= 24
    || /\d/.test(firstLine)
  );
  const paragraphs = text.split('\n').map((x) => x.trim()).filter(Boolean);
  const longParagraphs = paragraphs.filter((x) => x.length >= 40).length;
  const sentenceCount = (text.match(/[.!?](?:\s|$)/g) || []).length;
  const hasList = /(^|\n)\s*(?:[•\-]|\d+[.)])\s+/m.test(text);
  // Treat structure as valid for paragraph blocks, list format, or sufficiently detailed plain text.
  const hasStructure = (longParagraphs >= 2) || hasList || (text.length >= 180 && sentenceCount >= 3);
  const hasCta = String(cta || '').trim().length > 4 || /(напишите|оставьте|жмите|перейдите|подпишитесь|сохраните)/i.test(text);
  let tagsOk = true;
  if (p === 'instagram') tagsOk = tags.length >= 8 && tags.length <= 15;
  if (p === 'facebook') tagsOk = tags.length >= 1 && tags.length <= 8;
  if (p === 'youtube') tagsOk = tags.length >= 3 && tags.length <= 15;
  const hasOfferSignal = /(выгода|бонус|скидк|оффер|предложение|результат|прибыль|эконом)/i.test(text);
  const hasQuestion = /\?/.test(text);
  const hasEngageSignal = /(как вы|что думаете|поделитесь|напишите|обсудим|ваше мнение)/i.test(text);
  const goalMatch = (
    (g === 'sales' || g === 'lead')
      ? (hasOfferSignal || hasCta)
      : (g === 'engagement'
        ? (hasQuestion || hasEngageSignal || hasCta)
        : (g === 'awareness'
          ? text.length >= 160
          : true))
  );
  let score = 0;
  score += hasHook ? 20 : 0;
  score += hasStructure ? 20 : 0;
  score += hasCta ? 20 : 0;
  score += tagsOk ? 10 : 0;
  score += goalMatch ? 30 : 0;
  const checks = [
    { key: 'hook', label: 'Хук', state: hasHook ? 'green' : 'yellow' },
    { key: 'structure', label: 'Структура', state: hasStructure ? 'green' : 'yellow' },
    { key: 'cta', label: 'Призыв к действию', state: hasCta ? 'green' : 'red' },
    { key: 'hashtags', label: 'Хештеги', state: tagsOk ? 'green' : 'yellow' },
    { key: 'goal_match', label: 'Соответствие цели', state: goalMatch ? 'green' : 'yellow' },
  ];
  const warnings = [];
  if (!tagsOk) warnings.push('Проверьте количество хештегов под платформу.');
  if (!hasCta) warnings.push('Добавьте явный призыв к действию.');
  return { score, checks, warnings };
}

function directorVideoQualityLocal({ videoStructure, targetSeconds, orientation, cta, hashtags, realisticOnly, fixedSceneSeconds = 0 }) {
  const scenes = Array.isArray(videoStructure?.scenes) ? videoStructure.scenes : [];
  const target = Math.max(20, Math.min(480, Number(targetSeconds || 30) || 30));
  const fixedSlot = Math.max(0, Number(fixedSceneSeconds || 0) || 0);
  const sceneDurations = scenes.map((s) => {
    const raw = Number(s?.duration_s || s?.approx_duration_s || 0) || 0;
    if (raw > 0.01) return raw;
    if (fixedSlot > 0) return fixedSlot;
    return scenes.length ? (target / scenes.length) : 0;
  });
  const sumDuration = sceneDurations.reduce((acc, x) => acc + (Number(x || 0) || 0), 0);
  const timelineTolerance = Math.max(1.5, Math.min(4.0, target * 0.08));
  const coverageOk = scenes.length > 0 && Math.abs(sumDuration - target) <= timelineTolerance;
  const nonEmptyScenes = scenes.filter((s) => String(s?.text || '').trim().length >= 8).length;
  const minScenes = Math.max(3, Math.ceil(target / 12));
  const maxScenes = Math.max(minScenes + 2, Math.ceil(target / 2.5));
  const sceneCountOk = scenes.length >= minScenes && scenes.length <= maxScenes;
  const structureOk = sceneCountOk && nonEmptyScenes === scenes.length && scenes.length > 0;
  const longestSceneText = scenes.reduce((m, s) => Math.max(m, String(s?.text || '').trim().length), 0);
  const subtitleSafe = longestSceneText <= 85;
  const hasCta = String(cta || '').trim().length >= 6;
  const tags = Array.isArray(hashtags) ? hashtags.map((x) => String(x || '').trim()).filter(Boolean) : [];
  const tagsOk = tags.length >= 3 && tags.length <= 12;
  const durationByFormatOk = orientation === 'horizontal' ? (target >= 120 && target <= 480) : (target >= 20 && target <= 60);
  const realisticOk = !!realisticOnly;

  let score = 0;
  score += coverageOk ? 25 : 0;
  score += structureOk ? 25 : 0;
  score += subtitleSafe ? 20 : 0;
  score += hasCta ? 10 : 0;
  score += tagsOk ? 10 : 0;
  score += durationByFormatOk ? 5 : 0;
  score += realisticOk ? 5 : 0;

  const checks = [
    { key: 'timeline', label: 'Тайминг сцен', state: coverageOk ? 'green' : 'yellow' },
    { key: 'structure', label: 'Структура видео', state: structureOk ? 'green' : 'yellow' },
    { key: 'subtitles', label: 'Субтитры в кадре', state: subtitleSafe ? 'green' : 'yellow' },
    { key: 'cta', label: 'Призыв к действию', state: hasCta ? 'green' : 'red' },
    { key: 'hashtags', label: 'Хештеги', state: tagsOk ? 'green' : 'yellow' },
  ];
  const warnings = [];
  if (!coverageOk) warnings.push(`Сумма сцен ${sumDuration.toFixed(1)}с, а выбрано ${target}с. Нажмите «Обновить структуру».`);
  if (!sceneCountOk) warnings.push('Количество сцен не оптимально для выбранной длительности.');
  if (!subtitleSafe) warnings.push('Сделайте фразы короче, чтобы субтитры точно помещались в кадре.');
  if (!durationByFormatOk) warnings.push(orientation === 'horizontal' ? 'Для обычного видео используйте 120–480 сек.' : 'Для Shorts/Reels используйте 20–60 сек.');
  if (!hasCta) warnings.push('Добавьте чёткий призыв к действию.');
  if (!tagsOk) warnings.push('Рекомендуем 3–12 хештегов.');
  if (!realisticOk) warnings.push('Включите «Только реалистичные сцены» для стабильного качества.');
  return { score: Math.max(0, Math.min(100, Math.round(score))), checks, warnings };
}

function buildPreviewPayloadFromCreateCampaign(platform, kind) {
  const c = state.createCampaign || {};
  const assets = Array.isArray(c.assets) ? c.assets : [];
  const imageAsset = assets.filter((a) => a.type === 'image').slice(-1)[0] || null;
  const videoAsset = assets.filter((a) => a.type === 'video').slice(-1)[0] || null;
  const thumbAsset = assets.filter((a) => a.type === 'thumbnail').slice(-1)[0] || null;
  const p = String(platform || 'facebook').toLowerCase();
  const k = String(kind || (c.kinds?.[p] || 'image_post')).toLowerCase();
  const isVideo = ['video', 'reel', 'shorts'].includes(k);
  const media = isVideo
    ? {
      type: 'video',
      url: videoAsset?.storage_url || '',
      thumbnail_url: thumbAsset?.storage_url || null,
      width: Number(videoAsset?.width || 0) || null,
      height: Number(videoAsset?.height || 0) || null,
      duration_s: Number(videoAsset?.duration_sec || c.videoDuration || 0) || null,
    }
    : {
      type: 'image',
      url: imageAsset?.storage_url || '',
      thumbnail_url: null,
      width: Number(imageAsset?.width || 0) || null,
      height: Number(imageAsset?.height || 0) || null,
      duration_s: null,
    };
  return {
    platform: p,
    content_type: isVideo ? 'video_post' : 'image_post',
    caption: String(c.caption || '').trim(),
    cta: String(c.cta || '').trim() || null,
    hashtags: Array.isArray(c.hashtags) ? c.hashtags : [],
    media,
    meta: {
      page_name: (state.connections || []).find((x) => !!x.page_name)?.page_name || null,
      account_name: p === 'youtube'
        ? (state.youtubeConnection?.channel_title || state.youtubeConnection?.channel_name || null)
        : (p === 'instagram'
          ? ((state.connections || []).find((x) => !!x.instagram_username)?.instagram_username || null)
          : ((state.connections || []).find((x) => !!x.page_name)?.page_name || null)),
      scheduled_at: c.publishMode === 'schedule' ? localInputToIsoNoTz(c.scheduledAt || '') : null,
      goal: String(c.contentGoal || 'engagement'),
      format_hint: k,
      title: p === 'youtube' ? String((c.caption || '').split('\n')[0] || c.topic || '').slice(0, 100) : null,
      description: p === 'youtube' ? String(c.caption || '') : null,
      tags: Array.isArray(c.hashtags) ? c.hashtags : [],
    },
  };
}

function validatePreviewLocal(payload) {
  const p = payload || {};
  const platform = String(p.platform || 'facebook').toLowerCase();
  const contentType = String(p.content_type || 'image_post').toLowerCase();
  const caption = String(p.caption || '').trim();
  const cta = String(p.cta || '').trim();
  const hashtags = Array.isArray(p.hashtags) ? p.hashtags : [];
  const media = p.media || {};
  const meta = p.meta || {};
  const warnings = [];
  const suggestions = [];
  const errors = [];
  const mediaType = String(media.type || 'image').toLowerCase();
  const mediaUrl = String(media.url || '').trim();
  const duration = Number(media.duration_s || 0) || 0;
  const width = Number(media.width || 0) || 0;
  const height = Number(media.height || 0) || 0;
  const ratio = width > 0 && height > 0 ? (width / height) : null;
  const goal = String(meta.goal || 'engagement').toLowerCase();
  const formatHint = String(meta.format_hint || '').toLowerCase();

  if (!mediaUrl) errors.push({ level: 'error', code: 'media_missing', message: 'Нет медиа для публикации.' });
  if (!caption) warnings.push({ level: 'warning', code: 'caption_empty', message: 'Текст публикации пустой.' });
  if (['sales', 'lead', 'leads'].includes(goal) && !cta) warnings.push({ level: 'warning', code: 'cta_missing', message: 'Добавьте CTA для этой цели.' });
  if (platform === 'instagram' && (hashtags.length < 5 || hashtags.length > 20)) warnings.push({ level: 'warning', code: 'ig_hashtags', message: 'Instagram: рекомендуем 5-20 хештегов.' });
  if (platform === 'facebook' && hashtags.length > 8) warnings.push({ level: 'warning', code: 'fb_hashtags', message: 'Facebook: рекомендуем до 8 хештегов.' });
  if (platform === 'youtube' && hashtags.length < 5) warnings.push({ level: 'warning', code: 'yt_tags', message: 'YouTube: добавьте минимум 5 тегов.' });
  if (platform === 'instagram' && caption.length > 2200) warnings.push({ level: 'warning', code: 'ig_len', message: 'Слишком длинный текст для Instagram (>2200).' });
  if (platform === 'facebook' && caption.length > 5000) warnings.push({ level: 'warning', code: 'fb_len', message: 'Слишком длинный текст для Facebook (>5000).' });
  if (platform === 'youtube' && String(meta.description || caption || '').length < 200) warnings.push({ level: 'warning', code: 'yt_desc_short', message: 'Описание YouTube слишком короткое (<200).' });
  if (platform === 'youtube' && contentType !== 'video_post') errors.push({ level: 'error', code: 'platform_mismatch', message: 'YouTube требует video_post.' });
  if (contentType === 'video_post' && mediaType !== 'video') errors.push({ level: 'error', code: 'video_required', message: 'Выбран видео-пост, но медиа не видео.' });
  const shortMode = ['reel', 'shorts'].includes(formatHint) || (platform === 'instagram' && contentType === 'video_post');
  if (shortMode && duration > 60) warnings.push({ level: 'warning', code: 'short_duration', message: 'Для Reels/Shorts рекомендуется до 60 секунд.' });
  if (duration > 480) warnings.push({ level: 'warning', code: 'duration_480', message: 'Видео длиннее 480 секунд.' });
  if (shortMode && ratio !== null && Math.abs(ratio - (9 / 16)) > 0.22) warnings.push({ level: 'warning', code: 'ratio_916', message: 'Для Reels/Shorts лучше формат 9:16.' });
  if (warnings.some((x) => x.code === 'ig_len' || x.code === 'fb_len')) suggestions.push('Сократить текст');
  if (warnings.some((x) => x.code.includes('hashtags') || x.code === 'yt_tags')) suggestions.push('Добавить/нормализовать хештеги');
  if (warnings.some((x) => x.code === 'cta_missing')) suggestions.push('Сгенерировать призыв');

  let score = 100;
  score -= Math.min(60, errors.length * 25);
  score -= Math.min(45, warnings.length * 8);
  score = Math.max(0, Math.round(score));
  return { score, warnings: [...errors, ...warnings], suggestions, hasError: errors.length > 0 };
}

function renderSocialPreview(payload) {
  const p = payload || {};
  const platform = String(p.platform || 'facebook').toLowerCase();
  const media = p.media || {};
  const isVideo = String(media.type || '').toLowerCase() === 'video';
  const caption = String(p.caption || '').trim();
  const maxChars = platform === 'instagram' ? 220 : (platform === 'facebook' ? 300 : 320);
  const shortCaption = caption.length > maxChars ? `${caption.slice(0, maxChars)}... ещё` : caption;
  const name = p.meta?.account_name || p.meta?.page_name || (platform === 'youtube' ? 'YouTube канал' : 'Ваш аккаунт');
  const tags = Array.isArray(p.hashtags) ? p.hashtags : [];
  const cta = String(p.cta || '').trim();
  const mediaHtml = isVideo
    ? `<div class="social-preview-media video">
        ${media.thumbnail_url ? `<img src="${esc(media.thumbnail_url)}" alt="" />` : `<video src="${esc(media.url || '')}" preload="metadata"></video>`}
        <span class="play-badge">?</span>
        ${media.duration_s ? `<span class="duration-badge">${esc(String(Math.round(media.duration_s)))}s</span>` : ''}
      </div>`
    : `<div class="social-preview-media image">${media.url ? `<img src="${esc(media.url)}" alt="" />` : '<div class="media-missing">Нет изображения</div>'}</div>`;
  const actions = platform === 'youtube'
    ? '<div class="social-actions"><span>?? Нравится</span><span>?? Комментарии</span><span>?? Подписка</span></div>'
    : '<div class="social-actions"><span>Нравится</span><span>Комментарий</span><span>Поделиться</span></div>';
  const titleLine = platform === 'youtube'
    ? `<p class="small"><strong>${esc(p.meta?.title || 'Заголовок видео')}</strong></p>`
    : '';
  return `
    <article class="card social-preview-card glass-card">
      <div class="social-header"><div class="avatar"></div><div><strong>${esc(name)}</strong><p class="small">${platform === 'instagram' ? 'Instagram' : (platform === 'youtube' ? 'YouTube' : 'Facebook')}</p></div></div>
      ${titleLine}
      <p class="social-caption">${esc(shortCaption || 'Текст публикации')}</p>
      ${mediaHtml}
      <div class="social-tags">${tags.map((h) => `<span class="pill">${esc(h)}</span>`).join('')}</div>
      <button class="btn btn-secondary" type="button" ${cta ? '' : 'disabled'}>${esc(cta || 'Призыв')}</button>
      ${actions}
    </article>
  `;
}

function pageCreateDirector() {
  const d = state.createDirector || {};
  const generationMode = String(d.generationMode || 'manual').trim() === 'plan' ? 'plan' : 'manual';
  if (!d._contentTypeBootstrapped) {
    let localType = '';
    let queryType = '';
    try { localType = String(localStorage.getItem(CREATE_DIRECTOR_TYPE_KEY) || '').trim(); } catch {}
    try { queryType = String(new URLSearchParams(window.location.search).get('type') || '').trim(); } catch {}
    d.contentType = normalizeDirectorContentType(queryType || localType || d.contentType || 'post');
    d._contentTypeBootstrapped = true;
  }
  const contentType = normalizeDirectorContentType(d.contentType || 'post');
  const isVideo = contentType === 'video';
  const loading = !!d.loadingSuggest || !!d.loadingDrafts;
  const platforms = d.platforms || { facebook: true, instagram: true, youtube: false };
  if (isVideo) {
    platforms.facebook = true;
    platforms.instagram = true;
    platforms.youtube = true;
    d.platforms = platforms;
  }
  const platformOrder = isVideo ? ['facebook', 'instagram', 'youtube'] : ['facebook', 'instagram'];
  const selectedPlatforms = platformOrder.filter((k) => !!platforms[k]);
  const topics = (d.suggestions?.topics || []).slice(0, DIRECTOR_TOPIC_IDEA_COUNT);
  const localTopics = directorLocalTopicIdeas(d, DIRECTOR_TOPIC_IDEA_COUNT, d.refreshCount || 0);
  const topicsAll = Array.isArray(d.topicPool) && d.topicPool.length
    ? d.topicPool.slice(0, DIRECTOR_TOPIC_IDEA_COUNT)
    : (localTopics.length ? localTopics : topics);
  const topicHeadlineItems = directorHeadlineItems(topicsAll, d.selectedAngle);
  const baseTopic = directorBaseTopic(d, d.topic);
  const effectiveSelectedTopic = directorEffectiveTopic(d);
  const nicheMeta = directorCurrentNicheMeta(d);
  const quickActionResult = String(d.quickActionType || '').trim() && String(d.quickActionNicheId || '').trim()
    ? buildQuickActionResult(d.quickActionType, d.quickActionNicheId, state.billing, Number(d.quickActionSeed || 0))
    : null;
  const quickActionType = String(quickActionResult?.actionType || '').trim();
  const isWeeklyPlanFlow = quickActionType === 'weekly_plan';
  const isMonthlyPlanFlow = quickActionType === 'monthly_plan';
  const isPlanFlow = isWeeklyPlanFlow || isMonthlyPlanFlow;
  const prioritizeDirectorCard = isPlanFlow;
  const planFlowGenerated = isPlanFlow && d.planFlowState === 'generated';
  const planFlowLoading = isPlanFlow && d.planFlowState === 'loading';
  const planFlowError = isPlanFlow ? String(d.planFlowError || '').trim() : '';
  const planFlowDays = isMonthlyPlanFlow ? 30 : 7;
  const planFlowGoalLabel = planGoalLabel(d.goal || 'engagement');
  const angles = ((d.suggestions?.angles || []).slice(0, 3).length ? (d.suggestions?.angles || []).slice(0, 3) : directorLocalAngles(d).slice(0, 3));
  const ctaOptions = (d.suggestions?.cta_options || []).slice(0, 3);
  const hashtagSets = Array.isArray(d.suggestions?.hashtag_sets)
    ? d.suggestions.hashtag_sets.slice(0, 6).map((set) => normalizeHashtagSet(set))
    : [];
  const activePlatform = String(d.activePlatform || selectedPlatforms[0] || 'facebook');
  const draftsAll = Array.isArray(d.drafts) ? d.drafts : [];
  const draftsForPlatform = draftsAll.filter((x) => String(x.platform || '').toLowerCase() === activePlatform);
  const variantTabs = draftsForPlatform.map((x) => Number(x.variant_index || x.variant || 1));
  const activeVariant = Number(d.activeVariant || variantTabs[0] || 1);
  const activeDraft = draftsForPlatform.find((x) => Number(x.variant_index || x.variant || 1) === activeVariant) || draftsForPlatform[0] || null;
  const hasSelection = effectiveSelectedTopic && String(d.selectedAngle || '').trim();
  const draftMatchesSelection = !!activeDraft
    && String(d.lastDraftTopic || '').trim() === effectiveSelectedTopic
    && String(d.lastDraftAngle || '').trim() === String(d.selectedAngle || '').trim();
  const selectedThemePreviewText = [
    String(effectiveSelectedTopic || baseTopic || '').trim() ? `Тема: ${String(effectiveSelectedTopic || baseTopic || '').trim()}` : '',
    String(d.selectedAngle || '').trim() ? `Подход: ${String(d.selectedAngle || '').trim()}` : '',
    'Готовим текст под выбранную тему…',
  ].filter(Boolean).join('\n');
  const videoPreviewTextState = isVideo ? getVideoPreviewTextState(d, activePlatform) : null;
  const previewText = isVideo
    ? (videoPreviewTextState?.text || 'Сначала сгенерируйте структуру, затем соберите видео.')
    : resolveDirectorPostPreviewText({
      draft: activeDraft,
      draftMatchesSelection,
      loadingDrafts: d.loadingDrafts,
      selectedThemePreviewText,
      hasSelection,
    });
  const selectedTagSet = Array.isArray(d.selectedHashtags) ? directorPreferNicheHashtags(d, d.selectedHashtags, 8) : [];
  const hasVideoStructure = !!d.videoStructure;
  const previewTags = isVideo
    ? selectedTagSet
    : (selectedTagSet.length
      ? selectedTagSet
      : directorPreferNicheHashtags(d, Array.isArray(activeDraft?.hashtags) ? activeDraft.hashtags : [], 8));
  const activeTagsValue = isVideo
    ? selectedTagSet.join(' ')
    : (selectedTagSet.length
      ? selectedTagSet.join(' ')
      : directorPreferNicheHashtags(d, activeDraft?.hashtags || [], 8).join(' '));
  const videoPreviewUrl = String(d.videoPreviewUrl || '').trim();
  const videoFinalUrl = String(d.videoFinalUrl || '').trim();
  const videoPlayableUrl = videoFinalUrl || videoPreviewUrl;
  const videoSrtUrl = String(d.videoSrtUrl || '').trim();
  const videoDebug = (d.videoDebug && typeof d.videoDebug === 'object') ? d.videoDebug : {};
  const uniqueClipsUsed = Array.isArray(videoDebug.unique_clips_used) ? videoDebug.unique_clips_used : [];
  const videoOrientation = String(d.videoOrientation || 'vertical').toLowerCase() === 'horizontal' ? 'horizontal' : 'vertical';
  const videoFrameClass = videoOrientation === 'horizontal' ? 'is-horizontal' : 'is-vertical';
  const videoProgress = Math.max(0, Math.min(100, Number(d.videoProgress || 0)));
  const videoStep = String(d.videoStep || 'queued').trim().toLowerCase() || 'queued';
  const videoStepLabelMap = {
    structure: 'Структура',
    footage: 'Футажи',
    render: 'Рендер',
    export: 'Экспорт',
    upload: 'Загрузка',
    queued: 'Очередь',
  };
  const videoStepLabel = videoStepLabelMap[videoStep] || 'Обработка';
  const videoStepPills = ['structure', 'footage', 'render', 'export', 'upload']
    .map((stepKey, idx) => {
      const currentIdx = ['structure', 'footage', 'render', 'export', 'upload'].indexOf(videoStep);
      const done = currentIdx > idx || (videoProgress >= 100 && idx < 5);
      const active = currentIdx === idx && videoProgress < 100;
      const cls = `pill ${done ? 'done' : (active ? 'active' : '')}`;
      return `<span class="${cls}" data-cd-video-step="${esc(stepKey)}">${esc(videoStepLabelMap[stepKey])}</span>`;
    })
    .join('');
  const quality = d.quality || { score: 0, checks: [], warnings: [] };
  const debugWarnMap = {
    network_fallback: 'Сеть нестабильна: показаны локальные варианты, можно редактировать и публиковать.',
  };
  const warningsReadable = (() => {
    const src = Array.isArray(d.warnings) ? d.warnings : [];
    const out = [];
    const seen = new Set();
    for (const w of src) {
      const key = String(w || '').trim();
      if (!key) continue;
      const mapped = debugWarnMap[key];
      if (mapped) {
        if (!seen.has(mapped)) { out.push(mapped); seen.add(mapped); }
        continue;
      }
    }
    return out.slice(0, 2);
  })();
  const planItems = Array.isArray(d.planItems) ? d.planItems : [];
  const planRows = planItems.length
    ? `<div class="table-wrap" style="margin-top:10px;"><table><thead><tr><th>Дата</th><th>Тема</th><th>Статус</th></tr></thead><tbody>
      ${planItems.map((x) => `<tr><td>${esc(new Date(x.scheduled_at).toLocaleString('ru-RU'))}</td><td>${esc(x.topic || '—')}</td><td>${esc(x.status || 'planned')}</td></tr>`).join('')}
    </tbody></table></div>`
    : '<p class="small">План пока не сформирован.</p>';
  const bestSlots = d.bestSlots || null;
  const bestDaysText = Array.isArray(bestSlots?.best_days) ? bestSlots.best_days.map((x) => x.label).join(', ') : '';
  const bestHoursText = Array.isArray(bestSlots?.best_hours) ? bestSlots.best_hours.map((h) => `${h}:00`).join(', ') : '';
  const nextSlotPills = Array.isArray(bestSlots?.next_slots)
    ? bestSlots.next_slots.slice(0, 4).map((iso) => `<button type="button" class="btn btn-ghost" data-cd-slot="${esc(iso)}">${esc(new Date(iso).toLocaleString('ru-RU', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }))}</button>`).join('')
    : '';
  const miniPlanRows = planItems.slice(0, 6).map((x) => `<div class="small" style="display:flex;justify-content:space-between;gap:8px;"><span>${esc(new Date(x.scheduled_at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }))}</span><span class="truncate">${esc(x.topic || '—')}</span></div>`).join('');
  const quickPlanItems = isPlanFlow
    ? ((Array.isArray(d.planFlowItems) && d.planFlowItems.length)
      ? d.planFlowItems
      : (Array.isArray(quickActionResult?.items) ? quickActionResult.items : []))
    : [];
  const selectedPlanDay = isPlanFlow
    ? (quickPlanItems.find((item) => Number(item.day || 0) === Number(d.planFlowSelectedDay || 1)) || quickPlanItems[0] || null)
    : null;
  const isHorizontalVideo = String(d.videoOrientation || 'vertical') === 'horizontal';
  const durationOptions = (isHorizontalVideo ? ['120', '180', '240', '300', '360', '420', '480'] : ['20', '30', '40', '60']).map((v) => ({ value: v, label: `${v} сек` }));
  const previewStateText = [
    String(effectiveSelectedTopic || baseTopic || '').trim() ? `Тема: ${String(effectiveSelectedTopic || baseTopic || '').trim()}` : '',
    String(d.selectedAngle || '').trim() ? `Подход: ${String(d.selectedAngle || '').trim()}` : '',
  ].filter(Boolean).join(' · ') || (isVideo ? 'Соберите структуру, чтобы увидеть preview.' : 'Выберите тему и угол подачи, чтобы увидеть preview.');
  const planTitle = String(state.billing?.plan_title || planBadge(state.billing?.plan || state.user?.plan || 'free').replace(/<[^>]+>/g, '') || '\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0430\u0440\u0438\u0444').trim();
  const planPostsRemaining = Math.max(0, Number(state.billing?.remaining?.posts_generated ?? ((state.billing?.limits?.posts_per_month || 0) - (state.billing?.usage?.posts_per_month || 0))));
  const planVideosRemaining = Math.max(0, Number(state.billing?.remaining?.videos_generated ?? ((state.billing?.limits?.videos_per_month || 0) - (state.billing?.usage?.videos_per_month || 0))));
  const planChannelsRemaining = Number(state.billing?.limits?.accounts_connected || 0) >= 999999
    ? '\u0431\u0435\u0437 \u043b\u0438\u043c\u0438\u0442\u0430'
    : String(Math.max(0, Number(state.billing?.remaining?.accounts_connected ?? ((state.billing?.limits?.accounts_connected || 0) - (state.billing?.usage?.accounts_connected || 0)))));
  const planAwareBlock = `
      <article class="card" style="margin-top:10px;padding:12px;">
        <div class="small" style="margin-bottom:8px;font-weight:700;">\u0420\u0435\u0436\u0438\u043c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438</div>
        <div class="row" style="gap:8px;flex-wrap:wrap;">
          <button id="cdGenerationModeManual" type="button" class="btn ${generationMode === 'manual' ? 'btn-primary' : 'btn-ghost'}">\u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u0432\u0440\u0443\u0447\u043d\u0443\u044e</button>
          <button id="cdGenerationModePlan" type="button" class="btn ${generationMode === 'plan' ? 'btn-primary' : 'btn-ghost'}">\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u043b\u0438\u043c\u0438\u0442\u044b \u043c\u043e\u0435\u0433\u043e \u043f\u043b\u0430\u043d\u0430</button>
        </div>
        ${generationMode === 'plan'
          ? `<div style="margin-top:10px;">
               <p class="small" style="margin:0 0 10px 0;">\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0443\u0434\u0435\u0442 \u0443\u0447\u0438\u0442\u044b\u0432\u0430\u0442\u044c \u0432\u0430\u0448 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0430\u0440\u0438\u0444, \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438 \u0438 \u0432\u0438\u0434\u0435\u043e \u0432 \u044d\u0442\u043e\u043c \u043f\u0435\u0440\u0438\u043e\u0434\u0435.</p>
               <div class="small"><strong>\u0412\u0430\u0448 \u0442\u0430\u0440\u0438\u0444:</strong> ${esc(planTitle)}</div>
               <div class="small" style="margin-top:8px;"><strong>\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0441\u0435\u0439\u0447\u0430\u0441:</strong></div>
               <ul class="small" style="margin:8px 0 0 18px;padding:0;">
                 <li>${esc(String(planPostsRemaining))} \u043f\u043e\u0441\u0442\u043e\u0432</li>
                 <li>${esc(String(planVideosRemaining))} \u0432\u0438\u0434\u0435\u043e</li>
                 <li>${esc(String(planChannelsRemaining))} \u043a\u0430\u043d\u0430\u043b\u043e\u0432</li>
               </ul>
              </div>`
          : '<p class="small" style="margin:10px 0 0 0;">\u0412\u044b \u0441\u0430\u043c\u0438 \u0443\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442\u0435 \u043e\u0431\u044a\u0451\u043c\u043e\u043c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438, \u043f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u0430\u043c\u0438 \u0438 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u044f\u043c\u0438 \u0431\u0435\u0437 \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438 \u043f\u043e \u043b\u0438\u043c\u0438\u0442\u0430\u043c \u0442\u0430\u0440\u0438\u0444\u0430.</p>'}
      </article>`;

  const topicChooserHtml = `
      <div class="create-topic-picker">
        <div class="row create-topic-toolbar" style="margin-bottom:10px;">
          <button id="cdGenerateIdeas" class="btn btn-secondary" type="button" ${(loading || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
            ${directorIdeasButtonLabel(d, loading)}
          </button>
          <span class="small">Кнопка работает от текущей ниши или вашей темы.</span>
        </div>
        ${topicHeadlineItems.length ? `<div class="create-assist-list create-topic-list" style="margin-bottom:10px;">
          ${topicHeadlineItems.map((item) => `<button type="button" class="btn ${(String(d.selectedSuggestedTopic || '').trim() === item.title && !String(d.appliedManualTopic || '').trim()) ? 'btn-primary' : 'btn-ghost'}" data-cd-topic="${encodeURIComponent(item.title)}" title="Использовать эту тему">${esc(item.title)}</button>`).join('')}
        </div>
        ` : ''}
        <div class="create-topic-manual">
          ${field('cdManualTopic', 'Своя тема', 'text', d.manualTopicInput || '', 'Не нашли нужный вариант? Введите тему вручную')}
          <div class="row" style="gap:8px;flex-wrap:wrap;">
            <button id="cdApplyManualTopic" class="btn btn-ghost" type="button" ${String(d.manualTopicInput || '').trim() ? '' : 'disabled'}>Использовать эту тему</button>
            ${effectiveSelectedTopic ? `<span class="pill active">Выбрано: ${esc(effectiveSelectedTopic)}</span>` : '<span class="small">Тема пока не выбрана</span>'}
          </div>
        </div>
      </div>
  `;
  const quickActionItemsHtml = (() => {
    if (!quickActionResult) return '';
    if (quickActionResult.actionType === 'hooks_pack') {
      return quickActionResult.items.map((item) => `<article class="dash-quick-result-card">
        <div class="small">Hook ${Number(item.index || 0)}</div>
        <strong>${esc(item.hook || '—')}</strong>
        <button type="button" class="btn btn-ghost" data-cd-quick-hook="${encodeURIComponent(String(item.hook || ''))}">Использовать как тему</button>
      </article>`).join('');
    }
    if (quickActionResult.actionType === 'cta_pack') {
      return quickActionResult.items.map((item) => `<article class="dash-quick-result-card">
        <div class="small">CTA ${Number(item.index || 0)}</div>
        <strong>${esc(item.cta || '—')}</strong>
        <button type="button" class="btn btn-ghost" data-cd-quick-cta="${encodeURIComponent(String(item.cta || ''))}">Использовать CTA</button>
      </article>`).join('');
    }
    return quickActionResult.items.map((item) => `<article class="dash-quick-result-card">
      <div class="row" style="justify-content:space-between;gap:8px;align-items:flex-start;">
        <div class="small">${quickActionResult.actionType === 'monthly_plan' || quickActionResult.actionType === 'weekly_plan' ? `День ${Number(item.day || 0)}` : `Элемент ${Number(item.seriesIndex || item.day || 0)}`}</div>
        <span class="pill">${esc(item.contentFormat || item.objective || 'план')}</span>
      </div>
      <strong>${esc(item.topic || '—')}</strong>
      <p class="small">${esc(item.angle || '—')}</p>
      <p class="small" style="margin:0 0 8px 0;"><strong>CTA:</strong> ${esc(item.cta || '—')}</p>
      <button type="button" class="btn btn-ghost" data-cd-quick-topic="${encodeURIComponent(String(item.topic || ''))}" data-cd-quick-angle="${encodeURIComponent(String(item.angle || ''))}" data-cd-quick-cta="${encodeURIComponent(String(item.cta || ''))}" data-cd-quick-type="${esc(item.contentType || 'post')}">Использовать в директоре</button>
    </article>`).join('');
  })();
  const quickActionPanel = quickActionResult ? `
    <article class="card glass-card create-director-card dash-quick-result-shell">
      <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div style="max-width:760px;">
          <div class="create-step-label">Быстрый старт</div>
          <h3 style="margin:0 0 8px 0;">${esc(quickActionResult.title)} · ${esc(quickActionResult.nicheLabel || nicheMeta?.label || '—')}</h3>
          <p class="small" style="margin:0;">${esc(quickActionResult.subtitle)}</p>
          ${quickActionResult.access.isPreview ? '<p class="small" style="margin:8px 0 0 0;"><strong>Preview:</strong> полный объём доступен после апгрейда тарифа.</p>' : ''}
        </div>
        <div class="cta-row">
          <button id="cdQuickActionRefresh" class="btn btn-secondary" type="button">Обновить подборку</button>
          ${quickActionResult.access.isPreview ? '<button class="btn btn-ghost" type="button" data-link="/billing">Обновить тариф</button>' : ''}
        </div>
      </div>
      <div class="dash-quick-results-grid" style="margin-top:14px;">${quickActionItemsHtml}</div>
    </article>
  ` : '';

  const quickCard = `
    <article class="card glass-card create-director-card">
      <div class="row" style="justify-content:space-between;align-items:center;gap:10px;">
        <h2 style="margin:0;">AI Контент-директор</h2>
        <div class="row" style="gap:8px;">
          <div class="create-segmented-control" role="tablist" aria-label="Тип контента">
            <button id="cdTypePost" class="btn segment-btn ${!isVideo ? 'btn-primary' : 'btn-ghost'}" type="button" aria-pressed="${!isVideo ? 'true' : 'false'}">Пост</button>
            <button id="cdTypeVideo" class="btn segment-btn ${isVideo ? 'btn-primary' : 'btn-ghost'}" type="button" aria-pressed="${isVideo ? 'true' : 'false'}">Видео</button>
          </div>
        </div>
      </div>
      <p class="small" style="margin:0 0 8px 0;">Выберите сферу бизнеса, чтобы AI предложил релевантные идеи, формулировки и шаблоны именно под вашу нишу.</p>
      ${selectField('cdTopicPreset', 'Ниша *', d.topicPreset || DEFAULT_DIRECTOR_NICHE, DIRECTOR_NICHE_OPTIONS)}
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
      ${d.customTopicMode ? field('cdTopic', 'Своя ниша/тема', 'text', d.customBaseTopicInput || '', 'Например: контент-маркетинг для стоматологии') : ''}
      <p class="small create-selected-topic">Выбранная тема: <strong>${esc(effectiveSelectedTopic || '—')}</strong></p>
      <div class="grid-2">
        ${selectField('cdGoal', 'Цель *', d.goal || 'engagement', [{ value: 'awareness', label: 'Охват' }, { value: 'engagement', label: 'Вовлечение' }, { value: 'lead', label: 'Лиды' }, { value: 'sales', label: 'Продажи' }])}
        ${field('cdOffer', 'Оффер (опционально)', 'text', d.offer || '', 'Например: бесплатный аудит за 15 минут')}
      </div>
      ${selectField('cdLang', 'Язык', d.language || 'ru', CONTENT_LANG_OPTIONS)}
      ${!isVideo ? `<div class="row" style="gap:10px;flex-wrap:wrap;margin:8px 0 0 0;">
        <label class="create-toggle"><input id="cdImageEnabled" type="checkbox" ${d.imageEnabled ? 'checked' : ''}/> С картинкой</label>
        <span class="small">Если не отмечено, пост генерируется без картинки.</span>
      </div>` : ''}
      ${planAwareBlock}

      <details class="create-pro-accordion">
        <summary>Расширенные настройки</summary>
        ${isVideo
          ? `<article class="card" style="margin-top:10px;padding:10px;">
              <h4 style="margin:0 0 8px 0;">Настройки видео</h4>
              <div class="grid-2">
                ${selectField('cdVideoOrientation', 'Формат', d.videoOrientation || 'vertical', [{ value: 'vertical', label: 'Shorts/Reels (9:16)' }, { value: 'horizontal', label: 'Обычное видео (16:9, до 8 минут)' }])}
                ${selectField('cdVideoDurationPreset', 'Длительность', d.videoDurationPreset || '30', durationOptions)}
                ${selectField('cdVideoShotSeconds', 'Длительность сцены', String(Math.max(2, Math.min(12, Number(d.videoShotSeconds || 4) || 4))), [{ value: '2', label: '2 сек' }, { value: '3', label: '3 сек' }, { value: '4', label: '4 сек' }, { value: '5', label: '5 сек' }, { value: '6', label: '6 сек' }, { value: '7', label: '7 сек' }, { value: '8', label: '8 сек' }, { value: '10', label: '10 сек' }, { value: '12', label: '12 сек' }])}
                ${selectField('cdVideoVoiceGender', 'Голос', d.videoVoiceGender || 'male', [{ value: 'male', label: 'Мужской' }, { value: 'female', label: 'Женский' }])}
                ${selectField('cdVideoVoiceTone', 'Интонация', d.videoVoiceTone || 'neutral', [{ value: 'calm', label: 'Спокойная' }, { value: 'neutral', label: 'Нейтральная' }, { value: 'live', label: 'Живая' }])}
              </div>
              <p class="small" style="margin:6px 0 8px 0;">Лимит сервера: до 8 минут (480 сек) для обычного видео.</p>
              <label class="create-toggle"><input id="cdVideoSceneEvery4" type="checkbox" ${d.videoSceneEvery4 !== false ? 'checked' : ''}/> Фиксированная длительность сцены</label>
              <label class="create-toggle"><input id="cdVideoMinimizeRepeats" type="checkbox" ${d.videoMinimizeRepeats !== false ? 'checked' : ''}/> Минимизировать повторы</label>
              <label class="create-toggle"><input id="cdVideoRealisticOnly" type="checkbox" ${d.videoRealisticOnly !== false ? 'checked' : ''}/> Только реалистичные сцены</label>
            </article>`
          : `<article class="card" style="margin-top:10px;padding:10px;">
              <h4 style="margin:0 0 8px 0;">Настройки поста</h4>
              <div class="grid-2">
                ${field('cdAudience', 'Сегмент аудитории', 'text', d.audienceSegment || '', 'Например: владельцы малого бизнеса')}
                ${selectField('cdTone', 'Тон', d.tone || 'friendly', [{ value: 'friendly', label: 'Дружелюбный' }, { value: 'expert', label: 'Экспертный' }, { value: 'sales', label: 'Продающий' }, { value: 'neutral', label: 'Нейтральный' }])}
                ${selectField('cdLength', 'Длина', d.length || 'medium', [{ value: 'short', label: 'Коротко' }, { value: 'medium', label: 'Средне' }, { value: 'long', label: 'Длинно' }])}
                ${selectField('cdStyle', 'Стиль', d.style || 'short', [{ value: 'short', label: 'Short' }, { value: 'long', label: 'Long' }])}
              </div>
              ${field('cdRules', 'Запреты/бренд-правила', 'textarea', d.brandRules || '', 'Например: без черного юмора, без сравнения с конкурентами')}
            </article>`}
      </details>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        <button id="cdGenerateSelected" class="btn btn-primary" type="button" ${(loading || !String(baseTopic || '').trim()) ? 'disabled' : ''}>${directorIdeasButtonLabel(d, loading)}</button>
        ${isVideo ? `<button id="cdRenderVideo" class="btn btn-secondary" type="button" ${(loading || d.videoRenderLoading || !d.videoStructure) ? 'disabled' : ''}>${d.videoRenderLoading ? 'Собираем видео…' : 'Собрать видео'}</button>` : ''}
      </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
      ${isVideo ? `<div class="create-step-label">Шаг 4 — Видео</div>` : ''}
      ${isVideo ? `<p id="cdVideoStatusText" class="small">${esc(d.videoJobStatus ? `Статус видео: ${d.videoJobStatus}` : 'Статус видео: ожидание')}</p>` : ''}
      ${d.status === 'loading' ? '<div class="create-skeleton-lines"><span></span><span></span><span></span></div>' : ''}
      ${warningsReadable.length ? `<p class="small">${warningsReadable.map((w) => esc(w)).join(' · ')}</p>` : ''}
    </article>
  `;

  let resultCard = `
    <article class="card glass-card create-director-card">
      <h3 style="margin-top:0;">Результат</h3>
      <p class="small">Сначала получите заголовки, затем выберите тему. Дальше AI сразу соберёт результат в превью.</p>
      <article class="card" style="margin:8px 0 12px 0;padding:10px;">
        <label style="margin:0;font-weight:700;">Заголовки</label>
        <p class="small" style="margin:6px 0 8px 0;">Подберите темы под выбранную нишу и используйте нужный вариант для генерации.</p>
        ${topicChooserHtml}
      </article>
      ${isVideo ? `<article class="card" style="margin:8px 0 12px 0;padding:10px;">
        <h4 style="margin:0 0 8px 0;">Структура видео</h4>
        ${d.videoStructureLoading ? '<p class="small">AI формирует структуру...</p>' : ''}
        ${d.videoStructure ? `<p class="small"><strong>${esc(d.videoStructure.title || effectiveSelectedTopic || baseTopic || 'Видео')}</strong> · ${esc(String(d.videoDurationPreset || '30'))} сек</p>
          <p class="small">Озвучка: мужской голос Eddy · Субтитры: включены · Фоновая музыка: тихая</p>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
            ${(Array.isArray(d.videoStructure.scenes) ? d.videoStructure.scenes : []).map((s) => `<div class="small"><strong>${Number(s.index || 0) + 1}.</strong> ${esc(s.text || '')} <span style="opacity:.75;">(~${Number(s.duration_s || 0).toFixed(1)} c)</span></div>`).join('')}
          </div>` : '<p class="small">Нажмите «Сгенерировать структуру», чтобы получить план сцен под выбранную длительность.</p>'}
      </article>` : ''}
      <article class="card" style="margin-top:10px;padding:10px;">
        <label style="margin:0;font-weight:700;">Подходы</label>
        <p class="small" style="margin:6px 0 8px 0;">Выберите угол подачи, который лучше всего подходит для этого поста или видео.</p>
        <div class="row create-result-toolbar">
          <button id="cdRefreshApproaches" type="button" class="btn btn-secondary" ${(loading || d.refreshingApproaches || (Number(d.approachesRefreshCount || 0) >= 5) || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
            ${d.refreshingApproaches ? 'Обновляю…' : `Обновить подходы (${Math.min(Number(d.approachesRefreshCount || 0), 5)}/5)`}
          </button>
        </div>
        <div class="create-assist-list">
          ${angles.length ? angles.map((a) => `<button type="button" class="btn ${d.selectedAngle === a ? 'btn-primary' : 'btn-ghost'}" data-cd-angle="${encodeURIComponent(a)}">${esc(a)}</button>`).join('') : '<span class="small">Пока пусто</span>'}
        </div>
      </article>
      <article class="card" style="margin-top:10px;padding:10px;">
        <div class="small" style="margin-bottom:8px;font-weight:700;">\u0420\u0435\u0436\u0438\u043c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438</div>
        <p class="small" style="margin:6px 0 8px 0;">Подберите CTA под текущую тему, формат и цель публикации.</p>
        <div class="row create-result-toolbar">
          <button id="cdRefreshCta" type="button" class="btn btn-secondary" ${(loading || d.refreshingCta || (Number(d.ctaRefreshCount || 0) >= 5) || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
            ${d.refreshingCta ? 'Обновляю…' : `Обновить призыв (${Math.min(Number(d.ctaRefreshCount || 0), 5)}/5)`}
          </button>
        </div>
        <div class="create-assist-list">
          ${ctaOptions.length
            ? ctaOptions.map((c) => `<button type="button" class="btn ${(String(d.selectedCta || '').trim() === String(c || '').trim()) ? 'btn-primary' : 'btn-ghost'}" data-cd-cta="${encodeURIComponent(c)}">${esc(c)}</button>`).join('')
            : '<span class="small">Пока пусто</span>'}
        </div>
      </article>
      <article class="card" style="margin-top:10px;padding:10px;">
        ${isVideo
          ? `<div class="small" style="margin-bottom:8px;font-weight:700;">\u0420\u0435\u0436\u0438\u043c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438</div>
             <p class="small" style="margin:6px 0 8px 0;">GPT генерирует обложку без текста под тему ролика.</p>
             <div class="row" style="gap:8px;flex-wrap:wrap;">
               <button id="cdGenerateImage" type="button" class="btn btn-secondary" ${(loading || d.imageLoading) ? 'disabled' : ''}>${d.imageLoading ? 'Генерируем обложку…' : 'Сгенерировать обложку'}</button>
               <button id="cdRefreshImage" type="button" class="btn btn-ghost" ${(loading || d.imageLoading || (Number(d.imageRefreshCount || 0) >= 3)) ? 'disabled' : ''}>Обновить обложку (${Math.min(Number(d.imageRefreshCount || 0), 3)}/3)</button>
             </div>`
          : `<div class="small" style="margin-bottom:8px;font-weight:700;">\u0420\u0435\u0436\u0438\u043c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438</div>
              <p class="small" style="margin:6px 0 8px 0;">Управляется в расширенных настройках. Здесь можно только сгенерировать или обновить картинку.</p>
              <div class="row" style="gap:8px;flex-wrap:wrap;">
                <button id="cdGenerateImage" type="button" class="btn btn-secondary" ${(loading || !d.imageEnabled || d.imageLoading) ? 'disabled' : ''}>${d.imageLoading ? 'Генерируем картинку…' : 'Сгенерировать картинку'}</button>
                <button id="cdRefreshImage" type="button" class="btn btn-ghost" ${(loading || !d.imageEnabled || d.imageLoading || (Number(d.imageRefreshCount || 0) >= 3)) ? 'disabled' : ''}>Обновить картинку (${Math.min(Number(d.imageRefreshCount || 0), 3)}/3)</button>
              </div>`
        }
      </article>
      <article class="card" style="margin-top:10px;padding:10px;">
        <label style="margin:0;font-weight:700;">Хештеги</label>
        <p class="small" style="margin:6px 0 8px 0;">Подберите набор хештегов под текущую нишу и выбранную тему.</p>
        <div class="row create-result-toolbar">
          <button id="cdRefreshTags" type="button" class="btn btn-secondary" ${(loading || d.refreshingHashtags || (Number(d.hashtagsRefreshCount || 0) >= 5) || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
            ${d.refreshingHashtags ? 'Обновляю…' : `Обновить хештеги (${Math.min(Number(d.hashtagsRefreshCount || 0), 5)}/5)`}
          </button>
        </div>
        <div class="create-assist-list">
          ${hashtagSets.length
            ? hashtagSets.map((set) => {
                const arr = Array.isArray(set) ? set.filter(Boolean) : [];
                const key = arr.join(' ');
                const selected = (selectedTagSet.join(' ') === key) || (!selectedTagSet.length && key === ((hashtagSets[0] || []).join(' ')));
                return `<button type="button" class="btn ${selected ? 'btn-primary' : 'btn-ghost'}" data-cd-hset="${encodeURIComponent(key)}">${esc(key)}</button>`;
              }).join('')
            : '<span class="small">Пока пусто</span>'}
        </div>
      </article>
      <div class="row" style="gap:12px;flex-wrap:wrap;margin-top:10px;">
        <label class="create-toggle"><input id="cdFb" type="checkbox" ${platforms.facebook ? 'checked' : ''}/> Facebook</label>
        <label class="create-toggle"><input id="cdIg" type="checkbox" ${platforms.instagram ? 'checked' : ''}/> Instagram</label>
      </div>
      <div class="cta-row" style="margin-top:10px;">
        <button id="cdSave" type="button" class="btn btn-ghost" ${activeDraft ? '' : 'disabled'}>Сохранить</button>
        <button id="cdSchedule" type="button" class="btn btn-secondary" ${activeDraft ? '' : 'disabled'}>Запланировать</button>
        <button id="cdPublish" type="button" class="btn btn-primary" ${activeDraft ? '' : 'disabled'}>Опубликовать</button>
      </div>
      ${field('cdScheduleAt', 'Дата/время для планирования', 'datetime-local', d.scheduleAt || '')}
      <article class="card" style="margin-top:12px;padding:12px;">
        <h3 style="margin-top:0;">Контент-план</h3>
        <p class="small">AI может сам выбрать лучшие дни и часы публикации.</p>
        <div class="row" style="gap:8px;flex-wrap:wrap;">
          <button id="cdPlanWeek" type="button" class="btn ${d.planHorizon === 'week' ? 'btn-primary' : 'btn-ghost'}">План на неделю</button>
          <button id="cdPlanMonth" type="button" class="btn ${d.planHorizon === 'month' ? 'btn-primary' : 'btn-ghost'}">План на месяц</button>
          <button id="cdPlanGenerate" type="button" class="btn btn-secondary" ${d.planLoading ? 'disabled' : ''}>${d.planLoading ? 'Формирую…' : 'Сформировать план'}</button>
          <button id="cdBestTimes" type="button" class="btn btn-ghost">Лучшие дни/часы</button>
        </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        ${planRows}
      </article>
    </article>
  `;
  const shouldShowPostResult = isVideo || d.status !== 'idle' || d.loadingSuggest || d.loadingDrafts;
  if (isVideo && !d.videoStructure) {
    resultCard = '';
  }
  if (isVideo) {
    const scenes = Array.isArray(d.videoStructure?.scenes) ? d.videoStructure.scenes : [];
    const structureSceneLimit = 4;
    const structureCanToggle = scenes.length > structureSceneLimit;
    const structureExpanded = !!d.videoStructureExpanded;
    const visibleScenes = (!structureCanToggle || structureExpanded) ? scenes : scenes.slice(0, structureSceneLimit);
    const showVideoStructure = !!d.videoStructure;
    const hasReadyVideo = !!String(d.videoFinalUrl || d.videoPreviewUrl || '').trim();
    const resolvedVoiceGender = String(
      (hasReadyVideo && d.videoRenderedVoiceGender)
        || d.videoStructure?.voiceover?.gender
        || d.videoVoiceGender
        || 'male',
    ).toLowerCase();
    const resolvedVoiceTone = String(
      (hasReadyVideo && d.videoRenderedVoiceTone)
        || d.videoStructure?.voiceover?.tone
        || d.videoVoiceTone
        || 'neutral',
    ).toLowerCase();
    resultCard = showVideoStructure ? `
      <article class="card glass-card create-director-card">
        <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
          <h3 style="margin:0;">Структура видео</h3>
          ${structureCanToggle
            ? `<button id="cdToggleStructure" type="button" class="btn btn-ghost">${structureExpanded ? 'Свернуть' : 'Открыть больше'}</button>`
            : ''}
        </div>
        ${d.videoStructure
          ? `<p class="small"><strong>${esc(d.videoStructure.title || effectiveSelectedTopic || baseTopic || 'Видео')}</strong> · ${esc(String(d.videoDurationPreset || '30'))} сек</p>
             <p class="small">Голос: ${esc((resolvedVoiceGender === 'female' ? 'женский' : 'мужской'))} · Интонация: ${esc((resolvedVoiceTone === 'calm' ? 'спокойная' : (resolvedVoiceTone === 'live' ? 'живая' : 'нейтральная')))} · Субтитры: включены · Фон: тихая музыка</p>
             <p class="small">Перетяните сцены, чтобы изменить порядок в итоговом видео.</p>
             <div style="display:grid;gap:8px;margin-top:10px;">
               ${visibleScenes.map((s, scenePos) => `
                 <div class="small card" draggable="true" data-cd-scene="${scenePos}" style="padding:10px;border:1px solid rgba(99,102,241,.18);cursor:grab;">
                   <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
                     <span><strong>${scenePos + 1}.</strong> <span style="opacity:.75;">~${Number(s.duration_s || 0).toFixed(1)} c</span></span>
                     <div class="row" style="gap:8px;align-items:center;">


                     </div>
                   </div>
                   <textarea
                     data-cd-scene-text="${scenePos}"
                     placeholder="Текст сцены"
                     style="margin:8px 0 0 0;width:100%;min-height:36px;max-height:56px;border:1px solid rgba(99,102,241,.18);border-radius:8px;padding:6px 8px;background:transparent;color:inherit;line-height:1.35;font-size:14px;font-family:inherit;font-weight:500;resize:none;overflow:auto;"
                   >${esc(s.text || '')}</textarea>
                 </div>
               `).join('')}
              </div>
              ${structureCanToggle && !structureExpanded
                ? '<p class="small muted" style="margin-top:8px;">Показаны первые сцены. Нажмите «Открыть больше», чтобы увидеть всю структуру.</p>'
                : ''}`
          : '<p class="small">Нажмите «Сгенерировать структуру», чтобы получить структуру, хештеги и призыв.</p>'}
        ${showVideoStructure ? `<div class="row" style="margin-top:10px;justify-content:flex-end;gap:8px;">
          <button id="cdSceneAdd" type="button" class="btn btn-ghost">Добавить сцену</button>
        </div>` : ''}
        ${showVideoStructure ? `<div style="margin-top:10px;display:grid;gap:10px;">
          <div class="create-preview-meta-block">
            <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
              <p class="small" style="margin:0;"><strong>Хештеги</strong></p>
              <button id="cdRefreshTagsInline" type="button" class="btn btn-ghost" ${(loading || d.refreshingHashtags || (Number(d.hashtagsRefreshCount || 0) >= 5) || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
                ${d.refreshingHashtags ? 'Обновляю…' : `Обновить (${Math.min(Number(d.hashtagsRefreshCount || 0), 5)}/5)`}
              </button>
            </div>
            ${previewTags.length ? '' : '<p class="small director-meta-placeholder">Появятся после генерации структуры.</p>'}
            <input id="cdVideoTagsInline" class="director-meta-input" type="text" value="${esc((previewTags || []).join(' '))}" ${d.videoStructure ? '' : 'disabled'} />
          </div>
          <div class="create-preview-meta-block">
            <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
              <p class="small" style="margin:0;"><strong>Призыв</strong></p>
              <button id="cdRefreshCtaInline" type="button" class="btn btn-ghost" ${(loading || d.refreshingCta || (Number(d.ctaRefreshCount || 0) >= 5) || !String(baseTopic || '').trim()) ? 'disabled' : ''}>
                ${d.refreshingCta ? 'Обновляю…' : `Обновить (${Math.min(Number(d.ctaRefreshCount || 0), 5)}/5)`}
              </button>
            </div>
            ${String(d.selectedCta || '').trim() ? '' : '<p class="small director-meta-placeholder">Появится после генерации структуры.</p>'}
            <input id="cdVideoCtaInline" class="director-meta-input" type="text" value="${esc(String(d.selectedCta || '').trim())}" ${d.videoStructure ? '' : 'disabled'} />
          </div>
        </div>` : ''}
        <div class="row" style="gap:12px;flex-wrap:wrap;margin-top:10px;">
          <label class="create-toggle"><input id="cdFb" type="checkbox" ${platforms.facebook ? 'checked' : ''}/> Facebook</label>
          <label class="create-toggle"><input id="cdIg" type="checkbox" ${platforms.instagram ? 'checked' : ''}/> Instagram</label>
          <label class="create-toggle"><input id="cdYt" type="checkbox" ${platforms.youtube ? 'checked' : ''}/> YouTube</label>
        </div>
        <div class="cta-row" style="margin-top:12px;">
          <button type="button" class="btn btn-ghost" data-link="${plannerUrl('video', 7)}">План 7 дней</button>
          <button type="button" class="btn btn-ghost" data-link="${plannerUrl('video', 30)}">План 30 дней</button>
          <button id="cdDownloadVideo" type="button" class="btn btn-secondary" ${(!String(d.videoFinalUrl || d.videoPreviewUrl || '').trim()) ? 'disabled' : ''}>Скачать видео</button>
          <button id="cdPublishVideo" type="button" class="btn btn-primary" ${(!String(d.videoJobStatus || '').toLowerCase().startsWith('success') || !d.videoJobId) ? 'disabled' : ''}>Опубликовать видео</button>
        </div>
      </article>
    ` : '';
  }

  if (isPlanFlow) {
    const summaryFormat = isWeeklyPlanFlow ? 'Посты на неделю' : 'Посты на месяц';
    const planHeroTitle = isWeeklyPlanFlow ? 'Контент-план на 7 дней' : 'Контент-план на 30 дней';
    const planHeroSubtitle = isWeeklyPlanFlow
      ? 'AI подготовит 7 готовых идей для вашей ниши: темы, формат, угол подачи, CTA, хештеги и основу для публикации.'
      : 'AI подготовит месячный контент-план с идеями, структурой публикаций и готовыми заготовками под вашу нишу.';
    const selectedPlanItemFormat = planFormatLabel(selectedPlanDay?.contentFormat || selectedPlanDay?.objective || 'post');
    const progressSteps = ['Анализируем нишу', 'Подбираем темы', 'Формируем структуру публикаций', 'Готовим CTA и хештеги', 'Собираем итоговый план'];
    const currentProgressIdx = Math.max(0, Math.min(progressSteps.length, Number(d.planFlowProgressStep || 0)));
    const planSettingsCard = `
      <article class="card glass-card create-director-card plan-flow-settings-card">
        <div class="create-step-label">Настройки плана</div>
        <div class="grid-2">
          ${selectField('cdTopicPreset', 'Ниша', d.topicPreset || DEFAULT_DIRECTOR_NICHE, DIRECTOR_NICHE_OPTIONS)}
          ${selectField('cdGoal', 'Цель', d.goal || 'engagement', [{ value: 'awareness', label: 'Охват' }, { value: 'engagement', label: 'Вовлечение' }, { value: 'lead', label: 'Лиды' }, { value: 'sales', label: 'Продажи' }])}
          ${selectField('cdLang', 'Язык', d.language || 'ru', CONTENT_LANG_OPTIONS)}
          ${field('cdOffer', 'Оффер (опционально)', 'text', d.offer || '', 'Например: бесплатная консультация или диагностика')}
        </div>
        <label class="create-toggle" style="margin-top:10px;"><input id="cdTopicCustomEnabled" type="checkbox" ${d.customTopicMode ? 'checked' : ''}/> Своя ниша/тема</label>
        ${d.customTopicMode ? field('cdTopic', 'Своя ниша/тема', 'text', d.customBaseTopicInput || '', 'Например: продвижение студии массажа в Берлине') : ''}
        <p class="small create-plan-settings-note">AI использует эти данные, чтобы подобрать релевантные темы и структуру публикаций.</p>
        <div class="cta-row plan-flow-primary-cta">
          <button id="cdGeneratePlanFlow" class="btn btn-primary" type="button" ${planFlowLoading ? 'disabled' : ''}>${planFlowLoading ? 'Готовим план…' : `Сгенерировать план на ${planFlowDays} дней`}</button>
          ${planFlowGenerated ? '<button id="cdQuickActionRefresh" class="btn btn-ghost" type="button">Перегенерировать план</button>' : ''}
        </div>
      </article>
    `;
    const planProgressCard = planFlowLoading ? `
      <article class="card glass-card create-director-card plan-flow-progress-card">
        <h3 style="margin-top:0;">AI готовит ваш контент-план</h3>
        <div class="plan-flow-progress-list">
          ${progressSteps.map((label, idx) => {
            const stateCls = idx < currentProgressIdx ? 'done' : (idx === currentProgressIdx ? 'active' : '');
            return `<div class="plan-flow-progress-item ${stateCls}"><span class="plan-flow-progress-dot"></span><span>${esc(label)}</span></div>`;
          }).join('')}
        </div>
      </article>
    ` : '';
    const planEmptyCard = (!planFlowGenerated && !planFlowLoading && !planFlowError) ? `
      <article class="card glass-card create-director-card plan-flow-empty-card">
        <h3 style="margin-top:0;">Выберите нишу и запустите генерацию</h3>
        <p class="small">Выберите нишу и нажмите «Сгенерировать план», чтобы получить готовые идеи публикаций.</p>
      </article>
    ` : '';
    const planErrorCard = planFlowError ? `
      <article class="card glass-card create-director-card plan-flow-error-card">
        <h3 style="margin-top:0;">Не удалось создать план</h3>
        <p class="small">${esc(planFlowError)}</p>
        <p class="small">Если ошибка повторяется, обновите страницу или измените параметры.</p>
      </article>
    ` : '';
    const planResultsBody = (() => {
      if (!planFlowGenerated) return '';
      if (isMonthlyPlanFlow) {
        const weeks = groupPlanItemsByWeek(quickPlanItems);
        return weeks.map((week) => `
          <section class="plan-flow-week-group">
            <div class="row" style="justify-content:space-between;align-items:center;gap:8px;">
              <h4 style="margin:0;">Неделя ${week.index}</h4>
              <span class="small">${week.items.length} публикаций</span>
            </div>
            <div class="plan-flow-grid">
              ${week.items.map((item) => `
                <article class="plan-flow-day-card ${Number(item.day || 0) === Number(d.planFlowSelectedDay || 1) ? 'is-selected' : ''}">
                  <div class="row" style="justify-content:space-between;align-items:flex-start;gap:8px;">
                    <div>

                      <strong>${esc(item.topic || '—')}</strong>
                    </div>
                    <span class="pill">${esc(planFormatLabel(item.contentFormat || item.objective || 'post'))}</span>
                  </div>
                  <p class="small"><strong>Угол подачи:</strong> ${esc(item.angle || '—')}</p>
                  <p class="small">${esc(planDayPreview(item))}</p>
                  <p class="small"><strong>CTA:</strong> ${esc(item.cta || '—')}</p>
                  <div class="create-preview-tags">${String(item.hashtags || '').split(/\s+/).filter(Boolean).slice(0, 6).map((tag) => `<span class="pill">${esc(tag)}</span>`).join('')}</div>
                  <div class="cta-row plan-flow-day-actions">


                  </div>
                </article>
              `).join('')}
            </div>
          </section>
        `).join('');
      }
      return `<div class="plan-flow-grid">
        ${quickPlanItems.map((item) => `
          <article class="plan-flow-day-card ${Number(item.day || 0) === Number(d.planFlowSelectedDay || 1) ? 'is-selected' : ''}">
            <div class="row" style="justify-content:space-between;align-items:flex-start;gap:8px;">
              <div>
                <div class="small">День ${Number(item.day || 0)}</div>
                <strong>${esc(item.topic || '—')}</strong>
              </div>
              <span class="pill">${esc(planFormatLabel(item.contentFormat || item.objective || 'post'))}</span>
            </div>
            <p class="small"><strong>Угол подачи:</strong> ${esc(item.angle || '—')}</p>
            <p class="small">${esc(planDayPreview(item))}</p>
            <p class="small"><strong>CTA:</strong> ${esc(item.cta || '—')}</p>
            <div class="create-preview-tags">${String(item.hashtags || '').split(/\s+/).filter(Boolean).slice(0, 6).map((tag) => `<span class="pill">${esc(tag)}</span>`).join('')}</div>
            <div class="cta-row plan-flow-day-actions">
              <button type="button" class="btn btn-secondary" data-cd-plan-select-day="${Number(item.day || 0)}">Использовать</button>
              <button type="button" class="btn btn-primary" data-cd-plan-schedule-day="${Number(item.day || 0)}">Запланировать</button>
              <button type="button" class="btn btn-ghost" data-cd-plan-edit="${Number(item.day || 0)}">Редактировать</button>
            </div>
          </article>
        `).join('')}
      </div>`;
    })();
    const planResultsCard = planFlowGenerated ? `
      <article class="card glass-card create-director-card plan-flow-results-card">
        <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
          <div>
            <div class="create-step-label">Результат</div>
            <h3 style="margin:0 0 8px 0;">${esc(planHeroTitle)} готов</h3>
            <p class="small" style="margin:0;">${esc(isWeeklyPlanFlow ? '7 карточек с готовыми темами и CTA для вашей ниши.' : 'Месячный план сгруппирован по неделям, чтобы его было проще просмотреть и использовать.')}</p>
          </div>
          <div class="cta-row">
            <button id="cdPlanGenerate" type="button" class="btn btn-secondary" ${d.planLoading ? 'disabled' : ''}>${d.planLoading ? 'Сохраняем…' : 'Сохранить план'}</button>
            <button type="button" class="btn btn-ghost" data-link="/calendar">Открыть календарь</button>
          </div>
        </div>
        ${quickActionResult?.access?.isPreview ? '<p class="small" style="margin-top:10px;"><strong>Preview:</strong> полный объём плана доступен после апгрейда тарифа.</p>' : ''}
        ${planResultsBody}
      </article>
    ` : '';
    const planSidebar = `
      <aside class="create-preview-col create-preview-col-static plan-flow-sidebar">
        <article class="create-info-card glass-card">
          <div class="create-step-label">${esc(isPlanFlow ? 'Быстрый старт' : '')}</div>
          <h3 style="margin-top:0;">Вы создаёте: ${esc(planHeroTitle)}</h3>
          <div class="wizard-summary">
            <span class="pill">Ниша: ${esc(directorCurrentNicheMeta(d)?.label || directorBaseTopic(d, d.topic) || '—')}</span>
            <span class="pill">Формат: ${esc(summaryFormat)}</span>
            <span class="pill">Язык: ${esc((CONTENT_LANG_OPTIONS.find((opt) => opt.value === (d.language || 'ru')) || { label: 'Русский' }).label)}</span>
            <span class="pill">Цель: ${esc(planFlowGoalLabel)}</span>
          </div>
          ${!planFlowGenerated
            ? `<p class="small">Здесь появится preview выбранного дня после генерации плана.</p>`
            : ''}
        </article>
        ${!planFlowGenerated ? `
          <article class="create-info-card glass-card">
            <h3 style="margin-top:0;">Что вы получите</h3>
            <ul class="check-list">
              <li class="done">Готовые темы</li>
              <li class="done">Идеи публикаций</li>
              <li class="done">CTA для каждого дня</li>
              <li class="done">Хештеги и основу для плана</li>
            </ul>
          </article>
        ` : `
          <article class="create-preview-card glass-card">
            <div class="create-step-label">Preview дня</div>
            <h3 style="margin-top:0;">${esc(selectedPlanDay?.topic || 'Выберите день')}</h3>
            <p class="small create-preview-state">${esc(selectedPlanDay ? selectedPlanItemFormat : 'Здесь появится preview выбранного дня после генерации плана.')}</p>
            ${selectedPlanDay ? `
              <p class="create-preview-text" style="min-height:auto;">${esc(planDayPreview(selectedPlanDay))}</p>
              <div class="create-preview-meta-block">
                <p class="small" style="margin:0 0 6px 0;"><strong>CTA:</strong> ${esc(selectedPlanDay.cta || '—')}</p>
                <div class="create-preview-tags">${String(selectedPlanDay.hashtags || '').split(/\s+/).filter(Boolean).slice(0, 8).map((tag) => `<span class="pill">${esc(tag)}</span>`).join('') || '<span class="small">Хештеги появятся здесь</span>'}</div>
              </div>
              <div class="cta-row" style="margin-top:12px;">
                <button type="button" class="btn btn-secondary" data-cd-plan-select-day="${Number(selectedPlanDay.day || 0)}">Использовать</button>
                <button type="button" class="btn btn-primary" data-cd-plan-schedule-day="${Number(selectedPlanDay.day || 0)}">Запланировать</button>
                <button type="button" class="btn btn-ghost" data-cd-plan-edit="${Number(selectedPlanDay.day || 0)}">Редактировать</button>
              </div>
            ` : ''}
          </article>
          <article class="create-info-card glass-card">
            <h3 style="margin-top:0;">Быстрые действия</h3>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
              <button id="cdPlanGenerateSidebar" type="button" class="btn btn-secondary" ${d.planLoading ? 'disabled' : ''}>${d.planLoading ? 'Сохраняем…' : 'Сохранить план'}</button>
              ${selectedPlanDay ? `<button type="button" class="btn btn-primary" data-cd-plan-schedule-day="${Number(selectedPlanDay.day || 0)}">Запланировать день</button>` : '<button type="button" class="btn btn-ghost" data-link="/calendar">Открыть календарь</button>'}
            </div>
          </article>
        `}
      </aside>
    `;
    return appLayout('/create', 'Создать', `
      <section class="create-wizard-shell create-director-shell plan-flow-shell">
        <div class="create-wizard-grid plan-flow-layout">
          <article class="create-main-col">
            <article class="card glass-card create-director-card plan-flow-hero-card">
              <div class="create-step-label">Из панели управления</div>
              <div class="row" style="justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
                <div style="max-width:760px;">
                  <h1 class="plan-flow-hero-title">${esc(planHeroTitle)}</h1>
                  <p class="plan-flow-hero-subtitle">${esc(planHeroSubtitle)}</p>
                </div>
                <div class="wizard-summary plan-flow-summary">
                  <span class="pill">Ниша: ${esc(directorCurrentNicheMeta(d)?.label || directorBaseTopic(d, d.topic) || '—')}</span>
                  <span class="pill">Формат: ${esc(summaryFormat)}</span>
                  <span class="pill">Язык: ${esc((CONTENT_LANG_OPTIONS.find((opt) => opt.value === (d.language || 'ru')) || { label: 'Русский' }).label)}</span>
                  <span class="pill">Цель: ${esc(planFlowGoalLabel)}</span>
                </div>
              </div>
            </article>
            ${planSettingsCard}
            ${planProgressCard}
            ${planErrorCard}
            ${planEmptyCard}
            ${planResultsCard}
          </article>
          ${planSidebar}
        </div>
      </section>
    `);
  }

  const previewCard = `
    <article class="create-preview-card glass-card">
      <div class="row" style="justify-content:space-between;align-items:center;">
        <span class="small">Платформа</span>

      </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        <span class="small">Preview</span>
        <div class="create-segmented-control" role="tablist" aria-label="Preview type">
          <button id="cdPreviewTypePost" class="btn segment-btn ${!isVideo ? 'btn-primary' : 'btn-ghost'}" type="button">Пост</button>
          <button id="cdPreviewTypeVideo" class="btn segment-btn ${isVideo ? 'btn-primary' : 'btn-ghost'}" type="button">Видео</button>
        </div>
      </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        ${platformOrder.map((p) => {
          const enabled = !!(d.platforms && d.platforms[p]);
          const label = p === 'youtube' ? 'YouTube' : (p === 'instagram' ? 'Instagram' : 'Facebook');
          const cls = activePlatform === p ? 'pill active pill-btn' : 'pill pill-btn';
          return `<button type="button" class="${cls}" data-cd-preview-platform="${p}" ${enabled ? '' : 'disabled'} title="${enabled ? '' : 'Включите платформу слева'}" aria-pressed="${activePlatform === p ? 'true' : 'false'}">${label}</button>`;
        }).join('')}
      </div>
      <h3 id="cdPreviewTitle">${esc(d.videoStructure?.title || effectiveSelectedTopic || baseTopic || 'Тема')}</h3>
      <p class="small create-preview-state">${esc(previewStateText)}</p>
      ${isVideo
        ? `<div class="create-video-preview-block">
            ${videoPlayableUrl
              ? `<video class="create-video-player ${videoFrameClass}" controls preload="metadata" ${String(d.videoCoverUrl || '').trim() ? `poster="${esc(String(d.videoCoverUrl || '').trim())}"` : ''}>

                 </video>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>

                   <span id="cdVideoRatioTextReady" class="small">Готово: ${esc(String(d.videoDurationPreset || '30'))} сек · ${esc(videoOrientation === 'horizontal' ? '16:9' : '9:16')}</span>
                 </div>`
              : `<div class="create-video-placeholder ${videoFrameClass}">
                   ${String(d.videoCoverUrl || '').trim() ? `<img src="${esc(d.videoCoverUrl)}" alt="Video cover" style="width:100%;height:100%;object-fit:cover;border-radius:14px;" />` : ''}
                   <div class="play-icon">?</div>
                   <span id="cdVideoRatioText">${esc(videoOrientation === 'horizontal' ? '16:9' : '9:16')} · ${esc(String(d.videoDurationPreset || '30'))} сек</span>
                 </div>
                 <div style="margin-top:10px;">
                   <div id="cdVideoStepText" class="small"><strong>${esc(videoStepLabel)}</strong> · <span id="cdVideoProgressNum">${videoProgress}</span>%</div>
                   <div class="create-progress"><span id="cdVideoProgressFill" style="width:${videoProgress}%"></span></div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
                 </div>`}
            ${uniqueClipsUsed.length
              ? `<div class="create-preview-meta-block">
                   <p class="small" style="margin:0 0 6px 0;"><strong>Уникальные футажи:</strong> ${uniqueClipsUsed.length}</p>
                   <div class="create-preview-tags">${uniqueClipsUsed.map((clip, idx) => `<span class="pill" title="${esc(String(clip.query_used || ''))}">${esc(String(clip.query_bucket || clip.query_used || `Клип ${idx + 1}`))}</span>`).join('')}</div>
                 </div>`
              : ''}
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
            <p class="small" style="margin-top:10px;"><strong>Текст публикации:</strong></p>
            <p id="cdPreviewText" class="create-preview-text">${esc(previewText)}</p>
            ${videoPreviewTextState?.canExpand
              ? `<div class="row" style="margin-top:6px;">

                 </div>`
              : ''}
            <div class="create-preview-meta-block">
              <p class="small" style="margin:0 0 6px 0;"><strong>Хештеги:</strong></p>
              <div id="cdPreviewTags" class="create-preview-tags">${previewTags.map((h) => `<span class="pill">${esc(h)}</span>`).join('')}</div>
            </div>
            <div class="create-preview-meta-block">
              <p class="small" style="margin:0 0 6px 0;"><strong>Призыв к действию:</strong></p>
              <button id="cdPreviewCta" class="btn btn-secondary create-preview-cta" type="button">${esc(String(d.selectedCta || '').trim() || activeDraft?.cta || ctaOptions[0] || 'Призыв')}</button>
            </div>
          </div>`
        : `${(d.imageEnabled && String(d.imageUrl || '').trim())
            ? `<div style="margin:8px 0 10px 0;border-radius:14px;border:1px solid rgba(99,102,241,.2);background:rgba(99,102,241,.05);overflow:hidden;display:flex;align-items:center;justify-content:center;min-height:220px;max-height:320px;">
                 <img src="${esc(d.imageUrl)}" alt="Preview image" style="width:100%;height:100%;max-height:320px;object-fit:contain;display:block;" />
               </div>`
            : ''}
          ${d.loadingDrafts ? '<div class="create-skeleton-lines" style="margin:6px 0 10px 0;"><span></span><span></span><span></span></div>' : ''}
          <p id="cdPreviewText" class="create-preview-text">${esc(previewText)}</p>
          <div class="create-preview-meta-block">
            <p class="small" style="margin:0 0 6px 0;"><strong>Хештеги:</strong></p>
            <div id="cdPreviewTags" class="create-preview-tags">${previewTags.map((h) => `<span class="pill">${esc(h)}</span>`).join('')}</div>
          </div>
          <div class="create-preview-meta-block">
            <p class="small" style="margin:0 0 6px 0;"><strong>Призыв к действию:</strong></p>
            <button id="cdPreviewCta" class="btn btn-secondary create-preview-cta" type="button">${esc(String(d.selectedCta || '').trim() || activeDraft?.cta || ctaOptions[0] || 'Призыв')}</button>
          </div>`
      }
    </article>
  `;

  const qualityCard = `
    <article class="create-info-card glass-card">
      <h3>Проверка качества</h3>
      <div id="cdQualityScore" class="create-quality-score">${Number(quality.score || 0)}<span>/100</span></div>
      <ul id="cdQualityList" class="check-list">${(quality.checks || []).map((it) => `<li class="${it.state === 'green' ? 'done' : (it.state === 'red' ? 'bad' : '')}">${esc(it.label)}</li>`).join('')}</ul>
      <p id="cdQualityWarn" class="small">${(quality.warnings || []).length ? (quality.warnings || []).map((w) => esc(w)).join(' · ') : ''}</p>
    </article>
  `;
  const miniPlanCard = `
    <article class="create-info-card glass-card">
      <h3 style="margin-top:0;">План (мини)</h3>
      <div class="row" style="gap:8px;flex-wrap:wrap;">
        <button id="cdMiniWeek" type="button" class="btn ${d.planHorizon === 'week' ? 'btn-secondary' : 'btn-ghost'}">7 дней</button>
        <button id="cdMiniMonth" type="button" class="btn ${d.planHorizon === 'month' ? 'btn-secondary' : 'btn-ghost'}">30 дней</button>
        <button id="cdMiniBest" type="button" class="btn btn-ghost">AI время</button>
      </div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
      ${nextSlotPills ? `<div class="row" style="gap:6px;flex-wrap:wrap;margin-top:6px;">${nextSlotPills}</div>` : ''}
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
    </article>
  `;
  const mainColCards = prioritizeDirectorCard
    ? `${quickCard}${quickActionPanel}${resultCard}`
    : `${quickActionPanel}${quickCard}${resultCard}`;

  return appLayout('/create', 'Создать', `
    <section class="create-wizard-shell create-director-shell">
      <div class="create-wizard-grid">
        <article class="create-main-col">
          ${mainColCards}
        </article>
        <aside class="create-preview-col create-preview-col-static">
          ${previewCard}
          ${qualityCard}
          ${miniPlanCard}
        </aside>
      </div>
    </section>
  `);
}

function pageCreateVideoWeek() {
  return pageCreatePlanner(getCreatePlannerRoute(location.pathname.replace(/\/$/, '') || '/'));
}

function pageCreatePlanner(route = getCreatePlannerRoute()) {
  const planner = route || { kind: 'post', days: 7 };
  const cfg = getPlannerStateConfig(planner.kind, planner.days);
  const d = state.createDirector || {};
  if (!d.platforms) d.platforms = { facebook: true, instagram: true, youtube: false };
  const items = Array.isArray(d[cfg.itemsKey]) ? d[cfg.itemsKey] : [];
  const plannerConfig = getPlannerRenderConfig(cfg.kind, d);
  const bestSlots = d.bestSlots || null;
  const bestDaysText = Array.isArray(bestSlots?.best_days) ? bestSlots.best_days.map((x) => x.label).join(', ') : '';
  const bestHoursText = Array.isArray(bestSlots?.best_hours) ? bestSlots.best_hours.map((h) => `${h}:00`).join(', ') : '';
  const weeklyRecoText = Array.isArray(bestSlots?.weekly_plan)
    ? bestSlots.weekly_plan
        .map((dItem) => {
          const times = Array.isArray(dItem?.slots)
            ? dItem.slots
                .map((iso) => {
                  try { return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }); } catch { return ''; }
                })
                .filter(Boolean)
                .join(', ')
            : '';
          return times ? `${String(dItem?.weekday || '').trim()}: ${times}` : '';
        })
        .filter(Boolean)
        .join(' · ')
    : '';
  const selectedTopic = cfg.kind === 'video'
    ? directorEffectiveTopic(d, d.topic || '')
    : (String(d.topic || directorBaseTopic(d, d.topic) || '').trim() || directorCurrentNicheMeta(d)?.label || '');
  const plannerData = {
    cfg,
    d,
    items,
    selectedTopic,
    ...getPlannerDayState(items, d[cfg.selectedDateKey]),
  };
  const plannerView = renderPlanner(plannerData, plannerConfig);
  const postsPerDayValue = String((d[cfg.postsPerDayKey] || 1));
  const timeModeValue = String(d[cfg.timeModeKey] || 'ai');
  const manualTimeValue = String(d[cfg.manualTimeKey] || '12:00');
  const loading = !!d[cfg.loadingKey];
  const applying = !!d[cfg.applyingKey];
  const scheduling = !!d[cfg.schedulingKey];
  return appLayout('/create', cfg.title, `
    <section class="create-wizard-shell create-director-shell">
      <div class="create-wizard-grid">
        <article class="create-main-col">
          <article class="card glass-card create-director-card">
            <div class="row" style="justify-content:space-between;align-items:center;gap:12px;">
              <div>
                <h2 style="margin:0;">${esc(cfg.title)}</h2>
                <p class="small" style="margin:6px 0 0 0;">${esc(cfg.subtitle)}</p>
              </div>
              <button class="btn btn-ghost" type="button" data-link="${esc(cfg.backUrl)}">Назад в AI Контент-директор</button>
            </div>
            <div class="grid-2" style="margin-top:12px;">
              ${selectField('plannerNiche', 'Ниша', normalizeNicheIdSafe(String(d.topicPreset || DEFAULT_DIRECTOR_NICHE).trim()) || DEFAULT_DIRECTOR_NICHE, DIRECTOR_NICHE_OPTIONS)}
              ${field('plannerTopic', 'Своя тема/фокус', 'text', String(d.topic || '').trim(), plannerConfig.fieldConfig.topicPlaceholder)}
              ${selectField('plannerPostsPerDay', plannerConfig.fieldConfig.postsPerDayLabel, postsPerDayValue, [{ value: '1', label: '1' }, { value: '2', label: '2' }, { value: '3', label: '3' }, { value: '4', label: '4' }, { value: '5', label: '5' }, { value: '6', label: '6' }])}
              ${selectField('plannerLanguage', 'Язык', d.language || 'ru', [{ value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' }])}
              ${selectField('plannerTone', 'Стиль', d.tone || 'friendly', [{ value: 'friendly', label: 'Дружелюбный' }, { value: 'expert', label: 'Экспертный' }, { value: 'sales', label: 'Продающий' }])}
              ${plannerConfig.fieldConfig.secondaryField}
              ${plannerConfig.fieldConfig.tertiaryField}
            </div>
            <div class="row" style="gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px;">
              <span class="small">Платформы:</span>
              ${plannerConfig.fieldConfig.platformsMarkup}
            </div>
            <div class="row" style="gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px;">
              <span class="small">Время публикации:</span>
              <button id="plannerTimeAi" type="button" class="btn ${timeModeValue === 'ai' ? 'btn-primary' : 'btn-ghost'}">AI время</button>
              <button id="plannerTimeManual" type="button" class="btn ${timeModeValue === 'manual' ? 'btn-primary' : 'btn-ghost'}">Вручную</button>
              ${timeModeValue === 'manual' ? field('plannerManualTime', 'Часы', 'time', manualTimeValue) : ''}
            </div>
            ${weeklyRecoText
              ? `<p class="small muted" style="margin-top:8px;">Рекомендованный недельный план: ${esc(weeklyRecoText)}</p>`
              : ((bestDaysText || bestHoursText)
                ? `<p class="small muted" style="margin-top:8px;">${[
                    bestDaysText ? `Лучшие дни: ${bestDaysText}` : '',
                    bestHoursText ? `Лучшие часы: ${bestHoursText}` : '',
                  ].filter(Boolean).join(' · ')}</p>`
                : '')}
            <div class="cta-row" style="margin-top:12px;">
              <button id="plannerGenerate" class="btn btn-primary" type="button" ${loading ? 'disabled' : ''}>${loading ? 'Формирую…' : `Сформировать план ${cfg.days} дней`}</button>
              ${cfg.kind === 'post'
                ? `<button id="plannerScheduleAll" class="btn btn-secondary" type="button" ${(scheduling || !items.length) ? 'disabled' : ''}>${scheduling ? '🚀 Планирую…' : '🚀 Опубликовать весь план автоматически'}</button>`
                : ''}
              <button id="plannerApplyToDirector" class="btn btn-secondary" type="button" ${applying ? 'disabled' : ''}>${applying ? 'Применяю…' : 'Открыть в AI Контент-директор'}</button>
            </div>
          </article>
          <article class="card glass-card create-director-card">
            <h3 style="margin-top:0;">План по дням</h3>
            ${plannerView.sections}
          </article>
        </article>
        <aside class="create-preview-col">
          <article class="create-preview-card glass-card">
            <div class="row" style="justify-content:space-between;align-items:center;">
              <span class="small">${plannerConfig.panelLabel}</span>
              <span class="small">${cfg.days} дней</span>
            </div>
            <h3>${esc(plannerView.previewTitle)}</h3>
            ${plannerConfig.previewType === 'video'
              ? `<p class="small">${esc(plannerData.selectedPreviewItem ? planDayPreview(plannerData.selectedPreviewItem) : 'После генерации здесь появится подробное превью выбранного дня.')}</p>`
              : ''}
            ${plannerView.preview}
          </article>
        </aside>
      </div>
    </section>
  `);
}

function pageCreatePostWeek() {
  return pageCreatePlanner(getCreatePlannerRoute('/create/post-week'));
}

function pageCreateV2() {
  hydrateCampaignDefaults();
  syncCampaignKindsByMode();
  const c = state.createCampaign;
  const steps = ['Проект', 'Платформы', 'Медиа', 'Студия контента', 'Генерация', 'Публикация'];
  const project = state.projects.find((p) => String(p.id) === String(c.projectId)) || state.projects[0] || null;
  const projectName = project?.name || 'Проект не выбран';
  const hashtags = Array.isArray(c.hashtags) ? c.hashtags : [];
  const metaReady = (state.connections || []).filter((m) => isConnectionReady(m));
  const fbConnected = metaReady.some((m) => !!m.page_id);
  const igConnected = metaReady.some((m) => !!m.ig_user_id);
  const ytConnected = !!state.youtubeConnection?.connected;
  const running = !!c.generation?.running;
  const assets = Array.isArray(c.assets) ? c.assets : [];
  const imageAsset = assets.filter((a) => a.type === 'image').slice(-1)[0];
  const videoAsset = assets.filter((a) => a.type === 'video').slice(-1)[0];
  const thumbAsset = assets.filter((a) => a.type === 'thumbnail').slice(-1)[0];
  const previewText = String(c.caption || '').trim() || 'Текст появится после генерации.';
  const previewPlatform = String(c.previewPlatform || 'facebook').toLowerCase();
  const previewPlatformLabel = previewPlatform === 'youtube' ? 'YouTube' : (previewPlatform === 'instagram' ? 'Instagram' : 'Facebook');
  const stylePacks = Array.isArray(c.stylePacks) && c.stylePacks.length
    ? c.stylePacks
    : [{ id: 'default_pro', name: 'Default Pro', description: 'Сбалансированный стиль' }];
  const selectedStylePack = stylePacks.find((p) => String(p.id) === String(c.videoStylePackId || 'default_pro')) || stylePacks[0];
  const stylePackOptions = stylePacks.map((p) => ({ value: p.id, label: p.name }));

  const step1 = `
    <div class="wizard-step-note">Определите тип кампании, тему и язык. Это основа для AI-генерации.</div>
    <div class="create-mode-grid">
      <button type="button" class="create-mode-card ${c.mode === 'image' ? 'active' : ''}" data-cw-mode="image"><strong>Image + Text</strong><span>Картинка и текст для Meta</span></button>
      <button type="button" class="create-mode-card ${c.mode === 'video' ? 'active' : ''}" data-cw-mode="video"><strong>Видео + текст</strong><span>Видео и текст для YouTube/Meta</span></button>
      <button type="button" class="create-mode-card ${c.mode === 'both' ? 'active' : ''}" data-cw-mode="both"><strong>Картинка + видео</strong><span>Одна идея для всех форматов</span></button>
    </div>
    ${field('cwTopic', 'Тема/идея', 'text', c.topic || '', 'Например: как автосервису повысить повторные записи')}
    ${field('cwOffer', 'Цель/продукт/оффер (опционально)', 'text', c.offer || '', 'Например: диагностика подвески со скидкой')}
    ${selectField('cwProject', 'Проект (бренд/клиент)', c.projectId || '', state.projects.map((p) => ({ value: p.id, label: p.name })))}
    ${selectField('cwLang', 'Язык', c.language || 'ru', [
      { value: 'ru', label: 'Русский' },
      { value: 'ua', label: 'Українська' },
      { value: 'de', label: 'Deutsch' },
      { value: 'en', label: 'English' },
    ])}
  `;

  const step2 = `
    <div class="wizard-step-note">Выберите платформы, форматы и аккаунты публикации.</div>
    <div class="create-platform-grid">
      <article class="create-platform-card ${c.platforms.facebook ? 'active' : ''}">
        <div class="row" style="justify-content:space-between;align-items:center;"><strong>Facebook</strong><label class="create-toggle"><input id="cwFb" type="checkbox" ${c.platforms.facebook ? 'checked' : ''}/> Включить</label></div>
        <p class="small">Формат: ${c.kinds.facebook}</p>
        <p class="small">Статус: ${fbConnected ? '<span class="status success">Подключено</span>' : '<span class="status warning">Не подключено</span>'}</p>
        ${!fbConnected ? '<button id="cwGoConnectionsFb" class="btn btn-ghost connection-btn-sm" type="button">Подключить</button>' : ''}
        ${selectField('cwKindFb', 'Тип', c.kinds.facebook, c.mode === 'image' ? [{ value: 'image_post', label: 'Пост с изображением' }] : (c.mode === 'video' ? [{ value: 'video', label: 'Видео' }] : [{ value: 'image_post', label: 'Пост с изображением' }, { value: 'video', label: 'Видео' }]))}
        ${selectField('cwAccFb', 'Страница', c.accountRefs.facebook || '', metaReady.filter((m) => m.page_id).map((m) => ({ value: m.page_id, label: m.page_name || m.page_id })))}
      </article>
      <article class="create-platform-card ${c.platforms.instagram ? 'active' : ''}">
        <div class="row" style="justify-content:space-between;align-items:center;"><strong>Instagram</strong><label class="create-toggle"><input id="cwIg" type="checkbox" ${c.platforms.instagram ? 'checked' : ''}/> Включить</label></div>
        <p class="small">Формат: ${c.kinds.instagram}</p>
        <p class="small">Статус: ${igConnected ? '<span class="status success">Подключено</span>' : '<span class="status warning">Не подключено</span>'}</p>
        ${!igConnected ? '<button id="cwGoConnectionsIg" class="btn btn-ghost connection-btn-sm" type="button">Подключить</button>' : ''}
        ${selectField('cwKindIg', 'Тип', c.kinds.instagram, c.mode === 'image' ? [{ value: 'image_post', label: 'Пост с изображением' }] : (c.mode === 'video' ? [{ value: 'reel', label: 'Reel' }] : [{ value: 'image_post', label: 'Пост с изображением' }, { value: 'reel', label: 'Reel' }]))}
        ${selectField('cwAccIg', 'Instagram Business', c.accountRefs.instagram || '', metaReady.filter((m) => m.ig_user_id).map((m) => ({ value: m.ig_user_id, label: (m.instagram_username ? `@${m.instagram_username}` : 'IG Business') + (m.page_name ? ` · ${m.page_name}` : '') })))}
      </article>
      <article class="create-platform-card ${c.platforms.youtube ? 'active' : ''}">
        <div class="row" style="justify-content:space-between;align-items:center;"><strong>YouTube</strong><label class="create-toggle"><input id="cwYt" type="checkbox" ${c.platforms.youtube ? 'checked' : ''}/> Включить</label></div>
        <p class="small">Формат: ${c.kinds.youtube}</p>
        <p class="small">Статус: ${ytConnected ? '<span class="status success">Подключено</span>' : '<span class="status warning">Не подключено</span>'}</p>
        ${!ytConnected ? '<button id="cwGoConnectionsYt" class="btn btn-ghost connection-btn-sm" type="button">Подключить</button>' : ''}
        ${selectField('cwKindYt', 'Тип', c.kinds.youtube, [{ value: 'shorts', label: 'Shorts' }, { value: 'video', label: 'Видео' }])}
      </article>
    </div>
  `;

  const step3 = `
    <div class="wizard-step-note">Настройте генерацию медиа. Параметры сохраняются в черновик кампании.</div>
    ${(c.mode === 'image' || c.mode === 'both') ? `<article class="card" style="padding:14px;"><h3 style="margin-top:0;">Image</h3>${selectField('cwImageStyle', 'Стиль изображения', c.imageStyle || 'реалистично', [{ value: 'реалистично', label: 'Реалистично' }, { value: 'минимализм', label: 'Минимализм' }, { value: 'бизнес', label: 'Бизнес' }, { value: 'лайфстайл', label: 'Лайфстайл' }])}<label class="create-toggle"><input id="cwNoTextOnImage" type="checkbox" ${c.noTextOnImage !== false ? 'checked' : ''}/> Без текста на картинке</label></article>` : ''}
    ${(c.mode === 'video' || c.mode === 'both') ? `<article class="card" style="padding:14px;"><h3 style="margin-top:0;">Видео</h3>${selectField('cwDuration', 'Длительность', String(c.videoDuration || 30), [{ value: '20', label: '20 сек' }, { value: '30', label: '30 сек' }, { value: '40', label: '40 сек' }, { value: '60', label: '60 сек' }, { value: '120', label: '120 сек' }, { value: '240', label: '240 сек' }, { value: '480', label: '480 сек' }])}${selectField('cwRatio', 'Ориентация', c.videoAspectRatio || '9:16', [{ value: '9:16', label: '9:16' }, { value: '1:1', label: '1:1' }, { value: '16:9', label: '16:9' }])}${selectField('cwVideoStylePack', 'Стиль видео', c.videoStylePackId || 'default_pro', stylePackOptions)}<p class="small">Стиль ограничивает футажи и делает видео визуально единым.</p><p class="small"><span class="pill">Стиль: ${esc(selectedStylePack?.name || 'Default Pro')}</span></p><label class="create-toggle"><input id="cwNoFantasy" type="checkbox" ${c.noFantasy !== false ? 'checked' : ''}/> Без фантастических существ</label><label class="create-toggle"><input id="cwThumb" type="checkbox" ${c.generateThumbnail !== false ? 'checked' : ''}/> Генерировать обложку</label></article>` : ''}
  `;

  const cg = c.contentGeneration || {};
  const stage = String(cg.stage || 'idle');
  const stageClass = (name) => (stage === name ? 'active' : (['strategy', 'drafts', 'ready'].includes(stage) && ['strategy', 'drafts', 'ready'].indexOf(stage) > ['strategy', 'drafts', 'ready'].indexOf(name) ? 'done' : ''));
  const allDrafts = Array.isArray(cg.drafts) ? cg.drafts : [];
  const activePlatform = String(cg.activePlatform || 'facebook').toLowerCase();
  const platformLabels = { facebook: 'Facebook', instagram: 'Instagram', youtube: 'YouTube' };
  const platformTabs = ['facebook', 'instagram', 'youtube']
    .filter((platform) => !!c.platforms?.[platform])
    .map((platform) => `<button type="button" class="btn ${activePlatform === platform ? 'btn-primary' : 'btn-ghost'}" data-cw-draft-platform="${platform}">${platformLabels[platform]}</button>`)
    .join('');
  const draftsForActive = allDrafts
    .filter((d) => String(d.platform || '').toLowerCase() === activePlatform)
    .sort((a, b) => Number(a.variant || 0) - Number(b.variant || 0));
  const variantIds = [...new Set(draftsForActive.map((d) => Number(d.variant_index || d.variant || 1)).filter((v) => Number.isFinite(v)))];
  const activeVariant = Number(c.activeVariant || variantIds[0] || 1);
  const activeDraft = draftsForActive.find((d) => Number(d.variant_index || d.variant || 1) === activeVariant) || draftsForActive[0] || null;
  const goalOptions = [
    { value: 'sales', label: 'Продажи' },
    { value: 'awareness', label: 'Экспертность' },
    { value: 'announcement', label: 'Анонс' },
    { value: 'warmup', label: 'Прогрев' },
    { value: 'engagement', label: 'Вовлечение' },
    { value: 'lead', label: 'Лиды' },
  ];

  const renderPlatformPreviewText = () => {
    const text = String(previewText || '');
    if (previewPlatform === 'youtube') {
      const title = String(activeDraft?.title || c.topic || 'Название ролика');
      const desc = text.length > 520 ? `${text.slice(0, 520)}...` : text;
      return `<div class="preview-platform-block">
        <p class="small"><strong>Title:</strong> ${esc(title)}</p>
        <p class="small"><strong>Description:</strong></p>
        <p class="create-preview-text">${esc(desc || 'Описание появится после генерации.')}</p>
      </div>`;
    }
    if (previewPlatform === 'instagram') {
      const lines = text.split('\n').filter(Boolean);
      const first = lines.slice(0, 2).join('\n');
      const shortened = first.length > 180 ? `${first.slice(0, 180)}... more` : `${first}${lines.length > 2 ? '\n... more' : ''}`;
      return `<p class="create-preview-text">${esc(shortened || 'Подпись для Instagram появится после генерации.')}</p>`;
    }
    const shortened = text.length > 260 ? `${text.slice(0, 260)}... See more` : text;
    return `<p class="create-preview-text">${esc(shortened || 'Текст для Facebook появится после генерации.')}</p>`;
  };

  const localWarnings = [];
  if (previewPlatform === 'instagram' && String(c.caption || '').length > 2200) localWarnings.push('Слишком длинный текст для Instagram.');
  if (!String(c.cta || '').trim()) localWarnings.push('Нет призыва к действию.');
  if (!hashtags.length) localWarnings.push('Нет хештегов.');
  const checks = Array.isArray(c.quality?.checks) && c.quality.checks.length
    ? c.quality.checks
    : [
      { key: 'hook', label: 'Хук', state: 'yellow' },
      { key: 'structure', label: 'Структура', state: 'yellow' },
      { key: 'cta', label: 'Призыв к действию', state: 'yellow' },
      { key: 'hashtags', label: 'Хештеги', state: 'yellow' },
      { key: 'goal_match', label: 'Соответствие цели', state: 'yellow' },
    ];

  const strategyCard = cg.strategy
    ? `
      <article class="card content-ai-card">
        <h3 style="margin-top:0;">Стратегия</h3>
        <p class="small"><strong>Угол подачи:</strong> ${esc(cg.strategy.angle || '—')}</p>
        <p class="small"><strong>УТП:</strong> ${esc(cg.strategy.usp || '—')}</p>
        <p class="small"><strong>Аудитория:</strong> ${esc(cg.strategy.audience || '—')}</p>
        <p class="small"><strong>Хук:</strong> ${esc((cg.strategy.hook_ideas || [])[0] || '—')}</p>
        <p class="small"><strong>Призыв к действию:</strong> ${esc((cg.strategy.cta_variants || [])[0] || '—')}</p>
        <p class="small"><strong>Хештеги:</strong> ${esc(((cg.strategy.hashtag_sets || [])[0] || []).join(' ') || '—')}</p>
      </article>
    `
    : '';

  const assetsCard = cg.strategy
    ? `
      <article class="card content-ai-card">
        <h3 style="margin-top:0;">Assets</h3>
        <p class="small"><strong>Подписи без текста на картинке:</strong></p>
        <ul class="check-list">${((cg.strategy.visual_ideas || []).slice(0, 3)).map((idea) => `<li>${esc(idea)}</li>`).join('')}</ul>
      </article>
    `
    : '';

  const draftsCard = draftsForActive.length
    ? `
      <article class="card content-ai-card">
        <div class="row" style="justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
          <h3 style="margin:0;">Черновики ${esc(platformLabels[activePlatform] || activePlatform)}</h3>
          <div class="row" style="gap:8px;align-items:center;">${platformTabs}</div>
        </div>
        ${field('cwContentScheduleAt', 'Дата/время для Schedule', 'datetime-local', c.contentScheduleAt || '')}
        <div class="content-ai-drafts">
          ${draftsForActive.map((d) => `
            <article class="content-ai-draft-item">
              <div class="row" style="justify-content:space-between;align-items:center;">
                <strong>Вариант ${esc(String(d.variant || 1))}</strong>
                <span class="pill">${esc(platformLabels[activePlatform] || activePlatform)}</span>
              </div>
              ${(d.title || '').trim() ? `<p class="small"><strong>Title:</strong> ${esc(d.title)}</p>` : ''}
              <div class="small" style="white-space:pre-wrap;">${esc(d.post_text || d.description || '')}</div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
              <div class="cta-row" style="margin-top:10px;">
                <button type="button" class="btn btn-ghost" data-cw-copy-draft="${encodeURIComponent(String(d.post_text || d.description || ''))}">Копировать</button>
                <button type="button" class="btn btn-secondary" data-cw-save-draft="${Number(d.id || 0)}">Сохранить</button>
                <button type="button" class="btn btn-secondary" data-cw-schedule-draft="${Number(d.id || 0)}">Запланировать</button>
                <button type="button" class="btn btn-primary" data-cw-publish-draft="${Number(d.id || 0)}">Опубликовать</button>
              </div>
            </article>
          `).join('')}
        </div>
      </article>
    `
    : '';

  const step4 = `
    <div class="wizard-step-note">Студия контента: соберите бриф, сгенерируйте варианты и подготовьте финальный текст.</div>
    <div class="create-studio-mode">
      <button id="cwStudioQuick" type="button" class="btn ${c.studioMode === 'quick' ? 'btn-primary' : 'btn-ghost'}">Быстро</button>
      <button id="cwStudioPro" type="button" class="btn ${c.studioMode === 'pro' ? 'btn-primary' : 'btn-ghost'}">Профи</button>
    </div>
    <article class="card create-studio-card">
      <h3>Brief</h3>
      ${field('cwTopic', 'Тема/идея *', 'textarea', c.topic || '', 'Например: как сервису снизить стоимость привлечения клиента')}
      ${field('cwOffer', 'Цель/оффер', 'textarea', c.offer || '', 'Опционально: оффер, акция или продукт')}
      <div class="grid-2">
        ${selectField('cwAudienceType', 'Аудитория', c.audienceType || 'b2c', [{ value: 'b2c', label: 'B2C' }, { value: 'b2b', label: 'B2B' }])}
        ${field('cwAudienceSegment', 'Сегмент', 'text', c.audienceSegment || '', 'Например: владельцы малого бизнеса')}
      </div>
      <div class="grid-2">
        ${selectField('cwContentGoal', 'Цель контента', c.contentGoal || 'engagement', goalOptions)}
        ${selectField('cwContentFormat', 'Формат', c.contentFormat || 'post', [{ value: 'post', label: 'Пост' }, { value: 'reel', label: 'Reel' }, { value: 'video', label: 'Видео' }, { value: 'community', label: 'Сообщество' }])}
      </div>
      <div class="grid-2">
        ${selectField('cwContentTone', 'Тон', c.contentTone || 'friendly', [{ value: 'friendly', label: 'Дружелюбный' }, { value: 'expert', label: 'Экспертный' }, { value: 'sales', label: 'Продающий' }, { value: 'neutral', label: 'Нейтральный' }])}
        ${selectField('cwLang', 'Язык', c.language || 'ru', [{ value: 'ru', label: 'ru' }, { value: 'ua', label: 'ua' }, { value: 'de', label: 'de' }, { value: 'en', label: 'en' }])}
      </div>
      ${c.studioMode === 'pro' ? `${field('cwForbiddenTopics', 'Запрещенные темы', 'text', c.forbiddenTopics || '', 'Опционально: через запятую')}` : ''}
      <div class="cta-row">
        <button type="button" class="btn btn-ghost" data-cw-goal-shortcut="sales">Продажи</button>
        <button type="button" class="btn btn-ghost" data-cw-goal-shortcut="awareness">Экспертность</button>
        <button type="button" class="btn btn-ghost" data-cw-goal-shortcut="announcement">Анонс</button>
        <button type="button" class="btn btn-ghost" data-cw-goal-shortcut="warmup">Прогрев</button>
      </div>
    </article>
    <article class="card create-studio-card">
      <div class="row" style="justify-content:space-between;align-items:center;">
        <h3>AI Assist</h3>
        <button id="cwSuggestBtn" class="btn btn-secondary" type="button" ${c.aiAssist?.loading ? 'disabled' : ''}>${c.aiAssist?.loading ? 'Ищу варианты…' : 'Предложить варианты'}</button>
      </div>
      ${field('cwAssistHook', 'Хук', 'text', c.aiAssist?.hook || '', 'Короткая цепляющая фраза')}
      <label>Угол подачи</label>
      <div class="create-assist-list">${(c.aiAssist?.angles || []).map((a, i) => `<button type="button" class="btn btn-ghost" data-cw-angle="${i}">${esc(a)}</button>`).join('') || '<p class="small">Нажмите «Предложить варианты»</p>'}</div>
      <label>Варианты призыва к действию</label>
      <div class="create-assist-list">${(c.aiAssist?.ctaVariants || []).map((a, i) => `<button type="button" class="btn btn-ghost" data-cw-cta-variant="${i}">${esc(a)}</button>`).join('') || '<p class="small">Нажмите «Предложить варианты»</p>'}</div>
    </article>
    <article class="card create-studio-card">
      <div class="row" style="justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <h3 style="margin:0;">Черновики</h3>
        <div class="row" style="gap:8px;">${platformTabs || '<span class="small">Выберите платформу</span>'}</div>
      </div>
      <div class="row" style="gap:8px;flex-wrap:wrap;margin:8px 0;">${variantIds.map((v) => `<button type="button" class="btn ${activeVariant === v ? 'btn-primary' : 'btn-ghost'}" data-cw-variant="${v}">Variant ${v}</button>`).join('') || '<span class="small">Сначала сгенерируйте варианты</span>'}</div>
      ${cg.loading ? '<div class="create-skeleton-lines"><span></span><span></span><span></span></div>' : ''}
      ${(cg.error || '').trim() ? `<div class="notice error">${esc(cg.error)}</div>` : ''}
      <div class="content-ai-progress">
        <span class="pill ${stageClass('strategy')}">Стратегия</span>
        <span class="pill ${stageClass('drafts')}">Черновики</span>
        <span class="pill ${stageClass('ready')}">Готово</span>
      </div>
      <div class="cta-row">
        <button id="cwSmartGenerateBtn" class="btn btn-primary" type="button" ${cg.loading ? 'disabled' : ''}>${cg.loading ? 'Генерируем…' : 'Сгенерировать'}</button>
        <button id="cwABBtn" class="btn btn-secondary" type="button" ${cg.loading ? 'disabled' : ''}>Сделать A/B</button>
        ${cg.retryable ? '<button id="cwSmartRetryBtn" class="btn btn-ghost" type="button">Retry</button>' : ''}
      </div>
      ${field('cwCaption', 'Текст публикации', 'textarea', c.caption || (activeDraft?.post_text || ''), 'Основной текст публикации')}
      <div class="grid-2">
        ${field('cwCta', 'Призыв к действию', 'text', c.cta || (activeDraft?.cta || ''), 'Короткое действие для клиента')}
        ${selectField('cwRewriteStyle', 'Улучшить текст', c.rewriteStyle || 'короче', [{ value: 'короче', label: 'короче' }, { value: 'длиннее', label: 'длиннее' }, { value: 'более продающе', label: 'более продающе' }, { value: 'более экспертно', label: 'более экспертно' }, { value: 'больше эмоций', label: 'больше эмоций' }])}
      </div>
      ${field('cwHashtags', 'Хештеги', 'textarea', hashtags.join(' '), '#бизнес #контент #маркетинг')}
      <div class="cta-row">
        <button id="cwRewriteBtn" class="btn btn-ghost" type="button">Улучшить текст</button>
        <button id="cwSaveTemplateBtn" class="btn btn-ghost" type="button">Сохранить как шаблон</button>
      </div>
      <div class="row" style="gap:8px;flex-wrap:wrap;">
        ${(c.templates || []).map((t) => `<button type="button" class="btn btn-ghost" data-cw-apply-template="${Number(t.id)}">${esc(t.name)}</button><button type="button" class="btn btn-ghost" data-cw-del-template="${Number(t.id)}">?</button>`).join('') || '<span class="small">Мои шаблоны пока пусты.</span>'}
      </div>
    </article>
    ${strategyCard}
    ${assetsCard}
  `;

  const step5 = `
    <div class="wizard-step-note">Генерация и предпросмотр ассетов.</div>
    <div class="cta-row">
      ${(c.mode === 'image' || c.mode === 'both') ? `<button id="cwGenerateImage" class="btn btn-primary" type="button" ${running ? 'disabled' : ''}>${running ? 'Генерируем…' : 'Сгенерировать image'}</button>` : ''}
      ${(c.mode === 'video' || c.mode === 'both') ? `<button id="cwGenerateVideo" class="btn btn-secondary" type="button" ${running ? 'disabled' : ''}>${running ? 'Генерируем…' : 'Сгенерировать video'}</button>` : ''}
    </div>
    ${(c.generation?.statusText || '').trim() ? `<p class="small">${esc(c.generation.statusText)}</p>` : ''}
    <div class="create-asset-grid">
      <article class="card" style="padding:12px;"><h3 style="margin-top:0;">Изображение</h3>${imageAsset ? `<img class="create-asset-image" src="${esc(imageAsset.storage_url)}" alt="" />` : '<p class="small">Изображение не сгенерировано</p>'}</article>
      <article class="card" style="padding:12px;"><h3 style="margin-top:0;">Видео</h3><p class="small"><span class="pill">Стиль: ${esc(selectedStylePack?.name || 'Default Pro')}</span></p>${videoAsset ? `<video class="create-asset-video" controls preload="metadata" src="${esc(videoAsset.storage_url)}"></video><p class="small">${esc(String(videoAsset.duration_sec || c.videoDuration || 0))} сек</p>` : '<p class="small">Видео не сгенерировано</p>'}</article>
      ${thumbAsset ? `<article class="card" style="padding:12px;"><h3 style="margin-top:0;">Thumbnail</h3><img class="create-asset-image" src="${esc(thumbAsset.storage_url)}" alt="" /></article>` : ''}
    </div>
  `;

  const deliveryRows = (Array.isArray(c.deliveries) ? c.deliveries : []).map((d) => `<tr><td>${esc(d.platform)}</td><td>${esc(d.kind)}</td><td>${esc(d.status)}</td><td>${esc(d.error_message || d.remote_id || '—')}</td></tr>`).join('');
  const step6Platform = String(c.previewPlatform || (selectedCampaignPlatforms()[0] || 'facebook')).toLowerCase();
  const step6Kind = (c.kinds && c.kinds[step6Platform]) ? c.kinds[step6Platform] : (step6Platform === 'youtube' ? 'shorts' : 'image_post');
  const step6YtVariantTabs = step6Platform === 'youtube'
    ? `<div class="row" style="gap:8px;flex-wrap:wrap;">
      <button type="button" class="btn ${step6Kind === 'shorts' ? 'btn-secondary' : 'btn-ghost'}" data-cw-preview-yt-kind="shorts">Shorts</button>
      <button type="button" class="btn ${step6Kind === 'video' ? 'btn-secondary' : 'btn-ghost'}" data-cw-preview-yt-kind="video">Видео</button>
    </div>`
    : '';
  const step6PreviewPayload = buildPreviewPayloadFromCreateCampaign(step6Platform, step6Kind);
  const step6Checks = validatePreviewLocal(step6PreviewPayload);
  const step6WarningsHtml = (step6Checks.warnings || []).map((w) => `<li class="${w.level === 'error' ? 'bad' : ''}">${esc(w.message || w.code || '')}</li>`).join('');
  const step6 = `
    <div class="wizard-step-note">Публикация и очередь.</div>
    ${selectField('cwPublishMode', 'Режим', c.publishMode || 'now', [{ value: 'now', label: 'Опубликовать сейчас' }, { value: 'schedule', label: 'Запланировать' }, { value: 'draft', label: 'Сохранить черновик' }])}
    ${c.publishMode === 'schedule' ? field('cwScheduleAt', 'Дата и время', 'datetime-local', c.scheduledAt || '') : ''}
    <div class="row" style="gap:8px;flex-wrap:wrap;">
      <button type="button" class="btn ${step6Platform === 'facebook' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview-tab="facebook">Facebook</button>
      <button type="button" class="btn ${step6Platform === 'instagram' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview-tab="instagram">Instagram</button>
      <button type="button" class="btn ${step6Platform === 'youtube' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview-tab="youtube">YouTube</button>
    </div>
    ${step6YtVariantTabs}
    ${renderSocialPreview(step6PreviewPayload)}
    <article class="card glass-card" style="padding:12px;margin-top:10px;">
      <h3 style="margin-top:0;">Проверка перед публикацией</h3>
      <div class="create-quality-score">${step6Checks.score}<span>/100</span></div>
      <ul class="check-list">${step6WarningsHtml || '<li class="done">Ошибок не найдено</li>'}</ul>
      <div class="cta-row">
        <button id="cwAutoFixShorten" type="button" class="btn btn-ghost">Сократить текст</button>
        <button id="cwAutoFixTags" type="button" class="btn btn-ghost">Добавить хештеги</button>
        <button id="cwAutoFixCta" type="button" class="btn btn-ghost">Сгенерировать призыв</button>
      </div>
    </article>
    ${(c.publishMessage || '').trim() ? `<p class="small">${esc(c.publishMessage)}</p>` : ''}
    ${deliveryRows ? `<div class="table-wrap"><table><thead><tr><th>Платформа</th><th>Тип</th><th>Статус</th><th>Сообщение</th></tr></thead><tbody>${deliveryRows}</tbody></table></div>` : ''}
  `;
  const stepContent = [step1, step2, step3, step4, step5, step6][(c.step || 1) - 1] || step1;

  const previewCard = `
    <article class="create-preview-card">
      <div class="row" style="justify-content:space-between;align-items:center;"><span class="pill">${esc(previewPlatformLabel)}</span><span class="small">${esc(projectName)}</span></div>
            <p class="small muted" style="margin-top:8px;">\u0420\u0430\u0431\u043e\u0447\u0435\u0435 \u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0441\u0442\u0432\u043e \u2014 \u043e\u0431\u044b\u0447\u043d\u043e \u043e\u0434\u0438\u043d \u0431\u0440\u0435\u043d\u0434 \u0438\u043b\u0438 \u043e\u0434\u0438\u043d \u043a\u043b\u0438\u0435\u043d\u0442.</p>
        <button type="button" class="btn ${previewPlatform === 'facebook' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview="facebook">Facebook</button>
        <button type="button" class="btn ${previewPlatform === 'instagram' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview="instagram">Instagram</button>
        <button type="button" class="btn ${previewPlatform === 'youtube' ? 'btn-primary' : 'btn-ghost'}" data-cw-preview="youtube">YouTube</button>
      </div>
      <h3>${esc(c.topic || 'Опишите тему')}</h3>
      ${renderPlatformPreviewText()}
      <div class="create-preview-tags">${hashtags.map((h) => `<span class="pill">${esc(h)}</span>`).join('')}</div>
      <button class="btn btn-secondary create-preview-cta" type="button">${esc(c.cta || 'Оставить заявку')}</button>
      ${localWarnings.length ? `<div class="notice error" style="margin-top:10px;">${localWarnings.map((w) => esc(w)).join('<br/>')}</div>` : ''}
    </article>
  `;
  const infoCard = `
    <article class="create-info-card">
      <h3>Проверка качества</h3>
      <div class="create-quality-score">${Number(c.quality?.score || 0)}<span>/100</span></div>
      <ul class="check-list">${checks.map((it) => `<li class="${it.state === 'green' ? 'done' : (it.state === 'red' ? 'bad' : '')}">${esc(it.label)}</li>`).join('')}</ul>
      ${(c.quality?.warnings || []).length ? `<p class="small">${(c.quality.warnings || []).map((w) => esc(w)).join(' · ')}</p>` : ''}
    </article>
  `;
  const stickyDisabled = !(String(c.topic || '').trim() && String(c.caption || '').trim() && selectedCampaignPlatforms().length);

  return appLayout('/create', 'Создать', `
    <section class="create-wizard-shell">
      <div class="create-wizard-grid">
        <article class="card create-main-col">
          <h2>Студия контента</h2>
          <p class="small">Соберите бриф, получите варианты от AI и отправьте публикацию в очередь.</p>
          <div class="create-progress-badge">Шаг ${c.step || 1} из 6 · ~${Math.max(1, 7 - (c.step || 1))} минут до готового поста</div>
          <div class="stepper stepper-6">${steps.map((label, idx) => `<div class="step ${(c.step || 1) === (idx + 1) ? 'active' : ''}">${idx + 1}. ${esc(label)}</div>`).join('')}</div>
          <h3 class="create-step-title">${esc(steps[(c.step || 1) - 1] || 'Шаг')}</h3>
          ${stepContent}
          <div class="cta-row create-wizard-actions">
            ${c.step > 1 ? '<button id="cwPrev" type="button" class="btn btn-ghost">Назад</button>' : ''}
            ${c.step < 6 ? '<button id="cwNext" type="button" class="btn btn-primary">Далее</button>' : '<button id="cwSubmitPublish" type="button" class="btn btn-primary">Подтвердить</button>'}
          </div>
          <details class="create-mobile-preview"><summary>Предпросмотр</summary><div class="create-mobile-preview-content">${previewCard}${infoCard}</div></details>
        </article>
        <aside class="create-preview-col">${previewCard}${infoCard}</aside>
      </div>
      <div class="create-sticky-bar">
        <button id="cwStickySave" type="button" class="btn btn-secondary" ${stickyDisabled ? 'disabled' : ''}>Сохранить черновик</button>
        <button id="cwStickySchedule" type="button" class="btn btn-ghost" ${stickyDisabled ? 'disabled' : ''}>Запланировать</button>
        <button id="cwStickyPublish" type="button" class="btn btn-primary" ${stickyDisabled ? 'disabled' : ''}>Опубликовать</button>
      </div>
    </section>
  `);
}

function pageCampaignDetailsV2() {
  const detail = state.campaignDetails;
  if (!detail?.campaign) return appLayout('/campaigns', 'Кампания', `<section class="card">${emptyState('Кампания не найдена', 'Ссылка устарела или кампания удалена.', 'Открыть создание', '/create')}</section>`);
  const c = detail.campaign;
  const deliveries = detail.deliveries || [];
  const assets = detail.assets || [];
  return appLayout(`/campaigns/${c.id}`, 'Кампания', `
    <section class="grid-2">
      <article class="card"><h2>Кампания #${c.id}</h2><p class="small">Тема: <strong>${esc(c.topic || '—')}</strong></p><p class="small">Режим: ${esc(c.mode)} · Статус: ${esc(c.status)}</p><div class="cta-row"><button class="btn btn-primary" data-link="/create">Создать ещё</button><button class="btn btn-ghost" data-link="/history">Открыть историю</button></div></article>
      <article class="card"><h2>Ассеты</h2>${assets.length ? `<ul class="check-list">${assets.map((a) => `<li>${esc(a.type)} · <a href="${esc(a.storage_url)}" target="_blank" rel="noreferrer">Открыть</a></li>`).join('')}</ul>` : '<p class="small">Ассеты пока отсутствуют.</p>'}</article>
      <article class="card" style="grid-column:1 / -1;"><h2>Deliveries</h2>${deliveries.length ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Платформа</th><th>Формат</th><th>Статус</th><th>Remote ID</th><th>Ошибка</th></tr></thead><tbody>${deliveries.map((d) => `<tr><td>${d.id}</td><td>${esc(d.platform)}</td><td>${esc(d.kind)}</td><td>${esc(d.status)}</td><td>${esc(d.remote_id || '—')}</td><td>${esc(d.error_message || '—')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="small">Deliveries ещё не созданы.</p>'}</article>
    </section>
  `);
}

function adminUsersTable() {
  if (!state.adminUsers.length) return '<p class="small">Р—Р°РіСЂСѓР·РёС‚Рµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РґР»СЏ РїСЂРѕСЃРјРѕС‚СЂР°.</p>';
  return `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Email</th><th>Р РѕР»СЊ</th><th>РўР°СЂРёС„</th><th>РљСЂРµРґРёС‚С‹</th><th>Р‘РёР»Р»РёРЅРі</th><th>РЎРѕР·РґР°РЅ</th></tr></thead><tbody>${state.adminUsers.map((u)=>`<tr><td>${u.id}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td><td>${planBadge(u.role === 'admin' ? 'admin' : u.plan)}</td><td>${u.credits_left}</td><td>${esc(u.billing_status || 'вЂ”')}</td><td>${new Date(u.created_at).toLocaleDateString()}</td></tr>`).join('')}</tbody></table></div>`;
}

function pageAdmin() {
  if (state.user?.role !== 'admin') return appLayout('/admin','РђРґРјРёРЅ',emptyState('Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰РµРЅ','РўСЂРµР±СѓРµС‚СЃСЏ СЂРѕР»СЊ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°.','РќР°Р·Р°Рґ РЅР° РїР°РЅРµР»СЊ','/dashboard'));
  const revenue = state.adminRevenue ? `<p class="small">РўРѕРєРµРЅС‹: ${state.adminRevenue.tokens_total} В· OpenAI: в‚¬${state.adminRevenue.estimated_openai_cost_eur} В· Stripe: в‚¬${state.adminRevenue.stripe_revenue_eur} В· РњР°СЂР¶Р°: ${state.adminRevenue.margin_percent}%</p>` : '<p class="small">Р—Р°РіСЂСѓР·РёС‚Рµ РїР°РЅРµР»СЊ РІС‹СЂСѓС‡РєРё.</p>';
  return appLayout('/admin','РђРґРјРёРЅ',`<section class="grid-2"><article class="card"><h2>РџРѕР»СЊР·РѕРІР°С‚РµР»Рё</h2><button id="adminUsersBtn" class="btn btn-primary">Р—Р°РіСЂСѓР·РёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№</button><div style="margin-top:10px;">${adminUsersTable()}</div></article><article class="card"><h2>РўР°СЂРёС„С‹ Рё РєСЂРµРґРёС‚С‹</h2>${field('adminUserId','ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ')}${selectField('adminPlan','РўР°СЂРёС„','free',[{value:'free',label:'Free Trial'},{value:'starter',label:'Starter'},{value:'growth',label:'Growth'},{value:'agency',label:'Agency'}])}${field('adminDelta','Р·РјРµРЅРµРЅРёРµ РєСЂРµРґРёС‚РѕРІ','number','0')}<div class="cta-row"><button id="adminSetPlanBtn" class="btn btn-secondary">РЈСЃС‚Р°РЅРѕРІРёС‚СЊ С‚Р°СЂРёС„</button><button id="adminCreditsBtn" class="btn btn-ghost">Р·РјРµРЅРёС‚СЊ РєСЂРµРґРёС‚С‹</button></div></article><article class="card"><h2>РџР°РЅРµР»СЊ РІС‹СЂСѓС‡РєРё</h2>${revenue}<button id="adminRevenueBtn" class="btn btn-primary">РћР±РЅРѕРІРёС‚СЊ РІС‹СЂСѓС‡РєСѓ</button></article><article class="card"><h2>Р”РµР№СЃС‚РІРёСЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°</h2><div class="cta-row"><button id="adminGenBlogBtn" class="btn btn-secondary">РЎРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ СЃС‚Р°С‚СЊСЋ</button><button id="adminRunPlanBtn" class="btn btn-ghost">Р—Р°РїСѓСЃС‚РёС‚СЊ РєРѕРЅС‚РµРЅС‚-РїР»Р°РЅ</button></div></article></section>`);
}

function page(path) {
  const planner = getCreatePlannerRoute(path);
  if (planner) return pageCreatePlanner(planner);
  if (String(path || '').startsWith('/campaigns/')) return pageCampaignDetailsV2();
  const routes = { '/login': pageLogin, '/dashboard': pageDashboard, '/create': pageCreateDirector, '/calendar': pageCalendar, '/youtube': pageYouTubeStudio, '/connections': pageConnections, '/history': pageHistory, '/billing': pageBilling, '/settings': pageSettings, '/admin': pageAdmin, '/blog': pageBlog, '/contact': pageContact, '/support': pageSupport };
  return (routes[path] || pageDashboard)();
}

async function loadDashboardMetrics(days = 30) {
  const safe = async (url, fallback) => {
    try {
      const data = await api(url);
      return data ?? fallback;
    } catch {
      return fallback;
    }
  };
  const forecastHorizon = Number(state.dashboardMetrics?.forecastHorizon || 7) >= 30 ? 30 : 7;
  const [summary, timeseries, aiScore, insights, recent] = await Promise.all([
    safe(`/api/dashboard/summary?days=${Number(days) || 30}`, null),
    safe(`/api/dashboard/timeseries?days=${Number(days) || 30}`, { points: [] }),
    safe(`/api/dashboard/ai-score?days=${Number(days) || 30}`, { current: 0, delta_7d: 0, breakdown: null, timeseries: [] }),
    safe(`/api/dashboard/insights?days=${Number(days) || 30}`, { insights: [] }),
    safe('/api/dashboard/recent?limit=20', { items: [] }),
  ]);
  const forecast = await safe(`/api/dashboard/forecast?horizon=${forecastHorizon}&days=90`, { horizon_days: forecastHorizon, confidence: { level: 'low', reasons: ['недостаточно данных'] }, totals: { reach: 0, views: 0, engagement_rate_avg: 0 }, points: [], scenarios: { current: {}, plus30: {} } });
  state.dashboardMetrics = {
    ...(state.dashboardMetrics || {}),
    summary: summary || null,
    timeseries: timeseries || { points: [] },
    aiScore: aiScore || { current: 0, delta_7d: 0, breakdown: null, timeseries: [] },
    forecast: forecast || { horizon_days: forecastHorizon, confidence: { level: 'low', reasons: ['недостаточно данных'] }, totals: { reach: 0, views: 0, engagement_rate_avg: 0 }, points: [], scenarios: { current: {}, plus30: {} } },
    insights: (insights && insights.insights) || [],
    recent: (recent && recent.items) || [],
    chartMetric: state.dashboardMetrics?.chartMetric || 'reach',
    recentSort: state.dashboardMetrics?.recentSort || 'engagement',
    loading: false,
  };
}

async function preload(path) {
  if (path === '/blog') {
    state.blog = await api('/api/blog/posts');
    return;
  }
  if (!state.token) return;
  if (path === '/connections') {
    state.connections = await api('/api/connections');
    state.youtubeConnection = await api('/api/integrations/youtube/status');
  }
  if (String(path || '').startsWith('/create')) {
    state.connections = await api('/api/connections');
    state.youtubeConnection = await api('/api/integrations/youtube/status');
    const campaigns = await api('/api/campaigns?limit=10');
    state.campaignList = campaigns?.items || [];
    if (!state.createCampaign?.stylePacksLoaded) {
      try {
        const styleData = await api('/api/video/style-packs');
        state.createCampaign.stylePacks = Array.isArray(styleData?.items) ? styleData.items : [];
        state.createCampaign.videoStylePackId = String(styleData?.default_style_pack || state.createCampaign.videoStylePackId || 'default_pro');
        state.createCampaign.stylePacksLoaded = true;
      } catch {
        state.createCampaign.stylePacks = Array.isArray(state.createCampaign.stylePacks) ? state.createCampaign.stylePacks : [];
        state.createCampaign.videoStylePackId = String(state.createCampaign.videoStylePackId || 'default_pro');
        state.createCampaign.stylePacksLoaded = true;
      }
    }
    if (!state.createCampaign?.templatesLoaded) {
      try {
        const out = await api('/api/create/templates');
        state.createCampaign.templates = Array.isArray(out?.items) ? out.items : [];
        state.createCampaign.templatesLoaded = true;
      } catch {
        state.createCampaign.templates = Array.isArray(state.createCampaign.templates) ? state.createCampaign.templates : [];
        state.createCampaign.templatesLoaded = true;
      }
    }
  }
  if (String(path || '').startsWith('/campaigns/')) {
    const campaignId = Number(String(path).split('/')[2] || 0);
    if (campaignId > 0) state.campaignDetails = await api(`/api/campaigns/${campaignId}`);
  }
  if (path === '/history' || path === '/calendar') state.posts = await api('/api/posts');
  if (path === '/billing' || path === '/dashboard') state.plans = await api('/api/plans');
  if (path === '/dashboard') {
    state.connections = await api('/api/connections');
    state.youtubeConnection = await api('/api/integrations/youtube/status');
    state.posts = await api('/api/posts');
    state.dashboardMetrics = {
      ...(state.dashboardMetrics || {}),
      loading: true,
      aiScore: state.dashboardMetrics?.aiScore || { current: 0, delta_7d: 0, delta_vs_prev_period: 0, breakdown: null, timeseries: [] },
      forecast: state.dashboardMetrics?.forecast || { horizon_days: 7, confidence: { level: 'low', reasons: [] }, totals: { reach: 0, views: 0, engagement_rate_avg: 0 }, points: [], scenarios: { current: {}, plus30: {} } },
      forecastHorizon: state.dashboardMetrics?.forecastHorizon || 7,
      aiBreakdownOpen: !!state.dashboardMetrics?.aiBreakdownOpen,
    };
    await loadDashboardMetrics(30);
  }
  if (path === '/admin' && state.user?.role === 'admin') { state.adminUsers = await api('/api/admin/users'); state.adminRevenue = await api('/api/admin/revenue'); }
}
async function loadBase() { state.user = await api('/api/me'); state.billing = state.user.billing; state.projects = await api('/api/projects'); }
function bindCommon() {
  const sidebarLogoutBtn = document.getElementById('sidebarLogoutBtn');
  if (sidebarLogoutBtn) sidebarLogoutBtn.onclick = () => { state.token = ''; localStorage.removeItem('token'); state.user = null; nav('/login'); };
  const themeToggle = document.getElementById('themeToggleBtn');
  if (themeToggle) themeToggle.onclick = () => { setTheme(state.theme === 'dark' ? 'light' : 'dark'); render(); };
  const siteLangSelect = document.getElementById('siteLangSelect');
  if (siteLangSelect && !siteLangSelect.dataset.boundAppLang) {
    siteLangSelect.dataset.boundAppLang = '1';
    siteLangSelect.addEventListener('change', () => {
      const siteLang = String(siteLangSelect.value || '').trim();
      setLanguage(siteLang, { persist: true });
    });
  }
}

async function bindCreateWizardV2(path) {
  if (path !== '/create') {
    if (window.__campaignAutosaveTimer) clearInterval(window.__campaignAutosaveTimer);
    if (window.__campaignDeliveriesPoller) clearInterval(window.__campaignDeliveriesPoller);
    return;
  }
  hydrateCampaignDefaults();
  const c = state.createCampaign;
  if (!window.__campaignHydratedOnce) {
    const saved = loadCampaignDraftLocal();
    if (saved && typeof saved === 'object') state.createCampaign = { ...state.createCampaign, ...saved };
    window.__campaignHydratedOnce = true;
  }
  syncCampaignKindsByMode();
  if (window.__campaignAutosaveTimer) clearInterval(window.__campaignAutosaveTimer);
  window.__campaignAutosaveTimer = setInterval(async () => {
    try {
      if (location.pathname.replace(/\/$/, '') !== '/create') return;
      if (!state.createCampaign.dirty) return;
      await ensureCampaignSaved();
    } catch {}
  }, 2500);
  const update = (patch) => {
    state.createCampaign = { ...state.createCampaign, ...patch, dirty: true };
    saveCampaignDraftLocal();
  };
  const readLocalForm = () => {
    update({
      topic: document.getElementById('cwTopic')?.value || state.createCampaign.topic || '',
      offer: document.getElementById('cwOffer')?.value || state.createCampaign.offer || '',
      projectId: document.getElementById('cwProject')?.value || state.createCampaign.projectId || '',
      language: document.getElementById('cwLang')?.value || state.createCampaign.language || 'ru',
      studioMode: document.getElementById('cwStudioMode')?.value || state.createCampaign.studioMode || 'quick',
      caption: document.getElementById('cwCaption')?.value || state.createCampaign.caption || '',
      cta: document.getElementById('cwCta')?.value || state.createCampaign.cta || '',
      hashtags: parseCampaignHashtags(document.getElementById('cwHashtags')?.value || (state.createCampaign.hashtags || []).join(' ')),
      contentTone: document.getElementById('cwContentTone')?.value || state.createCampaign.contentTone || 'friendly',
      contentGoal: document.getElementById('cwContentGoal')?.value || state.createCampaign.contentGoal || 'engagement',
      contentFormat: document.getElementById('cwContentFormat')?.value || state.createCampaign.contentFormat || 'post',
      audienceType: document.getElementById('cwAudienceType')?.value || state.createCampaign.audienceType || 'b2c',
      audienceSegment: document.getElementById('cwAudienceSegment')?.value || state.createCampaign.audienceSegment || '',
      forbiddenTopics: document.getElementById('cwForbiddenTopics')?.value || state.createCampaign.forbiddenTopics || '',
      rewriteStyle: document.getElementById('cwRewriteStyle')?.value || state.createCampaign.rewriteStyle || 'короче',
      contentVariants3: !!document.getElementById('cwVariants3')?.checked,
      contentScheduleAt: document.getElementById('cwContentScheduleAt')?.value || state.createCampaign.contentScheduleAt || '',
      publishMode: document.getElementById('cwPublishMode')?.value || state.createCampaign.publishMode || 'now',
      scheduledAt: document.getElementById('cwScheduleAt')?.value || state.createCampaign.scheduledAt || '',
      imageStyle: document.getElementById('cwImageStyle')?.value || state.createCampaign.imageStyle || 'реалистично',
      videoDuration: Number(document.getElementById('cwDuration')?.value || state.createCampaign.videoDuration || 30),
      videoAspectRatio: document.getElementById('cwRatio')?.value || state.createCampaign.videoAspectRatio || '9:16',
      videoStylePackId: document.getElementById('cwVideoStylePack')?.value || state.createCampaign.videoStylePackId || 'default_pro',
      noTextOnImage: !!document.getElementById('cwNoTextOnImage')?.checked,
      noFantasy: !!document.getElementById('cwNoFantasy')?.checked,
      generateThumbnail: !!document.getElementById('cwThumb')?.checked,
      kinds: {
        facebook: document.getElementById('cwKindFb')?.value || state.createCampaign.kinds.facebook,
        instagram: document.getElementById('cwKindIg')?.value || state.createCampaign.kinds.instagram,
        youtube: document.getElementById('cwKindYt')?.value || state.createCampaign.kinds.youtube,
      },
      accountRefs: {
        facebook: document.getElementById('cwAccFb')?.value || state.createCampaign.accountRefs.facebook || '',
        instagram: document.getElementById('cwAccIg')?.value || state.createCampaign.accountRefs.instagram || '',
        youtube: state.youtubeConnection?.channel_id || '',
      },
      aiAssist: {
        ...(state.createCampaign.aiAssist || {}),
        hook: document.getElementById('cwAssistHook')?.value || state.createCampaign.aiAssist?.hook || '',
        angles: String(document.getElementById('cwAssistAngles')?.value || (state.createCampaign.aiAssist?.angles || []).join(' | '))
          .split('|').map((x) => x.trim()).filter(Boolean).slice(0, 3),
        ctaVariants: String(document.getElementById('cwAssistCtas')?.value || (state.createCampaign.aiAssist?.ctaVariants || []).join(' | '))
          .split('|').map((x) => x.trim()).filter(Boolean).slice(0, 3),
      },
    });
    syncCampaignKindsByMode();
  };

  const validateStep = (step) => {
    const w = state.createCampaign;
    if (step === 1 && !String(w.topic || '').trim()) return 'Укажите тему/идею.';
    if (step === 2) {
      const platforms = selectedCampaignPlatforms();
      if (!platforms.length) return 'Выберите минимум одну платформу.';
      if (w.platforms.youtube && !state.youtubeConnection?.connected) return 'YouTube не подключен. Откройте Подключения.';
      const metaReady = (state.connections || []).filter((m) => isConnectionReady(m));
      if (w.platforms.facebook && !metaReady.some((m) => !!m.page_id)) return 'Для Facebook нет подключенной страницы.';
      if (w.platforms.instagram && !metaReady.some((m) => !!m.ig_user_id)) return 'Для Instagram нет IG Business подключения.';
      if (w.mode === 'image' && w.platforms.youtube) return 'В режиме image публикация в YouTube недоступна.';
    }
    return '';
  };

  const computePublishPreview = () => {
    const c = state.createCampaign;
    const platform = String(c.previewPlatform || selectedCampaignPlatforms()[0] || 'facebook').toLowerCase();
    const kind = (c.kinds && c.kinds[platform]) ? c.kinds[platform] : (platform === 'youtube' ? 'shorts' : 'image_post');
    const payload = buildPreviewPayloadFromCreateCampaign(platform, kind);
    const checks = validatePreviewLocal(payload);
    return { payload, checks, platform, kind };
  };

  const ensurePreviewBeforePublish = async () => {
    const { checks } = computePublishPreview();
    const all = Array.isArray(checks.warnings) ? checks.warnings : [];
    const errors = all.filter((x) => String(x.level || '').toLowerCase() === 'error');
    if (errors.length) {
      throw new Error(errors.map((x) => x.message || x.code || 'Ошибка предпросмотра').join(' '));
    }
    if (all.length) {
      const msg = `Есть предупреждения перед публикацией:\n- ${all.map((x) => x.message || x.code || '').join('\n- ')}\n\nПродолжить публикацию?`;
      if (!window.confirm(msg)) throw new Error('Публикация отменена.');
    }
    return checks;
  };

  const selectedContentPlatforms = () => {
    const p = state.createCampaign.platforms || {};
    const out = [];
    if (p.facebook) out.push('facebook');
    if (p.instagram) out.push('instagram');
    if (p.youtube) out.push('youtube');
    return out;
  };

  const applyFirstDraftToCampaign = () => {
    const cg = state.createCampaign.contentGeneration || {};
    const drafts = Array.isArray(cg.drafts) ? cg.drafts : [];
    if (!drafts.length) return;
    const targetPlatform = String(cg.activePlatform || '').trim().toLowerCase();
    const first = drafts.find((d) => String(d.platform || '').toLowerCase() === targetPlatform) || drafts[0];
    if (!first) return;
    const text = String(first.post_text || '').trim();
    const cta = String(first.cta || '').trim();
    const hashtags = Array.isArray(first.hashtags) ? first.hashtags : [];
    if (text) state.createCampaign.caption = text;
    if (cta) state.createCampaign.cta = cta;
    if (hashtags.length) state.createCampaign.hashtags = parseCampaignHashtags(hashtags.join(' '));
    state.createCampaign.dirty = true;
  };

  const runSmartContentGeneration = async () => {
    readLocalForm();
    const c = state.createCampaign;
    if (!String(c.topic || '').trim()) throw new Error('Поле "Тема/идея" обязательно.');
    const platforms = selectedContentPlatforms();
    if (!platforms.length) throw new Error('Выберите хотя бы одну платформу.');

    c.contentGeneration = {
      ...(c.contentGeneration || {}),
      loading: true,
      stage: 'strategy',
      error: '',
      retryable: false,
      drafts: [],
      strategy: null,
    };
    render();

    try {
      await new Promise((r) => setTimeout(r, 80));
      const payload = {
        mode: c.studioMode || 'quick',
        topic: String(c.topic || '').trim(),
        offer: String(c.offer || '').trim() || null,
        language: c.language || 'ru',
        tone: c.contentTone || 'friendly',
        goal: c.contentGoal || 'engagement',
        platforms,
        variants: c.studioMode === 'quick' ? 1 : (c.contentVariants3 ? 3 : 2),
      };
      const generated = await api('/api/create/generate', {
        method: 'POST',
        body: JSON.stringify(payload),
        timeoutMs: 180000,
      });
      c.contentGeneration.stage = 'drafts';
      render();
      await new Promise((r) => setTimeout(r, 80));
      const drafts = Array.isArray(generated?.drafts) ? generated.drafts : [];
      const activePlatform = platforms.includes(c.contentGeneration.activePlatform)
        ? c.contentGeneration.activePlatform
        : platforms[0];
      c.contentGeneration = {
        loading: false,
        stage: 'ready',
        error: '',
        retryable: false,
        briefId: generated?.brief_id || null,
        strategy: generated?.strategy || null,
        drafts,
        activePlatform: activePlatform || 'facebook',
      };
      c.quality = {
        score: Number(generated?.quality?.score || 0),
        checks: Array.isArray(generated?.quality?.checks) ? generated.quality.checks : [],
        warnings: Array.isArray(generated?.warnings) ? generated.warnings : (Array.isArray(generated?.quality?.warnings) ? generated.quality.warnings : []),
      };
      c.contentGeneration.debugCode = generated?.debug_code || '';
      applyFirstDraftToCampaign();
      render();
    } catch (e) {
      c.contentGeneration = {
        ...(c.contentGeneration || {}),
        loading: false,
        stage: 'error',
        error: e.message || 'Ошибка генерации контента',
        retryable: true,
      };
      render();
    }
  };

  const runQualityCheck = async () => {
    readLocalForm();
    const c = state.createCampaign;
    const out = await api('/api/create/quality-check', {
      method: 'POST',
      body: JSON.stringify({
        caption: c.caption || '',
        cta: c.cta || '',
        hashtags: c.hashtags || [],
        goal: c.contentGoal || 'engagement',
      }),
    });
    const q = out?.quality || {};
    c.quality = {
      score: Number(q.score || 0),
      checks: Array.isArray(q.checks) ? q.checks : [],
      warnings: Array.isArray(q.warnings) ? q.warnings : [],
    };
    c.dirty = true;
    render();
  };

  const runSuggest = async () => {
    readLocalForm();
    const c = state.createCampaign;
    if (!String(c.topic || '').trim()) throw new Error('Введите тему/идею');
    c.aiAssist = { ...(c.aiAssist || {}), loading: true };
    render();
    const out = await api('/api/create/suggest', {
      method: 'POST',
      body: JSON.stringify({
        topic: c.topic || '',
        offer: c.offer || '',
        goal: c.contentGoal || 'engagement',
        tone: c.contentTone || 'friendly',
        language: c.language || 'ru',
      }),
    });
    const s = out?.suggestions || {};
    c.aiAssist = {
      loading: false,
      hook: String(s.hook || ''),
      angles: Array.isArray(s.angles) ? s.angles : [],
      ctaVariants: Array.isArray(s.cta_variants) ? s.cta_variants : [],
    };
    if (!c.cta && c.aiAssist.ctaVariants?.[0]) c.cta = c.aiAssist.ctaVariants[0];
    c.dirty = true;
    render();
  };

  const runRewrite = async () => {
    readLocalForm();
    const c = state.createCampaign;
    if (!String(c.caption || '').trim()) throw new Error('Введите текст для улучшения');
    const out = await api('/api/create/rewrite', {
      method: 'POST',
      body: JSON.stringify({
        caption: c.caption,
        instruction: c.rewriteStyle || 'короче',
        goal: c.contentGoal || 'engagement',
        tone: c.contentTone || 'friendly',
        language: c.language || 'ru',
      }),
    });
    const first = (out?.drafts || [])[0] || {};
    c.caption = String(first.caption || c.caption || '');
    c.cta = String(first.cta || c.cta || '');
    if (Array.isArray(first.hashtags) && first.hashtags.length) c.hashtags = parseCampaignHashtags(first.hashtags.join(' '));
    c.dirty = true;
    render();
    await runQualityCheck();
  };

  async function loadTemplates() {
    const out = await api('/api/create/templates');
    state.createCampaign.templates = Array.isArray(out?.items) ? out.items : [];
    state.createCampaign.templatesLoaded = true;
    render();
  }

  const saveTemplate = async () => {
    readLocalForm();
    const c = state.createCampaign;
    const name = `Шаблон ${new Date().toLocaleDateString('ru-RU')}`;
    await api('/api/create/templates', {
      method: 'POST',
      body: JSON.stringify({
        name,
        preset: {
          tone: c.contentTone || 'friendly',
          goal: c.contentGoal || 'engagement',
          cta: c.cta || '',
          hashtags: c.hashtags || [],
          format: c.contentFormat || 'post',
        },
      }),
    });
    await loadTemplates();
  };

  const applyTemplate = (id) => {
    const t = (state.createCampaign.templates || []).find((x) => Number(x.id) === Number(id));
    if (!t) return;
    const p = t.preset || {};
    update({
      contentTone: p.tone || state.createCampaign.contentTone,
      contentGoal: p.goal || state.createCampaign.contentGoal,
      contentFormat: p.format || state.createCampaign.contentFormat,
      cta: p.cta || state.createCampaign.cta,
      hashtags: Array.isArray(p.hashtags) && p.hashtags.length ? parseCampaignHashtags(p.hashtags.join(' ')) : state.createCampaign.hashtags,
    });
    render();
  };

  const deleteTemplate = async (id) => {
    await api(`/api/create/templates/${Number(id)}`, { method: 'DELETE' });
    await loadTemplates();
  };

  const runDraftAction = async (action, draftId) => {
    readLocalForm();
    if (action === 'publish' || action === 'schedule') {
      await ensurePreviewBeforePublish();
    }
    const projectId = Number(state.createCampaign.projectId || state.projects?.[0]?.id || 0) || null;
    if (!projectId) throw new Error('Выберите проект.');
    const endpoint = `/api/content/drafts/${Number(draftId || 0)}/${action}`;
    const payload = { project_id: projectId };
    if (action === 'schedule') {
      const scheduleAtIso = localInputToIsoNoTz(state.createCampaign.contentScheduleAt || '');
      if (!scheduleAtIso) throw new Error('Укажите дату и время для планирования.');
      payload.schedule_at = scheduleAtIso;
    }
    return api(endpoint, { method: 'POST', body: JSON.stringify(payload), timeoutMs: 180000 });
  };

  document.querySelectorAll('[data-cw-mode]').forEach((btn) => {
    btn.onclick = () => {
      state.createCampaign.mode = btn.getAttribute('data-cw-mode') || 'image';
      syncCampaignKindsByMode();
      state.createCampaign.dirty = true;
      render();
    };
  });
  const studioQuickBtn = document.getElementById('cwStudioQuick');
  if (studioQuickBtn) studioQuickBtn.onclick = () => { update({ studioMode: 'quick' }); render(); };
  const studioProBtn = document.getElementById('cwStudioPro');
  if (studioProBtn) studioProBtn.onclick = () => { update({ studioMode: 'pro' }); render(); };
  const bindField = (id, fn) => { const el = document.getElementById(id); if (el) el.oninput = fn; };
  bindField('cwTopic', () => update({ topic: document.getElementById('cwTopic').value }));
  bindField('cwOffer', () => update({ offer: document.getElementById('cwOffer').value }));
  bindField('cwCaption', () => update({ caption: document.getElementById('cwCaption').value }));
  bindField('cwCta', () => update({ cta: document.getElementById('cwCta').value }));
  bindField('cwHashtags', () => update({ hashtags: parseCampaignHashtags(document.getElementById('cwHashtags').value) }));
  ['cwProject', 'cwLang', 'cwStudioMode', 'cwPublishMode', 'cwScheduleAt', 'cwImageStyle', 'cwDuration', 'cwRatio', 'cwVideoStylePack', 'cwKindFb', 'cwKindIg', 'cwKindYt', 'cwAccFb', 'cwAccIg', 'cwContentTone', 'cwContentGoal', 'cwContentFormat', 'cwAudienceType', 'cwRewriteStyle', 'cwContentScheduleAt'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.onchange = () => { readLocalForm(); render(); };
  });
  ['cwFb', 'cwIg', 'cwYt', 'cwNoTextOnImage', 'cwNoFantasy', 'cwThumb', 'cwVariants3'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.onchange = () => {
      const patch = {};
      if (id === 'cwFb') patch.platforms = { ...state.createCampaign.platforms, facebook: !!el.checked };
      if (id === 'cwIg') patch.platforms = { ...state.createCampaign.platforms, instagram: !!el.checked };
      if (id === 'cwYt') patch.platforms = { ...state.createCampaign.platforms, youtube: !!el.checked };
      if (id === 'cwNoTextOnImage') patch.noTextOnImage = !!el.checked;
      if (id === 'cwNoFantasy') patch.noFantasy = !!el.checked;
      if (id === 'cwThumb') patch.generateThumbnail = !!el.checked;
      if (id === 'cwVariants3') patch.contentVariants3 = !!el.checked;
      update(patch);
      syncCampaignKindsByMode();
      render();
    };
  });
  ['cwGoConnectionsFb', 'cwGoConnectionsIg', 'cwGoConnectionsYt'].forEach((id) => {
    const el = document.getElementById(id);

  });

  document.querySelectorAll('input[name="cwGoal"]').forEach((el) => {
    el.onchange = () => update({ objective: el.value || 'sales' });
  });
  document.querySelectorAll('[data-cw-ai]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        readLocalForm();
        if (!String(state.createCampaign.topic || '').trim()) throw new Error('Введите тему перед генерацией текста');
        state.createCampaign.generation = { ...state.createCampaign.generation, running: true, statusText: 'AI готовит пост…' };
        render();
        const text = await api('/api/generate', {
          method: 'POST',
          body: JSON.stringify({
            project_id: Number(state.createCampaign.projectId || state.projects?.[0]?.id || 0) || null,
            topic: state.createCampaign.topic,
            language: state.createCampaign.language || 'ru',
            tone: btn.getAttribute('data-cw-ai') || 'friendly',
            platforms: selectedCampaignPlatforms(),
          }),
          timeoutMs: 90000,
        });
        const generated = String(text?.text || '').trim();
        state.createCampaign.caption = generated || state.createCampaign.caption;
        if ((!state.createCampaign.hashtags || !state.createCampaign.hashtags.length) && generated) {
          state.createCampaign.hashtags = parseCampaignHashtags(generated);
        }
        state.createCampaign.generation = { ...state.createCampaign.generation, running: false, statusText: 'Текст готов' };
        state.createCampaign.dirty = true;
        render();
      } catch (e) {
        state.createCampaign.generation = { ...state.createCampaign.generation, running: false, statusText: '' };
        state.notice = { type: 'error', text: e.message || 'Не удалось сгенерировать текст' };
        render();
      }
    };
  });

  const pollJob = async (jobId) => {
    const stageLabels = {
      queued: 'в очереди',
      running: 'выполняется',
      downloading: 'скачивание футажей',
      rendering: 'рендер видео',
      uploading: 'подготовка к публикации',
      done: 'готово',
      failed: 'ошибка',
    };
    for (let i = 0; i < 90; i += 1) {
      const res = await api(`/api/jobs/${jobId}`);
      const job = res?.job || {};
      const statusKey = String(job.status || 'queued').toLowerCase();
      const statusLabel = stageLabels[statusKey] || statusKey;
      state.createCampaign.generation.statusText = `Статус генерации: ${statusLabel} (${job.progress || 0}%)`;
      if (job.status === 'done') return true;
      if (job.status === 'failed') throw new Error(job.error_message || 'Ошибка генерации');
      await new Promise((r) => setTimeout(r, 2000));
    }
    throw new Error('Генерация заняла слишком много времени');
  };

  const generateAsset = async (kind) => {
    readLocalForm();
    await ensureCampaignSaved();
    state.createCampaign.generation = { ...state.createCampaign.generation, running: true, statusText: 'Запуск генерации…' };
    render();
    try {
      const endpoint = kind === 'image' ? `/api/campaigns/${state.createCampaign.campaignId}/generate-image` : `/api/campaigns/${state.createCampaign.campaignId}/generate-video`;
      const payload = kind === 'image'
        ? { style: state.createCampaign.imageStyle, no_text_on_image: state.createCampaign.noTextOnImage, realism: true, prompt_guards: { no_fantasy: true } }
        : { duration_sec: state.createCampaign.videoDuration, aspect_ratio: state.createCampaign.videoAspectRatio, realism: true, prompt_guards: { no_fantasy: true }, generate_thumbnail: state.createCampaign.generateThumbnail, style_pack_id: state.createCampaign.videoStylePackId || 'default_pro' };
      const started = await api(endpoint, { method: 'POST', body: JSON.stringify(payload), timeoutMs: 180000 });
      const jobId = started?.job?.id;
      if (!jobId) throw new Error('Сервер не вернул job id');
      await pollJob(jobId);
      await loadCampaignDetails(state.createCampaign.campaignId);
      state.createCampaign.generation = { ...state.createCampaign.generation, running: false, statusText: 'Генерация завершена' };
      state.notice = { type: 'ok', text: `${kind === 'image' ? 'Изображение' : 'Видео'} готово` };
      render();
    } catch (e) {
      state.createCampaign.generation = { ...state.createCampaign.generation, running: false, statusText: '' };
      state.notice = { type: 'error', text: e.message || 'Не удалось завершить генерацию' };
      render();
    }
  };
  const genTextBtn = document.getElementById('cwGenerateText');
  if (genTextBtn) genTextBtn.onclick = async () => {
    const salesBtn = document.querySelector('[data-cw-ai="sales"]');
    if (salesBtn) salesBtn.click();
  };
  const smartGenerateBtn = document.getElementById('cwSmartGenerateBtn');
  if (smartGenerateBtn) smartGenerateBtn.onclick = async () => {
    try {
      await runSmartContentGeneration();
      await runQualityCheck();
      state.notice = { type: 'ok', text: 'Стратегия и черновики готовы.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сгенерировать контент' };
      render();
    }
  };
  const smartRetryBtn = document.getElementById('cwSmartRetryBtn');
  if (smartRetryBtn) smartRetryBtn.onclick = async () => {
    try {
      await runSmartContentGeneration();
      await runQualityCheck();
      state.notice = { type: 'ok', text: 'Повторная генерация завершена.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Retry не удался' };
      render();
    }
  };
  const suggestBtn = document.getElementById('cwSuggestBtn');
  if (suggestBtn) suggestBtn.onclick = async () => {
    try {
      await runSuggest();
      state.notice = { type: 'ok', text: 'AI подсказки готовы.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось получить подсказки' };
      render();
    }
  };
  const rewriteBtn = document.getElementById('cwRewriteBtn');
  if (rewriteBtn) rewriteBtn.onclick = async () => {
    try {
      await runRewrite();
      state.notice = { type: 'ok', text: 'Текст улучшен.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось улучшить текст' };
      render();
    }
  };
  const abBtn = document.getElementById('cwABBtn');
  if (abBtn) abBtn.onclick = async () => {
    try {
      state.createCampaign.contentVariants3 = true;
      await runSmartContentGeneration();
      await runQualityCheck();
      state.notice = { type: 'ok', text: 'A/B варианты обновлены.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сделать A/B варианты' };
      render();
    }
  };
  const saveTemplateBtn = document.getElementById('cwSaveTemplateBtn');
  if (saveTemplateBtn) saveTemplateBtn.onclick = async () => {
    try {
      await saveTemplate();
      state.notice = { type: 'ok', text: 'Шаблон сохранен.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сохранить шаблон' };
      render();
    }
  };
  const stickySave = document.getElementById('cwStickySave');
  if (stickySave) stickySave.onclick = async () => {
    try {
      readLocalForm();
      await ensureCampaignSaved();
      await api(`/api/campaigns/${state.createCampaign.campaignId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'draft', caption_master: state.createCampaign.caption, cta: state.createCampaign.cta, hashtags_master: state.createCampaign.hashtags }),
      });
      state.notice = { type: 'ok', text: 'Черновик сохранен.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сохранить черновик' };
      render();
    }
  };
  const stickySchedule = document.getElementById('cwStickySchedule');
  if (stickySchedule) stickySchedule.onclick = () => {
    state.createCampaign.publishMode = 'schedule';
    state.createCampaign.step = 6;
    render();
  };
  const stickyPublish = document.getElementById('cwStickyPublish');
  if (stickyPublish) stickyPublish.onclick = () => {
    state.createCampaign.publishMode = 'now';
    state.createCampaign.step = 6;
    render();
  };
  const qualityBtn = document.getElementById('cwQualityCheckBtn');
  if (qualityBtn) qualityBtn.onclick = async () => {
    try {
      await runQualityCheck();
      state.notice = { type: 'ok', text: 'Quality check обновлен.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось выполнить quality check' };
      render();
    }
  };
  document.querySelectorAll('[data-cw-draft-platform]').forEach((btn) => {
    btn.onclick = () => {
      const platform = String(btn.getAttribute('data-cw-draft-platform') || '').trim().toLowerCase();
      if (!platform) return;
      state.createCampaign.contentGeneration.activePlatform = platform;
      applyFirstDraftToCampaign();
      render();
    };
  });
  document.querySelectorAll('[data-cw-preview]').forEach((btn) => {
    btn.onclick = () => {
      state.createCampaign.previewPlatform = btn.getAttribute('data-cw-preview') || 'facebook';
      applyFirstDraftToCampaign();
      render();
    };
  });
  document.querySelectorAll('[data-cw-preview-tab]').forEach((btn) => {
    btn.onclick = () => {
      state.createCampaign.previewPlatform = btn.getAttribute('data-cw-preview-tab') || 'facebook';
      applyFirstDraftToCampaign();
      render();
    };
  });
  document.querySelectorAll('[data-cw-preview-yt-kind]').forEach((btn) => {
    btn.onclick = () => {
      const kind = String(btn.getAttribute('data-cw-preview-yt-kind') || 'shorts').toLowerCase();
      state.createCampaign.kinds.youtube = kind === 'video' ? 'video' : 'shorts';
      render();
    };
  });
  document.querySelectorAll('[data-cw-variant]').forEach((btn) => {
    btn.onclick = () => {
      state.createCampaign.activeVariant = Number(btn.getAttribute('data-cw-variant') || 1);
      applyFirstDraftToCampaign();
      render();
    };
  });
  document.querySelectorAll('[data-cw-angle]').forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.getAttribute('data-cw-angle') || 0);
      const val = (state.createCampaign.aiAssist?.angles || [])[idx];
      if (!val) return;
      state.createCampaign.offer = val;
      state.createCampaign.dirty = true;
      render();
    };
  });
  document.querySelectorAll('[data-cw-cta-variant]').forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.getAttribute('data-cw-cta-variant') || 0);
      const val = (state.createCampaign.aiAssist?.ctaVariants || [])[idx];
      if (!val) return;
      state.createCampaign.cta = val;
      state.createCampaign.dirty = true;
      render();
    };
  });
  document.querySelectorAll('[data-cw-goal-shortcut]').forEach((btn) => {
    btn.onclick = async () => {
      const goal = String(btn.getAttribute('data-cw-goal-shortcut') || 'engagement');
      state.createCampaign.contentGoal = goal;
      state.createCampaign.dirty = true;
      render();
      try {
        await runSmartContentGeneration();
        await runQualityCheck();
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось сгенерировать вариант' };
        render();
      }
    };
  });
  document.querySelectorAll('[data-cw-apply-template]').forEach((btn) => {
    btn.onclick = () => applyTemplate(btn.getAttribute('data-cw-apply-template'));
  });
  document.querySelectorAll('[data-cw-del-template]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await deleteTemplate(btn.getAttribute('data-cw-del-template'));
        state.notice = { type: 'ok', text: 'Шаблон удален.' };
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось удалить шаблон' };
      }
      render();
    };
  });
  document.querySelectorAll('[data-cw-copy-draft]').forEach((btn) => {
    btn.onclick = async () => {
      const raw = btn.getAttribute('data-cw-copy-draft') || '';
      const text = decodeURIComponent(raw);
      try {
        if (navigator?.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const area = document.createElement('textarea');
          area.value = text;
          document.body.appendChild(area);
          area.select();
          document.execCommand('copy');
          area.remove();
        }
        state.notice = { type: 'ok', text: 'Текст скопирован.' };
      } catch {
        state.notice = { type: 'error', text: 'Не удалось скопировать текст.' };
      }
      render();
    };
  });
  document.querySelectorAll('[data-cw-save-draft]').forEach((btn) => {
    btn.onclick = async () => {
      const draftId = Number(btn.getAttribute('data-cw-save-draft') || 0);
      if (!draftId) return;
      try {
        await runDraftAction('save', draftId);
        state.notice = { type: 'ok', text: 'Черновик сохранен в историю постов.' };
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось сохранить черновик.' };
      }
      render();
    };
  });
  document.querySelectorAll('[data-cw-schedule-draft]').forEach((btn) => {
    btn.onclick = async () => {
      const draftId = Number(btn.getAttribute('data-cw-schedule-draft') || 0);
      if (!draftId) return;
      try {
        await runDraftAction('schedule', draftId);
        state.notice = { type: 'ok', text: 'Черновик поставлен в расписание.' };
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось запланировать.' };
      }
      render();
    };
  });
  document.querySelectorAll('[data-cw-publish-draft]').forEach((btn) => {
    btn.onclick = async () => {
      const draftId = Number(btn.getAttribute('data-cw-publish-draft') || 0);
      if (!draftId) return;
      try {
        const out = await runDraftAction('publish', draftId);
        state.notice = { type: 'ok', text: out?.message || 'Публикация запущена.' };
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось опубликовать.' };
      }
      render();
    };
  });
  const genImageBtn = document.getElementById('cwGenerateImage');
  if (genImageBtn) genImageBtn.onclick = async () => generateAsset('image');
  const genVideoBtn = document.getElementById('cwGenerateVideo');
  if (genVideoBtn) genVideoBtn.onclick = async () => generateAsset('video');
  const autoFixShortenBtn = document.getElementById('cwAutoFixShorten');
  if (autoFixShortenBtn) autoFixShortenBtn.onclick = async () => {
    try {
      readLocalForm();
      if (!String(state.createCampaign.caption || '').trim()) throw new Error('Сначала добавьте текст.');
      const out = await api('/api/create/rewrite', {
        method: 'POST',
        body: JSON.stringify({
          caption: state.createCampaign.caption,
          instruction: 'короче',
          goal: state.createCampaign.contentGoal || 'engagement',
          tone: state.createCampaign.contentTone || 'friendly',
          language: state.createCampaign.language || 'ru',
        }),
      });
      const first = (out?.drafts || [])[0] || {};
      state.createCampaign.caption = String(first.caption || state.createCampaign.caption || '');
      if (String(first.cta || '').trim()) state.createCampaign.cta = String(first.cta || '').trim();
      if (Array.isArray(first.hashtags) && first.hashtags.length) state.createCampaign.hashtags = parseCampaignHashtags(first.hashtags.join(' '));
      state.notice = { type: 'ok', text: 'Текст сокращен.' };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сократить текст.' };
    }
    render();
  };
  const autoFixTagsBtn = document.getElementById('cwAutoFixTags');
  if (autoFixTagsBtn) autoFixTagsBtn.onclick = () => {
    readLocalForm();
    const { platform } = computePublishPreview();
    const tags = parseCampaignHashtags((state.createCampaign.hashtags || []).join(' '));
    const defaults = ['#контент', '#маркетинг', '#бизнес', '#продвижение', '#соцсети', '#smm', '#рост', '#аудитория'];
    let targetMin = 3;
    let targetMax = 8;
    if (platform === 'instagram') { targetMin = 8; targetMax = 15; }
    if (platform === 'youtube') { targetMin = 5; targetMax = 15; }
    const merged = Array.from(new Set([...tags, ...defaults])).slice(0, Math.max(targetMin, targetMax));
    state.createCampaign.hashtags = merged.slice(0, targetMax);
    state.notice = { type: 'ok', text: 'Хештеги обновлены.' };
    render();
  };
  const autoFixCtaBtn = document.getElementById('cwAutoFixCta');
  if (autoFixCtaBtn) autoFixCtaBtn.onclick = async () => {
    try {
      readLocalForm();
      const out = await api('/api/create/suggest', {
        method: 'POST',
        body: JSON.stringify({
          topic: state.createCampaign.topic || '',
          offer: state.createCampaign.offer || '',
          goal: state.createCampaign.contentGoal || 'engagement',
          tone: state.createCampaign.contentTone || 'friendly',
          language: state.createCampaign.language || 'ru',
        }),
      });
      const arr = Array.isArray(out?.suggestions?.cta_variants) ? out.suggestions.cta_variants : [];
      state.createCampaign.cta = String(arr[0] || state.createCampaign.cta || 'Напишите в сообщения').trim();
      state.notice = { type: 'ok', text: 'Призыв обновлен.' };
    } catch (e) {
      state.createCampaign.cta = String(state.createCampaign.cta || 'Напишите в сообщения').trim();
      state.notice = { type: 'ok', text: 'Призыв добавлен.' };
    }
    render();
  };

  const prevBtn = document.getElementById('cwPrev');
  if (prevBtn) prevBtn.onclick = () => { state.createCampaign.step = Math.max(1, (state.createCampaign.step || 1) - 1); render(); };
  const nextBtn = document.getElementById('cwNext');
  if (nextBtn) nextBtn.onclick = async () => {
    readLocalForm();
    const error = validateStep(state.createCampaign.step || 1);
    if (error) {
      state.notice = { type: 'error', text: error };
      render();
      return;
    }
    if ((state.createCampaign.step || 1) >= 4) await ensureCampaignSaved();
    state.createCampaign.step = Math.min(6, (state.createCampaign.step || 1) + 1);
    render();
  };

  const submitBtn = document.getElementById('cwSubmitPublish');
  if (submitBtn) submitBtn.onclick = async () => {
    try {
      readLocalForm();
      await ensureCampaignSaved();
      if (state.createCampaign.publishMode === 'draft') {
        await api(`/api/campaigns/${state.createCampaign.campaignId}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'draft', caption_master: state.createCampaign.caption, cta: state.createCampaign.cta, hashtags_master: state.createCampaign.hashtags }),
        });
        state.createCampaign.publishMessage = 'Черновик сохранён. Можно продолжить позже.';
        state.notice = { type: 'ok', text: 'Черновик сохранён' };
        saveCampaignDraftLocal();
        render();
        return;
      }
      const deliveries = [];
      const w = state.createCampaign;
      await ensurePreviewBeforePublish();
      const when = w.publishMode === 'schedule'
        ? localInputToIsoNoTz(w.scheduledAt || '')
        : null;
      if (w.publishMode === 'schedule' && !when) throw new Error('Укажите корректную дату и время');
      if (w.platforms.facebook) deliveries.push({ platform: 'facebook', kind: w.kinds.facebook, account_ref: w.accountRefs.facebook || null, scheduled_at: when, caption_override: w.caption, hashtags_override: w.hashtags });
      if (w.platforms.instagram) deliveries.push({ platform: 'instagram', kind: w.kinds.instagram, account_ref: w.accountRefs.instagram || null, scheduled_at: when, caption_override: w.caption, hashtags_override: w.hashtags });
      if (w.platforms.youtube) deliveries.push({ platform: 'youtube', kind: w.kinds.youtube, account_ref: state.youtubeConnection?.channel_id || null, scheduled_at: when, caption_override: w.caption, hashtags_override: w.hashtags });
      if (!deliveries.length) throw new Error('Выберите платформу для публикации');
      const published = await api(`/api/campaigns/${w.campaignId}/publish`, { method: 'POST', body: JSON.stringify({ deliveries }), timeoutMs: 180000 });
      state.createCampaign.deliveries = published?.deliveries || [];
      state.createCampaign.publishMessage = 'Кампания отправлена в очередь. Отслеживаем статусы…';
      state.notice = { type: 'ok', text: 'Публикация запущена' };
      render();
      if (window.__campaignDeliveriesPoller) clearInterval(window.__campaignDeliveriesPoller);
      window.__campaignDeliveriesPoller = setInterval(async () => {
        if (location.pathname.replace(/\/$/, '') !== '/create') return;
        await loadCampaignDetails(state.createCampaign.campaignId);
        const statuses = (state.createCampaign.deliveries || []).map((d) => String(d.status || '').toLowerCase());
        if (statuses.length && statuses.every((s) => ['published', 'failed'].includes(s))) {
          clearInterval(window.__campaignDeliveriesPoller);
          state.createCampaign.publishMessage = 'Очередь завершена. Откройте детали кампании.';
          state.notice = { type: 'ok', text: 'Готово. Статусы обновлены.' };
          render();
        } else {
          render();
        }
      }, 2500);
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось отправить кампанию в публикацию' };
      render();
    }
  };
}

async function bindCreateDirector(path) {
  if (path !== '/create') return false;
  if (window.__campaignAutosaveTimer) {
    clearInterval(window.__campaignAutosaveTimer);
    window.__campaignAutosaveTimer = null;
  }
  if (window.__campaignDeliveriesPoller) {
    clearInterval(window.__campaignDeliveriesPoller);
    window.__campaignDeliveriesPoller = null;
  }
  const d = state.createDirector;
  if (!Object.prototype.hasOwnProperty.call(d, 'manualTopicInput')) d.manualTopicInput = String(d.manualTopic || '').trim();
  if (!Object.prototype.hasOwnProperty.call(d, 'appliedManualTopic')) d.appliedManualTopic = String(d.manualTopic || '').trim();
  if (!Object.prototype.hasOwnProperty.call(d, 'selectedSuggestedTopic')) d.selectedSuggestedTopic = String(d.selectedTopic || '').trim();
  if (!Object.prototype.hasOwnProperty.call(d, 'topicPreset')) d.topicPreset = String(d.topic || DEFAULT_DIRECTOR_NICHE).trim() || DEFAULT_DIRECTOR_NICHE;
  if (!Object.prototype.hasOwnProperty.call(d, 'customTopicMode')) d.customTopicMode = false;
  if (!Object.prototype.hasOwnProperty.call(d, 'customBaseTopicInput')) d.customBaseTopicInput = String(d.topic || '').trim();
  d.topicPreset = directorCurrentNicheId({ ...d, customTopicMode: false, topicPreset: d.topicPreset || DEFAULT_DIRECTOR_NICHE });
  if (!String(d.topicPreset || '').trim()) d.topicPreset = DEFAULT_DIRECTOR_NICHE;
  d.topic = directorBaseTopic(d, d.topic);
  const persistContentType = (value) => {
    const nextType = normalizeDirectorContentType(value);
    d.contentType = nextType;
    try { localStorage.setItem(CREATE_DIRECTOR_TYPE_KEY, nextType); } catch {}
    try {
      const u = new URL(window.location.href);
      if (nextType === 'video') u.searchParams.set('type', 'video');
      else u.searchParams.delete('type');
      history.replaceState({}, '', `${u.pathname}${u.search}${u.hash}`);
    } catch {}
  };
  const hydrateContentType = () => {
    if (d._contentTypeInited) return;
    let localType = '';
    let queryType = '';
    try { localType = String(localStorage.getItem(CREATE_DIRECTOR_TYPE_KEY) || '').trim(); } catch {}
    try { queryType = String(new URLSearchParams(window.location.search).get('type') || '').trim(); } catch {}
    const nextType = normalizeDirectorContentType(queryType || localType || d.contentType || 'post');
    persistContentType(nextType);
    d._contentTypeInited = true;
  };
  const hydrateQuickActionFromLocation = () => {
    let queryAction = '';
    let queryNiche = '';
    try {
      const params = new URLSearchParams(window.location.search);
      queryAction = String(params.get('quickAction') || '').trim();
      queryNiche = String(params.get('niche') || '').trim();
    } catch {}
    const validActions = new Set(DASHBOARD_QUICK_ACTIONS.map((item) => item.key));
    if (!validActions.has(queryAction)) {
      d.quickActionType = '';
      d.quickActionNicheId = '';
      d.quickActionPreviewOnly = false;
      d.planFlowState = 'idle';
      d.planFlowItems = [];
      d.planFlowError = '';
      return;
    }
    const normalizedNicheId = normalizeNicheIdSafe(queryNiche || d.quickActionNicheId || '');
    if (!normalizedNicheId || normalizedNicheId === 'fallback') {
      d.quickActionType = '';
      d.quickActionNicheId = '';
      d.quickActionPreviewOnly = false;
      d.planFlowState = 'idle';
      d.planFlowItems = [];
      d.planFlowError = '';
      return;
    }
    const prevKey = `${String(d.quickActionType || '').trim()}:${String(d.quickActionNicheId || '').trim()}`;
    const nextKey = `${queryAction}:${normalizedNicheId}`;
    d.quickActionType = queryAction;
    d.quickActionNicheId = normalizedNicheId;
    d.quickActionPreviewOnly = getQuickActionAccess(queryAction, state.billing).isPreview;
    d.planHorizon = queryAction === 'monthly_plan' ? 'month' : 'week';
    if (prevKey !== nextKey) {
      d.planFlowState = 'idle';
      d.planFlowItems = [];
      d.planFlowError = '';
      d.planFlowSelectedDay = 1;
      d.planFlowProgressStep = 0;
    }
    if (!d.customTopicMode) d.topicPreset = normalizedNicheId;
  };
  const ensureVideoDefaults = () => {
    if (!d.videoOrientation || !['vertical', 'horizontal'].includes(String(d.videoOrientation))) d.videoOrientation = 'vertical';
    const allowed = String(d.videoOrientation || 'vertical') === 'horizontal'
      ? ['120', '180', '240', '300', '360', '420', '480']
      : ['20', '30', '40', '60'];
    if (!allowed.includes(String(d.videoDurationPreset || ''))) d.videoDurationPreset = allowed[0];
    if (typeof d.videoSceneEvery4 !== 'boolean') d.videoSceneEvery4 = true;
    if (!Number.isFinite(Number(d.videoShotSeconds))) d.videoShotSeconds = 4;
    d.videoShotSeconds = Math.max(2, Math.min(12, Number(d.videoShotSeconds) || 4));
    if (typeof d.videoMinimizeRepeats !== 'boolean') d.videoMinimizeRepeats = true;
    if (typeof d.videoRealisticOnly !== 'boolean') d.videoRealisticOnly = true;
    if (!['male', 'female'].includes(String(d.videoVoiceGender || ''))) d.videoVoiceGender = 'male';
    if (!['calm', 'neutral', 'live'].includes(String(d.videoVoiceTone || ''))) d.videoVoiceTone = 'neutral';
    if (!d.previewVideoTab || !['meta', 'youtube'].includes(String(d.previewVideoTab))) d.previewVideoTab = 'meta';
    if (!d.previewVideoMetaPlatform || !['facebook', 'instagram'].includes(String(d.previewVideoMetaPlatform))) d.previewVideoMetaPlatform = 'facebook';
    if (!d.previewExpanded || typeof d.previewExpanded !== 'object') d.previewExpanded = {};
    if (typeof d.videoStructureExpanded !== 'boolean') d.videoStructureExpanded = false;
  };
  const ensureContentTypePlatforms = () => {
    const type = normalizeDirectorContentType(d.contentType || 'post');
    if (type !== 'video') {
      d.platforms.youtube = false;
      if (String(d.activePlatform || '') === 'youtube') {
        d.activePlatform = d.platforms.facebook ? 'facebook' : 'instagram';
      }
      return;
    }
    d.imageEnabled = true;
    d.platforms.facebook = true;
    d.platforms.instagram = true;
    d.platforms.youtube = true;
    if (!d.platforms.facebook && !d.platforms.instagram && !d.platforms.youtube) {
      d.platforms.youtube = true;
    }
  };
  const setDefaultsFromConnections = () => {
    const metaReady = (state.connections || []).filter((m) => isConnectionReady(m));
    const fb = metaReady.some((m) => !!m.page_id);
    const ig = metaReady.some((m) => !!m.ig_user_id);
    const yt = !!state.youtubeConnection?.connected;
    if (!d._platformsInited) {
      d.platforms = { facebook: fb, instagram: ig, youtube: yt };
      if (!d.platforms.facebook && !d.platforms.instagram && !d.platforms.youtube) {
        d.platforms = { facebook: true, instagram: true, youtube: false };
      }
      d._platformsInited = true;
    }
  };
  hydrateContentType();
  hydrateQuickActionFromLocation();
  ensureVideoDefaults();
  setDefaultsFromConnections();
  ensureContentTypePlatforms();

  const selectedPlatforms = () => ['facebook', 'instagram', 'youtube'].filter((p) => !!d.platforms?.[p]);
  const activeDraft = () => {
    const platform = String(d.activePlatform || 'facebook');
    const list = (d.drafts || []).filter((x) => String(x.platform || '').toLowerCase() === platform);
    const variant = Number(d.activeVariant || 1);
    return list.find((x) => Number(x.variant_index || x.variant || 1) === variant) || list[0] || null;
  };
  const syncQuality = () => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    if (isVideoType) {
      d.quality = directorVideoQualityLocal({
        videoStructure: d.videoStructure,
        targetSeconds: Number(d.videoDurationPreset || 30),
        orientation: String(d.videoOrientation || 'vertical').toLowerCase() === 'horizontal' ? 'horizontal' : 'vertical',
        cta: String(d.selectedCta || '').trim(),
        hashtags: Array.isArray(d.selectedHashtags) ? d.selectedHashtags : [],
        realisticOnly: !!d.videoRealisticOnly,
        fixedSceneSeconds: (d.videoSceneEvery4 ? Math.max(2, Math.min(12, Number(d.videoShotSeconds || 4) || 4)) : 0),
      });
      return;
    }
    const draft = activeDraft();
    const effectiveTags = Array.isArray(d.selectedHashtags) && d.selectedHashtags.length
      ? d.selectedHashtags
      : (draft?.hashtags || []);
    const effectiveCta = String(d.selectedCta || '').trim() || String(draft?.cta || '').trim();
    d.quality = directorQualityLocal({
      caption: draft?.post_text || '',
      cta: effectiveCta,
      hashtags: effectiveTags,
      goal: d.goal,
      platform: d.activePlatform,
    });
  };
  const refreshQualityDom = () => {
    const scoreEl = document.getElementById('cdQualityScore');
    if (scoreEl) scoreEl.innerHTML = `${Number(d.quality?.score || 0)}<span>/100</span>`;
    const listEl = document.getElementById('cdQualityList');
    if (listEl) {
      listEl.innerHTML = (d.quality?.checks || []).map((it) => `<li class="${it.state === 'green' ? 'done' : (it.state === 'red' ? 'bad' : '')}">${esc(it.label)}</li>`).join('');
    }
    const warnEl = document.getElementById('cdQualityWarn');
    if (warnEl) warnEl.textContent = ((d.quality?.warnings || []).join(' · ')).trim();
  };
  const refreshVideoProgressDom = () => {
    const statusTextEl = document.getElementById('cdVideoStatusText');
    if (statusTextEl) statusTextEl.textContent = `Статус видео: ${String(d.videoJobStatus || 'ожидание')}`;
    const progress = Math.max(0, Math.min(100, Number(d.videoProgress || 0)));
    const step = String(d.videoStep || 'queued').trim().toLowerCase() || 'queued';
    const labelMap = {
      structure: 'Структура',
      footage: 'Футажи',
      render: 'Рендер',
      export: 'Экспорт',
      upload: 'Загрузка',
      queued: 'Очередь',
    };
    const stepTextEl = document.getElementById('cdVideoStepText');
    if (stepTextEl) stepTextEl.innerHTML = `<strong>${esc(labelMap[step] || 'Обработка')}</strong> · <span id="cdVideoProgressNum">${progress}</span>%`;
    const numEl = document.getElementById('cdVideoProgressNum');
    if (numEl) numEl.textContent = String(progress);
    const fillEl = document.getElementById('cdVideoProgressFill');
    if (fillEl) fillEl.style.width = `${progress}%`;
    const msgEl = document.getElementById('cdVideoProgressMessage');
    if (msgEl) msgEl.textContent = String(d.videoMessage || d.videoJobStatus || 'Ожидаем запуск сборки видео.');
    const order = ['structure', 'footage', 'render', 'export', 'upload'];
    const idx = order.indexOf(step);
    document.querySelectorAll('[data-cd-video-step]').forEach((node) => {
      const stepKey = String(node.getAttribute('data-cd-video-step') || '').trim().toLowerCase();
      const curIdx = order.indexOf(stepKey);
      node.classList.remove('done', 'active');
      if (idx >= 0 && (idx > curIdx || progress >= 100)) node.classList.add('done');
      else if (idx === curIdx && progress < 100) node.classList.add('active');
    });
  };
  const refreshDirectorPreviewDom = () => {
    const draft = activeDraft();
    const effectiveSelectedTopic = directorEffectiveTopic(d);
    const baseTopic = directorBaseTopic(d, d.topic);
    const hasSelection = effectiveSelectedTopic && String(d.selectedAngle || '').trim();
    const draftMatchesSelection = !!draft
      && String(d.lastDraftTopic || '').trim() === effectiveSelectedTopic
      && String(d.lastDraftAngle || '').trim() === String(d.selectedAngle || '').trim();
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    const selectedThemePreviewText = [
      String(effectiveSelectedTopic || baseTopic || '').trim() ? `Тема: ${String(effectiveSelectedTopic || baseTopic || '').trim()}` : '',
      String(d.selectedAngle || '').trim() ? `Подход: ${String(d.selectedAngle || '').trim()}` : '',
      'Готовим текст под выбранную тему…',
    ].filter(Boolean).join('\n');
    const videoTextState = isVideoType ? getVideoPreviewTextState(d, String(d.activePlatform || 'facebook')) : null;
    const nextText = isVideoType
      ? String(videoTextState?.text || 'Сначала сгенерируйте структуру, затем соберите видео.')
      : resolveDirectorPostPreviewText({
        draft,
        draftMatchesSelection,
        loadingDrafts: d.loadingDrafts,
        selectedThemePreviewText,
        hasSelection,
      });
    const selectedTagSet = Array.isArray(d.selectedHashtags) ? normalizeHashtagSet(d.selectedHashtags) : [];
    const tags = selectedTagSet.length ? selectedTagSet : normalizeHashtagSet(Array.isArray(draft?.hashtags) ? draft.hashtags : []);
    const cta = String(d.selectedCta || '').trim() || String(draft?.cta || '').trim() || 'Призыв';

    const titleEl = document.getElementById('cdPreviewTitle');
    if (titleEl) titleEl.textContent = String(effectiveSelectedTopic || baseTopic || 'Тема');
    const textEl = document.getElementById('cdPreviewText');
    if (textEl) textEl.textContent = nextText;
    const toggleBtn = document.getElementById('cdPreviewToggleText');
    if (toggleBtn && isVideoType && videoTextState?.canExpand) {
      toggleBtn.textContent = videoTextState.expanded ? 'Свернуть' : 'Открыть больше';
      toggleBtn.style.display = '';
    } else if (toggleBtn) {
      toggleBtn.style.display = 'none';
    }
    const tagsEl = document.getElementById('cdPreviewTags');
    if (tagsEl) tagsEl.innerHTML = tags.map((h) => `<span class="pill">${esc(h)}</span>`).join('');
    const ctaEl = document.getElementById('cdPreviewCta');
    if (ctaEl) ctaEl.textContent = cta;
    const ratioText = String(d.videoOrientation || 'vertical').toLowerCase() === 'horizontal' ? '16:9' : '9:16';
    const durationText = `${String(d.videoDurationPreset || '30')} сек`;
    const ratioEl = document.getElementById('cdVideoRatioText');
    if (ratioEl) ratioEl.textContent = `${ratioText} · ${durationText}`;
    const ratioReadyEl = document.getElementById('cdVideoRatioTextReady');
    if (ratioReadyEl) ratioReadyEl.textContent = `Готово: ${durationText} · ${ratioText}`;
    document.querySelectorAll('.create-video-player').forEach((el) => {
      el.classList.toggle('is-horizontal', ratioText === '16:9');
      el.classList.toggle('is-vertical', ratioText !== '16:9');
    });
    document.querySelectorAll('.create-video-placeholder').forEach((el) => {
      el.classList.toggle('is-horizontal', ratioText === '16:9');
      el.classList.toggle('is-vertical', ratioText !== '16:9');
    });

    document.querySelectorAll('[data-cd-preview-platform]').forEach((btn) => {
      const platform = String(btn.getAttribute('data-cd-preview-platform') || '').trim().toLowerCase();
      const active = platform === String(d.activePlatform || '').trim().toLowerCase();
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cd-platform]').forEach((btn) => {
      const platform = String(btn.getAttribute('data-cd-platform') || '').trim().toLowerCase();
      const active = platform === String(d.activePlatform || '').trim().toLowerCase();
      btn.classList.toggle('btn-primary', active);
      btn.classList.toggle('btn-ghost', !active);
    });
    document.querySelectorAll('[data-cd-variant]').forEach((btn) => {
      const v = Number(btn.getAttribute('data-cd-variant') || 1);
      const active = v === Number(d.activeVariant || 1);
      btn.classList.toggle('btn-secondary', active);
      btn.classList.toggle('btn-ghost', !active);
    });
  };
  const refreshVideoDurationOptionsDom = () => {
    const sel = document.getElementById('cdVideoDurationPreset');
    if (!sel) return;
    const allowed = String(d.videoOrientation || 'vertical') === 'horizontal'
      ? ['120', '180', '240', '300', '360', '420', '480']
      : ['20', '30', '40', '60'];
    const current = String(d.videoDurationPreset || '');
    sel.innerHTML = allowed.map((v) => `<option value="${v}" ${current === v ? 'selected' : ''}>${v} сек</option>`).join('');
    const preferred = String(d.videoOrientation || 'vertical') === 'horizontal' ? '120' : '30';
    d.videoDurationPreset = preferred;
    sel.value = preferred;
  };
  const resetDirectorTopicSelection = ({ keepManualInput = true } = {}) => {
    d.manualTopicInput = keepManualInput ? String(d.manualTopicInput || '').trim() : '';
    d.appliedManualTopic = '';
    d.selectedSuggestedTopic = '';
    d.selectedAngle = '';
    d.topicPool = [];
    d.suggestions = null;
    d.selectedHashtags = [];
    d.selectedCta = '';
    d.activeVariant = 1;
    d.drafts = [];
    d.lastDraftTopic = '';
    d.lastDraftAngle = '';
    d.imageUrl = '';
    d.videoCoverUrl = '';
    state.notice = null;
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') {
      resetVideoGenerationState({ clearStructure: true });
    }
  };
  const buildDirectorTopicPool = (seed = 0, incoming = []) => {
    const localPool = directorLocalTopicIdeas(d, DIRECTOR_TOPIC_IDEA_COUNT, seed);
    const scopedIncoming = (Array.isArray(incoming) ? incoming : []).filter((topic) => directorTopicBelongsToNiche(topic, d));
    if (localPool.length) return mergeTopicPool(localPool, scopedIncoming);
    return mergeTopicPool([], scopedIncoming);
  };
  const collectPayloadBase = () => ({
    niche_id: directorCurrentNicheId(d),
    niche_label: directorCurrentNicheMeta(d)?.label || directorBaseTopic(d, d.topic),
    niche_context: directorNicheAiContext(d),
    topic: directorBaseTopic({
      ...d,
      topicPreset: document.getElementById('cdTopicPreset')?.value || d.topicPreset || DEFAULT_DIRECTOR_NICHE,
      customTopicMode: !!(document.getElementById('cdTopicCustomEnabled')?.checked ?? d.customTopicMode),
      customBaseTopicInput: String(document.getElementById('cdTopic')?.value || d.customBaseTopicInput || '').trim(),
    }, d.topic),
    offer: String(document.getElementById('cdOffer')?.value || d.offer || '').trim() || null,
    goal: document.getElementById('cdGoal')?.value || d.goal || 'engagement',
    language: document.getElementById('cdLang')?.value || d.language || 'ru',
    tone: document.getElementById('cdTone')?.value || d.tone || 'friendly',
    platforms: selectedPlatforms(),
    content_type: normalizeDirectorContentType(d.contentType || 'post'),
  });
  const collectVideo = () => ({
    orientation: document.getElementById('cdVideoOrientation')?.value || d.videoOrientation || 'vertical',
    duration_preset: String(document.getElementById('cdVideoDurationPreset')?.value || d.videoDurationPreset || '30'),
    scene_every_4s: !!(document.getElementById('cdVideoSceneEvery4')?.checked ?? d.videoSceneEvery4),
    shot_seconds: (() => {
      const fixed = !!(document.getElementById('cdVideoSceneEvery4')?.checked ?? d.videoSceneEvery4);
      if (!fixed) return 0;
      const raw = Number(document.getElementById('cdVideoShotSeconds')?.value || d.videoShotSeconds || 4);
      return Math.max(2, Math.min(12, Number.isFinite(raw) ? raw : 4));
    })(),
    minimize_repeats: !!(document.getElementById('cdVideoMinimizeRepeats')?.checked ?? d.videoMinimizeRepeats),
    realistic_only: !!(document.getElementById('cdVideoRealisticOnly')?.checked ?? d.videoRealisticOnly),
    voice_gender: document.getElementById('cdVideoVoiceGender')?.value || d.videoVoiceGender || 'male',
    voice_tone: document.getElementById('cdVideoVoiceTone')?.value || d.videoVoiceTone || 'neutral',
  });
  const wordsPerSecond = 2.2;
  const targetVideoSeconds = () => Math.max(20, Math.min(480, Number(d.videoDurationPreset || 30) || 30));
  const sceneSlotSeconds = () => {
    const fixed = !!(document.getElementById('cdVideoSceneEvery4')?.checked ?? d.videoSceneEvery4);
    if (!fixed) return 0;
    const raw = Number(document.getElementById('cdVideoShotSeconds')?.value || d.videoShotSeconds || 4);
    return Math.max(2, Math.min(12, Number.isFinite(raw) ? raw : 4));
  };
  const maxScenesByBudget = () => {
    const target = targetVideoSeconds();
    const slot = sceneSlotSeconds();
    if (slot > 0) return Math.max(1, Math.floor(target / slot));
    return Math.max(1, Math.floor(target / 2));
  };
  const trimWords = (text, maxWords) => {
    const words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!Number.isFinite(maxWords) || maxWords <= 0 || words.length <= maxWords) return String(text || '').trim();
    return words.slice(0, maxWords).join(' ');
  };
  const normalizeVideoScenesBudget = ({ silent = false } = {}) => {
    if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return { ok: true };
    const target = targetVideoSeconds();
    const fixedSlot = sceneSlotSeconds();
    const maxScenes = maxScenesByBudget();
    let scenes = d.videoStructure.scenes.slice();
    let truncatedCount = 0;
    if (scenes.length > maxScenes) {
      truncatedCount = scenes.length - maxScenes;
      scenes = scenes.slice(0, maxScenes);
    }
    scenes = scenes.map((scene, idx) => {
      const raw = String(scene?.text || '').trim();
      const slot = fixedSlot > 0 ? fixedSlot : Math.max(1.8, Number(scene?.duration_s || (target / Math.max(1, scenes.length))) || 2.5);
      const maxWords = Math.max(6, Math.floor(slot * wordsPerSecond));
      const clipped = trimWords(raw, maxWords);
      const estimated = Math.max(1.2, Number((clipped.split(/\s+/).filter(Boolean).length / wordsPerSecond).toFixed(2)));
      return {
        ...(scene || {}),
        index: idx,
        text: clipped,
        duration_s: fixedSlot > 0 ? fixedSlot : Math.max(1.5, Math.min(12, estimated)),
      };
    });
    const sum = scenes.reduce((acc, s) => acc + (Number(s?.duration_s || 0) || 0), 0);
    if (fixedSlot <= 0 && sum > 0) {
      const ratio = target / sum;
      scenes = scenes.map((s) => ({ ...s, duration_s: Math.max(1.5, Math.min(12, Number((Number(s.duration_s || 0) * ratio).toFixed(2)))) }));
    }
    d.videoStructure.scenes = scenes;
    syncVideoStructureFromInputs();
    if (!silent && truncatedCount > 0) {
      state.notice = { type: 'ok', text: `Сцены ограничены под выбранную длительность: удалено ${truncatedCount}.` };
    }
    return { ok: true, target, scenes: scenes.length };
  };
  const validateVideoScenesBudget = () => {
    if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return { ok: false, message: 'Сначала сгенерируйте структуру видео.' };
    const target = targetVideoSeconds();
    const fixedSlot = sceneSlotSeconds();
    const maxScenes = maxScenesByBudget();
    const scenes = d.videoStructure.scenes;
    if (!scenes.length) return { ok: false, message: 'Добавьте хотя бы одну сцену.' };
    if (scenes.length > maxScenes) return { ok: false, message: `Слишком много сцен для ${target} сек. Максимум: ${maxScenes}.` };
    for (const s of scenes) {
      const text = String(s?.text || '').trim();
      if (!text) return { ok: false, message: 'У каждой сцены должен быть текст.' };
      const slot = fixedSlot > 0 ? fixedSlot : Math.max(1.8, Number(s?.duration_s || 2.5) || 2.5);
      const maxWords = Math.max(6, Math.floor(slot * wordsPerSecond));
      const words = text.split(/\s+/).filter(Boolean).length;
      if (words > maxWords) {
        return { ok: false, message: `Сцена "${(Number(s?.index || 0) + 1)}" слишком длинная. Максимум ~${maxWords} слов.` };
      }
    }
    return { ok: true };
  };
  const syncVideoStructureFromInputs = () => {
    if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return;
    d.videoStructure.scenes = d.videoStructure.scenes.map((scene, idx) => ({ ...(scene || {}), index: idx }));
    const sceneTexts = d.videoStructure.scenes
      .map((s) => String(s?.text || '').trim())
      .filter(Boolean);
    if (!d.videoStructure.subtitles || typeof d.videoStructure.subtitles !== 'object') {
      d.videoStructure.subtitles = { enabled: true, lines: sceneTexts };
    } else {
      d.videoStructure.subtitles.lines = sceneTexts;
    }
  };
  const collectPro = () => ({
    audienceSegment: String(document.getElementById('cdAudience')?.value || d.audienceSegment || '').trim(),
    length: document.getElementById('cdLength')?.value || d.length || 'medium',
    style: document.getElementById('cdStyle')?.value || d.style || 'short',
    brandRules: String(document.getElementById('cdRules')?.value || d.brandRules || '').trim(),
  });
  const selectedProjectId = () => Number(state.projects?.[0]?.id || 0) || null;
  const planHorizonDays = () => (d.planHorizon === 'month' ? 30 : 7);
  const loadPlanItems = async () => {
    const projectId = selectedProjectId();
    const rows = await api(`/api/content-plan?project_id=${projectId || ''}`);
    const now = Date.now();
    const horizonMs = planHorizonDays() * 24 * 60 * 60 * 1000;
    const list = (Array.isArray(rows) ? rows : [])
      .filter((x) => {
        const ts = new Date(x.scheduled_at || '').getTime();
        return Number.isFinite(ts) && ts >= now && ts <= (now + horizonMs);
      })
      .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
      .slice(0, d.planHorizon === 'month' ? 30 : 10);
    d.planItems = list;
    d.planItemsAll = Array.isArray(rows) ? rows : [];
    d.planLoaded = true;
  };
  const buildContentPlan = async () => {
    const base = collectPayloadBase();
    if (!base.topic) throw new Error('Введите нишу/тему для плана.');
    d.planLoading = true;
    render();
    try {
      await api('/api/ai-smm-manager/start', {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId(),
          business_type: base.topic,
          niche: base.topic,
          goal: base.goal,
          language: base.language || 'ru',
        }),
        timeoutMs: 180000,
      });
      await loadPlanItems();
      state.notice = { type: 'ok', text: `План на ${d.planHorizon === 'month' ? 'месяц' : 'неделю'} сформирован.` };
    } finally {
      d.planLoading = false;
      render();
    }
  };
  const loadBestTimes = async () => {
    const platform = String(d.activePlatform || 'instagram').toLowerCase();
    const out = await api(`/api/ai/best-posting-times?days=90&platform=${encodeURIComponent(platform)}`);
    d.bestSlots = out || null;
    const first = Array.isArray(out?.next_slots) ? out.next_slots[0] : null;
    if (first) d.scheduleAt = toLocalInputValue(first);
  };
  const buildLocalDraftFallback = (topic, angle, platforms) => {
    const list = Array.isArray(platforms) && platforms.length ? platforms : ['facebook'];
    const out = [];
    list.forEach((p) => {
      for (let i = 1; i <= 3; i += 1) {
        out.push({
          id: `local-${p}-${i}`,
          platform: p,
          variant: i,
          variant_index: i,
          post_text: `${topic}\n\n${angle}\n\n1) Короткий контекст.\n2) Практический шаг на сегодня.\n3) Результат и следующий шаг.`,
          cta: 'Напишите «ПЛАН» в комментариях — отправлю структуру.',
          hashtags: ['#контент', '#маркетинг', '#smm'],
          warnings: ['network_fallback'],
        });
      }
    });
    return out;
  };
  const normalizeDraftTextForTopic = (text, topic, angle, platform) => {
    const raw = String(text || '').replace(/\s+/g, ' ').trim();
    const sentences = raw.match(/[^.!?]+[.!?]?/g) || [raw];
    const seen = new Set();
    const cleaned = [];
    for (const s of sentences) {
      const one = String(s || '').replace(/\s+/g, ' ').trim();
      if (!one) continue;
      const key = one.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, '').replace(/\s+/g, ' ').trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      cleaned.push(one);
    }
    let body = cleaned.join(' ').trim();
    const topicWords = String(topic || '')
      .toLowerCase()
      .split(/[^\p{L}\p{N}]+/u)
      .map((w) => w.trim())
      .filter((w) => w.length >= 4);
    const hasTopic = topicWords.some((w) => body.toLowerCase().includes(w));
    if (!hasTopic && String(topic || '').trim()) {
      body = `${String(topic).trim()}. ${body}`.trim();
    }
    if (!body) {
      body = `${String(topic || 'Тема').trim()}\n\n${String(angle || 'Практический подход').trim()}\n\n1) Что важно клиенту.\n2) Что вы предлагаете.\n3) Как записаться.`;
    }
    const platformHint = platform === 'instagram'
      ? 'Сохраните пост и напишите в директ для деталей.'
      : (platform === 'facebook'
        ? 'Напишите в сообщения — подскажем лучший вариант для вас.'
        : 'Смотрите до конца и переходите по ссылке в описании.');
    if (!body.toLowerCase().includes(platformHint.toLowerCase())) {
      body = `${body}\n\n${platformHint}`.trim();
    }
    return body;
  };
  const normalizeDraftRowsForPreview = (rows, topic, angle) => {
    const list = Array.isArray(rows) ? rows : [];
    return list.map((row, idx) => {
      const platform = String(row?.platform || 'facebook').trim().toLowerCase();
      const normalizedText = normalizeDraftTextForTopic(row?.post_text || row?.body_text || '', topic, angle, platform);
      return {
        ...(row || {}),
        platform,
        variant: Number(row?.variant || row?.variant_index || ((idx % 3) + 1)),
        variant_index: Number(row?.variant_index || row?.variant || ((idx % 3) + 1)),
        post_text: normalizedText,
      };
    });
  };
  let regenerateSeq = 0;
  const applySelectedTagsToActiveDraft = () => {
    const draft = activeDraft();
    if (!draft) return;
    if (Array.isArray(d.selectedHashtags) && d.selectedHashtags.length) {
      draft.hashtags = d.selectedHashtags.slice(0, 20);
    }
  };
  const applySelectedCtaToActiveDraft = () => {
    const draft = activeDraft();
    if (!draft) return;
    const cta = String(d.selectedCta || '').trim();
    if (cta) draft.cta = cta;
  };
  const isPlanQuickAction = () => ['weekly_plan', 'monthly_plan'].includes(String(d.quickActionType || '').trim());
  const isMonthlyPlanQuickAction = () => String(d.quickActionType || '').trim() === 'monthly_plan';
  const resetVideoGenerationState = ({ clearStructure = true } = {}) => {
    if (clearStructure) {
      d.videoStructure = null;
      d.videoStructureExpanded = false;
    }
    d.selectedHashtags = [];
    d.selectedCta = '';
    d.videoJobId = null;
    d.videoJobStatus = '';
    d.videoProgress = 0;
    d.videoStep = 'queued';
    d.videoMessage = '';
    d.videoPreviewUrl = '';
    d.videoFinalUrl = '';
    d.videoSrtUrl = '';
    d.videoDebug = null;
    d.videoRenderedVoiceGender = '';
    d.videoRenderedVoiceTone = '';
    d.videoRenderRequestedVoiceGender = '';
    d.videoRenderRequestedVoiceTone = '';
    d.videoRenderLoading = false;
    d.videoCoverUrl = '';
    if (Object.prototype.hasOwnProperty.call(d, 'videoError')) d.videoError = '';
  };
  const getEffectiveSelectedTopic = (fallback = '') => directorEffectiveTopic(d, fallback);
  const applySuggestedTopicSelection = (topic) => {
    d.selectedSuggestedTopic = String(topic || '').trim();
    d.appliedManualTopic = '';
    d.activeVariant = 1;
    state.notice = null;
    if (d.imageEnabled) d.imageUrl = '';
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') d.videoCoverUrl = '';
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') {
      resetVideoGenerationState({ clearStructure: true });
    }
  };
  const applyManualTopicSelection = (topic) => {
    d.appliedManualTopic = String(topic || '').trim();
    d.selectedSuggestedTopic = '';
    d.activeVariant = 1;
    state.notice = null;
    if (d.imageEnabled) d.imageUrl = '';
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') d.videoCoverUrl = '';
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') {
      resetVideoGenerationState({ clearStructure: true });
    }
  };
  const mergeTopicPool = (existing, incoming) => {
    const out = [];
    const seen = new Set();
    const push = (v) => {
      const key = String(v || '').trim();
      if (!key) return;
      const low = key.toLowerCase();
      if (seen.has(low)) return;
      seen.add(low);
      out.push(key);
    };
    (Array.isArray(existing) ? existing : []).forEach(push);
    (Array.isArray(incoming) ? incoming : []).forEach(push);
    return out.slice(0, DIRECTOR_TOPIC_IDEA_COUNT);
  };
  const mergeUniquePlanStrings = (existing, incoming, limit = 64) => {
    const out = [];
    const seen = new Set();
    const push = (value) => {
      const text = String(value || '').trim();
      if (!text) return;
      const key = text.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push(text);
    };
    (Array.isArray(existing) ? existing : []).forEach(push);
    (Array.isArray(incoming) ? incoming : []).forEach(push);
    return out.slice(0, limit);
  };
  const buildPlanFlowItemsFromAi = ({ count, topics, angles, ctaOptions, hashtagSets, slots }) => {
    const total = Math.max(1, Number(count || 0) || 0);
    const topicList = mergeUniquePlanStrings([], topics || [], Math.max(total, 8));
    if (!topicList.length) throw new Error('AI не вернул темы для плана.');
    const angleList = mergeUniquePlanStrings([], angles || [], 24);
    const ctaList = mergeUniquePlanStrings([], ctaOptions || [], 24);
    const tagSets = (Array.isArray(hashtagSets) ? hashtagSets : []).map((set) => normalizeHashtagSet(set)).filter((set) => Array.isArray(set) && set.length);
    const formatPool = ['expert_post', 'checklist_post', 'story_post', 'carousel', 'sales_post', 'tutorial_post', 'comparison_post'];
    return Array.from({ length: total }, (_, idx) => {
      const topic = topicList[idx % topicList.length];
      const angle = angleList[idx % Math.max(1, angleList.length)] || '';
      const cta = ctaList[idx % Math.max(1, ctaList.length)] || '';
      const hashtags = directorPreferNicheHashtags(d, tagSets[idx % Math.max(1, tagSets.length)] || [], 8).join(' ');
      return {
        day: idx + 1,
        topic,
        angle,
        cta,
        hashtags,
        scheduled_at: String((Array.isArray(slots) ? slots[idx] : '') || '').trim(),
        contentFormat: formatPool[idx % formatPool.length],
        objective: d.goal || 'engagement',
        contentType: 'post',
      };
    });
  };
  const fetchPlanAiSuggestions = async (requiredCount) => {
    const base = collectPayloadBase();
    if (!String(base.topic || '').trim()) throw new Error('Выберите нишу или укажите свою тему.');
    if (!base.platforms.length) throw new Error('Выберите хотя бы одну платформу.');
    const topics = [];
    const angles = [];
    const ctaOptions = [];
    const hashtagSets = [];
    const batchCount = Math.max(1, Math.ceil(Number(requiredCount || 1) / Math.max(1, DIRECTOR_TOPIC_IDEA_COUNT)));
    for (let idx = 0; idx < batchCount; idx += 1) {
      const out = await api('/api/ai/director/suggest', {
        method: 'POST',
        body: JSON.stringify({ ...base, variation_seed: Number(d.quickActionSeed || 0) + idx }),
        timeoutMs: 120000,
      });
      const data = out?.data || {};
      topics.push(...(Array.isArray(data.topics) ? data.topics : []));
      angles.push(...(Array.isArray(data.angles) ? data.angles : []));
      ctaOptions.push(...(Array.isArray(data.cta_options) ? data.cta_options : []));
      hashtagSets.push(...(Array.isArray(data.hashtag_sets) ? data.hashtag_sets : []));
      d.warnings = Array.isArray(out?.warnings) ? out.warnings : [];
      d.debugCode = out?.debug_code || '';
    }
    const mergedTopics = mergeUniquePlanStrings([], topics, Math.max(requiredCount, 8));
    if (!mergedTopics.length) throw new Error('AI не смог подобрать темы для плана.');
    return {
      topics: mergedTopics,
      angles: mergeUniquePlanStrings([], angles, 24),
      ctaOptions: mergeUniquePlanStrings([], ctaOptions, 24),
      hashtagSets,
    };
  };

  let suggestSeq = 0;
  let suggestAbortController = null;

  const requestTopicSuggestions = async ({ seed = 0, notify = true } = {}) => {
    const base = collectPayloadBase();
    const video = normalizeDirectorContentType(d.contentType) === 'video' ? collectVideo() : {};
    d.topic = base.topic;
    d.offer = base.offer || '';
    d.goal = base.goal;
    d.language = base.language;
    d.tone = base.tone;
    if (!String(base.topic || '').trim()) throw new Error('Введите нишу/тему.');
    if (!base.platforms.length) throw new Error('Выберите хотя бы одну платформу.');
    const seq = ++suggestSeq;
    if (suggestAbortController) {
      try { suggestAbortController.abort(); } catch {}
    }
    suggestAbortController = new AbortController();
    d.loadingSuggest = true;
    d.loadingDrafts = false;
    d.status = 'loading';
    d.warnings = [];
    render();
    try {
      const out = await api('/api/ai/director/suggest', {
        method: 'POST',
        body: JSON.stringify({ ...base, ...video, variation_seed: seed }),
        timeoutMs: 120000,
        signal: suggestAbortController.signal,
      });
      if (seq !== suggestSeq) return null;
      const suggestData = out?.data || {};
      const freshTopics = buildDirectorTopicPool(seed, suggestData.topics || []);
      d.suggestions = suggestData;
      d.topicPool = freshTopics;
      if (!String(d.appliedManualTopic || '').trim() && !String(d.selectedSuggestedTopic || '').trim()) {
        d.selectedSuggestedTopic = String(freshTopics[0] || base.topic || '').trim();
      }
      if (!String(d.selectedAngle || '').trim()) {
        const localAngles = directorLocalAngles(d);
        d.selectedAngle = String((suggestData.angles || [])[0] || localAngles[0] || 'Практический подход: шаги и сроки').trim();
      }
      d.selectedHashtags = directorPreferNicheHashtags(d, suggestData.hashtag_sets?.[0], 8);
      d.selectedCta = String((suggestData.cta_options || [])[0] || '').trim();
      d.warnings = out?.warnings || [];
      d.debugCode = out?.debug_code || '';
      d.loadingSuggest = false;
      d.status = 'ready';
      const preferredPlatform = Array.isArray(base.platforms) && base.platforms.length ? base.platforms[0] : 'facebook';
      if (!base.platforms.includes(String(d.activePlatform || '').toLowerCase())) d.activePlatform = preferredPlatform;
      if (notify) {
        state.notice = { type: 'ok', text: freshTopics.length ? `AI подобрал ${DIRECTOR_TOPIC_IDEA_COUNT} тем. Выберите нужную.` : 'Темы обновлены.' };
      }
      return suggestData;
    } catch (e) {
      if (seq !== suggestSeq) return null;
      if (e && /долго отвечает/i.test(String(e.message || ''))) throw e;
      if (e && String(e.name || '').toLowerCase() === 'aborterror') return null;
      d.loadingSuggest = false;
      d.status = 'error';
      throw e;
    } finally {
      if (seq === suggestSeq) suggestAbortController = null;
      render();
    }
  };

  const generateVideoStructureFromSelection = async () => {
    const base = collectPayloadBase();
    const video = collectVideo();
    const selectedTopic = getEffectiveSelectedTopic(base.topic);
    if (!selectedTopic) {
      state.notice = { type: 'error', text: 'Сначала выберите тему для видео.' };
      render();
      return;
    }
    if (!String(d.selectedAngle || '').trim()) {
      d.selectedAngle = String((Array.isArray(d.suggestions?.angles) ? d.suggestions.angles[0] : '') || directorLocalAngles(d)[0] || 'Практический подход: шаги и сроки').trim();
    }
    resetVideoGenerationState({ clearStructure: true });
    d.selectedHashtags = [];
    d.selectedCta = '';
    d.videoStructureLoading = true;
    d.status = 'loading';
    d.warnings = [];
    render();
    try {
      const targetSeconds = Math.max(20, Math.min(480, Number(video.duration_preset || 30) || 30));
      const out = await api('/api/video/structure', {
        method: 'POST',
        body: JSON.stringify({
          topic: selectedTopic,
          niche_visual_profile: directorCurrentNicheId(d),
          offer: base.offer,
          language: base.language || 'ru',
          style: base.tone || 'friendly',
          target_seconds: targetSeconds,
          orientation: video.orientation || 'vertical',
          scene_every_4s: !!video.scene_every_4s,
          scene_seconds: Number(video.shot_seconds || 0) || 0,
        }),
        timeoutMs: 120000,
      });
      d.videoStructure = out?.data || null;
      d.videoStructureExpanded = false;
      normalizeVideoScenesBudget({ silent: true });
      if (String(d.appliedManualTopic || '').trim()) d.appliedManualTopic = selectedTopic;
      else d.selectedSuggestedTopic = selectedTopic;
      d.selectedHashtags = normalizeHashtagSet(out?.data?.hashtags || []);
      d.selectedCta = String(out?.data?.cta || '').trim() || 'Сохраните, чтобы не потерять и напишите «ПЛАН».';
      d.videoStructureLoading = false;
      d.status = 'ready';
      syncQuality();
      state.notice = { type: 'ok', text: 'Структура видео готова. Теперь можно сразу нажать «Собрать видео».' };
    } catch (e) {
      d.videoStructureLoading = false;
      d.status = 'error';
      state.notice = { type: 'error', text: e.message || 'Не удалось сгенерировать структуру видео.' };
    }
    render();
  };

  const generateDirector = async () => {
    const pro = collectPro();
    d.audienceSegment = pro.audienceSegment;
    d.length = pro.length;
    d.style = pro.style;
    d.brandRules = pro.brandRules;
    d.refreshCount = 0;
    d.hashtagsRefreshCount = 0;
    d.ctaRefreshCount = 0;
    d.approachesRefreshCount = 0;
    d.imageRefreshCount = 0;
    d.topicPool = [];
    d.selectedSuggestedTopic = '';
    d.appliedManualTopic = '';
    d.selectedHashtags = [];
    d.selectedCta = '';
    d.imageUrl = '';
    d.videoCoverUrl = '';
    d.manualTopicInput = '';
    if (normalizeDirectorContentType(d.contentType || 'post') === 'video') {
      resetVideoGenerationState({ clearStructure: true });
    }
    try {
      d.topicPool = buildDirectorTopicPool(0, []);
      await requestTopicSuggestions({ seed: 0, notify: true });
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось получить AI рекомендации.' };
      render();
    }
  };

  const runPlanFlow = async () => {
    const base = collectPayloadBase();
    if (!String(base.topic || '').trim()) {
      d.planFlowError = 'Выберите нишу или укажите свою тему.';
      d.planFlowState = 'error';
      render();
      return;
    }
    d.planFlowState = 'loading';
    d.planFlowError = '';
    d.planFlowItems = [];
    d.planFlowProgressStep = 0;
    state.notice = null;
    render();
    const advanceStep = async (idx, wait = 180) => {
      d.planFlowProgressStep = idx;
      render();
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    };
    try {
      const planCount = isMonthlyPlanQuickAction() ? 30 : 7;
      await advanceStep(0, 120);
      const bestOut = await api(`/api/ai/best-posting-times?days=90&platform=${encodeURIComponent(String(base.platforms[0] || 'instagram').toLowerCase())}&horizon_days=${planCount}&posts_per_day=1`);
      d.bestSlots = bestOut || null;
      await advanceStep(1, 120);
      const suggestData = await fetchPlanAiSuggestions(planCount);
      d.topicPool = suggestData.topics.slice(0, DIRECTOR_TOPIC_IDEA_COUNT);
      d.suggestions = {
        ...(d.suggestions || {}),
        topics: suggestData.topics.slice(0, DIRECTOR_TOPIC_IDEA_COUNT),
        angles: suggestData.angles.slice(0, 3),
        cta_options: suggestData.ctaOptions.slice(0, 3),
        hashtag_sets: suggestData.hashtagSets.slice(0, 6),
      };
      if (!String(d.selectedSuggestedTopic || '').trim() && !String(d.appliedManualTopic || '').trim()) {
        const firstTopic = String(suggestData.topics[0] || '').trim();
        if (firstTopic) d.selectedSuggestedTopic = firstTopic;
      }
      if (!String(d.selectedAngle || '').trim()) {
        d.selectedAngle = String(suggestData.angles[0] || '').trim();
      }
      d.selectedHashtags = directorPreferNicheHashtags(d, suggestData.hashtagSets[0], 8);
      d.selectedCta = String(suggestData.ctaOptions[0] || '').trim();
      await advanceStep(2, 120);
      d.planFlowItems = buildPlanFlowItemsFromAi({
        count: planCount,
        topics: suggestData.topics,
        angles: suggestData.angles,
        ctaOptions: suggestData.ctaOptions,
        hashtagSets: suggestData.hashtagSets,
        slots: Array.isArray(bestOut?.next_slots) ? bestOut.next_slots.slice(0, planCount) : [],
      });
      await advanceStep(3, 120);
      await advanceStep(4, 0);
      d.planFlowState = 'generated';
      d.planFlowSelectedDay = Number(d.planFlowItems[0]?.day || d.planFlowSelectedDay || 1) || 1;
      state.notice = { type: 'ok', text: `AI подготовил ${isMonthlyPlanQuickAction() ? 'контент-план на 30 дней' : 'контент-план на 7 дней'}.` };
    } catch (e) {
      d.planFlowState = 'error';
      d.planFlowItems = [];
      d.planFlowError = e.message || 'Не удалось создать план. Попробуйте ещё раз.';
      state.notice = null;
    } finally {
      d.planFlowProgressStep = 0;
      render();
    }
  };
  const getPlanFlowItemByDay = (day) => {
    const dayNum = Number(day || 0) || 0;
    const list = Array.isArray(d.planFlowItems) ? d.planFlowItems : [];
    return list.find((item) => Number(item.day || 0) === dayNum) || null;
  };
  const applyPlanItemToDirector = (item) => {
    if (!item) return;
    const topic = String(item.topic || '').trim();
    const angle = String(item.angle || '').trim();
    const cta = String(item.cta || '').trim();
    applySuggestedTopicSelection(topic);
    d.selectedAngle = angle || String(directorLocalAngles(d)[0] || '').trim();
    d.selectedCta = cta || d.selectedCta || '';
    d.selectedHashtags = parseCampaignHashtags(String(item.hashtags || '').trim()).slice(0, 20);
    d.planFlowSelectedDay = Number(item.day || 1) || 1;
  };

  const refreshTopics = async () => {
    if (Number(d.refreshCount || 0) >= 5) {
      state.notice = { type: 'error', text: 'Лимит обновления тем: 5 раз.' };
      render();
      return;
    }
    d.refreshingTopics = true;
    d.warnings = [];
    render();
    try {
      const nextSeed = Number(d.refreshCount || 0) + 1;
      await requestTopicSuggestions({ seed: nextSeed, notify: false });
      d.refreshCount = nextSeed;
      state.notice = { type: 'ok', text: `Темы обновлены (${d.refreshCount}/5).` };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось обновить темы.' };
    } finally {
      d.refreshingTopics = false;
      render();
    }
  };

  const refreshApproaches = async () => {
    const base = collectPayloadBase();
    const video = normalizeDirectorContentType(d.contentType) === 'video' ? collectVideo() : {};
    if (!String(base.topic || '').trim()) {
      state.notice = { type: 'error', text: 'Сначала введите нишу/тему.' };
      render();
      return;
    }
    if (Number(d.approachesRefreshCount || 0) >= 5) {
      state.notice = { type: 'error', text: 'Лимит обновления подходов: 5 раз.' };
      render();
      return;
    }
    d.refreshingApproaches = true;
    render();
    try {
      const nextSeed = Number(d.approachesRefreshCount || 0) + 1;
      const out = await api('/api/ai/director/suggest', {
        method: 'POST',
        body: JSON.stringify({ ...base, ...video, variation_seed: 300 + nextSeed }),
        timeoutMs: 120000,
      });
      const suggestData = out?.data || {};
      const newAngles = Array.isArray(suggestData.angles) ? suggestData.angles : [];
      if (newAngles.length) {
        d.suggestions = { ...(d.suggestions || {}), angles: newAngles };
        d.selectedAngle = String(newAngles[0] || d.selectedAngle || '').trim();
      }
      d.approachesRefreshCount = nextSeed;
      d.warnings = out?.warnings || [];
      state.notice = { type: 'ok', text: `Подходы обновлены (${d.approachesRefreshCount}/5).` };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось обновить подходы.' };
    } finally {
      d.refreshingApproaches = false;
      render();
    }
  };

  const refreshHashtags = async () => {
    const base = collectPayloadBase();
    const video = normalizeDirectorContentType(d.contentType) === 'video' ? collectVideo() : {};
    if (!String(base.topic || '').trim()) {
      state.notice = { type: 'error', text: 'Сначала введите нишу/тему.' };
      render();
      return;
    }
    if (Number(d.hashtagsRefreshCount || 0) >= 5) {
      state.notice = { type: 'error', text: 'Лимит обновления хештегов: 5 раз.' };
      render();
      return;
    }
    d.refreshingHashtags = true;
    render();
    try {
      const nextSeed = Number(d.hashtagsRefreshCount || 0) + 1;
      const out = await api('/api/ai/director/suggest', {
        method: 'POST',
        body: JSON.stringify({ ...base, ...video, variation_seed: 100 + nextSeed }),
        timeoutMs: 120000,
      });
      const suggestData = out?.data || {};
      const sets = Array.isArray(suggestData.hashtag_sets)
        ? suggestData.hashtag_sets.map((set) => directorPreferNicheHashtags(d, set, 8))
        : [];
      if (sets.length) {
        d.suggestions = { ...(d.suggestions || {}), hashtag_sets: sets };
        d.selectedHashtags = directorPreferNicheHashtags(d, sets[0], 8);
        applySelectedTagsToActiveDraft();
        applySelectedCtaToActiveDraft();
        syncQuality();
      }
      d.hashtagsRefreshCount = nextSeed;
      d.warnings = out?.warnings || [];
      state.notice = { type: 'ok', text: `Хештеги обновлены (${d.hashtagsRefreshCount}/5).` };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось обновить хештеги.' };
    } finally {
      d.refreshingHashtags = false;
      render();
    }
  };

  const refreshCta = async () => {
    const base = collectPayloadBase();
    const video = normalizeDirectorContentType(d.contentType) === 'video' ? collectVideo() : {};
    if (!String(base.topic || '').trim()) {
      state.notice = { type: 'error', text: 'Сначала введите нишу/тему.' };
      render();
      return;
    }
    if (Number(d.ctaRefreshCount || 0) >= 5) {
      state.notice = { type: 'error', text: 'Лимит обновления призыва: 5 раз.' };
      render();
      return;
    }
    d.refreshingCta = true;
    render();
    try {
      const nextSeed = Number(d.ctaRefreshCount || 0) + 1;
      const out = await api('/api/ai/director/suggest', {
        method: 'POST',
        body: JSON.stringify({ ...base, ...video, variation_seed: 200 + nextSeed }),
        timeoutMs: 120000,
      });
      const suggestData = out?.data || {};
      const ctas = Array.isArray(suggestData.cta_options) ? suggestData.cta_options : [];
      if (ctas.length) {
        d.suggestions = { ...(d.suggestions || {}), cta_options: ctas };
        d.selectedCta = String(ctas[0] || '').trim();
        applySelectedCtaToActiveDraft();
        syncQuality();
      }
      d.ctaRefreshCount = nextSeed;
      d.warnings = out?.warnings || [];
      state.notice = { type: 'ok', text: `Призыв обновлен (${d.ctaRefreshCount}/5).` };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось обновить призыв.' };
    } finally {
      d.refreshingCta = false;
      render();
    }
  };

  const generatePreviewImage = async ({ refresh = false, announce = true } = {}) => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    if (!isVideoType && !d.imageEnabled) return;
    const base = collectPayloadBase();
    const draft = activeDraft();
    const topicForImage = getEffectiveSelectedTopic(base.topic || d.topic || '');
    if (!topicForImage) {
      state.notice = { type: 'error', text: 'Сначала выберите или введите тему.' };
      render();
      return;
    }
    if (refresh && Number(d.imageRefreshCount || 0) >= 3) {
      state.notice = { type: 'error', text: 'Лимит обновления картинки: 3 раза.' };
      render();
      return;
    }
    d.imageLoading = true;
    if (isVideoType) d.videoCoverUrl = '';
    else d.imageUrl = '';
    render();
    try {
      const out = await api('/api/ai/director/generate-image', {
        method: 'POST',
        body: JSON.stringify({
          topic: topicForImage,
          caption: String(draft?.post_text || d.caption || '').trim(),
          asset_ideas: Array.isArray(draft?.asset_ideas) ? draft.asset_ideas : [],
          niche_label: directorCurrentNicheMeta(d)?.label || '',
          niche_context: directorNicheAiContext(d),
          language: base.language || d.language || 'ru',
          tone: base.tone || d.tone || 'friendly',
          style: isVideoType ? 'cinematic' : 'реалистично',
          no_text_on_image: true,
          realism: true,
        }),
        timeoutMs: 120000,
      });
      const imageUrl = String(out?.data?.image_url || '').trim();
      if (!imageUrl) throw new Error(isVideoType ? 'Сервер не вернул обложку для видео.' : 'Сервер не вернул картинку для поста.');
      if (isVideoType) d.videoCoverUrl = imageUrl;
      else d.imageUrl = imageUrl;
      if (refresh) d.imageRefreshCount = Number(d.imageRefreshCount || 0) + 1;
      if (announce) {
        state.notice = {
          type: 'ok',
          text: isVideoType
            ? (refresh ? `Обложка обновлена (${d.imageRefreshCount}/3).` : 'Обложка видео сгенерирована.')
            : (refresh ? `Картинка обновлена (${d.imageRefreshCount}/3).` : 'Картинка сгенерирована.'),
        };
      }
    } catch (e) {
      if (announce) {
        state.notice = { type: 'error', text: e.message || (isVideoType ? 'Не удалось сгенерировать обложку.' : 'Не удалось сгенерировать картинку.') };
      }
      throw e;
    } finally {
      d.imageLoading = false;
      render();
    }
  };

  const regenerateBySelection = async (variantsCount = 1) => {
    const base = collectPayloadBase();
    const video = normalizeDirectorContentType(d.contentType) === 'video' ? collectVideo() : {};
    const selectedTopic = getEffectiveSelectedTopic(base.topic);
    if (!selectedTopic || !d.selectedAngle) return;
    const seq = ++regenerateSeq;
    d.loadingDrafts = true;
    d.status = 'loading';
    render();
    try {
      const draftsOut = await api('/api/ai/director/generate-drafts', {
        method: 'POST',
        body: JSON.stringify({
          ...base,
          ...video,
          topic: selectedTopic,
          angle: d.selectedAngle,
          variants: Math.max(1, Math.min(Number(variantsCount || 1), 3)),
        }),
        timeoutMs: 180000,
      });
      if (seq !== regenerateSeq) return;
      d.loadingDrafts = false;
      d.status = 'ready';
      d.briefId = draftsOut?.data?.brief_id || d.briefId || null;
      const incomingDrafts = Array.isArray(draftsOut?.data?.drafts) ? draftsOut.data.drafts : [];
      d.drafts = normalizeDraftRowsForPreview(
        incomingDrafts.length ? incomingDrafts : d.drafts,
        selectedTopic || base.topic || d.topic || 'Тема',
        d.selectedAngle || 'Практический подход',
      );
      d.activeVariant = 1;
      d.lastDraftTopic = selectedTopic;
      d.lastDraftAngle = String(d.selectedAngle || '').trim();
      applySelectedTagsToActiveDraft();
      applySelectedCtaToActiveDraft();
      d.warnings = draftsOut?.warnings || [];
      syncQuality();
      render();
    } catch (e) {
      if (seq !== regenerateSeq) return;
      d.loadingDrafts = false;
      d.status = 'partial';
      d.drafts = buildLocalDraftFallback(selectedTopic || base.topic || d.topic || 'Тема', d.selectedAngle || 'Практический подход', base.platforms);
      d.activeVariant = 1;
      d.lastDraftTopic = selectedTopic;
      d.lastDraftAngle = String(d.selectedAngle || '').trim();
      applySelectedTagsToActiveDraft();
      applySelectedCtaToActiveDraft();
      d.warnings = ['network_fallback'];
      syncQuality();
      state.notice = { type: 'error', text: `Сеть нестабильна (${e.message || 'Failed to fetch'}). Показаны локальные варианты.` };
      render();
    }
  };

  const saveBtn = document.getElementById('cdSave');
  if (saveBtn) {
    saveBtn.onclick = () => {
      const draft = activeDraft();
      if (!draft) return;
      state.notice = { type: 'ok', text: `Черновик #${draft.id} уже сохранён в базе.` };
      render();
    };
  }
  const scheduleOrPublish = async (action) => {
    const draft = activeDraft();
    if (!draft?.id) throw new Error('Черновик не выбран');
    if (action === 'schedule' && !d.scheduleAt) {
      try {
        await loadBestTimes();
      } catch {
        // keep manual scheduling if AI timing is unavailable
      }
    }
    const payload = {};
    if (action === 'schedule') {
      const at = document.getElementById('cdScheduleAt')?.value || d.scheduleAt || '';
      if (!at) throw new Error('Укажите дату/время для планирования.');
      d.scheduleAt = at;
      payload.schedule_at = localInputToIsoNoTz(at);
      if (!payload.schedule_at) throw new Error('Некорректная дата/время.');
    }
    return api(`/api/content/drafts/${Number(draft.id)}/${action}`, { method: 'POST', body: JSON.stringify(payload), timeoutMs: 180000 });
  };
  const scheduleBtn = document.getElementById('cdSchedule');
  if (scheduleBtn) scheduleBtn.onclick = async () => {
    try {
      await scheduleOrPublish('schedule');
      state.notice = { type: 'ok', text: 'Черновик запланирован.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось запланировать.' };
      render();
    }
  };
  const publishBtn = document.getElementById('cdPublish');
  if (publishBtn) publishBtn.onclick = async () => {
    try {
      await scheduleOrPublish('publish');
      state.notice = { type: 'ok', text: 'Отправлено в публикацию.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось опубликовать.' };
      render();
    }
  };

  const genBtn = document.getElementById('cdGenerateIdeas');
  if (genBtn) genBtn.onclick = () => {
    if (Array.isArray(d.topicPool) && d.topicPool.length) {
      refreshTopics();
      return;
    }
    generateDirector();
  };
  const generateContentFromCurrentSelection = async () => {
    const shouldGenerateImage = normalizeDirectorContentType(d.contentType || 'post') !== 'video' && !!d.imageEnabled;
    if (normalizeDirectorContentType(d.contentType) === 'video') {
      await generateVideoStructureFromSelection();
      return;
    }
    const base = collectPayloadBase();
    if (!String(getEffectiveSelectedTopic(base.topic) || '').trim()) {
      applySuggestedTopicSelection(String(base.topic || '').trim());
    }
    if (!String(d.selectedAngle || '').trim()) {
      d.selectedAngle = String((Array.isArray(d.suggestions?.angles) ? d.suggestions.angles[0] : '') || directorLocalAngles(d)[0] || 'Практический подход: шаги и сроки').trim();
    }
    await regenerateBySelection(1);
    if (shouldGenerateImage) {
      try {
        await generatePreviewImage({ refresh: false, announce: false });
      } catch {
        state.notice = { type: 'error', text: 'Пост сгенерирован, но картинку создать не удалось.' };
        render();
        return;
      }
    }
    state.notice = { type: 'ok', text: 'Пост сгенерирован по выбранной теме.' };
    render();
  };
  const genSelectedBtn = document.getElementById('cdGenerateSelected');
  if (genSelectedBtn) genSelectedBtn.onclick = () => {
    if (Array.isArray(d.topicPool) && d.topicPool.length) {
      refreshTopics();
      return;
    }
    generateDirector();
  };
  const generatePlanFlowBtn = document.getElementById('cdGeneratePlanFlow');
  if (generatePlanFlowBtn) generatePlanFlowBtn.onclick = async () => {
    await runPlanFlow();
  };
  const renderVideoBtn = document.getElementById('cdRenderVideo');
  if (renderVideoBtn) renderVideoBtn.onclick = async () => {
    syncVideoStructureFromInputs();
    const base = collectPayloadBase();
    const video = collectVideo();
    const resolvedTopic = getEffectiveSelectedTopic(base.topic);
    if (!String(resolvedTopic || '').trim()) {
      state.notice = { type: 'error', text: 'Введите тему для видео.' };
      render();
      return;
    }
    d.videoRenderLoading = true;
    d.videoJobStatus = 'queued';
    d.videoProgress = 0;
    d.videoStep = 'queued';
    d.videoMessage = 'Задача поставлена в очередь';
    d.videoPreviewUrl = '';
    d.videoFinalUrl = '';
    d.videoSrtUrl = '';
    d.videoDebug = null;
    d.videoRenderRequestedVoiceGender = String(video.voice_gender || d.videoVoiceGender || 'male').toLowerCase();
    d.videoRenderRequestedVoiceTone = String(video.voice_tone || d.videoVoiceTone || 'neutral').toLowerCase();
    render();
    try {
      const budgetCheck = validateVideoScenesBudget();
      if (!budgetCheck.ok) throw new Error(budgetCheck.message || 'Проверьте структуру видео.');
      normalizeVideoScenesBudget({ silent: true });
      const targetSeconds = Math.max(20, Math.min(480, Number(video.duration_preset || 30) || 30));
      const format = String(video.orientation || 'vertical') === 'horizontal' ? 'long' : 'short';
      const start = await api('/api/ai/video/render', {
        method: 'POST',
        body: JSON.stringify({
          topic: resolvedTopic,
          offer: base.offer,
          language: base.language || 'ru',
          style: base.tone || 'friendly',
          format,
          target_seconds: targetSeconds,
          orientation: video.orientation || 'vertical',
          voice_gender: String(video.voice_gender || d.videoVoiceGender || 'male').toLowerCase(),
          voice_tone: String(video.voice_tone || d.videoVoiceTone || 'neutral').toLowerCase(),
          scene_seconds: Number(video.shot_seconds || 0) || 0,
          minimize_repeats: !!video.minimize_repeats,
          realistic_only: !!video.realistic_only,
          avoid_duplicate_footage: true,
          niche_visual_profile: directorCurrentNicheId(d),
          diversity_mode: format === 'short' ? 'high' : 'balanced',
          allow_emergency_reuse: format === 'short' ? false : true,
          subtitle_mode: 'auto',
          platform_target: String(d.activePlatform || 'facebook').toLowerCase(),
          subtitle_style: 'social_default',
          min_unique_clips_short: 8,
          fallback_related_keywords: true,
          custom_title: String(d.videoStructure?.title || resolvedTopic).trim(),
          custom_description: String(d.videoStructure?.description || '').trim(),
          custom_hashtags: Array.isArray(d.videoStructure?.hashtags) ? d.videoStructure.hashtags : (Array.isArray(d.selectedHashtags) ? d.selectedHashtags : []),
          custom_cta: String(d.selectedCta || d.videoStructure?.cta || '').trim(),
          custom_scenes: Array.isArray(d.videoStructure?.scenes)
            ? d.videoStructure.scenes.map((s, idx) => ({
                index: idx,
                text: String(s?.text || '').trim(),
                duration_s: Number(s?.duration_s || 0) || 0,
                scene_type: String(s?.scene_type || 'work').trim(),
                queries: Array.isArray(s?.queries) ? s.queries : [],
              })).filter((s) => s.text)
            : [],
        }),
        timeoutMs: 120000,
      });
      d.videoJobId = Number(start?.job_id || 0) || null;
      if (!d.videoJobId) throw new Error('Не удалось получить id задачи видео.');
      for (let i = 0; i < 180; i += 1) {
        await new Promise((r) => setTimeout(r, 1500));
        const hadPlayable = !!String(d.videoFinalUrl || d.videoPreviewUrl || '').trim();
        const st = await api(`/api/ai/video/jobs/${d.videoJobId}`, { timeoutMs: 120000 });
        const status = String(st?.status || '').toLowerCase();
        const progress = Math.max(0, Math.min(100, Number(st?.progress || 0)));
        d.videoProgress = progress;
        d.videoStep = String(st?.step || d.videoStep || 'queued').toLowerCase();
        d.videoMessage = String(st?.message || '').trim();
        d.videoJobStatus = `${status || 'running'} ${progress}%`;
        d.videoDebug = (st?.debug && typeof st.debug === 'object') ? st.debug : ((st?.result?.debug && typeof st.result.debug === 'object') ? st.result.debug : null);
        d.videoSrtUrl = String(st?.subtitlesSrtUrl || st?.result?.subtitles_srt_url || '').trim();
        if (String(st?.previewUrl || '').trim()) {
          const raw = String(st.previewUrl).trim();
          d.videoPreviewUrl = `${raw}${raw.includes('?') ? '&' : '?'}v=${Date.now()}`;
        }
        if (String(st?.finalUrl || '').trim()) {
          const raw = String(st.finalUrl).trim();
          d.videoFinalUrl = `${raw}${raw.includes('?') ? '&' : '?'}v=${Date.now()}`;
        }
        const hasPlayable = !!String(d.videoFinalUrl || d.videoPreviewUrl || '').trim();
        if (!hadPlayable && hasPlayable) render();
        else refreshVideoProgressDom();
        if (status === 'success') {
          d.videoProgress = 100;
          d.videoMessage = 'Видео готово к публикации.';
          d.videoRenderedVoiceGender = String(d.videoRenderRequestedVoiceGender || d.videoVoiceGender || 'male').toLowerCase();
          d.videoRenderedVoiceTone = String(d.videoRenderRequestedVoiceTone || d.videoVoiceTone || 'neutral').toLowerCase();
          state.notice = { type: 'ok', text: 'Видео собрано. Можно публиковать.' };
          render();
          break;
        }
        if (status === 'error') {
          throw new Error(st?.error || 'Сборка видео завершилась ошибкой.');
        }
      }
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось собрать видео.' };
    } finally {
      d.videoRenderLoading = false;
      render();
    }
  };
  const publishVideoBtn = document.getElementById('cdPublishVideo');
  if (publishVideoBtn) publishVideoBtn.onclick = async () => {
    try {
      if (!d.videoJobId) throw new Error('Сначала соберите видео.');
      await api(`/api/video/jobs/${Number(d.videoJobId)}/publish`, {
        method: 'POST',
        body: JSON.stringify({ platforms: selectedPlatforms() }),
        timeoutMs: 180000,
      });
      state.notice = { type: 'ok', text: 'Видео отправлено в публикацию.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось опубликовать видео.' };
      render();
    }
  };
  const downloadVideoBtn = document.getElementById('cdDownloadVideo');
  if (downloadVideoBtn) downloadVideoBtn.onclick = async () => {
    const rawUrl = String(d.videoFinalUrl || d.videoPreviewUrl || '').trim();
    if (!rawUrl) return;
    const cleanUrl = rawUrl.split('?')[0] || rawUrl;
    const baseName = cleanUrl.substring(cleanUrl.lastIndexOf('/') + 1) || `autosocial-video-${Date.now()}.mp4`;
    try {
      const resp = await fetch(rawUrl, { credentials: 'include' });
      if (!resp.ok) throw new Error(`download_failed_${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = baseName.endsWith('.mp4') ? baseName : `${baseName}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
      state.notice = { type: 'ok', text: 'Видео скачивается.' };
      render();
    } catch (_) {
      const a = document.createElement('a');
      a.href = rawUrl;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.download = baseName.endsWith('.mp4') ? baseName : `${baseName}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  };
  const planWeekBtn = document.getElementById('cdPlanWeek');
  if (planWeekBtn) planWeekBtn.onclick = async () => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    nav(plannerUrl(isVideoType ? 'video' : 'post', 7), { keepNotice: true });
  };
  const planMonthBtn = document.getElementById('cdPlanMonth');
  if (planMonthBtn) planMonthBtn.onclick = async () => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    nav(plannerUrl(isVideoType ? 'video' : 'post', 30), { keepNotice: true });
  };
  const miniWeekBtn = document.getElementById('cdMiniWeek');
  if (miniWeekBtn) miniWeekBtn.onclick = async () => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    nav(plannerUrl(isVideoType ? 'video' : 'post', 7), { keepNotice: true });
  };
  const miniMonthBtn = document.getElementById('cdMiniMonth');
  if (miniMonthBtn) miniMonthBtn.onclick = async () => {
    const isVideoType = normalizeDirectorContentType(d.contentType || 'post') === 'video';
    nav(plannerUrl(isVideoType ? 'video' : 'post', 30), { keepNotice: true });
  };
  const planGenerateBtn = document.getElementById('cdPlanGenerate');
  if (planGenerateBtn) planGenerateBtn.onclick = async () => {
    try {
      await buildContentPlan();
    } catch (e) {
      d.planLoading = false;
      state.notice = { type: 'error', text: e.message || 'Не удалось сформировать контент-план.' };
      render();
    }
  };
  const planGenerateSidebarBtn = document.getElementById('cdPlanGenerateSidebar');
  if (planGenerateSidebarBtn) planGenerateSidebarBtn.onclick = async () => {
    try {
      await buildContentPlan();
    } catch (e) {
      d.planLoading = false;
      state.notice = { type: 'error', text: e.message || 'Не удалось сформировать контент-план.' };
      render();
    }
  };
  const bestTimesBtn = document.getElementById('cdBestTimes');
  if (bestTimesBtn) bestTimesBtn.onclick = async () => {
    try {
      await loadBestTimes();
      state.notice = { type: 'ok', text: 'AI подобрал лучшие дни и часы.' };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось получить лучшие слоты.' };
    }
    render();
  };
  const miniBestBtn = document.getElementById('cdMiniBest');
  if (miniBestBtn) miniBestBtn.onclick = async () => {
    try {
      await loadBestTimes();
      state.notice = { type: 'ok', text: 'AI подобрал лучшие дни и часы.' };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось получить лучшие слоты.' };
    }
    render();
  };
  const typePostBtn = document.getElementById('cdTypePost');
  if (typePostBtn) typePostBtn.onclick = () => { persistContentType('post'); ensureContentTypePlatforms(); render(); };
  const typeVideoBtn = document.getElementById('cdTypeVideo');
  if (typeVideoBtn) typeVideoBtn.onclick = () => { persistContentType('video'); ensureVideoDefaults(); ensureContentTypePlatforms(); render(); };
  const generationModeManualBtn = document.getElementById('cdGenerationModeManual');
  if (generationModeManualBtn) generationModeManualBtn.onclick = () => { d.generationMode = 'manual'; render(); };
  const generationModePlanBtn = document.getElementById('cdGenerationModePlan');
  if (generationModePlanBtn) generationModePlanBtn.onclick = () => { d.generationMode = 'plan'; render(); };
  const previewTypePostBtn = document.getElementById('cdPreviewTypePost');
  if (previewTypePostBtn) previewTypePostBtn.onclick = () => { persistContentType('post'); ensureContentTypePlatforms(); render(); };
  const previewTypeVideoBtn = document.getElementById('cdPreviewTypeVideo');
  if (previewTypeVideoBtn) previewTypeVideoBtn.onclick = () => { persistContentType('video'); ensureVideoDefaults(); ensureContentTypePlatforms(); render(); };
  const toggleStructureBtn = document.getElementById('cdToggleStructure');
  if (toggleStructureBtn) toggleStructureBtn.onclick = () => {
    d.videoStructureExpanded = !d.videoStructureExpanded;
    render();
  };
  const openVideoBtn = document.getElementById('cdOpenVideo');
  if (openVideoBtn) openVideoBtn.onclick = () => {
    const url = String(d.videoFinalUrl || d.videoPreviewUrl || '').trim();
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  };
  const previewToggleTextBtn = document.getElementById('cdPreviewToggleText');
  if (previewToggleTextBtn) previewToggleTextBtn.onclick = () => {
    const key = String(d.activePlatform || 'facebook').trim().toLowerCase();
    if (!d.previewExpanded || typeof d.previewExpanded !== 'object') d.previewExpanded = {};
    d.previewExpanded[key] = !d.previewExpanded[key];
    refreshDirectorPreviewDom();
  };
  const refreshApproachesBtn = document.getElementById('cdRefreshApproaches');
  if (refreshApproachesBtn) refreshApproachesBtn.onclick = refreshApproaches;
  const refreshTagsBtn = document.getElementById('cdRefreshTags');
  if (refreshTagsBtn) refreshTagsBtn.onclick = refreshHashtags;
  const refreshTagsInlineBtn = document.getElementById('cdRefreshTagsInline');
  if (refreshTagsInlineBtn) refreshTagsInlineBtn.onclick = refreshHashtags;
  const refreshCtaBtn = document.getElementById('cdRefreshCta');
  if (refreshCtaBtn) refreshCtaBtn.onclick = refreshCta;
  const refreshCtaInlineBtn = document.getElementById('cdRefreshCtaInline');
  if (refreshCtaInlineBtn) refreshCtaInlineBtn.onclick = refreshCta;
  const genImageBtn = document.getElementById('cdGenerateImage');
  if (genImageBtn) genImageBtn.onclick = () => generatePreviewImage({ refresh: false });
  const refreshImageBtn = document.getElementById('cdRefreshImage');
  if (refreshImageBtn) refreshImageBtn.onclick = () => generatePreviewImage({ refresh: true });
  const genDraftsBtn = document.getElementById('cdGenerateDrafts');
  if (genDraftsBtn) genDraftsBtn.onclick = async () => {
    if (normalizeDirectorContentType(d.contentType) === 'video') {
      await generateVideoStructureFromSelection();
      return;
    }
    await regenerateBySelection(3);
  };
  const quickActionRefreshBtn = document.getElementById('cdQuickActionRefresh');
  if (quickActionRefreshBtn) quickActionRefreshBtn.onclick = async () => {
    d.quickActionSeed = Number(d.quickActionSeed || 0) + 1;
    if (isPlanQuickAction()) {
      d.planFlowSelectedDay = 1;
      await runPlanFlow();
      return;
    }
    render();
  };
  document.querySelectorAll('[data-cd-plan-select-day]').forEach((btn) => {
    btn.onclick = () => {
      const day = Number(btn.getAttribute('data-cd-plan-select-day') || 0) || 0;
      const item = getPlanFlowItemByDay(day);
      if (!item) return;
      applyPlanItemToDirector(item);
      state.notice = { type: 'ok', text: `День ${day} перенесён в директор. Можно использовать идею дальше.` };
      render();
    };
  });
  const openPlanDayForCreate = async (item, { schedule = false } = {}) => {
    if (!item) return;
    applyPlanItemToDirector(item);
    if (schedule && String(item.scheduled_at || '').trim()) {
      d.scheduleAt = toLocalInputValue(String(item.scheduled_at || '').trim());
    }
    d.quickActionType = '';
    d.quickActionNicheId = '';
    d.quickActionPreviewOnly = false;
    d.planFlowState = 'idle';
    d.planFlowItems = [];
    d.planFlowError = '';
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('quickAction');
      url.searchParams.delete('niche');
      history.replaceState({}, '', `${url.pathname}${url.search}`);
    } catch {}
    render();
    await generateContentFromCurrentSelection();
    if (schedule) {
      state.notice = { type: 'ok', text: `День ${Number(item.day || 0)} подготовлен. Дата и время уже подставлены, можно нажать «Запланировать».` };
      render();
    }
  };
  document.querySelectorAll('[data-cd-plan-schedule-day]').forEach((btn) => {
    btn.onclick = async () => {
      const day = Number(btn.getAttribute('data-cd-plan-schedule-day') || 0) || 0;
      const item = getPlanFlowItemByDay(day);
      if (!item) return;
      await openPlanDayForCreate(item, { schedule: true });
    };
  });
  document.querySelectorAll('[data-cd-plan-edit]').forEach((btn) => {
    btn.onclick = async () => {
      const day = Number(btn.getAttribute('data-cd-plan-edit') || 0) || 0;
      const item = getPlanFlowItemByDay(day);
      if (!item) return;
      await openPlanDayForCreate(item, { schedule: false });
      state.notice = { type: 'ok', text: `День ${day} открыт для ручной доработки в Create.` };
      render();
    };
  });
  document.querySelectorAll('[data-cd-quick-topic]').forEach((btn) => {
    btn.onclick = () => {
      const topic = decodeURIComponent(String(btn.getAttribute('data-cd-quick-topic') || ''));
      const angle = decodeURIComponent(String(btn.getAttribute('data-cd-quick-angle') || ''));
      const cta = decodeURIComponent(String(btn.getAttribute('data-cd-quick-cta') || ''));
      const nextType = normalizeDirectorContentType(btn.getAttribute('data-cd-quick-type') || d.contentType || 'post');
      if (!d.customTopicMode && d.quickActionNicheId) d.topicPreset = d.quickActionNicheId;
      d.contentType = nextType;
      applySuggestedTopicSelection(topic);
      d.selectedAngle = String(angle || directorLocalAngles(d)[0] || '').trim();
      d.selectedCta = String(cta || d.selectedCta || '').trim();
      d.quickActionType = '';
      d.planFlowItems = [];
      state.notice = { type: 'ok', text: 'Тема перенесена в AI Контент-директор. Теперь можно продолжить генерацию.' };
      render();
    };
  });
  document.querySelectorAll('[data-cd-quick-hook]').forEach((btn) => {
    btn.onclick = () => {
      const hook = decodeURIComponent(String(btn.getAttribute('data-cd-quick-hook') || ''));
      if (!d.customTopicMode && d.quickActionNicheId) d.topicPreset = d.quickActionNicheId;
      d.manualTopicInput = hook;
      applyManualTopicSelection(hook);
      d.selectedAngle = String(directorLocalAngles(d)[0] || '').trim();
      d.quickActionType = '';
      d.planFlowItems = [];
      state.notice = { type: 'ok', text: 'Hook выбран как стартовая тема. Теперь можно сгенерировать результат.' };
      render();
    };
  });
  document.querySelectorAll('[data-cd-quick-cta]').forEach((btn) => {
    btn.onclick = () => {
      const cta = decodeURIComponent(String(btn.getAttribute('data-cd-quick-cta') || ''));
      d.selectedCta = cta;
      applySelectedCtaToActiveDraft();
      syncQuality();
      refreshQualityDom();
      state.notice = { type: 'ok', text: 'CTA применён. Можно использовать его в черновике или видео.' };
      render();
    };
  });

  ['cdTopicPreset', 'cdTopic', 'cdManualTopic', 'cdGoal', 'cdOffer', 'cdLang', 'cdTone', 'cdAudience', 'cdLength', 'cdStyle', 'cdRules', 'cdScheduleAt', 'cdVideoOrientation', 'cdVideoDurationPreset', 'cdVideoShotSeconds', 'cdVideoVoiceGender', 'cdVideoVoiceTone'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.oninput = () => {
        if (id === 'cdScheduleAt') d.scheduleAt = el.value;
        if (id === 'cdTopicPreset') {
          d.topicPreset = String(el.value || DEFAULT_DIRECTOR_NICHE).trim() || DEFAULT_DIRECTOR_NICHE;
          resetDirectorTopicSelection({ keepManualInput: false });
          d.topic = directorBaseTopic(d, d.topic);
          render();
          return;
        }
        if (id === 'cdTopic') {
          d.customBaseTopicInput = el.value;
          if (d.customTopicMode) {
            resetDirectorTopicSelection({ keepManualInput: false });
            d.topic = directorBaseTopic(d, d.topic);
          }
        }
        if (id === 'cdManualTopic') d.manualTopicInput = el.value;
        if (id === 'cdOffer') d.offer = el.value;
        if (id === 'cdGoal') d.goal = el.value;
        if (id === 'cdLang') d.language = normalizeContentLanguage(el.value);
        if (id === 'cdTone') d.tone = el.value;
        if (id === 'cdVideoOrientation') d.videoOrientation = el.value;
        if (id === 'cdVideoShotSeconds') d.videoShotSeconds = Math.max(2, Math.min(12, Number(el.value || 4) || 4));
        if (id === 'cdVideoVoiceGender') d.videoVoiceGender = el.value;
        if (id === 'cdVideoVoiceTone') d.videoVoiceTone = el.value;
        if (id === 'cdVideoOrientation') {
          refreshVideoDurationOptionsDom();
          normalizeVideoScenesBudget({ silent: true });
          syncQuality();
          refreshQualityDom();
          refreshDirectorPreviewDom();
          return;
        }
        if (id === 'cdVideoDurationPreset') {
          d.videoDurationPreset = String(el.value || '30');
          normalizeVideoScenesBudget({ silent: true });
          syncQuality();
          refreshQualityDom();
          refreshDirectorPreviewDom();
          return;
        }
        if (id === 'cdVideoShotSeconds') {
          normalizeVideoScenesBudget({ silent: true });
          syncQuality();
          refreshQualityDom();
          refreshDirectorPreviewDom();
          return;
        }
        syncQuality();
      };
      el.onchange = el.oninput;
    }
  });
  const customTopicModeEl = document.getElementById('cdTopicCustomEnabled');
  if (customTopicModeEl) {
    customTopicModeEl.onchange = () => {
      d.customTopicMode = !!customTopicModeEl.checked;
      resetDirectorTopicSelection({ keepManualInput: false });
      d.topic = directorBaseTopic(d, d.topic);
      render();
    };
  }
  const videoScene4El = document.getElementById('cdVideoSceneEvery4');
  if (videoScene4El) {
    videoScene4El.onchange = () => {
      d.videoSceneEvery4 = !!videoScene4El.checked;
      if (d.videoSceneEvery4) d.videoShotSeconds = Math.max(2, Math.min(12, Number(d.videoShotSeconds || 4) || 4));
      normalizeVideoScenesBudget({ silent: true });
      syncQuality();
      refreshQualityDom();
      refreshDirectorPreviewDom();
    };
  }
  const videoMinRepeatsEl = document.getElementById('cdVideoMinimizeRepeats');
  if (videoMinRepeatsEl) {
    videoMinRepeatsEl.onchange = () => {
      d.videoMinimizeRepeats = !!videoMinRepeatsEl.checked;
      syncQuality();
      refreshQualityDom();
    };
  }
  const videoRealisticEl = document.getElementById('cdVideoRealisticOnly');
  if (videoRealisticEl) {
    videoRealisticEl.onchange = () => {
      d.videoRealisticOnly = !!videoRealisticEl.checked;
      syncQuality();
      refreshQualityDom();
    };
  }
  ['cdFb', 'cdIg', 'cdYt'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.onchange = () => {



        ensureContentTypePlatforms();
      };
    }
  });
  const imageEnabledEl = document.getElementById('cdImageEnabled');
  if (imageEnabledEl) {
    imageEnabledEl.onchange = () => {
      d.imageEnabled = !!imageEnabledEl.checked;
      if (!d.imageEnabled) {
        d.imageUrl = '';
        d.imageRefreshCount = 0;
        render();
        return;
      }
      render();
    };
  }

  document.querySelectorAll('[data-cd-topic]').forEach((btn) => {
    btn.onclick = async () => {
      applySuggestedTopicSelection(decodeURIComponent(btn.getAttribute('data-cd-topic') || ''));
      render();
      await generateContentFromCurrentSelection();
    };
  });
  const applyManualTopicBtn = document.getElementById('cdApplyManualTopic');
  if (applyManualTopicBtn) {
    applyManualTopicBtn.onclick = async () => {
      const manual = String(document.getElementById('cdManualTopic')?.value || d.manualTopicInput || '').trim();
      if (!manual) return;
      applyManualTopicSelection(manual);
      render();
      await generateContentFromCurrentSelection();
    };
  }
  document.querySelectorAll('[data-cd-angle]').forEach((btn) => {
    btn.onclick = async () => {
      d.selectedAngle = decodeURIComponent(btn.getAttribute('data-cd-angle') || '');
      state.notice = null;
      d.activeVariant = 1;
      d.drafts = [];
      d.lastDraftTopic = '';
      d.lastDraftAngle = '';
      if (!String(d.appliedManualTopic || '').trim()) {
        const nextTopics = Array.isArray(d.topicPool) && d.topicPool.length
          ? d.topicPool.slice(0, DIRECTOR_TOPIC_IDEA_COUNT)
          : directorLocalTopicIdeas(d, DIRECTOR_TOPIC_IDEA_COUNT, d.refreshCount || 0);
        const nextHeadline = directorHeadlineItems(nextTopics, d.selectedAngle)[0]?.title || '';
        d.selectedSuggestedTopic = String(nextHeadline || '').trim();
      }
      if (d.imageEnabled) d.imageUrl = '';
      if (normalizeDirectorContentType(d.contentType || 'post') === 'video') d.videoCoverUrl = '';
      if (normalizeDirectorContentType(d.contentType || 'post') === 'video') {
        resetVideoGenerationState({ clearStructure: true });
      }
      render();
      await generateContentFromCurrentSelection();
    };
  });
  document.querySelectorAll('[data-cd-hset]').forEach((btn) => {
    btn.onclick = () => {
      const raw = decodeURIComponent(btn.getAttribute('data-cd-hset') || '');
      d.selectedHashtags = normalizeHashtagSet(parseCampaignHashtags(raw).slice(0, 20));
      applySelectedTagsToActiveDraft();
      syncQuality();
      render();
    };
  });
  document.querySelectorAll('[data-cd-cta]').forEach((btn) => {
    btn.onclick = () => {
      d.selectedCta = decodeURIComponent(btn.getAttribute('data-cd-cta') || '');
      applySelectedCtaToActiveDraft();
      syncQuality();
      render();
    };
  });
  document.querySelectorAll('[data-cd-platform]').forEach((btn) => {
    btn.onclick = () => {
      d.activePlatform = btn.getAttribute('data-cd-platform') || 'facebook';
      d.activeVariant = 1;
      syncQuality();
      render();
    };
  });
  document.querySelectorAll('[data-cd-preview-platform]').forEach((btn) => {
    btn.onclick = () => {
      d.activePlatform = btn.getAttribute('data-cd-preview-platform') || 'facebook';
      d.activeVariant = 1;
      syncQuality();
      refreshQualityDom();
      refreshDirectorPreviewDom();
    };
  });
  document.querySelectorAll('[data-cd-variant]').forEach((btn) => {
    btn.onclick = () => {
      d.activeVariant = Number(btn.getAttribute('data-cd-variant') || 1);
      syncQuality();
      render();
    };
  });
  document.querySelectorAll('[data-cd-vtab]').forEach((btn) => {
    btn.onclick = () => {
      d.previewVideoTab = String(btn.getAttribute('data-cd-vtab') || 'meta');
      render();
    };
  });
  document.querySelectorAll('[data-cd-vmeta]').forEach((btn) => {
    btn.onclick = () => {
      d.previewVideoMetaPlatform = String(btn.getAttribute('data-cd-vmeta') || 'facebook');
      render();
    };
  });
  let dragSceneFrom = null;
  document.querySelectorAll('[data-cd-scene]').forEach((el) => {
    el.ondragstart = (ev) => {
      dragSceneFrom = Number(el.getAttribute('data-cd-scene') || -1);
      el.style.opacity = '0.55';
      try { ev.dataTransfer.effectAllowed = 'move'; } catch {}
    };
    el.ondragend = () => {
      dragSceneFrom = null;
      el.style.opacity = '1';
    };
    el.ondragover = (ev) => {
      ev.preventDefault();
      try { ev.dataTransfer.dropEffect = 'move'; } catch {}
    };
    el.ondrop = (ev) => {
      ev.preventDefault();
      const to = Number(el.getAttribute('data-cd-scene') || -1);
      const from = Number(dragSceneFrom);
      if (!Number.isFinite(from) || !Number.isFinite(to) || from < 0 || to < 0 || from === to) return;
      if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return;
      const arr = d.videoStructure.scenes.slice();
      if (from >= arr.length || to >= arr.length) return;
      const [moved] = arr.splice(from, 1);
      arr.splice(to, 0, moved);
      d.videoStructure.scenes = arr.map((scene, idx) => ({ ...(scene || {}), index: idx }));
      normalizeVideoScenesBudget({ silent: true });
      syncQuality();
      render();
    };
  });
  document.querySelectorAll('[data-cd-scene-text]').forEach((el) => {
    el.oninput = () => {
      const idx = Number(el.getAttribute('data-cd-scene-text') || -1);
      if (!Number.isFinite(idx) || idx < 0) return;
      if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return;
      if (idx >= d.videoStructure.scenes.length) return;
      const next = d.videoStructure.scenes.slice();
      next[idx] = { ...(next[idx] || {}), text: String(el.value || '').trim() };
      d.videoStructure.scenes = next.map((scene, pos) => ({ ...(scene || {}), index: pos }));
      normalizeVideoScenesBudget({ silent: true });
      syncQuality();
      refreshDirectorPreviewDom();
      refreshQualityDom();
    };
  });
  document.querySelectorAll('[data-cd-scene-delete]').forEach((btn) => {
    btn.onclick = () => {
      const idx = Number(btn.getAttribute('data-cd-scene-delete') || -1);
      if (!Number.isFinite(idx) || idx < 0) return;
      if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return;
      if (d.videoStructure.scenes.length <= 1) {
        state.notice = { type: 'error', text: 'Нужна минимум одна сцена.' };
        render();
        return;
      }
      const next = d.videoStructure.scenes.slice();
      next.splice(idx, 1);
      d.videoStructure.scenes = next.map((scene, pos) => ({ ...(scene || {}), index: pos }));
      normalizeVideoScenesBudget({ silent: true });
      syncQuality();
      render();
    };
  });
  const addSceneBtn = document.getElementById('cdSceneAdd');
  if (addSceneBtn) {
    addSceneBtn.onclick = () => {
      if (!d.videoStructure || !Array.isArray(d.videoStructure.scenes)) return;
      const scenes = d.videoStructure.scenes.slice();
      const nextIndex = scenes.length;
      const avgDuration = scenes.length
        ? (scenes.reduce((sum, s) => sum + (Number(s?.duration_s || 0) || 0), 0) / scenes.length)
        : Math.max(2, Number(d.videoShotSeconds || 4) || 4);
      const safeDuration = Math.max(1.5, Math.min(10, Number(avgDuration || 4)));
      scenes.push({
        index: nextIndex,
        text: '',
        duration_s: safeDuration,
        scene_type: 'work',
        mood: 'neutral',
        queries: [],
      });
      d.videoStructure.scenes = scenes.map((scene, pos) => ({ ...(scene || {}), index: pos }));
      normalizeVideoScenesBudget({ silent: true });
      syncQuality();
      render();
    };
  }
  document.querySelectorAll('[data-cd-slot]').forEach((btn) => {
    btn.onclick = () => {
      const iso = String(btn.getAttribute('data-cd-slot') || '').trim();
      if (!iso) return;
      d.scheduleAt = toLocalInputValue(iso);
      render();
    };
  });

  const bodyEl = document.getElementById('cdBody');
  if (bodyEl) {
    bodyEl.oninput = () => {
      const draft = activeDraft();
      if (!draft) return;
      draft.post_text = bodyEl.value;
      syncQuality();
      refreshQualityDom();
    };
  }
  const ctaEl = document.getElementById('cdCta');
  if (ctaEl) {
    ctaEl.oninput = () => {
      const draft = activeDraft();
      if (!draft) return;
      draft.cta = ctaEl.value;
      d.selectedCta = String(ctaEl.value || '').trim();
      syncQuality();
      refreshQualityDom();
    };
  }
  const tagsEl = document.getElementById('cdTags');
  if (tagsEl) {
    tagsEl.oninput = () => {
      const draft = activeDraft();
      if (!draft) return;
      draft.hashtags = parseCampaignHashtags(tagsEl.value);
      d.selectedHashtags = draft.hashtags.slice(0, 20);
      syncQuality();
      refreshQualityDom();
    };
  }
  const videoTagsInlineEl = document.getElementById('cdVideoTagsInline');
  if (videoTagsInlineEl) {
    videoTagsInlineEl.oninput = () => {
      d.selectedHashtags = parseCampaignHashtags(videoTagsInlineEl.value).slice(0, 20);
      if (d.videoStructure && Array.isArray(d.selectedHashtags)) {
        d.videoStructure.hashtags = d.selectedHashtags.slice(0, 20);
      }
      applySelectedTagsToActiveDraft();
      syncQuality();
      refreshQualityDom();
      refreshDirectorPreviewDom();
    };
    videoTagsInlineEl.onchange = videoTagsInlineEl.oninput;
  }
  const videoCtaInlineEl = document.getElementById('cdVideoCtaInline');
  if (videoCtaInlineEl) {
    videoCtaInlineEl.oninput = () => {
      d.selectedCta = String(videoCtaInlineEl.value || '').trim();
      if (d.videoStructure) d.videoStructure.cta = d.selectedCta;
      applySelectedCtaToActiveDraft();
      syncQuality();
      refreshQualityDom();
      refreshDirectorPreviewDom();
    };
    videoCtaInlineEl.onchange = videoCtaInlineEl.oninput;
  }

  syncQuality();
  refreshQualityDom();
  return true;
}

async function bindCreatePlanner(path) {
  const planner = getCreatePlannerRoute(path);
  if (!planner) return false;

  const d = state.createDirector;
  const cfg = getPlannerStateConfig(planner.kind, planner.days);
  const getPlanValue = (suffix, fallback = null) => {
    const key = `${cfg.baseKey}${suffix}`;
    const value = d[key];
    return value == null ? fallback : value;
  };
  const setPlanValue = (suffix, value) => {
    d[`${cfg.baseKey}${suffix}`] = value;
  };
  if (!d.platforms) d.platforms = { facebook: true, instagram: true, youtube: false };
  if (!Number.isFinite(Number(getPlanValue('PostsPerDay', 1))) || Number(getPlanValue('PostsPerDay', 1)) < 1) setPlanValue('PostsPerDay', 1);
  if (!['ai', 'manual'].includes(String(getPlanValue('TimeMode', 'ai') || ''))) setPlanValue('TimeMode', 'ai');
  if (!String(getPlanValue('ManualTime', '12:00') || '').trim()) setPlanValue('ManualTime', '12:00');
  if (!String(d.language || '').trim()) d.language = 'ru';
  if (!String(d.tone || '').trim()) d.tone = 'friendly';
  if (!String(d.videoDurationPreset || '').trim()) d.videoDurationPreset = '30';
  if (!['vertical', 'horizontal'].includes(String(d.videoOrientation || ''))) d.videoOrientation = 'vertical';

  const selectedProjectId = () => Number(state.activeProjectId || state.currentProjectId || state.projectId || state.projects?.[0]?.id || 0) || null;
  const selectedPlannerPlatforms = () => {
    const out = [
      d.platforms?.facebook ? 'facebook' : null,
      d.platforms?.instagram ? 'instagram' : null,
      cfg.kind === 'video' && d.platforms?.youtube ? 'youtube' : null,
    ].filter(Boolean);
    return out.length ? out : (cfg.kind === 'video' ? ['youtube'] : ['facebook']);
  };
  const buildSlots = async () => {
    const postsPerDay = Math.max(1, Math.min(6, Number(getPlanValue('PostsPerDay', 1) || 1)));
    const total = cfg.days * postsPerDay;
    const nextSlots = [];
    let aiHours = [];
    if (String(getPlanValue('TimeMode', 'ai') || 'ai') === 'ai') {
      try {
        const preferredPlatform = cfg.kind === 'video'
          ? (d.platforms?.youtube ? 'youtube' : (d.platforms?.instagram ? 'instagram' : 'facebook'))
          : (d.platforms?.instagram && !d.platforms?.facebook ? 'instagram' : 'facebook');

        d.bestSlots = best || null;
        aiHours = (Array.isArray(best?.best_hours) ? best.best_hours : [])
          .map((h) => Math.max(0, Math.min(23, Number(h))))
          .filter((h) => Number.isFinite(h));
      } catch {}
    }
    const raw = String(getPlanValue('ManualTime', '12:00') || '12:00');
    const hh = Math.max(0, Math.min(23, Number(raw.split(':')[0] || 12)));
    const mm = Math.max(0, Math.min(59, Number(raw.split(':')[1] || 0)));
    const seedHours = aiHours.length ? aiHours : [hh, Math.min(23, hh + 4), Math.min(23, hh + 8)];
    const now = new Date();
    for (let day = 0; day < cfg.days; day += 1) {
      const base = new Date(now.getFullYear(), now.getMonth(), now.getDate() + day, 0, 0, 0, 0);
      for (let i = 0; i < postsPerDay; i += 1) {
        const hour = seedHours[i] ?? Math.min(23, hh + (i * 2));
        nextSlots.push(new Date(base.getFullYear(), base.getMonth(), base.getDate(), hour, mm, 0, 0).toISOString());
      }
    }
    return nextSlots.slice(0, total);
  };
  const plannerTopicSeed = () => String(document.getElementById('plannerTopic')?.value || d.topic || d.manualTopicInput || d.appliedManualTopic || d.selectedSuggestedTopic || directorBaseTopic(d, d.topic) || '').trim();
  const buildPostPlanner = async () => {
    const topic = plannerTopicSeed();
    if (!topic) throw new Error('Укажите тему.');
    d.topic = topic;
    setPlanValue('Loading', true);
    render();
    try {
      const slots = await buildSlots();
      const total = slots.length;
      const nicheId = normalizeNicheIdSafe(String(document.getElementById('plannerNiche')?.value || d.topicPreset || DEFAULT_DIRECTOR_NICHE).trim()) || DEFAULT_DIRECTOR_NICHE;
      d.topicPreset = nicheId;
      const planEntries = (typeof DIRECTOR_NICHE_ENGINE.getContentPlan === 'function'
        ? DIRECTOR_NICHE_ENGINE.getContentPlan(nicheId, total, 'post')
        : []) || [];
      const fallbackTags = (Array.isArray(d.selectedHashtags) ? d.selectedHashtags : []).slice(0, 5);
      const builtItems = slots.map((iso, idx) => {
        const entry = planEntries[idx] || {};
        const entryTopic = String(entry.topic || '').trim() || `${topic}: ???? ${idx + 1}`;
        const angle = String(entry.angle || '').trim() || '????? ???????????? ???';
        const cta = String(entry.cta || d.selectedCta || '????????? ? ???????? ??????.').trim();
        const postDraft = String(entry.captionText || entry.postText || entry.caption || '').trim()
          || `${entryTopic}. ???? ??????: ${angle}. ????? ???? ?????????? ???, ?????? ? ????? ??? ?????????.`;
        const hashTokens = (Array.isArray(entry.keywords) ? entry.keywords : fallbackTags)
          .map((x) => String(x || '').trim())
          .filter(Boolean)
          .slice(0, 6)
          .map((x) => x.startsWith('#') ? x : `#${x.replace(/\s+/g, '')}`);
        return {
          index: idx + 1,
          scheduled_at: iso,
          topic: entryTopic,
          angle,
          format_hint: String(entry.contentFormat || entry.format || '').trim() || '????',
          content_shape: String(entry.contentShape || '').trim() || 'educational',
          caption_text: postDraft,
          post_text: postDraft,
          caption: postDraft,
          cta,
          hashtags: hashTokens.join(' ') || '#??????? #????????? #smm',
          post_included: true,
        };
      });
      setPlanValue('Items', builtItems);
      setPlanValue('SelectedDate', builtItems[0] ? String(builtItems[0].scheduled_at || '').slice(0, 10) : '');
      if (builtItems[0]) {
        d.selectedCta = builtItems[0].cta;
        d.selectedHashtags = parseCampaignHashtags(builtItems[0].hashtags).slice(0, 20);
      }
      state.notice = { type: 'ok', text: cfg.days === 30 ? 'Контент-план постов на 30 дней сформирован.' : 'Контент-план постов на 7 дней сформирован.' };
    } finally {
      setPlanValue('Loading', false);
      render();
    }
  };
  const buildVideoPlanner = async () => {
    const topic = plannerTopicSeed();
    if (!topic) throw new Error('Укажите тему.');
    d.topic = topic;
    setPlanValue('Loading', true);
    render();
    try {
      const slots = await buildSlots();
      const total = slots.length;
      const topicsPool = [];
      const anglesPool = [];
      const ctaPool = [];
      for (const seed of [0, 101, 202]) {
        try {
          const out = await api('/api/ai/director/suggest', {
            method: 'POST',
            body: JSON.stringify({
              topic,
              niche_id: directorCurrentNicheId(d),
              niche_label: directorCurrentNicheMeta(d)?.label || directorBaseTopic(d, d.topic),
              niche_context: directorNicheAiContext(d),
              goal: d.goal || 'engagement',
              language: d.language || 'ru',
              tone: d.tone || 'friendly',
              platforms: ['facebook', 'instagram', 'youtube'],
              content_type: 'video',
              orientation: d.videoOrientation || 'vertical',
              duration_preset: String(d.videoDurationPreset || '30'),
              variation_seed: seed,
            }),
            timeoutMs: 120000,
          });
          const s = out?.data || {};
          (Array.isArray(s.topics) ? s.topics : []).forEach((x) => { if (x) topicsPool.push(String(x).trim()); });
          (Array.isArray(s.angles) ? s.angles : []).forEach((x) => { if (x) anglesPool.push(String(x).trim()); });
          (Array.isArray(s.cta_options) ? s.cta_options : []).forEach((x) => { if (x) ctaPool.push(String(x).trim()); });
        } catch {}
      }
      const builtItems = slots.map((iso, idx) => {
        const title = String(topicsPool[idx % Math.max(1, topicsPool.length)] || `${topic}: короткий разбор ${idx + 1}`).trim();
        const angle = String(anglesPool[idx % Math.max(1, anglesPool.length)] || 'через короткий практический сценарий').trim();
        const hook = title;
        const script = `${title}. Короткий ход через ${angle} с 3 шагами и понятным выводом для зрителя.`;
        return {
          index: idx + 1,
          scheduled_at: iso,
          topic: title,
          hook,
          format: d.videoOrientation || 'vertical',
          script,
          caption: script,
          cta: String(ctaPool[idx % Math.max(1, ctaPool.length)] || d.selectedCta || 'Сохраните и напишите «ПЛАН».').trim(),

          duration_sec: Number(d.videoDurationPreset || 30) || 30,
          orientation: d.videoOrientation || 'vertical',
          video_included: true,
        };
      });
      setPlanValue('Items', builtItems);
      setPlanValue('SelectedDate', builtItems[0] ? String(builtItems[0].scheduled_at || '').slice(0, 10) : '');
      if (builtItems[0]) {
        d.selectedCta = builtItems[0].cta;
        d.selectedHashtags = parseCampaignHashtags(builtItems[0].hashtags).slice(0, 20);
      }
      state.notice = { type: 'ok', text: cfg.days === 30 ? 'Видео-посты на 30 дней сформированы.' : 'Видео-посты на 7 дней сформированы.' };
    } finally {
      setPlanValue('Loading', false);
      render();
    }
  };

  const bindRerender = (id, handler) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.onchange = () => { handler(el); render(); };
  };
  bindRerender('plannerNiche', (el) => {
    d.topicPreset = normalizeNicheIdSafe(String(el.value || DEFAULT_DIRECTOR_NICHE).trim()) || DEFAULT_DIRECTOR_NICHE;
    setPlanValue('Items', []);
    setPlanValue('SelectedDate', '');
  });
  bindRerender('plannerTopic', (el) => { d.topic = String(el.value || '').trim(); });
  bindRerender('plannerPostsPerDay', (el) => { setPlanValue('PostsPerDay', Math.max(1, Math.min(6, Number(el.value || 1)))); });
  bindRerender('plannerLanguage', (el) => { d.language = String(el.value || 'ru').trim() || 'ru'; });
  bindRerender('plannerTone', (el) => { d.tone = String(el.value || 'friendly').trim() || 'friendly'; });
  bindRerender('plannerManualTime', (el) => { setPlanValue('ManualTime', String(el.value || '12:00')); });
  bindRerender('plannerImageEnabled', (el) => { d.imageEnabled = !!el.checked; });
  bindRerender('plannerOrientation', (el) => { d.videoOrientation = String(el.value || 'vertical'); });
  bindRerender('plannerDuration', (el) => { d.videoDurationPreset = String(el.value || '30'); });
  bindRerender('plannerPlatformFacebook', (el) => { d.platforms.facebook = !!el.checked; });
  bindRerender('plannerPlatformInstagram', (el) => { d.platforms.instagram = !!el.checked; });
  bindRerender('plannerPlatformYouTube', (el) => { d.platforms.youtube = !!el.checked; });

  const plannerTimeAi = document.getElementById('plannerTimeAi');
  if (plannerTimeAi) plannerTimeAi.onclick = async () => {
    setPlanValue('TimeMode', 'ai');
    render();
  };
  const plannerTimeManual = document.getElementById('plannerTimeManual');
  if (plannerTimeManual) plannerTimeManual.onclick = () => {
    setPlanValue('TimeMode', 'manual');
    render();
  };
  const plannerGenerate = document.getElementById('plannerGenerate');
  if (plannerGenerate) plannerGenerate.onclick = async () => {
    try {
      const access = getPlannerMonetizationAccess(cfg.kind, cfg.days);
      if (!access.canGenerate) {
        showPaywall(access.generateMessage);
        return;
      }
      if (cfg.kind === 'video') await buildVideoPlanner();
      else await buildPostPlanner();
    } catch (e) {
      setPlanValue('Loading', false);
      state.notice = { type: 'error', text: e.message || 'Не удалось сформировать план.' };
      render();
    }
  };
  const plannerScheduleAll = document.getElementById('plannerScheduleAll');
  if (plannerScheduleAll) plannerScheduleAll.onclick = async () => {
    try {
      const access = getPlannerMonetizationAccess(cfg.kind, cfg.days);
      if (!access.canAutopublish) {
        showPaywall(access.autopublishMessage);
        return;
      }
      const items = Array.isArray(d[cfg.itemsKey]) ? d[cfg.itemsKey].filter((x) => x && x.scheduled_at && x.topic) : [];
      if (!items.length) throw new Error('Сначала сформируйте план.');
      setPlanValue('Scheduling', true);
      render();
      const out = await api('/api/posts/bulk-schedule', {
        method: 'POST',
        body: JSON.stringify({
          items: items.map((item) => ({
            topic: String(item.topic || '').trim(),
            generated_text: [String(item.post_text || '').trim() || String(item.caption || '').trim()].filter(Boolean).join('\\n\\n').trim(),
            schedule_at: String(item.scheduled_at || '').trim(),
          })),
          category: directorBaseTopic(d, d.topic) || directorCurrentNicheMeta(d)?.label || null,
          platforms: selectedPlannerPlatforms().filter((p) => ['facebook', 'instagram'].includes(p)),
          language: d.language || 'ru',
          tone: d.tone || 'friendly',
          image_enabled: !!d.imageEnabled,
          project_id: selectedProjectId() || undefined,
        }),
        timeoutMs: 120000,
      });
      const created = Number(out?.created || 0);
      const reused = Number(out?.reused || 0);
      state.notice = { type: 'ok', text: reused ? `Запланировано: ${created}. Уже существовало: ${reused}.` : `Запланировано публикаций: ${created}.` };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось запланировать публикации.' };
    } finally {
      setPlanValue('Scheduling', false);
      render();
    }
  };
  const plannerApplyToDirector = document.getElementById('plannerApplyToDirector');
  if (plannerApplyToDirector) plannerApplyToDirector.onclick = async () => {
    setPlanValue('Applying', true);
    try {
      d.contentType = cfg.kind;
      try { localStorage.setItem(CREATE_DIRECTOR_TYPE_KEY, cfg.kind); } catch {}
      history.pushState({}, '', `/create?type=${cfg.kind}`);
      await render();
    } finally {
      setPlanValue('Applying', false);
    }
  };
  document.querySelectorAll('[data-planner-day]').forEach((btn) => {
    btn.onclick = () => {
      setPlanValue('SelectedDate', String(btn.getAttribute('data-planner-day') || '').trim());
      render();
    };
  });
  return true;
}

async function bindCreateVideoWeek(path) {
  return ['/create/video-week', '/create/video-month'].includes(path) ? bindCreatePlanner(path) : false;
}

async function bindCreatePostWeek(path) {
  return path === '/create/post-week' ? bindCreatePlanner(path) : false;
}

async function bind(path = location.pathname.replace(/\/$/, '') || '/') {
  bindCommon();
  const plannerBound = await bindCreatePlanner(path);
  const directorBound = plannerBound ? true : await bindCreateDirector(path);
  if (!directorBound) await bindCreateWizardV2(path);
  const blogBackBtn = document.getElementById('blogBackBtn');
  if (blogBackBtn) {
    blogBackBtn.onclick = () => {
      history.pushState({}, '', '/blog');
      state.notice = null;
      render();
    };
  }
  document.querySelectorAll('[data-blog-open]').forEach((btn) => {
    btn.onclick = () => {
      const slug = btn.getAttribute('data-blog-open');
      if (!slug) return;
      history.pushState({}, '', `/blog?slug=${encodeURIComponent(slug)}`);
      state.notice = null;
      render();
    };
  });

  const oauthGoogleBtn = document.getElementById('oauthGoogleBtn');
  if (oauthGoogleBtn && !oauthGoogleBtn.disabled) oauthGoogleBtn.onclick = () => { window.location.href = `${API_BASE}/api/auth/oauth/google/start`; };
  const oauthFacebookBtn = document.getElementById('oauthFacebookBtn');
  if (oauthFacebookBtn && !oauthFacebookBtn.disabled) oauthFacebookBtn.onclick = () => { window.location.href = `${API_BASE}/api/auth/oauth/facebook/start`; };

  const authSwitchBtn = document.getElementById('authSwitchBtn');
  if (authSwitchBtn) authSwitchBtn.onclick = () => {
    state.authMode = state.authMode === 'login' ? 'register' : 'login';
    state.authChallenge = null;
    state.notice = null;
    render();
  };

  const focusAuthEmail = () => {
    setTimeout(() => {
      const emailInput = document.getElementById('authEmail');
      if (emailInput) {
        emailInput.focus();
        emailInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 0);
  };

  const heroRegisterBtn = document.getElementById('heroRegisterBtn');
  if (heroRegisterBtn) heroRegisterBtn.onclick = () => {
    state.authMode = 'register';
    state.authChallenge = null;
    state.notice = null;
    render();
    focusAuthEmail();
  };

  const finalRegisterBtn = document.getElementById('finalRegisterBtn');
  if (finalRegisterBtn) finalRegisterBtn.onclick = () => {
    state.authMode = 'register';
    state.authChallenge = null;
    state.notice = null;
    render();
    focusAuthEmail();
  };

  const finalPricingBtn = document.getElementById('finalPricingBtn');
  if (finalPricingBtn) finalPricingBtn.onclick = () => nav('/billing');

  document.querySelectorAll('[data-pricing-cta]').forEach((btn) => {
    btn.onclick = () => {
      const plan = String(btn.getAttribute('data-pricing-cta') || '').trim();
      if (plan === 'free') {
        state.authMode = 'register';
        state.authChallenge = null;
        state.notice = null;
        render();
        focusAuthEmail();
        return;
      }
      nav('/billing');
    };
  });

  const authBackBtn = document.getElementById('authBackBtn');
  if (authBackBtn) authBackBtn.onclick = () => {
    state.authChallenge = null;
    state.notice = null;
    render();
    focusAuthEmail();
  };

  const authSubmitBtn = document.getElementById('authSubmitBtn');
  if (authSubmitBtn) authSubmitBtn.onclick = async () => {
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const challenge = state.authChallenge;
    if (challenge) {
      const code = (document.getElementById('authCode')?.value || '').trim();
      if (!/^\d{4}$/.test(code)) {
        state.notice = { type: 'error', text: 'Введите 4-значный код из письма.' };
        render();
        return;
      }
      try {
        const data = await api('/api/auth/verify-code', {
          method: 'POST',
          body: JSON.stringify({ challenge_token: challenge.challengeToken, code }),
        });
        state.token = data.token;
        localStorage.setItem('token', data.token);
        state.authChallenge = null;
        await loadBase();
        state.notice = { type: 'ok', text: challenge.flow === 'register' ? 'Регистрация успешно завершена.' : 'Вход выполнен успешно.' };
        nav('/connections', { keepNotice: true });
      } catch (e) {
        const raw = String(e.message || 'Ошибка авторизации');
        state.notice = { type: 'error', text: raw || 'Неверный код или код просрочен.' };
        render();
      }
      return;
    }

    const email = document.getElementById('authEmail')?.value.trim().toLowerCase();
    const password = document.getElementById('authPassword')?.value || '';
    const website = document.getElementById('authWebsite')?.value || '';
    if (!email || !emailRe.test(email)) {
      state.notice = { type: 'error', text: 'Введите корректный email.' };
      render();
      return;
    }
    if (password.length < 8) {
      state.notice = { type: 'error', text: 'Пароль должен быть не короче 8 символов.' };
      render();
      return;
    }
    try {
      const flow = state.authMode === 'login' ? 'login' : 'register';
      const data = await api('/api/auth/challenge', {
        method: 'POST',
        body: JSON.stringify({ flow, email, password, website }),
      });
      state.authChallenge = { flow, email, password, website, challengeToken: data.challenge_token };
      const suffix = data.dev_code ? ` (dev-код: ${data.dev_code})` : '';
      state.notice = { type: 'ok', text: `Код отправлен на ${email}.${suffix}` };
      render();
    } catch (e) {
      const raw = String(e.message || 'Ошибка авторизации');

      if (raw.toLowerCase().includes('существует') || raw.toLowerCase().includes('already')) {
        text = 'Этот email уже зарегистрирован. Войдите в аккаунт.';
      } else if (raw.toLowerCase().includes('не короче') || raw.toLowerCase().includes('short')) {
        text = 'Пароль должен быть не короче 8 символов.';
      } else if (raw.toLowerCase().includes('неверный') || raw.toLowerCase().includes('invalid')) {
        text = 'Неверный email или пароль.';
      } else if (raw) {
        text = raw;
      }
      state.notice = { type: 'error', text };
      render();
    }
  };

  const authResendBtn = document.getElementById('authResendBtn');
  if (authResendBtn) authResendBtn.onclick = async () => {
    const challenge = state.authChallenge;
    if (!challenge) return;
    try {
      const data = await api('/api/auth/challenge', {
        method: 'POST',
        body: JSON.stringify({
          flow: challenge.flow,
          email: challenge.email,
          password: challenge.password,
          website: challenge.website || '',
        }),
      });
      state.authChallenge = { ...challenge, challengeToken: data.challenge_token };
      const suffix = data.dev_code ? ` (dev-код: ${data.dev_code})` : '';
      state.notice = { type: 'ok', text: `Новый код отправлен.${suffix}` };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: String(e.message || 'Не удалось отправить код повторно.') };
      render();
    }
  };

  const authCodeInput = document.getElementById('authCode');
  if (authCodeInput) {
    authCodeInput.maxLength = 4;
    authCodeInput.inputMode = 'numeric';
    authCodeInput.autocomplete = 'one-time-code';
  }

  ensureAiWizardState();

  const setManagerLoading = (isLoading) => {
    ensureAiWizardState();
    state.aiWizard.status = isLoading ? 'submitting' : 'idle';
    saveAiWizardDraft();
  };

  const setQuickLoading = (btn, loadingText, isLoading) => {
    if (!btn) return;
    if (!btn.dataset.defaultText) btn.dataset.defaultText = btn.textContent || '';
    btn.disabled = !!isLoading;
    btn.textContent = isLoading ? loadingText : btn.dataset.defaultText;
  };

  const readManagerPayload = ({ requireConnection, requireStep = 2 }) => {
    ensureAiWizardState();
    const w = state.aiWizard;
    const errors = getWizardValidationErrors(w, requireStep);
    if (errors.business_type) throw new Error(errors.business_type);
    if (errors.niche) throw new Error(errors.niche);
    if (errors.product_summary) throw new Error(errors.product_summary);
    if (errors.goal) throw new Error(errors.goal);
    if (errors.tone) throw new Error(errors.tone);
    const hasConnectedAccount = (state.connections || []).some((c) => isConnectionReady(c));
    if (requireConnection && !hasConnectedAccount) throw new Error('Сначала подключите Facebook/Instagram в разделе "Подключения".');
    return mapWizardStateToExistingPayload(w);
  };

  const updateWizard = (patch, status = 'typing') => {
    ensureAiWizardState();
    state.aiWizard = { ...state.aiWizard, ...patch };
    state.aiWizard.status = status;
    saveAiWizardDraft();
  };

  const scheduleAnalyzeRender = () => {
    ensureAiWizardState();
    state.aiWizard.status = 'analyzing';
    saveAiWizardDraft();
    if (window.__wizardAnalyzeTimer) clearTimeout(window.__wizardAnalyzeTimer);
    window.__wizardAnalyzeTimer = setTimeout(() => {
      ensureAiWizardState();
      if (state.aiWizard.status !== 'submitting') state.aiWizard.status = 'idle';
      saveAiWizardDraft();
      render();
    }, 260);
    render();
  };

  const wizardBlock = document.getElementById('aiWizardBlock');
  if (wizardBlock) {
    wizardBlock.addEventListener('keydown', (e) => {
      ensureAiWizardState();
      if (e.key !== 'Enter') return;
      if (state.aiWizard.step >= 3) return;
      const tag = String(e.target?.tagName || '').toLowerCase();
      if (tag === 'textarea') return;
      e.preventDefault();
    });
  }

  const wizardProjectEl = document.getElementById('wizardProject');
  if (wizardProjectEl) wizardProjectEl.onchange = () => {
    updateWizard({ project_id: wizardProjectEl.value }, 'typing');
    render();
  };
  const wizardNicheEl = document.getElementById('wizardNiche');
  if (wizardNicheEl) wizardNicheEl.oninput = () => {
    updateWizard({ niche: wizardNicheEl.value }, 'typing');
    scheduleAnalyzeRender();
  };
  const wizardProductSummaryEl = document.getElementById('wizardProductSummary');
  if (wizardProductSummaryEl) wizardProductSummaryEl.oninput = () => {
    updateWizard({ product_summary: wizardProductSummaryEl.value }, 'typing');
    render();
  };
  const wizardLangEl = document.getElementById('wizardLang');
  if (wizardLangEl) wizardLangEl.onchange = () => {
    updateWizard({ language: wizardLangEl.value }, 'typing');
    scheduleAnalyzeRender();
  };

  document.querySelectorAll('[data-wizard-business]').forEach((btn) => {
    btn.onclick = () => {
      const value = String(btn.getAttribute('data-wizard-business') || '').trim();
      updateWizard({ business_type: value }, 'typing');
      scheduleAnalyzeRender();
    };
  });
  document.querySelectorAll('[data-wizard-goal]').forEach((btn) => {
    btn.onclick = () => {
      const value = String(btn.getAttribute('data-wizard-goal') || '').trim();
      updateWizard({ goal: value }, 'typing');
      scheduleAnalyzeRender();
    };
  });
  document.querySelectorAll('[data-wizard-tone]').forEach((btn) => {
    btn.onclick = () => {
      const value = String(btn.getAttribute('data-wizard-tone') || '').trim();
      updateWizard({ tone: value }, 'typing');
      scheduleAnalyzeRender();
    };
  });
  const wizardPlatformFacebook = document.getElementById('wizardPlatformFacebook');
  if (wizardPlatformFacebook) wizardPlatformFacebook.onchange = () => {
    ensureAiWizardState();
    const next = {
      ...(state.aiWizard.platforms || defaultAiWizardState().platforms),
      facebook: !!wizardPlatformFacebook.checked,
    };
    if (!next.facebook && !next.instagram) next.instagram = true;
    updateWizard({ platforms: next }, 'typing');
    render();
  };
  const wizardPlatformInstagram = document.getElementById('wizardPlatformInstagram');
  if (wizardPlatformInstagram) wizardPlatformInstagram.onchange = () => {
    ensureAiWizardState();
    const next = {
      ...(state.aiWizard.platforms || defaultAiWizardState().platforms),
      instagram: !!wizardPlatformInstagram.checked,
    };
    if (!next.facebook && !next.instagram) next.facebook = true;
    updateWizard({ platforms: next }, 'typing');
    render();
  };
  document.querySelectorAll('[data-wizard-output]').forEach((el) => {
    el.onchange = () => {
      const key = String(el.getAttribute('data-wizard-output') || '').trim();
      ensureAiWizardState();
      state.aiWizard.outputs = { ...(state.aiWizard.outputs || {}), [key]: !!el.checked };
      state.aiWizard.status = 'typing';
      saveAiWizardDraft();
      render();
    };
  });

  const wizardPrevBtn = document.getElementById('wizardPrevBtn');
  if (wizardPrevBtn) wizardPrevBtn.onclick = () => {
    ensureAiWizardState();
    state.aiWizard.step = Math.max(1, Number(state.aiWizard.step || 1) - 1);
    state.aiWizard.status = 'idle';
    saveAiWizardDraft();
    render();
  };
  const wizardNextBtn = document.getElementById('wizardNextBtn');
  if (wizardNextBtn) wizardNextBtn.onclick = () => {
    ensureAiWizardState();
    const step = Number(state.aiWizard.step || 1);
    const errors = getWizardValidationErrors(state.aiWizard, step);
    if (Object.keys(errors).length > 0) {
      const firstError = errors.business_type || errors.niche || errors.product_summary || errors.goal || errors.tone || errors.outputs || 'Заполните обязательные поля шага.';
      state.notice = { type: 'error', text: firstError };
      return render();
    }
    state.aiWizard.step = Math.min(3, step + 1);
    state.aiWizard.status = 'idle';
    saveAiWizardDraft();
    render();
  };
  const wizardRefreshPreviewBtn = document.getElementById('wizardRefreshPreviewBtn');
  if (wizardRefreshPreviewBtn) wizardRefreshPreviewBtn.onclick = () => {
    ensureAiWizardState();
    state.aiWizard.status = 'analyzing';
    saveAiWizardDraft();
    render();
    setTimeout(() => {
      ensureAiWizardState();
      state.aiWizard.status = 'idle';
      saveAiWizardDraft();
      render();
    }, 220);
  };
  const wizardSubmitBtn = document.getElementById('wizardSubmitBtn');
  if (wizardSubmitBtn) wizardSubmitBtn.onclick = async () => {
    try {
      ensureAiWizardState();
      const errors = getWizardValidationErrors(state.aiWizard, 3);
      if (Object.keys(errors).length > 0) {
        const firstError = errors.business_type || errors.niche || errors.product_summary || errors.goal || errors.tone || errors.outputs || 'Проверьте поля и попробуйте снова.';
        throw new Error(firstError);
      }
      setManagerLoading(true);
      render();
      const payload = readManagerPayload({ requireConnection: true, requireStep: 2 });
      const r = await api('/api/ai-smm-manager/start', { method: 'POST', body: JSON.stringify(payload) });
      const materializeDays = state.aiWizard.outputs?.plan7 ? 7 : 3;
      const materializeLimit = state.aiWizard.outputs?.posts10 ? 10 : 5;
      const warmup = await api('/api/content-plan/materialize', {
        method: 'POST',
        body: JSON.stringify({ project_id: payload.project_id, days: materializeDays, limit: materializeLimit, platforms: payload.platforms }),
      });
      const created = Number(r?.result?.created_plan_items || 0);
      const existing = Number(r?.result?.existing_future_items || 0);
      const queued = Number(warmup?.result?.created_posts || warmup?.created_posts || 0);
      const skipped = Number(warmup?.result?.skipped || warmup?.skipped || 0);
      if (created === 0 && existing > 0) {
        state.notice = { type: 'ok', text: `Контент-план уже существует (будущих публикаций: ${existing}). Подготовлено черновиков: ${queued}.` };
      } else {
        state.notice = { type: 'ok', text: `План и черновики готовы: создан план на 30 дней, добавлено постов: ${queued}${skipped ? `, пропущено: ${skipped}` : ''}.` };
      }
      state.aiWizard.status = 'idle';
      saveAiWizardDraft();
      nav('/history', { keepNotice: true });
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось запустить генерацию.' };
      ensureAiWizardState();
      state.aiWizard.status = 'idle';
      saveAiWizardDraft();
      render();
    }
  };

  const goConnectionsBtn = document.getElementById('goConnectionsBtn'); if (goConnectionsBtn) goConnectionsBtn.onclick = () => nav('/connections');
  const goCreateBtn = document.getElementById('goCreateBtn'); if (goCreateBtn) goCreateBtn.onclick = () => nav('/create');
  const goBillingBtn = document.getElementById('goBillingBtn'); if (goBillingBtn) goBillingBtn.onclick = () => nav('/billing');
  const postTodayBtn = document.getElementById('postTodayBtn');
  if (postTodayBtn) postTodayBtn.onclick = async () => {
    try {
      setQuickLoading(postTodayBtn, 'Публикую...', true);
      const payload = readManagerPayload({ requireConnection: true });
      await api('/api/ai-smm-manager/start', { method: 'POST', body: JSON.stringify(payload) });
      const warmup = await api('/api/content-plan/materialize', {
        method: 'POST',
        body: JSON.stringify({ project_id: payload.project_id, days: 1, limit: 3, platforms: payload.platforms }),
      });
      const queued = Number(warmup?.result?.created_posts || warmup?.created_posts || 0);
      state.notice = { type: 'ok', text: queued > 0 ? `Поставлено в очередь на сегодня: ${queued} пост(ов).` : 'На сегодня уже есть готовые публикации. Откройте «Календарь».' };
      nav('/history', { keepNotice: true });
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    } finally {
      setQuickLoading(postTodayBtn, 'Публикую...', false);
    }
  };

  const scheduleWeekBtn = document.getElementById('scheduleWeekBtn');
  if (scheduleWeekBtn) scheduleWeekBtn.onclick = async () => {
    try {
      setQuickLoading(scheduleWeekBtn, 'Планирую...', true);
      const payload = readManagerPayload({ requireConnection: true });
      await api('/api/ai-smm-manager/start', { method: 'POST', body: JSON.stringify(payload) });
      const warmup = await api('/api/content-plan/materialize', {
        method: 'POST',
        body: JSON.stringify({ project_id: payload.project_id, days: 7, limit: 20, platforms: payload.platforms }),
      });
      const queued = Number(warmup?.result?.created_posts || warmup?.created_posts || 0);
      state.notice = { type: 'ok', text: queued > 0 ? `План на неделю готов: в очередь добавлено ${queued} пост(ов).` : 'На ближайшую неделю контент уже подготовлен.' };
      nav('/history', { keepNotice: true });
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    } finally {
      setQuickLoading(scheduleWeekBtn, 'Планирую...', false);
    }
  };
  const createProjectInlineBtn = document.getElementById('createProjectInlineBtn');
  if (createProjectInlineBtn) createProjectInlineBtn.onclick = async () => {
    try {
      const name = document.getElementById('dashboardProjectName').value.trim();
      if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
      await api('/api/projects', { method: 'POST', body: JSON.stringify({ name }) });
      await loadBase();
      state.notice = { type: 'ok', text: 'Проект создан.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    }
  };

  // Dashboard interactions
  const dashCreatePostBtn = document.getElementById('dashCreatePostBtn');
  if (dashCreatePostBtn) dashCreatePostBtn.onclick = () => openCreateFromDashboard('post');
  const dismissDashboardOnboarding = () => {
    localStorage.setItem(`dashboardOnboardingDismissed:${String(state.user?.id || 'anon').trim() || 'anon'}`, '1');
  };
  const openCreateFromDashboard = (mode = 'post') => {
    dismissDashboardOnboarding();
    state.createDirector = {
      ...state.createDirector,
      contentType: mode === 'video' ? 'video' : 'post',
      quickActionType: '',
      quickActionNicheId: '',
      quickActionSeed: 0,
      quickActionPreviewOnly: false,
    };
    state.notice = {
      type: 'ok',
      text: mode === 'video'
        ? `Шаг 1: выберите тему или нажмите «Подобрать ${DIRECTOR_TOPIC_IDEA_COUNT} тем», затем сгенерируйте структуру видео.`
        : `Шаг 1: выберите тему или нажмите «Подобрать ${DIRECTOR_TOPIC_IDEA_COUNT} тем», затем сгенерируйте первый пост.`,
    };
    nav('/create', { keepNotice: true });
  };
  const setDashboardQuickNiche = (value) => {
    ensureDashboardQuickStartState();
    const normalized = normalizeNicheIdSafe(value || '');
    state.dashboardQuickStart = {
      ...state.dashboardQuickStart,
      nicheId: normalized && normalized !== 'fallback' ? normalized : '',
    };
    if (state.dashboardQuickStart.nicheId) persistDashboardNicheId(state.dashboardQuickStart.nicheId);
  };
  const openDashboardQuickAction = (actionType) => {
    ensureDashboardQuickStartState();
    const nicheId = String(state.dashboardQuickStart.nicheId || resolveDashboardActiveNicheId() || '').trim();
    if (!nicheId) {
      state.notice = { type: 'error', text: 'Сначала выберите нишу.' };
      render();
      return;
    }
    const access = getQuickActionAccess(actionType, state.billing);
    if (access.isLocked) {
      state.notice = { type: 'error', text: 'Это действие недоступно на текущем тарифе. Обновите тариф, чтобы продолжить.' };
      nav('/billing', { keepNotice: true });
      return;
    }
    dismissDashboardOnboarding();
    const nextType = actionType === 'video_series' ? 'video' : 'post';
    state.dashboardQuickStart = {
      ...state.dashboardQuickStart,
      nicheId,
      actionType,
    };
    if (actionType === 'weekly_plan' || actionType === 'monthly_plan') {
      const isMonthPlan = actionType === 'monthly_plan';
      state.createDirector = {
        ...state.createDirector,
        contentType: 'post',
        quickActionType: '',
        quickActionNicheId: '',
        quickActionSeed: 0,
        quickActionPreviewOnly: false,
        topicPreset: nicheId,
        customTopicMode: false,
        topic: '',
        manualTopicInput: '',
        appliedManualTopic: '',
        selectedSuggestedTopic: '',
        ...(isMonthPlan
          ? { postMonthItems: [], postMonthSelectedDate: '' }
          : { postWeekItems: [], postWeekSelectedDate: '' }),
      };
      state.notice = { type: 'ok', text: isMonthPlan ? 'Открыт контент-план постов на 30 дней по выбранной нише.' : 'Открыт контент-план постов на 7 дней по выбранной нише.' };
      nav(plannerUrl('post', isMonthPlan ? 30 : 7), { keepNotice: true });
      return;
    }
    if (actionType === 'video_week_plan' || actionType === 'video_month_plan') {
      const isMonthPlan = actionType === 'video_month_plan';
      state.createDirector = {
        ...state.createDirector,
        contentType: 'video',
        quickActionType: '',
        quickActionNicheId: '',
        quickActionSeed: 0,
        quickActionPreviewOnly: false,
        topicPreset: nicheId,
        customTopicMode: false,
        topic: '',
        manualTopicInput: '',
        appliedManualTopic: '',
        selectedSuggestedTopic: '',
        ...(isMonthPlan
          ? { videoMonthItems: [], videoMonthSelectedDate: '' }
          : { videoWeekItems: [], videoWeekSelectedDate: '' }),
      };
      state.notice = { type: 'ok', text: isMonthPlan ? 'Открыт видеоплан на 30 дней по выбранной нише.' : 'Открыт видеоплан на 7 дней по выбранной нише.' };
      nav(plannerUrl('video', isMonthPlan ? 30 : 7), { keepNotice: true });
      return;
    }
    state.createDirector = {
      ...state.createDirector,
      contentType: nextType,
      quickActionType: actionType,
      quickActionNicheId: nicheId,
      quickActionSeed: Number(state.dashboardQuickStart.seed || 0),
      quickActionPreviewOnly: access.isPreview,
      topicPreset: nicheId,
      customTopicMode: false,
    };
    state.notice = {
      type: 'ok',
      text: access.isPreview
        ? 'Открыт preview по выбранной нише. Полный объём доступен после апгрейда.'
        : 'Открыт быстрый сценарий по выбранной нише. Можно сразу использовать результат в AI Контент-директоре.',
    };
    const query = new URLSearchParams();
    query.set('quickAction', actionType);
    query.set('niche', nicheId);
    if (nextType === 'video') query.set('type', 'video');
    nav(`/create?${query.toString()}`, { keepNotice: true });
  };
  const dashFirstPostBtn = document.getElementById('dashFirstPostBtn');
  if (dashFirstPostBtn) dashFirstPostBtn.onclick = () => openCreateFromDashboard('post');
  const dashFirstVideoBtn = document.getElementById('dashFirstVideoBtn');
  if (dashFirstVideoBtn) dashFirstVideoBtn.onclick = () => openCreateFromDashboard('video');
  const dashOpenCreateBtn = document.getElementById('dashOpenCreateBtn');
  if (dashOpenCreateBtn) dashOpenCreateBtn.onclick = () => openCreateFromDashboard('post');
  const dashEmptyCreateBtn = document.getElementById('dashEmptyCreateBtn');
  if (dashEmptyCreateBtn) dashEmptyCreateBtn.onclick = () => openCreateFromDashboard('post');
  const dashConnectChannelsBtn = document.getElementById('dashConnectChannelsBtn');
  if (dashConnectChannelsBtn) dashConnectChannelsBtn.onclick = () => {
    dismissDashboardOnboarding();
    nav('/connections');
  };
  const dashDismissOnboardingBtn = document.getElementById('dashDismissOnboardingBtn');
  if (dashDismissOnboardingBtn) dashDismissOnboardingBtn.onclick = () => {
    dismissDashboardOnboarding();
    render();
  };
  const dashEmptySyncBtn = document.getElementById('dashEmptySyncBtn');
  if (dashEmptySyncBtn) dashEmptySyncBtn.onclick = () => {
    dismissDashboardOnboarding();
    render();
  };
  const dashQuickNiche = document.getElementById('dashQuickNiche');
  if (dashQuickNiche) dashQuickNiche.onchange = () => {
    setDashboardQuickNiche(dashQuickNiche.value);
    render();
  };
  const dashQuickPickNicheBtn = document.getElementById('dashQuickPickNicheBtn');
  if (dashQuickPickNicheBtn) dashQuickPickNicheBtn.onclick = () => {
    setDashboardQuickNiche(document.getElementById('dashQuickNiche')?.value || '');
    if (!String(state.dashboardQuickStart?.nicheId || '').trim()) {
      state.notice = { type: 'error', text: 'Сначала выберите нишу.' };
    }
    render();
  };
  document.querySelectorAll('[data-dash-quick-action]').forEach((btn) => {
    btn.onclick = () => {
      openDashboardQuickAction(String(btn.getAttribute('data-dash-quick-action') || '').trim());
    };
  });
  const dashOpenCalendarBtn = document.getElementById('dashOpenCalendarBtn');
  if (dashOpenCalendarBtn) dashOpenCalendarBtn.onclick = () => nav('/calendar');
  const dashAiBreakdownBtn = document.getElementById('dashAiBreakdownBtn');
  if (dashAiBreakdownBtn) dashAiBreakdownBtn.onclick = () => {
    state.dashboardMetrics = { ...(state.dashboardMetrics || {}), aiBreakdownOpen: true };
    render();
  };
  const dashAiBreakdownClose = document.getElementById('dashAiBreakdownClose');
  if (dashAiBreakdownClose) dashAiBreakdownClose.onclick = () => {
    state.dashboardMetrics = { ...(state.dashboardMetrics || {}), aiBreakdownOpen: false };
    render();
  };
  const dashAiModalBackdrop = document.getElementById('dashAiModalBackdrop');
  if (dashAiModalBackdrop) dashAiModalBackdrop.onclick = (event) => {
    if (event.target === dashAiModalBackdrop) {
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), aiBreakdownOpen: false };
      render();
    }
  };
  const dashApplyRecommendationsBtn = document.getElementById('dashApplyRecommendationsBtn');
  if (dashApplyRecommendationsBtn) dashApplyRecommendationsBtn.onclick = () => {
    const insights = Array.isArray(state.dashboardMetrics?.insights) ? state.dashboardMetrics.insights : [];
    const bestFormat = insights.find((i) => String(i?.title || '').toLowerCase().includes('формат'));
    const bestDay = insights.find((i) => String(i?.title || '').toLowerCase().includes('день'));
    state.createCampaign = {
      ...state.createCampaign,
      contentTone: 'friendly',
      contentGoal: 'engagement',
      topic: String(bestFormat?.text || bestDay?.text || state.createCampaign.topic || '').slice(0, 240),
      dirty: true,
    };
    state.notice = { type: 'ok', text: 'Рекомендации применены. Параметры перенесены в Create.' };
    nav('/create', { keepNotice: true });
  };
  const dashSyncMetricsBtn = document.getElementById('dashSyncMetricsBtn');
  if (dashSyncMetricsBtn) dashSyncMetricsBtn.onclick = async () => {
    try {
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), syncing: true };
      render();
      const sync = await api('/api/dashboard/sync', { method: 'POST', body: JSON.stringify({}) });
      await loadDashboardMetrics(30);
      const parts = [
        `Facebook: ${Number(sync.facebook_items || 0)}`,
        `Instagram: ${Number(sync.instagram_items || 0)}`,
        `YouTube: ${Number(sync.youtube_items || 0)}`,
      ];
      if (Array.isArray(sync.errors) && sync.errors.length) {
        const firstError = String(sync.errors[0] || '').trim();
        const advice = firstError.toLowerCase().includes('youtube')
          ? ' Переподключите YouTube в разделе «Подключения».'
          : '';
        state.notice = { type: 'error', text: `Синхронизация завершена с ошибками. ${parts.join(' · ')}. ${firstError}${advice}`.trim() };
      } else {
        state.notice = { type: 'ok', text: `Метрики синхронизированы. ${parts.join(' · ')}.` };
      }
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось синхронизировать метрики.' };
    } finally {
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), syncing: false };
      render();
    }
  };
  document.querySelectorAll('[data-dash-metric]').forEach((btn) => {
    btn.onclick = () => {
      const metric = String(btn.getAttribute('data-dash-metric') || 'reach');
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), chartMetric: metric };
      render();
    };
  });
  document.querySelectorAll('[data-dash-sort]').forEach((btn) => {
    btn.onclick = () => {
      const sort = String(btn.getAttribute('data-dash-sort') || 'engagement');
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), recentSort: sort };
      render();
    };
  });
  document.querySelectorAll('[data-dash-forecast-horizon]').forEach((btn) => {
    btn.onclick = async () => {
      const horizon = Number(btn.getAttribute('data-dash-forecast-horizon') || 7) >= 30 ? 30 : 7;
      state.dashboardMetrics = { ...(state.dashboardMetrics || {}), forecastHorizon: horizon, loading: true };
      render();
      await loadDashboardMetrics(30);
      render();
    };
  });
  document.querySelectorAll('[data-dash-insight-action]').forEach((btn) => {
    btn.onclick = () => {
      const action = String(btn.getAttribute('data-dash-insight-action') || '');
      if (action === 'open-top-content') {
        nav('/history');
        return;
      }
      if (action === 'schedule-best-day') {
        nav('/calendar');
        return;
      }
      if (action === 'create-format-post') {
        state.createCampaign = { ...state.createCampaign, contentGoal: 'engagement', contentTone: 'friendly', dirty: true };
        nav('/create');
      }
    };
  });
  document.querySelectorAll('.dash-row-link').forEach((row) => {
    row.onclick = (event) => {
      const target = event.target;
      if (target && target.closest && target.closest('[data-dash-recent-delete]')) return;
      const url = String(row.getAttribute('data-dash-item-url') || '').trim();
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
      } else {
        nav('/history');
      }
    };
  });
  document.querySelectorAll('[data-dash-recent-delete]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const id = Number(btn.getAttribute('data-dash-recent-delete') || 0);
        if (!id) return;
        if (!confirm('Удалить публикацию из списка метрик?')) return;
        setQuickLoading(btn, 'Удаляю...', true);
        await api(`/api/dashboard/recent/${id}`, { method: 'DELETE' });
        await loadDashboardMetrics(30);
        state.notice = { type: 'ok', text: 'Публикация удалена.' };
        render();
      } catch (e) {
        state.notice = { type: 'error', text: e.message || 'Не удалось удалить публикацию.' };
        render();
      }
    };
  });

  const dashBrandDescription = document.getElementById('dashBrandDescription');
  if (dashBrandDescription) dashBrandDescription.oninput = () => {
    state.dashboardBrand = { ...(state.dashboardBrand || {}), description: dashBrandDescription.value };
  };
  const dashBrandAudience = document.getElementById('dashBrandAudience');
  if (dashBrandAudience) dashBrandAudience.oninput = () => {
    state.dashboardBrand = { ...(state.dashboardBrand || {}), audience: dashBrandAudience.value };
  };
  const dashBrandCtaStyle = document.getElementById('dashBrandCtaStyle');
  if (dashBrandCtaStyle) dashBrandCtaStyle.onchange = () => {
    state.dashboardBrand = { ...(state.dashboardBrand || {}), ctaStyle: dashBrandCtaStyle.value };
  };
  const dashSaveBrandBtn = document.getElementById('dashSaveBrandBtn');
  if (dashSaveBrandBtn) dashSaveBrandBtn.onclick = () => {
    const payload = state.dashboardBrand || { description: '', audience: '', ctaStyle: 'value' };
    localStorage.setItem('dashboardBrandSettings', JSON.stringify(payload));
    state.notice = { type: 'ok', text: 'Настройки бренда сохранены.' };
    render();
  };

  document.querySelectorAll('[data-project-edit]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const id = Number(btn.dataset.projectEdit);
        const current = btn.dataset.projectName || '';
        const next = prompt('Новое название проекта:', current);
        if (next === null) return; // cancel
        const name = String(next).trim();
        if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
        await api(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) });
        await loadBase();
        state.notice = { type: 'ok', text: 'Проект переименован.' };
        render();
      } catch (e) {
        state.notice = { type: 'error', text: e.message };
        render();
      }
    };
  });
  document.querySelectorAll('[data-project-delete]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        const rawId = btn.getAttribute('data-project-delete') || btn.dataset.projectDelete || '';
        const id = Number(rawId);
        const name = String(btn.getAttribute('data-project-name') || btn.dataset.projectName || '').trim();
        if (!id) throw new Error('Не удалось определить ID проекта.');
        const reallyDelete = confirm(`Вы точно хотите удалить проект "${name}"? Это действие необратимо.`);
        if (!reallyDelete) return;
        if (!name) throw new Error('Не удалось получить название проекта для удаления.');
        const deleted = await api(`/api/projects/${id}/delete`, { method: 'POST', body: JSON.stringify({ confirm_name: name }) });
        await loadBase();
        const stillExists = state.projects.some((p) => Number(p.id) === id);
        if (stillExists) throw new Error(`Сервер вернул успех, но проект #${id} все еще в списке.`);
        state.notice = { type: 'ok', text: `Проект #${id} удален.` };
        render();
      } catch (e) {
        state.notice = { type: 'error', text: e.message };
        render();
      }
    };
  });
  const createProjectFromCreateBtn = document.getElementById('createProjectFromCreateBtn');
  if (createProjectFromCreateBtn) createProjectFromCreateBtn.onclick = async () => {
    try {
      const input = document.getElementById('wNewProject');
      const name = (input?.value || '').trim();
      if (name.length < 3) throw new Error('Название проекта должно быть минимум 3 символа.');
      createProjectFromCreateBtn.disabled = true;
      const created = await api('/api/projects', { method: 'POST', body: JSON.stringify({ name }) });
      await loadBase();
      state.createWizard.projectId = String(created?.id || state.projects[state.projects.length - 1]?.id || '');
      state.notice = { type: 'ok', text: 'Проект создан и выбран в мастере.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message };
      render();
    } finally {
      createProjectFromCreateBtn.disabled = false;
    }
  };
  const parseHashtags = (raw) => {
    const tags = String(raw || '')
      .split(/\s+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => s.startsWith('#') ? s : `#${s}`);
    return [...new Set(tags)].slice(0, 8);
  };
  const buildLocalPreviewText = (wizard) => {
    const goalMap = {
      sales: 'Сделайте акцент на выгоде и действии клиента.',
      warmup: 'Разогрейте интерес через историю и пользу.',
      expert: 'Покажите экспертность через конкретные шаги.',
      announce: 'Сделайте четкий анонс с датой и выгодой.',
    };
    const topic = String(wizard.topic || '').trim();
    const cta = String(wizard.finalCta || '').trim() || `CTA: ${String(wizard.ctaAction || 'Написать').trim()}`;
    if (!topic) return '';
    return `${topic}\n\n${goalMap[wizard.goal] || goalMap.sales}\n\n1) Боль аудитории.\n2) Решение и польза.\n3) ${cta}`;
  };
  const selectedApiPlatforms = (wizard) => {
    const meta = !!(wizard.platforms?.facebook || wizard.platforms?.instagram);
    const youtube = !!wizard.platforms?.youtube;
    const platforms = [];
    if (meta) platforms.push('facebook', 'instagram');
    if (youtube) platforms.push('youtube');
    return [...new Set(platforms)];
  };
  const generatePreviewByAi = async () => {
    const w = state.createWizard;
    const topic = String(w.topic || '').trim();
    if (!topic) throw new Error('Сначала заполните поле «О чём пост?»');
    const platforms = selectedApiPlatforms(w);
    w.generating = true;
    w.publishSuccess = null;
    render();
    try {
      const previewPayload = await api('/api/generate-preview', {
        method: 'POST',
        body: JSON.stringify({
          project_id: Number(w.projectId || state.projects[0]?.id || 0) || null,
          topic,
          category: w.category || 'business',
          tone: w.tone || 'friendly',
          language: 'ru',
          platforms: platforms.length ? platforms : ['instagram'],
        }),
        timeoutMs: 90000,
      });
      const generated = String(previewPayload?.text || '').trim();
      w.previewText = generated || buildLocalPreviewText(w);
      if (!Array.isArray(w.hashtags) || w.hashtags.length === 0) {
        const topicWord = topic.split(/\s+/).slice(0, 2).join('');
        w.hashtags = parseHashtags(`#${topicWord} #маркетинг #бизнес`);
      }
      if (!w.finalCta) w.finalCta = `Напишите «ХОЧУ», чтобы ${String(w.ctaAction || 'записаться').toLowerCase()}.`;
      w.generatedAt = new Date().toISOString();
    } catch {
      await new Promise((r) => setTimeout(r, 900));
      w.previewText = buildLocalPreviewText(w);
      if (!Array.isArray(w.hashtags) || w.hashtags.length === 0) w.hashtags = ['#контент', '#бизнес', '#маркетинг'];
      if (!w.finalCta) w.finalCta = `Напишите «ХОЧУ», чтобы ${String(w.ctaAction || 'записаться').toLowerCase()}.`;
      w.generatedAt = new Date().toISOString();
    } finally {
      w.generating = false;
      render();
    }
  };

  const wProjectEl = document.getElementById('wProject');
  if (wProjectEl) wProjectEl.onchange = () => { state.createWizard.projectId = wProjectEl.value; state.createWizard.publishSuccess = null; };
  const wNicheEl = document.getElementById('wNiche');
  if (wNicheEl) wNicheEl.onchange = () => {
    state.createWizard.niche = normalizeNicheIdSafe(wNicheEl.value || DEFAULT_DIRECTOR_NICHE) || DEFAULT_DIRECTOR_NICHE;
    state.createWizard.category = state.createWizard.niche;
    state.createWizard.quickTopicsVersion = 0;
    state.createWizard.previewText = '';
    state.createWizard.publishSuccess = null;
    render();
  };
  const refreshTopicTemplates = () => {
    const container = document.getElementById('wTopicTemplates');
    if (!container) return;
    const topicTemplates = buildCreateQuickTopics(state.createWizard.niche || state.createWizard.category, state.createWizard.quickTopicsVersion || 0);
    container.innerHTML = topicTemplates.map((t) => `<button type="button" class="btn btn-ghost btn-topic-template" data-topic-template="${esc(t)}">${esc(t)}</button>`).join('');
    bindTopicTemplateButtons();
  };
  const bindTopicTemplateButtons = () => {
    document.querySelectorAll('[data-topic-template]').forEach((btn) => {
      btn.onclick = () => {
        const topic = (btn.getAttribute('data-topic-template') || '').trim();
        const topicInput = document.getElementById('wTopic');
        if (topicInput) topicInput.value = topic;
        state.createWizard.topic = topic;
        state.createWizard.previewText = '';
        state.createWizard.publishSuccess = null;
        state.notice = null;
      };
    });
  };
  const wRefreshTopicsBtn = document.getElementById('wRefreshTopics');
  if (wRefreshTopicsBtn) wRefreshTopicsBtn.onclick = () => {
    state.createWizard.quickTopicsVersion = Number(state.createWizard.quickTopicsVersion || 0) + 1;
    refreshTopicTemplates();
  };
  const wTopicEl = document.getElementById('wTopic');
  if (wTopicEl) wTopicEl.oninput = () => {
    state.createWizard.topic = wTopicEl.value;
    state.createWizard.previewText = '';
    state.createWizard.publishSuccess = null;
  };
  const wGoalRadios = document.querySelectorAll('input[name="wGoal"]');
  wGoalRadios.forEach((el) => {
    el.onchange = () => {
      state.createWizard.goal = el.value;
      state.createWizard.publishSuccess = null;
    };
  });
  const wCtaAction = document.getElementById('wCtaAction');
  if (wCtaAction) wCtaAction.oninput = () => {
    state.createWizard.ctaAction = wCtaAction.value;
    state.createWizard.publishSuccess = null;
  };
  const wMeta = document.getElementById('wMeta');
  if (wMeta) wMeta.onchange = () => {
    const checked = !!wMeta.checked;
    state.createWizard.platforms.facebook = checked;
    state.createWizard.platforms.instagram = checked;
    state.createWizard.publishSuccess = null;
    render();
  };
  const wYoutube = document.getElementById('wYoutube');
  if (wYoutube) wYoutube.onchange = () => {
    state.createWizard.platforms.youtube = !!wYoutube.checked;
    state.createWizard.publishSuccess = null;
    render();
  };
  const wMetaFormat = document.getElementById('wMetaFormat');
  if (wMetaFormat) wMetaFormat.onchange = () => { state.createWizard.metaFormat = wMetaFormat.value; };
  const wYoutubeFormat = document.getElementById('wYoutubeFormat');
  if (wYoutubeFormat) wYoutubeFormat.onchange = () => { state.createWizard.youtubeFormat = wYoutubeFormat.value; };
  const wConnectMeta = document.getElementById('wConnectMeta');
  if (wConnectMeta) wConnectMeta.onclick = async () => {
    const r = await api('/api/integrations/meta/connect', { method: 'POST', body: '{}' });
    location.href = r.oauth_url;
  };
  const wConnectYoutube = document.getElementById('wConnectYoutube');
  if (wConnectYoutube) wConnectYoutube.onclick = async () => {
    const r = await api('/api/integrations/youtube/start', { method: 'POST', body: '{}' });
    location.href = r.oauth_url;
  };
  document.querySelectorAll('[data-ai-prompt]').forEach((btn) => {
    btn.onclick = () => {
      const kind = String(btn.getAttribute('data-ai-prompt') || '');
      const map = {
        sales: { goal: 'sales', tone: 'sales' },
        expert: { goal: 'expert', tone: 'expert' },
        announce: { goal: 'announce', tone: 'friendly' },
        warmup: { goal: 'warmup', tone: 'friendly' },
      };
      const payload = map[kind] || map.sales;
      state.createWizard.goal = payload.goal;
      state.createWizard.tone = payload.tone;
      state.createWizard.publishSuccess = null;
      render();
    };
  });
  const wToneEl = document.getElementById('wTone');
  if (wToneEl) wToneEl.onchange = () => {
    state.createWizard.tone = wToneEl.value;
    state.createWizard.previewText = '';
    state.createWizard.publishSuccess = null;
    render();
  };
  state.createWizard.language = 'ru';
  const wModeEl = document.getElementById('wMode');
  if (wModeEl) wModeEl.onchange = () => { state.createWizard.mode = wModeEl.value; state.createWizard.publishSuccess = null; render(); };
  const wScheduleEl = document.getElementById('wSchedule');
  if (wScheduleEl) wScheduleEl.oninput = () => { state.createWizard.scheduleAt = wScheduleEl.value; };
  const wPreviewTextEl = document.getElementById('wPreviewText');
  if (wPreviewTextEl) wPreviewTextEl.oninput = () => { state.createWizard.previewText = wPreviewTextEl.value; state.createWizard.publishSuccess = null; };
  const wHashtagsEl = document.getElementById('wHashtags');
  if (wHashtagsEl) wHashtagsEl.oninput = () => { state.createWizard.hashtags = parseHashtags(wHashtagsEl.value); state.createWizard.publishSuccess = null; };
  const wFinalCtaEl = document.getElementById('wFinalCta');
  if (wFinalCtaEl) wFinalCtaEl.oninput = () => { state.createWizard.finalCta = wFinalCtaEl.value; state.createWizard.publishSuccess = null; };
  const wGenerateBtn = document.getElementById('wGenerateBtn');
  if (wGenerateBtn) wGenerateBtn.onclick = async () => {
    try {
      await generatePreviewByAi();
      state.notice = { type: 'ok', text: 'AI подготовил черновик поста. Проверьте текст и CTA.' };
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сгенерировать пост.' };
      render();
    }
  };
  bindTopicTemplateButtons();

  const wPrev = document.getElementById('wPrev'); if (wPrev) wPrev.onclick = () => { state.createWizard.step = Math.max(1, state.createWizard.step - 1); render(); };
  const wNext = document.getElementById('wNext'); if (wNext) wNext.onclick = async () => {
    try {
      const w = state.createWizard;
      const selectedPlatforms = selectedApiPlatforms(w);
      if (w.step === 1) {
        w.projectId = document.getElementById('wProject')?.value || w.projectId || '';
        if (!w.projectId && state.projects?.[0]?.id) w.projectId = String(state.projects[0].id);
      }
      if (w.step === 2) {
        if (!selectedPlatforms.length) { state.notice = { type: 'error', text: 'Выберите хотя бы одну платформу.' }; return render(); }
      }
      if (w.step === 3) {
        w.topic = (document.getElementById('wTopic')?.value || w.topic || '').trim();
        w.ctaAction = (document.getElementById('wCtaAction')?.value || w.ctaAction || 'Записаться').trim();
        if (!w.topic) { state.notice = { type: 'error', text: 'Укажите тему поста.' }; return render(); }
        if (!w.previewText) {
          wNext.disabled = true;
          wNext.textContent = 'AI готовит пост…';
          await generatePreviewByAi();
        }
      }
      if (w.step === 4) {
        w.previewText = (document.getElementById('wPreviewText')?.value || '').trim();
        if (!w.previewText) { state.notice = { type: 'error', text: 'Добавьте текст в предпросмотре.' }; return render(); }
        w.hashtags = parseHashtags(document.getElementById('wHashtags')?.value || (w.hashtags || []).join(' '));
        w.finalCta = (document.getElementById('wFinalCta')?.value || w.finalCta || '').trim();
      }
      if (w.step === 5) {
        w.mode = document.getElementById('wMode')?.value || 'now';
        w.scheduleAt = document.getElementById('wSchedule')?.value || '';
      }
      w.publishSuccess = null;
      w.step = Math.min(5, w.step + 1);
      render();
    } catch (e) {
      state.notice = { type: 'error', text: `Не удалось перейти к следующему шагу: ${e?.message || 'ошибка формы'}` };
      render();
    } finally {
      wNext.disabled = false;
      wNext.textContent = 'Далее';
    }
  };

  const wSubmit = document.getElementById('wSubmit');
  if (wSubmit) wSubmit.onclick = async () => {
    try {
      const w = state.createWizard;
      w.mode = document.getElementById('wMode')?.value || w.mode || 'now';
      w.scheduleAt = document.getElementById('wSchedule')?.value || w.scheduleAt || '';
      w.previewText = (document.getElementById('wPreviewText')?.value || w.previewText || '').trim();
      const selectedPlatforms = selectedApiPlatforms(w);
      const metaSelected = selectedPlatforms.includes('facebook') || selectedPlatforms.includes('instagram');
      const youtubeSelected = selectedPlatforms.includes('youtube');
      const metaConnected = (state.connections || []).some((c) => isConnectionReady(c));
      const youtubeConnected = !!state.youtubeConnection?.connected;
      if (!selectedPlatforms.length) throw new Error('Выберите хотя бы одну платформу.');
      if (metaSelected && !metaConnected) throw new Error('Сначала подключите Meta в разделе «Подключения».');
      if (youtubeSelected && !youtubeConnected) throw new Error('Сначала подключите YouTube в разделе «Подключения».');
      if (!w.topic) throw new Error('Тема обязательна.');
      if (!w.previewText) throw new Error('Добавьте текст в предпросмотре.');
      const project_id = Number(w.projectId || state.projects[0]?.id || 0) || null;
      const payloadBase = {
        project_id,
        topic: w.topic,
        category: w.category,
        tone: w.tone,
        language: 'ru',
        media_url: w.mediaUrl || null,
        generated_text: w.previewText,
      };

      wSubmit.disabled = true;
      wSubmit.textContent = (w.mode === 'schedule') ? 'Планирую…' : 'Публикую…';

      if (w.mode === 'schedule') {
        if (!w.scheduleAt) throw new Error('Укажите дату и время для планирования.');
        const scheduleAtIso = localInputToIsoNoTz(w.scheduleAt);
        if (!scheduleAtIso) throw new Error('Некорректные дата/время планирования.');
        for (const platform of selectedPlatforms) {
          const payload = { ...payloadBase, platform, schedule_at: scheduleAtIso };
          await api('/api/generate', { method: 'POST', body: JSON.stringify(payload), timeoutMs: 90000 });
        }
        w.publishSuccess = 'Публикация успешно запланирована. Вы можете создать следующий пост или открыть календарь.';
        state.notice = { type: 'ok', text: 'Пост успешно запланирован.' };
        render();
        return;
      }

      if (w.mode === 'draft') {
        for (const platform of selectedPlatforms) {
          const payload = { ...payloadBase, platform, save_as_draft: true };
          await api('/api/generate', { method: 'POST', body: JSON.stringify(payload), timeoutMs: 90000 });
        }
        w.publishSuccess = 'Черновик сохранен. Можно создать следующий пост или перейти в календарь.';
        state.notice = { type: 'ok', text: 'Черновик успешно сохранён.' };
        render();
        return;
      }

      let sharedMediaUrl = (w.mediaUrl || '').trim() || null;
      const createdPosts = [];
      for (let i = 0; i < selectedPlatforms.length; i += 1) {
        const platform = selectedPlatforms[i];
        const platformLabel = platform === 'facebook' ? 'Facebook' : (platform === 'instagram' ? 'Instagram' : 'YouTube');
        wSubmit.textContent = `Готовлю ${platformLabel} (${i + 1}/${selectedPlatforms.length})...`;
        const payload = { ...payloadBase, platform, media_url: sharedMediaUrl };
        const created = await api('/api/generate', { method: 'POST', body: JSON.stringify(payload), timeoutMs: 90000 });
        const postId = created?.id;
        if (!postId) throw new Error(`Не удалось создать пост для ${platform}.`);
        if (!sharedMediaUrl && created?.media_url) sharedMediaUrl = created.media_url;
        createdPosts.push({ platform, postId });
      }
      const publishErrors = [];
      for (let i = 0; i < createdPosts.length; i += 1) {
        const platform = createdPosts[i]?.platform;
        const postId = createdPosts[i]?.postId;
        const platformLabel = platform === 'facebook' ? 'Facebook' : (platform === 'instagram' ? 'Instagram' : 'YouTube');
        wSubmit.textContent = `Публикую ${platformLabel} (${i + 1}/${createdPosts.length})...`;
        try {
          await api(`/api/posts/${postId}/publish`, { method: 'POST', body: '{}', timeoutMs: 180000 });
        } catch (reason) {
          publishErrors.push(`${platformLabel}: ${reason?.message || 'ошибка публикации'}`);
        }
      }
      if (publishErrors.length) {
        throw new Error(`Часть публикаций не выполнена: ${publishErrors.join(' ; ')}`);
      }
      w.publishSuccess = 'Пост опубликован. Отлично! Можно сразу создать следующий пост.';
      state.notice = { type: 'ok', text: 'Публикация успешно выполнена.' };
      render();
    } catch (e) {
      let text = e.message || 'Ошибка публикации.';
      if (String(text).includes('OpenAI: недостаточно квоты')) {
        text = 'OpenAI: недостаточно квоты. Пополните лимит/баланс в OpenAI или включите USE_MOCK_PROVIDERS=true для теста без ключей.';
      }
      state.notice = { type: 'error', text };
      render();
    } finally {
      try {
        const mode = document.getElementById('wMode')?.value || state.createWizard.mode || 'now';
        wSubmit.disabled = false;
        wSubmit.textContent = mode === 'schedule' ? 'Запланировать' : (mode === 'draft' ? 'Сохранить как черновик' : 'Опубликовать');
      } catch {}
    }
  };
  const wCreateMoreBtn = document.getElementById('wCreateMoreBtn');
  if (wCreateMoreBtn) wCreateMoreBtn.onclick = () => {
    const currentProjectId = state.createWizard.projectId || '';
    state.createWizard = {
      ...state.createWizard,
      step: 1,
      projectId: currentProjectId,
      topic: '',
      previewText: '',
      hashtags: ['#контент', '#бизнес'],
      finalCta: 'Напишите в директ, чтобы получить консультацию.',
      publishSuccess: null,
      generating: false,
    };
    render();
  };
  const wOpenCalendarBtn = document.getElementById('wOpenCalendarBtn');
  if (wOpenCalendarBtn) wOpenCalendarBtn.onclick = () => nav('/calendar');

  const startMetaConnect = async () => {
    const r = await api('/api/integrations/meta/connect', { method: 'POST', body: '{}' });
    location.href = r.oauth_url;
  };
  const connectMetaBtn = document.getElementById('connectMetaBtn');
  if (connectMetaBtn) connectMetaBtn.onclick = async () => {
    try {
      setQuickLoading(connectMetaBtn, 'Открываю...', true);
      await startMetaConnect();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось запустить подключение Facebook.' };
      render();
    } finally {
      setQuickLoading(connectMetaBtn, 'Открываю...', false);
    }
  };
  const connectYoutubeBtn = document.getElementById('connectYoutubeBtn');
  if (connectYoutubeBtn) connectYoutubeBtn.onclick = async () => {
    try {
      setQuickLoading(connectYoutubeBtn, 'Открываю...', true);
      const r = await api('/api/integrations/youtube/start', { method: 'POST', body: '{}' });
      if (!r?.oauth_url) throw new Error('Сервер не вернул OAuth ссылку для YouTube.');
      location.href = r.oauth_url;
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось запустить подключение YouTube.' };
      render();
    } finally {
      setQuickLoading(connectYoutubeBtn, 'Открываю...', false);
    }
  };
  document.querySelectorAll('[data-youtube-disconnect]').forEach((b) => b.onclick = async () => {
    if (!confirm('Отключить YouTube?')) return;
    await api('/api/integrations/youtube/disconnect', { method: 'POST', body: '{}' });
    state.youtubeConnection = await api('/api/integrations/youtube/status');
    state.notice = { type: 'ok', text: 'YouTube отключен.' };
    render();
  });
  document.querySelectorAll('[data-disconnect]').forEach((b) => b.onclick = async () => {
    if (!confirm('Отключить интеграцию Meta?')) return;
    await api(`/api/connections/${b.dataset.disconnect}/disconnect`, { method: 'POST', body: '{}' });
    state.connections = await api('/api/connections');
    state.notice = { type: 'ok', text: 'Интеграция отключена.' };
    render();
  });
  document.querySelectorAll('[data-refresh]').forEach((b) => b.onclick = async () => {
    try {
      setQuickLoading(b, 'Проверяю...', true);
      await api(`/api/connections/${b.dataset.refresh}/refresh-token`, { method: 'POST', body: '{}' });
      state.connections = await api('/api/connections');
      state.notice = { type: 'ok', text: 'Статус подключения обновлён.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось обновить токен.' };
      render();
    } finally {
      setQuickLoading(b, 'Проверяю...', false);
    }
  });

  // Meta Page picker (explicit Page selection for multi-Page accounts).
  const closePicker = () => {
    state.connectionPicker.open = false;
    state.connectionPicker.loading = false;
    state.connectionPicker.pages = [];
    state.connectionPicker.selectedPageId = '';
    state.connectionPicker.error = '';
    state.connectionPicker.filter = 'all';
    state.connectionPicker.query = '';
  };

  const openPagePicker = async (id, opts = {}) => {
    try {
      const preferUnconnected = !!opts.preferUnconnected;
      state.connectionPicker.open = true;
      state.connectionPicker.connectionId = id;
      state.connectionPicker.loading = true;
      state.connectionPicker.pages = [];
      state.connectionPicker.selectedPageId = '';
      state.connectionPicker.error = '';
      state.connectionPicker.filter = preferUnconnected ? 'not_connected' : 'all';
      state.connectionPicker.query = '';
      render();

      const r = await api(`/api/integrations/meta/pages?connection_id=${encodeURIComponent(id)}`);
      state.connectionPicker.pages = r.pages || [];
      state.connectionPicker.loading = false;
      // Preselect page that has IG if possible.
      const pagePool = preferUnconnected
        ? (state.connectionPicker.pages || []).filter((p) => !p.already_connected)
        : (state.connectionPicker.pages || []);
      const preferred = pagePool.find((p) => p.has_ig) || pagePool[0];
      if (preferred) state.connectionPicker.selectedPageId = String(preferred.page_id || '');
      render();
    } catch (e) {
      state.connectionPicker.loading = false;
      state.connectionPicker.error = e.message || 'Не удалось загрузить страницы.';
      render();
    }
  };

  document.querySelectorAll('[data-primary-action]').forEach((b) => b.onclick = async () => {
    const action = String(b.dataset.primaryAction || '');
    const id = Number(b.dataset.connectionId || 0);
    try {
      if (action === 'connect' || action === 'reconnect') {
        await startMetaConnect();
        return;
      }
      if (action === 'pick_page') {
        await openPagePicker(id);
        return;
      }
      if (action === 'test') {
        const r = await api(`/api/connections/${id}/test-publish`, { method: 'POST', body: '{}' });
        state.connections = await api('/api/connections');

        const postId = (r && r.post_id) ? String(r.post_id) : '';
        const text = postId
          ? `Тестовая публикация отправлена (${mode || 'real'}). Post ID: ${postId}`
          : 'Тест публикации пройден.';
        state.notice = { type: 'ok', text };
        render();
        return;
      }
      await api(`/api/connections/${id}/refresh-token`, { method: 'POST', body: '{}' });
      state.connections = await api('/api/connections');
      state.notice = { type: 'ok', text: 'Повторная проверка выполнена.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Ошибка действия интеграции.' };
      render();
    }
  });

  const pickerBackdrop = document.getElementById('connectionPickerBackdrop');
  if (pickerBackdrop) pickerBackdrop.onclick = (e) => {
    if (e.target === pickerBackdrop) { closePicker(); render(); }
  };

  const closePickerBtn = document.getElementById('closePickerBtn');
  if (closePickerBtn) closePickerBtn.onclick = () => { closePicker(); render(); };

  document.querySelectorAll('input[name="pagePick"]').forEach((el) => el.onchange = () => {
    state.connectionPicker.selectedPageId = el.value;
    const saveBtn = document.getElementById('savePickedPageBtn');
    if (saveBtn) saveBtn.disabled = !state.connectionPicker.selectedPageId;
    const addBtn = document.getElementById('addPickedPageBtn');
    if (addBtn) addBtn.disabled = !state.connectionPicker.selectedPageId;
  });

  const applyFilterBtnState = () => {
    const a = document.getElementById('filterAllBtn');
    const nc = document.getElementById('filterNotConnectedBtn');
    const w = document.getElementById('filterWithIgBtn');
    const n = document.getElementById('filterWithoutIgBtn');
    const f = state.connectionPicker.filter;
    const activeClass = 'btn btn-secondary';
    const normalClass = 'btn btn-ghost';
    if (a) a.className = f === 'all' ? activeClass : normalClass;
    if (nc) nc.className = f === 'not_connected' ? activeClass : normalClass;
    if (w) w.className = f === 'with_ig' ? activeClass : normalClass;
    if (n) n.className = f === 'without_ig' ? activeClass : normalClass;
  };

  const filterAllBtn = document.getElementById('filterAllBtn');
  if (filterAllBtn) filterAllBtn.onclick = () => { state.connectionPicker.filter = 'all'; applyFilterBtnState(); render(); };
  const filterNotConnectedBtn = document.getElementById('filterNotConnectedBtn');
  if (filterNotConnectedBtn) filterNotConnectedBtn.onclick = () => { state.connectionPicker.filter = 'not_connected'; applyFilterBtnState(); render(); };
  const filterWithIgBtn = document.getElementById('filterWithIgBtn');
  if (filterWithIgBtn) filterWithIgBtn.onclick = () => { state.connectionPicker.filter = 'with_ig'; applyFilterBtnState(); render(); };
  const filterWithoutIgBtn = document.getElementById('filterWithoutIgBtn');
  if (filterWithoutIgBtn) filterWithoutIgBtn.onclick = () => { state.connectionPicker.filter = 'without_ig'; applyFilterBtnState(); render(); };

  const pageSearchInput = document.getElementById('pageSearchInput');
  if (pageSearchInput) {
    pageSearchInput.value = state.connectionPicker.query || '';
    pageSearchInput.oninput = () => { state.connectionPicker.query = pageSearchInput.value; render(); };
    setTimeout(() => { try { pageSearchInput.focus(); } catch {} }, 0);
  }
  applyFilterBtnState();

  const refreshPagesBtn = document.getElementById('refreshPagesBtn');
  if (refreshPagesBtn) refreshPagesBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      if (!id) return;
      state.connectionPicker.loading = true;
      state.connectionPicker.error = '';
      render();
      const r = await api(`/api/integrations/meta/pages?connection_id=${encodeURIComponent(id)}`);
      state.connectionPicker.pages = r.pages || [];
      state.connectionPicker.loading = false;
      render();
    } catch (e) {
      state.connectionPicker.loading = false;
      state.connectionPicker.error = e.message || 'Не удалось обновить список.';
      render();
    }
  };

  const savePickedPageBtn = document.getElementById('savePickedPageBtn');
  if (savePickedPageBtn) savePickedPageBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      const page_id = state.connectionPicker.selectedPageId;
      if (!id || !page_id) return;
      savePickedPageBtn.disabled = true;
      await api('/api/integrations/meta/select-page', { method: 'POST', body: JSON.stringify({ connection_id: id, page_id }) });
      state.connections = await api('/api/connections');
      closePicker();
      state.notice = { type: 'ok', text: 'Страница выбрана.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось сохранить выбор.' };
      render();
    } finally {
      savePickedPageBtn.disabled = false;
    }
  };

  const addPickedPageBtn = document.getElementById('addPickedPageBtn');
  if (addPickedPageBtn) addPickedPageBtn.onclick = async () => {
    try {
      const id = state.connectionPicker.connectionId;
      const page_id = state.connectionPicker.selectedPageId;
      if (!id || !page_id) return;
      addPickedPageBtn.disabled = true;
      await api('/api/connections/meta/add-page', { method: 'POST', body: JSON.stringify({ source_connection_id: id, page_id }) });
      state.connections = await api('/api/connections');
      closePicker();
      state.notice = { type: 'ok', text: 'Страница добавлена как отдельное подключение.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось добавить подключение.' };
      render();
    } finally {
      addPickedPageBtn.disabled = false;
    }
  };

  const openPostEditor = async (id) => {
    if (!id) return;
    state.postEditor = { open: true, saving: false, post: null, error: '', loading: true };
    render();
    try {
      const post = await api(`/api/posts/${id}`);
      const relatedPosts = (Array.isArray(state.posts) ? state.posts : []).filter((row) => {
        if (!row || Number(row.id) === Number(post.id)) return false;
        if (String(row.topic || '').trim() !== String(post.topic || '').trim()) return false;
        if (String(row.schedule_at || '').trim() !== String(post.schedule_at || '').trim()) return false;
        const status = String(row.status || '').toLowerCase();
        if (status === 'deleted') return false;
        return ['facebook', 'instagram'].includes(String(row.platform || '').toLowerCase());
      });
      const platforms = {
        facebook: String(post.platform || '').toLowerCase() === 'facebook' || relatedPosts.some((row) => String(row.platform || '').toLowerCase() === 'facebook'),
        instagram: String(post.platform || '').toLowerCase() === 'instagram' || relatedPosts.some((row) => String(row.platform || '').toLowerCase() === 'instagram'),
      };
      state.postEditor = { open: true, saving: false, post, error: '', loading: false, platforms, relatedPostIds: relatedPosts.map((row) => Number(row.id)).filter(Boolean) };
      render();
    } catch (e) {
      state.postEditor = { open: true, saving: false, post: null, error: e.message || 'Не удалось загрузить пост.', loading: false };
      render();
    }
  };
  const closePostEditor = () => {
    state.postEditor = { open: false, saving: false, post: null, error: '' };
    render();
  };

  const postEditBackdrop = document.getElementById('postEditBackdrop');
  if (postEditBackdrop) postEditBackdrop.onclick = (e) => { if (e.target && e.target.id === 'postEditBackdrop') closePostEditor(); };
  const closePostEditBtn = document.getElementById('closePostEditBtn');
  if (closePostEditBtn) closePostEditBtn.onclick = closePostEditor;

  const clearScheduleBtn = document.getElementById('clearScheduleBtn');
  if (clearScheduleBtn) clearScheduleBtn.onclick = () => {
    const el = document.getElementById('editSchedule');
    if (el) el.value = '';
  };

  const savePostEditBtn = document.getElementById('savePostEditBtn');
  if (savePostEditBtn) savePostEditBtn.onclick = async () => {
    const post = state.postEditor?.post;
    if (!post?.id) return;
    const topic = (document.getElementById('editTopic')?.value || '').trim();
    if (!topic) {
      state.postEditor = { ...state.postEditor, error: 'Введите тему поста.' };
      render();
      return;
    }
    const selectedPlatforms = [
      document.getElementById('editPlatformFacebook')?.checked ? 'facebook' : null,
      document.getElementById('editPlatformInstagram')?.checked ? 'instagram' : null,
    ].filter(Boolean);
    if (!selectedPlatforms.length) {
      state.postEditor = { ...state.postEditor, error: 'Выберите хотя бы одну платформу.' };
      render();
      return;
    }
    const payload = {
      topic,
      generated_text: (document.getElementById('editText')?.value || '').trim(),
      platforms: selectedPlatforms,
      related_post_ids: Array.isArray(state.postEditor?.relatedPostIds) ? state.postEditor.relatedPostIds : [],
      media_url: (document.getElementById('editMedia')?.value || '').trim(),
      schedule_at: null,
    };
    const scheduleValue = (document.getElementById('editSchedule')?.value || '').trim();
    if (scheduleValue) {
      payload.schedule_at = localInputToIsoNoTz(scheduleValue);
      if (!payload.schedule_at) {
        state.postEditor = { ...state.postEditor, saving: false, error: 'Некорректные дата/время публикации.' };
        render();
        return;
      }
    }
    state.postEditor = { ...state.postEditor, saving: true, error: '' };
    render();
    try {
      await api(`/api/posts/${post.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост обновлен.' };
      state.postEditor = { open: false, saving: false, post: null, error: '' };
      render();
    } catch (e) {
      state.postEditor = { ...state.postEditor, saving: false, error: e.message || 'Не удалось сохранить пост.' };
      render();
    }
  };

  document.querySelectorAll('[data-edit-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.editPost || b.getAttribute('data-edit-post'));
    await openPostEditor(id);
  });
  document.querySelectorAll('[data-add-page]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.addPage || 0);
    if (!id) return;
    try {
      await openPagePicker(id, { preferUnconnected: true });
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось открыть список страниц.' };
      render();
    }
  });

  const updateHistorySelectedDayPanel = (key) => {
    if (!key) return;
    const labelEl = document.getElementById('historySelectedDayLabel');
    const postsEl = document.getElementById('historySelectedDayPosts');
    if (!labelEl || !postsEl) return;

    const dayDate = new Date(`${key}T00:00:00`);
    labelEl.textContent = dayDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });

    const isPublishedPostLocal = (p) => {
      const status = String(p?.status || '').toLowerCase();
      return Boolean(p?.published_at) || Boolean(p?.remote_id) || status === 'published';
    };
    const postsForDay = (state.posts || []).filter((p) => {
      const published = isPublishedPostLocal(p);
      const calendarDate = published ? (p.published_at || p.schedule_at || p.created_at) : p.schedule_at;
      return calendarDate && localDateKey(calendarDate) === key;
    }).sort((a, b) => {
      const da = new Date(a.published_at || a.schedule_at || a.created_at).getTime();
      const db = new Date(b.published_at || b.schedule_at || b.created_at).getTime();
      return da - db;
    });

    if (!postsForDay.length) {
      postsEl.innerHTML = '<div class="small muted">На этот день постов нет</div>';
      return;
    }

    postsEl.innerHTML = postsForDay.map((p) => {
      const published = isPublishedPostLocal(p);
      const title = p.topic || p.title_preview || `Пост #${p.id}`;
      const when = p.published_at
        ? `Опубликовано: ${new Date(p.published_at).toLocaleString()}`
        : (p.schedule_at ? `План: ${new Date(p.schedule_at).toLocaleString()}` : 'Без даты');
      return `<article class="phone-post-row">
        <div class="phone-post-main">
          <strong class="truncate" title="${esc(title)}">${esc(title)}</strong>
          <div class="small">${esc(p.platform || '—')} · ${esc(when)} · ${published ? 'Опубликован' : 'Черновик'}</div>
        </div>
      </article>`;
    }).join('');
  };

  document.querySelectorAll('[data-calendar-day]').forEach((btn) => {
    btn.onclick = () => {
      const key = String(btn.dataset.calendarDay || '');
      if (!key) return;
      state.historyCalendar = { ...(state.historyCalendar || {}), selectedDayKey: key, monthsSpan: 1 };
      document.querySelectorAll('[data-calendar-day].is-selected').forEach((el) => el.classList.remove('is-selected'));
      btn.classList.add('is-selected');
      updateHistorySelectedDayPanel(key);
    };
  });

  const calendarPrevMonthBtn = document.getElementById('calendarPrevMonthBtn');
  if (calendarPrevMonthBtn) calendarPrevMonthBtn.onclick = () => {
    const cur = monthStartFromKey(state.historyCalendar?.monthKey);
    const prev = new Date(cur.getFullYear(), cur.getMonth() - 1, 1);
    state.historyCalendar = { ...(state.historyCalendar || {}), monthKey: localMonthKey(prev) };
    render();
  };
  const calendarNextMonthBtn = document.getElementById('calendarNextMonthBtn');
  if (calendarNextMonthBtn) calendarNextMonthBtn.onclick = () => {
    const cur = monthStartFromKey(state.historyCalendar?.monthKey);
    const next = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
    state.historyCalendar = { ...(state.historyCalendar || {}), monthKey: localMonthKey(next) };
    render();
  };
  const calendarTodayBtn = document.getElementById('calendarTodayBtn');
  if (calendarTodayBtn) calendarTodayBtn.onclick = () => {
    state.historyCalendar = { ...(state.historyCalendar || {}), monthKey: localMonthKey(new Date()), monthsSpan: 1 };
    render();
  };

  const closePostViewer = () => { state.postViewer = { open: false, loading: false, post: null, error: '' }; render(); };
  const closePostViewerBtn = document.getElementById('closePostViewerBtn');
  if (closePostViewerBtn) closePostViewerBtn.onclick = closePostViewer;
  const postViewerBackdrop = document.getElementById('postViewerBackdrop');
  if (postViewerBackdrop) postViewerBackdrop.onclick = (e) => { if (e.target && e.target.id === 'postViewerBackdrop') closePostViewer(); };

  document.querySelectorAll('[data-view-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.viewPost || b.getAttribute('data-view-post'));
    if (!id) return;
    state.postViewer = { open: true, loading: true, post: null, error: '' };
    render();
    try {
      const post = await api(`/api/posts/${id}`);
      state.postViewer = { open: true, loading: false, post, error: '' };
      render();
    } catch (e) {
      state.postViewer = { open: true, loading: false, post: null, error: e.message || 'Не удалось загрузить пост.' };
      render();
    }
  });

  document.querySelectorAll('[data-retry]').forEach((b) => b.onclick = async () => {
    const p = state.posts.find((x) => x.id === Number(b.dataset.retry));
    if (!p) return;
    await api('/api/generate', { method: 'POST', body: JSON.stringify({ project_id: p.project_id, topic: p.topic, category: p.category || 'business' }) });
    state.posts = await api('/api/posts');
    render();
  });

  document.querySelectorAll('[data-publish-now]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.publishNow || b.getAttribute('data-publish-now'));
    if (!id) return;
    b.disabled = true;
    try {
      await api(`/api/posts/${id}/publish`, { method: 'POST', body: '{}' });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост отправлен в публикацию.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось опубликовать пост.' };
      render();
    }
  });

  document.querySelectorAll('[data-delete-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.deletePost || b.getAttribute('data-delete-post'));
    if (!id) return;
    if (!confirm('Удалить неопубликованный пост? Это действие нельзя отменить.')) return;
    try {
      await api(`/api/posts/${id}`, { method: 'DELETE' });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост удален.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось удалить пост.' };
      render();
    }
  });

  document.querySelectorAll('[data-hide-post]').forEach((b) => b.onclick = async () => {
    const id = Number(b.dataset.hidePost || b.getAttribute('data-hide-post'));
    if (!id) return;
    if (!confirm('Убрать опубликованный пост из календаря/истории на сайте?')) return;
    try {
      await api(`/api/posts/${id}/hide`, { method: 'POST', body: '{}' });
      state.posts = await api('/api/posts');
      state.notice = { type: 'ok', text: 'Пост скрыт с сайта.' };
      render();
    } catch (e) {
      state.notice = { type: 'error', text: e.message || 'Не удалось скрыть пост.' };
      render();
    }
  });

  const checkoutSubscription = async (plan) => {
    const normalizedPlan = normalizePublicPlan(plan);
    if (!state.billing?.stripe?.prices?.[normalizedPlan]) {
      state.notice = {
        type: 'error',
        text: 'Оплата этого тарифа пока недоступна. Тариф уже есть в продукте, но checkout появится позже.',
      };
      render();
      return;
    }
    try {
      const candidates = normalizeCheckoutPlanCode(plan);
      let lastErr = null;
      for (const planCode of candidates) {
        try {
          const r = await api('/api/billing/checkout/subscription', { method: 'POST', body: JSON.stringify({ plan: planCode }) });
          location.href = r.checkout_url;
          return;
        } catch (e) {
          lastErr = e;
          const msg = String(e?.message || '').toLowerCase();
          if (!/валидный тариф|starter|growth|agency/.test(msg)) {
            throw e;
          }
        }
      }
      throw lastErr || new Error('Не удалось открыть оплату.');
    } catch (e) {
      const msg = String(e?.message || '');
      const stripeConfigError = /stripe.+not configured|price id.+not configured/i.test(msg);
      state.notice = {
        type: 'error',
        text: stripeConfigError
          ? 'Оплата временно недоступна: checkout для тарифов пока выключен.'
          : (msg || 'Не удалось открыть оплату. Проверьте настройки Stripe.'),
      };
      render();
    }
  };
  document.querySelectorAll('[data-upgrade]').forEach((btn) => btn.onclick = () => checkoutSubscription(btn.dataset.upgrade));

  const portalBtn = document.querySelector('[data-portal]');
  if (portalBtn) portalBtn.onclick = async () => {
    try {
      const r = await api('/api/billing/portal', { method: 'POST', body: '{}' });
      location.href = r.portal_url;
    } catch (e) {
      const msg = String(e?.message || '');
      const stripeConfigError = /stripe.+not configured|stripe customer is not linked/i.test(msg);
      state.notice = {
        type: 'error',
        text: stripeConfigError
          ? 'Портал подписки недоступен: Stripe не подключен.'
          : (msg || 'Не удалось открыть портал подписки. Проверьте настройки Stripe.'),
      };
      render();
    }
  };

  const saveProfileBtn = document.getElementById('saveProfileBtn'); if (saveProfileBtn) saveProfileBtn.onclick = async () => { await api('/api/settings/profile', { method: 'PATCH', body: JSON.stringify({ email: document.getElementById('profileEmail').value.trim() }) }); state.notice = { type: 'ok', text: 'РџСЂРѕС„РёР»СЊ РѕР±РЅРѕРІР»С‘РЅ.' }; await loadBase(); render(); };
  const savePassBtn = document.getElementById('savePassBtn'); if (savePassBtn) savePassBtn.onclick = async () => { await api('/api/settings/password', { method: 'POST', body: JSON.stringify({ current_password: document.getElementById('curPass').value, new_password: document.getElementById('newPass').value }) }); state.notice = { type: 'ok', text: 'РџР°СЂРѕР»СЊ РѕР±РЅРѕРІР»С‘РЅ.' }; render(); };

  const adminUsersBtn = document.getElementById('adminUsersBtn'); if (adminUsersBtn) adminUsersBtn.onclick = async () => { state.adminUsers = await api('/api/admin/users'); render(); };
  const adminSetPlanBtn = document.getElementById('adminSetPlanBtn'); if (adminSetPlanBtn) adminSetPlanBtn.onclick = async () => { const uid = document.getElementById('adminUserId').value; await api(`/api/admin/users/${uid}/plan`, { method: 'PATCH', body: JSON.stringify({ plan: document.getElementById('adminPlan').value }) }); state.adminUsers = await api('/api/admin/users'); render(); };
  const adminCreditsBtn = document.getElementById('adminCreditsBtn'); if (adminCreditsBtn) adminCreditsBtn.onclick = async () => { const uid = document.getElementById('adminUserId').value; await api(`/api/admin/users/${uid}/credits`, { method: 'PATCH', body: JSON.stringify({ delta: Number(document.getElementById('adminDelta').value || 0) }) }); state.adminUsers = await api('/api/admin/users'); render(); };
  const adminRevenueBtn = document.getElementById('adminRevenueBtn'); if (adminRevenueBtn) adminRevenueBtn.onclick = async () => { state.adminRevenue = await api('/api/admin/revenue'); render(); };
  const adminGenBlogBtn = document.getElementById('adminGenBlogBtn'); if (adminGenBlogBtn) adminGenBlogBtn.onclick = async () => { await api('/api/admin/blog/generate', { method: 'POST', body: '{}' }); render(); };
  const adminRunPlanBtn = document.getElementById('adminRunPlanBtn'); if (adminRunPlanBtn) adminRunPlanBtn.onclick = async () => { await api('/api/content-plan/run-due', { method: 'POST', body: '{}' }); render(); };

  const ytGenerateVideoBtn = document.getElementById('ytGenerateVideoBtn');
  if (ytGenerateVideoBtn) ytGenerateVideoBtn.onclick = async () => {
    try {
      const y = state.youtubeStudio || {};
      y.projectId = (document.getElementById('ytProject')?.value || '').trim();
      y.topic = (document.getElementById('ytTopic')?.value || '').trim();
      y.videoType = (document.getElementById('ytVideoType')?.value || 'short').trim();
      y.durationSeconds = Number(document.getElementById('ytDuration')?.value || (y.videoType === 'short' ? 45 : 180));
      y.language = (document.getElementById('ytLang')?.value || 'ru').trim();
      y.tone = (document.getElementById('ytTone')?.value || 'expert').trim();
      y.style = (document.getElementById('ytStyle')?.value || 'educational').trim();
      y.audience = (document.getElementById('ytAudience')?.value || '').trim();
      y.goal = (document.getElementById('ytGoal')?.value || 'engagement').trim();
      if (!y.topic) throw new Error('Укажите тему ролика.');
      const shortMode = y.videoType === 'short';
      const minLen = shortMode ? 15 : 120;
      const maxLen = shortMode ? 70 : 480;
      y.durationSeconds = Math.max(minLen, Math.min(maxLen, Number(y.durationSeconds) || minLen));
      y.loadingVideo = true;
      state.youtubeStudio = y;
      render();
      const payload = {
        project_id: y.projectId ? Number(y.projectId) : null,
        topic: y.topic,
        video_type: y.videoType,
        duration_seconds: y.durationSeconds,
        language: y.language,
        tone: y.tone,
        style: y.style,
        audience: y.audience,
        goal: y.goal,
      };
      const result = await api('/api/youtube/generate-video', { method: 'POST', body: JSON.stringify(payload) });
      y.videoResult = result;
      y.loadingVideo = false;
      state.notice = { type: 'ok', text: `YouTube-пакет готов. Примерное время генерации: ${result.estimated_wait_seconds || '—'} сек.` };
      state.youtubeStudio = y;
      render();
    } catch (e) {
      state.youtubeStudio.loadingVideo = false;
      state.notice = { type: 'error', text: e.message || 'Ошибка генерации YouTube-видео.' };
      render();
    }
  };

  const ytGeneratePostBtn = document.getElementById('ytGeneratePostBtn');
  if (ytGeneratePostBtn) ytGeneratePostBtn.onclick = async () => {
    try {
      const y = state.youtubeStudio || {};
      y.projectId = (document.getElementById('ytProject')?.value || '').trim();
      y.topic = (document.getElementById('ytTopic')?.value || '').trim();
      y.postKind = (document.getElementById('ytPostKind')?.value || 'community').trim();
      y.language = (document.getElementById('ytLang')?.value || 'ru').trim();
      y.tone = (document.getElementById('ytTone')?.value || 'expert').trim();
      if (!y.topic) throw new Error('Укажите тему для YouTube-поста.');
      y.loadingPost = true;
      state.youtubeStudio = y;
      render();
      const result = await api('/api/youtube/generate-post', {
        method: 'POST',
        body: JSON.stringify({
          project_id: y.projectId ? Number(y.projectId) : null,
          topic: y.topic,
          post_kind: y.postKind,
          language: y.language,
          tone: y.tone,
        }),
      });
      y.postResult = result;
      y.loadingPost = false;
      state.notice = { type: 'ok', text: `YouTube-пост создан: #${result.id}.` };
      state.youtubeStudio = y;
      render();
    } catch (e) {
      state.youtubeStudio.loadingPost = false;
      state.notice = { type: 'error', text: e.message || 'Ошибка генерации YouTube-поста.' };
      render();
    }
  };
}

async function render() {
  const currentRender = ++renderVersion;
  let path = location.pathname.replace(/\/$/, '') || '/';
  const query = new URLSearchParams(location.search);
  const clearResolvedLoadNotice = () => {
    const text = String(state.notice?.text || '').trim();
    if (!text) return;
    if (
      text.includes('Ошибка сервера (500). Повторите позже.') ||
      text.includes('Не удалось загрузить данные страницы. Попробуйте еще раз.') ||
      text.includes('Ошибка доступа к данным страницы. Обновите страницу.')
    ) {
      state.notice = null;
    }
  };
  if (path === '/') { history.replaceState({}, '', state.token ? '/dashboard' : '/login'); path = location.pathname.replace(/\/$/, '') || '/'; }
  if (path === '/login') {
    if (!state.authProviders) await loadAuthProviders();
    const oauthToken = query.get('oauth_token');
    const oauthError = query.get('oauth_error');

    if (oauthToken) {
      state.token = oauthToken;
      localStorage.setItem('token', oauthToken);
      try {
        await loadBase();
        state.notice = { type: 'ok', text: 'Вход выполнен успешно.' };
        history.replaceState({}, '', '/dashboard');
        path = '/dashboard';
      } catch {
        state.token = '';
        localStorage.removeItem('token');
        state.notice = { type: 'error', text: 'Не удалось выполнить вход. Попробуйте снова.' };
        history.replaceState({}, '', '/login');
        path = '/login';
      }
    } else if (oauthError) {
      state.notice = { type: 'error', text: 'Социальный вход временно недоступен. Используйте email и пароль.' };
      history.replaceState({}, '', '/login');
      path = '/login';
    }
  }
  if (isAuthRoute(path) && !state.token) { history.replaceState({}, '', '/login'); path = '/login'; }
  if (path === '/connections') {
    const err = query.get('error');
    const msg = query.get('message');
    const status = query.get('status');
    const ytErr = query.get('youtube_error');
    const ytMsg = query.get('message');
    if (query.get('connected') === '1') {
      state.notice = { type: 'ok', text: '\u0410\u043a\u043a\u0430\u0443\u043d\u0442 Facebook/Instagram \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d.' };
      history.replaceState({}, '', '/connections');
    } else if (query.get('youtube_connected') === '1') {
      state.notice = { type: 'ok', text: 'YouTube канал подключен.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'oauth_denied') {
      state.notice = { type: 'error', text: 'Вы отменили подключение Google/YouTube.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'state_invalid') {
      state.notice = { type: 'error', text: 'Сессия подключения YouTube устарела. Запустите подключение снова.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'missing_code') {
      state.notice = { type: 'error', text: 'Google не вернул код авторизации для YouTube.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'google_not_configured') {
      state.notice = { type: 'error', text: 'Google OAuth для YouTube не настроен.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'token_exchange_failed' || ytErr === 'token_missing') {
      state.notice = { type: 'error', text: 'Не удалось получить токен Google для YouTube.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'youtube_api_not_enabled') {
      state.notice = { type: 'error', text: ytMsg ? `YouTube Data API не включен: ${ytMsg}` : 'YouTube Data API v3 не включен в Google Cloud проекте.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'youtube_api_failed') {
      state.notice = { type: 'error', text: ytMsg ? `YouTube API: ${ytMsg}` : 'YouTube API вернул ошибку при чтении канала.' };
      history.replaceState({}, '', '/connections');
    } else if (ytErr === 'no_channel') {
      state.notice = { type: 'error', text: ytMsg || 'В выбранном Google-аккаунте не найден YouTube-канал.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'state_invalid') {
      state.notice = { type: 'error', text: '\u041e\u0448\u0438\u0431\u043a\u0430 OAuth state. \u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u0441\u043d\u043e\u0432\u0430 \u0438\u0437 \u043f\u0430\u043d\u0435\u043b\u0438.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'oauth_denied') {
      state.notice = { type: 'error', text: '\u0412\u044b \u043e\u0442\u043c\u0435\u043d\u0438\u043b\u0438 \u0434\u043e\u0441\u0442\u0443\u043f Facebook. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435.' };
      history.replaceState({}, '', '/connections');
    } else if (err === 'token_exchange_failed') {
      let text = '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0442\u043e\u043a\u0435\u043d Facebook. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 FB_APP_ID/FB_APP_SECRET \u0438 Redirect URI.';
      if (status) text += ` (HTTP ${status})`;
      if (msg) text += `: ${msg}`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'no_pages') {
      let text = '\u0423 \u044d\u0442\u043e\u0433\u043e Facebook-\u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u0421\u0442\u0440\u0430\u043d\u0438\u0446. \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0441 \u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0435\u0439.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'no_ig_business') {
      let text = '\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0430 Facebook \u043d\u0430\u0439\u0434\u0435\u043d\u0430, \u043d\u043e \u043d\u0435\u0442 Instagram Business. \u041f\u0440\u0438\u0432\u044f\u0436\u0438\u0442\u0435 IG Business \u043a \u0421\u0442\u0440\u0430\u043d\u0438\u0446\u0435.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    } else if (err === 'meta_api_error') {
      let text = '\u041e\u0448\u0438\u0431\u043a\u0430 Meta API. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 permissions \u0432 Meta Developers.';
      if (msg) text += ` (${msg})`;
      state.notice = { type: 'error', text };
      history.replaceState({}, '', '/connections');
    }
  }
  if (path === '/billing') {
    if (query.get('success') === '1') {
      state.notice = { type: 'ok', text: 'Оплата прошла успешно. Тариф обновится после подтверждения Stripe.' };
      history.replaceState({}, '', '/billing');
    } else if (query.get('cancel') === '1') {
      state.notice = { type: 'error', text: 'Оплата отменена. Тариф не изменен.' };
      history.replaceState({}, '', '/billing');
    }
  }
  try {
    if (isAuthRoute(path)) {
      await loadBase();
      await preload(path);
      clearResolvedLoadNotice();
    } else if (path === '/blog') {
      await preload(path);
    }
  } catch (e) {
    if (path === '/blog') {
      state.notice = { type: 'error', text: 'Не удалось загрузить статьи блога.' };
    } else if (Number(e?.status || 0) === 401 || Number(e?.status || 0) === 403) {
      let sessionAlive = false;
      try {
        await loadBase();
        sessionAlive = true;
      } catch {
        sessionAlive = false;
      }
      if (!sessionAlive) {
        state.token = '';
        localStorage.removeItem('token');
        history.replaceState({}, '', '/login');
        path = '/login';
        state.notice = { type: 'error', text: 'Сессия истекла. Войдите снова.' };
      } else {
        const details = (e?.message || '').trim();
        state.notice = { type: 'error', text: details || 'Ошибка доступа к данным страницы. Обновите страницу.' };
      }
    } else {
      const fallback = 'Не удалось загрузить данные страницы. Попробуйте еще раз.';
      state.notice = { type: 'error', text: e?.message || fallback };
    }
  }
  if (currentRender !== renderVersion) return;
  document.body.setAttribute('data-route', path);
  document.getElementById('app').innerHTML = decodeMojibake(page(path));
  if (currentRender !== renderVersion) return;
  await bind(path);
}

window.addEventListener('popstate', () => render());
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-link]');
  if (!el) return;
  e.preventDefault();
  e.stopPropagation();
  nav(el.getAttribute('data-link'));
});
loadAiWizardDraft();
render();














