import React from 'react'
import HeroSection from './components/HeroSection'
import PlatformFeatures from './components/PlatformFeatures'
import HowItWorks from './components/HowItWorks'
import Pricing from './components/Pricing'
import FAQ from './components/FAQ'
import './index.css'

function App() {
  return (
    <div className="bg-white text-gray-900 font-sans">
      <HeroSection />
      <main>
        <PlatformFeatures />
        <HowItWorks />
        <Pricing />
        <FAQ />
      </main>
      <footer className="text-center py-6 border-t mt-10 text-sm text-gray-500">
        © {new Date().getFullYear()} AutoSocial GPT — All rights reserved
      </footer>
    </div>
  )
}

export default App
