// src/components/FAQ.jsx
import React from 'react'

const faqItems = [
  {
    question: 'Нужно ли мне что-то писать самому?',
    answer: 'Нет. GPT-4 сам генерирует текст постов на основе выбранной вами тематики.',
  },
  {
    question: 'Как подбираются изображения?',
    answer: 'Сервис использует Pexels API — изображения подбираются автоматически по теме поста.',
  },
  {
    question: 'Я могу выбрать, когда публикуются посты?',
    answer: 'Да, по умолчанию посты выходят в 09:00, но можно изменить это в настройках.',
  },
  {
    question: 'Могу ли я использовать это для нескольких страниц?',
    answer: 'Пока один аккаунт = одна страница, но мультиаккаунт в планах.',
  },
  {
    question: 'Что произойдет, если закончится подписка?',
    answer: 'Публикации остановятся, но все ваши данные сохранятся. Можно будет возобновить позже.',
  },
]

const FAQ = () => {
  return (
    <section id="faq" className="py-20 bg-white">
      <div className="max-w-4xl mx-auto px-4">
        <h2 className="text-3xl font-bold text-center mb-12">Часто задаваемые вопросы</h2>
        <div className="space-y-6">
          {faqItems.map((item, index) => (
            <div key={index} className="border-b pb-4">
              <h3 className="text-xl font-semibold mb-2">{item.question}</h3>
              <p className="text-gray-600">{item.answer}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default FAQ
