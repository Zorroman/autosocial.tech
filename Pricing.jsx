// src/components/Pricing.jsx
import React from 'react'

const plans = [
  {
    name: 'Free',
    price: '0€',
    features: [
      '1 пост в день',
      'GPT-контент',
      'Автоизображения',
      'Интеграция с Instagram/Facebook',
    ],
    cta: 'Начать бесплатно',
    highlight: false,
  },
  {
    name: 'Pro',
    price: '9€/мес',
    features: [
      '3 поста в день',
      'Приоритетная генерация',
      'Расширенная статистика',
      'Поддержка 24/7',
    ],
    cta: 'Оформить подписку',
    highlight: true,
  },
]

const Pricing = () => {
  return (
    <section id="pricing" className="py-20 bg-gray-100">
      <div className="max-w-6xl mx-auto px-4 text-center">
        <h2 className="text-3xl font-bold mb-12">Тарифы</h2>
        <div className="grid md:grid-cols-2 gap-8">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`rounded-lg p-6 shadow-md bg-white ${
                plan.highlight ? 'border-4 border-blue-500 scale-105' : 'border'
              } transition transform duration-300`}
            >
              <h3 className="text-2xl font-semibold mb-2">{plan.name}</h3>
              <p className="text-4xl font-bold mb-4">{plan.price}</p>
              <ul className="text-gray-700 text-left mb-6">
                {plan.features.map((feature, i) => (
                  <li key={i} className="mb-2">✅ {feature}</li>
                ))}
              </ul>
              <button className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 transition">
                {plan.cta}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default Pricing
