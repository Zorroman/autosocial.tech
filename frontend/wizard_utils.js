(function (global) {
  function normalizeText(value) {
    return String(value || "").trim();
  }

  function normalizeGoalKey(goal) {
    const g = normalizeText(goal).toLowerCase();
    if (g === "лиды") return "leads";
    if (g === "продажи") return "sales";
    if (g === "бренд") return "brand";
    return "reach";
  }

  function goalMix(goal) {
    const key = normalizeGoalKey(goal);
    if (key === "sales") return { expert: 25, nurture: 25, sales: 50 };
    if (key === "leads") return { expert: 35, nurture: 30, sales: 35 };
    if (key === "brand") return { expert: 40, nurture: 45, sales: 15 };
    return { expert: 45, nurture: 35, sales: 20 };
  }

  function toneHint(tone) {
    const t = normalizeText(tone).toLowerCase();
    if (t === "экспертный") return "Давайте факты, примеры и короткие чек-листы.";
    if (t === "продающий") return "Фокус на выгоде и понятном CTA в конце поста.";
    if (t === "провокационный") return "Начинайте с сильного хука и контраста мнений.";
    return "Пишите простым языком и добавляйте дружелюбные призывы.";
  }

  function mapWizardStateToExistingPayload(state) {
    const w = state || {};

    // Keep backend contract stable for /api/ai-smm-manager/start.
    // TODO(backend-v3): extend API schema to support tone, outputs and product_summary explicitly.
    return {
      project_id: w.project_id ? Number(w.project_id) : null,
      business_type: normalizeText(w.business_type),
      niche: normalizeText(w.niche),
      goal: normalizeText(w.goal),
      language: normalizeText(w.language || "ru"),
    };
  }

  function generateWizardPreview(state) {
    const w = state || {};
    const niche = normalizeText(w.niche) || "ваша ниша";
    const goal = normalizeText(w.goal) || "Охваты";
    const tone = normalizeText(w.tone) || "Дружелюбный";
    const product = normalizeText(w.product_summary) || "ваш продукт";
    const mix = goalMix(goal);

    return {
      weeklyTopic: `Неделя 1: «${niche} — практические советы и кейсы под цель ${goal}»`,
      samplePost: `Клиенты выбирают ${product}, когда видят конкретную пользу. Разберём 3 шага, как получить результат в направлении «${goal}» без лишних затрат.`,
      strategyMix: mix,
      focusHint: `Рекомендуемый фокус: ${niche} + ${goal}. ${toneHint(tone)}`,
    };
  }

  var api = {
    mapWizardStateToExistingPayload: mapWizardStateToExistingPayload,
    generateWizardPreview: generateWizardPreview,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.WizardUtils = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
