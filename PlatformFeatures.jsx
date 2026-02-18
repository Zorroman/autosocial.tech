// src/components/PlatformFeatures.jsx
import React from 'react'

const features = [
  {
    icon: '🧠',
    title: 'AI-копирайтер',
    description: 'GPT-4 создает уникальные посты на основе вашей ниши и стиля.',
  },
  {
    icon: '📸',
    title: 'Подбор изображений',
    description: 'Интеграция с Pexels API для автоматического подбора картинок.',
  },
  {
    icon: '📤',
    title: 'Автопостинг',
    description: 'Публикация в Instagram и Facebook через официальные API.',
  },
  {
    icon: '🕒',
    title: 'График публикаций',
    description: 'Автоматическое расписание постов каждый день в нужное время.',
  },
  {
    icon: '⚙️',
    title: 'Автоматизация 24/7',
    description: 'Всё работает на автопилоте. Вы отдыхаете — AI публикует.',
  },
  {
    icon: '🎯',
    title: 'Интуитивный интерфейс',
    description: 'Простой и понятный личный кабинет — максимум пользы без сложностей.',
  },
]

const PlatformFeatures = () => {
  return (
    <section id="platform" className="py-16 bg-gray-50">
      <div className="max-w-6xl mx-auto px-4">
        <h2 className="text-3xl font-bold text-center mb-10">Что умеет платформа?</h2>
        <div className="grid md:grid-cols-3 sm:grid-cols-2 grid-cols-1 gap-8">
          {features.map((feature, index) => (
            <div key={index} className="bg-white rounded-lg shadow-md p-6 hover:shadow-xl transition duration-300">
              <div className="text-4xl mb-3">{feature.icon}</div>
              <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
              <p className="text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default PlatformFeatures
