/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#003366",
          80: "#1A4D80",
          60: "#336699",
          30: "#99BBDD",
          10: "#E0EAF4",
        },
        gold: {
          DEFAULT: "#C8982A",
          light: "#E8C46A",
        },
        opb: {
          dark: "#1C1C2E",
          mid: "#6B7280",
          light: "#F4F6F9",
        },
        sev: {
          red:    "#E03448",
          redbg:  "#FDEAEA",
          redtxt: "#7A1020",
          org:    "#F07020",
          orgbg:  "#FEF0E6",
          orgtxt: "#7A3800",
          grn:    "#27B97C",
          grnbg:  "#E0F7EF",
          grntxt: "#0D5C3A",
          pur:    "#7C4DBD",
          purbg:  "#F0EBF9",
          purtxt: "#3D1F70",
        },
      },
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        body: ['"Plus Jakarta Sans"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
