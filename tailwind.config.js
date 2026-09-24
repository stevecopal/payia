/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "system-ui", "sans-serif"],
        display: ["Sora", "Manrope", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        white: "#FFFFFF",
        black: "#000000",
        /* Signature PAYIA : vert #00FA9A (400/600) */
        green: {
          50: "#EDFFF7",
          100: "#D5FFF1",
          200: "#AAFFDF",
          300: "#66FEC6",
          400: "#00FA9A",
          500: "#4DFBBA",
          600: "#00FA9A",
          700: "#00C47C",
          800: "#009A66",
          900: "#04784F",
          950: "#024A33",
        },
        "payia-green": {
          DEFAULT: "#00FA9A",
          50: "#EDFFF7",
          100: "#D5FFF1",
          200: "#AAFFDF",
          300: "#66FEC6",
          400: "#00FA9A",
          500: "#4DFBBA",
          600: "#00FA9A",
          700: "#00C47C",
          800: "#009A66",
          900: "#04784F",
          950: "#024A33",
        },
        /* Gris neutres (zinc) */
        gray: {
          50: "#FAFAFA",
          100: "#F4F4F5",
          200: "#E4E4E7",
          300: "#D4D4D8",
          400: "#A1A1AA",
          500: "#71717A",
          600: "#52525B",
          700: "#3F3F46",
          800: "#27272A",
          900: "#18181B",
          950: "#09090B",
        },
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out forwards",
        "slide-up": "slideUp 0.4s ease-out forwards",
        toast: "toast 0.4s ease-out forwards",
        "toast-exit": "toastExit 0.3s ease-in forwards",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        toast: {
          "0%": { opacity: "0", transform: "translateY(-100%)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        toastExit: {
          "0%": { opacity: "1", transform: "translateY(0)" },
          "100%": { opacity: "0", transform: "translateY(-100%)" },
        },
      },
    },
  },
  plugins: [],
};
