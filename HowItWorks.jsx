// src/components/HowItWorks.jsx
import React from 'react'

const steps = [
  {
    step: '1',
    title: 'Подключите Facebook/Instagram',
    description: 'Авторизуйтесь через Meta OAuth и выберите страницу, на которую хотите постить.',
    icon: '🔗',
  },
  {
    step: '2',
    title: 'Выберите нишу',
    description: 'Укажите тематику постов (бьюти, маркетинг, фитнес и т.д.) — GPT всё сделает сам.',
    icon: '🎨',
  },
  {
    step: '3',
    title: 'Получайте посты каждый день',
    description: 'Текст + картинка публикуются автоматически по расписанию — вы отдыхаете.',
    icon: '📅',
  },
]

const HowItWorks = () => {
  return (
    <section id="how" className="py-20 bg-white">
      <div className="max-w-6xl mx-auto px-4 text-center">
        <h2 className="text-3xl font-bold mb-12">Как это работает?</h2>
        <div className="grid md:grid-cols-3 gap-10">
          {steps.map((step, index) => (
            <div
              key={index}
              className="bg-gray-50 p-6 rounded-lg shadow hover:shadow-md transition duration-300"
            >
              <div className="text-5xl mb-4">{step.icon}</div>
              <h3 className="text-xl font-semibold mb-2">{step.title}</h3>
              <p className="text-gray-600">{step.description}</p>
              <span className="inline-block mt-4 px-4 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                Шаг {step.step}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default HowItWorks
