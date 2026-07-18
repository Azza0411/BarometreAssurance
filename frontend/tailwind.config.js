/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ey: {
          yellow: "#FFE600",
          dark:   "#2E2E38",
          grey:   "#747480",
          light:  "#F5F6F8",
          green:  "#2DB87C",
          red:    "#E8433A",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

