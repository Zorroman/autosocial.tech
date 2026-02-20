const test = require("node:test");
const assert = require("node:assert/strict");
const {
  mapWizardStateToExistingPayload,
  generateWizardPreview,
} = require("../../frontend/wizard_utils.js");

test("mapWizardStateToExistingPayload keeps existing backend contract only", () => {
  const payload = mapWizardStateToExistingPayload({
    project_id: "42",
    business_type: "  SaaS / IT ",
    niche: "  SMM ",
    goal: " Лиды ",
    language: " ru ",
    tone: "Экспертный",
    outputs: { plan7: true },
    product_summary: "test",
  });

  assert.deepEqual(payload, {
    project_id: 42,
    business_type: "SaaS / IT",
    niche: "SMM",
    goal: "Лиды",
    language: "ru",
  });
});

test("generateWizardPreview returns stable local preview fields", () => {
  const preview = generateWizardPreview({
    niche: "Автосервис",
    goal: "Продажи",
    tone: "Продающий",
    product_summary: "диагностику и ремонт",
  });

  assert.ok(preview.weeklyTopic.includes("Автосервис"));
  assert.ok(preview.samplePost.includes("диагностику и ремонт"));
  assert.equal(typeof preview.focusHint, "string");
  assert.deepEqual(preview.strategyMix, { expert: 25, nurture: 25, sales: 50 });
});
