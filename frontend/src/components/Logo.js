import React from 'react';

/**
 * InfoSeek Logo component.
 * 
 * Displays the InfoSeek logo image.
 * 
 * @returns {JSX.Element} The rendered Logo component
 */
function Logo() {
  return (
    <div className="flex justify-center items-center mb-12">
      <img
        src="/infoseek_logo_long.png"
        alt="InfoSeek Logo"
        className="h-32 md:h-40 lg:h-48 w-auto max-w-4xl object-contain"
      />
    </div>
  );
}

export default Logo;

