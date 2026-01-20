import React from 'react';
import NewsSearch from './components/NewsSearch';

/**
 * Main App component.
 * 
 * @returns {JSX.Element} The rendered App component
 */
function App() {
  return (
    <div className="min-h-screen text-white flex flex-col relative overflow-hidden" style={{ background: 'radial-gradient(circle at center, #0f172a 0%, #000000 100%)' }}>
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-4">
        <NewsSearch />
      </div>
    </div>
  );
}

export default App;

