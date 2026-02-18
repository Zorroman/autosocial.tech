// src/components/HeroSection.jsx
import React from 'react'

const HeroSection = () => {
  return (
    <section className="bg-gradient-to-br from-blue-600 to-purple-700 text-white py-24 px-6 text-center">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-5xl font-bold mb-6">GPT-бот, который ведёт ваш Instagram</h1>
        <p className="text-lg mb-8">
          AutoSocial GPT генерирует и публикует посты с помощью нейросети. Просто выбери нишу и расслабься.
        </p>

        <a
          href="https://www.facebook.com/v18.0/dialog/oauth?client_id=9696886733725672&redirect_uri=http://localhost:5000/auth/callback&scope=pages_show_list,pages_manage_posts,instagram_basic,instagram_content_publish"
          className="bg-white text-blue-700 font-semibold px-8 py-3 rounded shadow hover:bg-gray-100 transition"
        >
          🔗 Подключить Facebook
        </a>
      </div>
    </section>
  )
}

export default HeroSection
