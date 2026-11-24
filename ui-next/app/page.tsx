import type { Metadata } from "next";
import { Inter } from "next/font/google";
import LandingPage from "../components/landing/LandingPage";
import "./landing.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "THE FLOOR — Hire the company, not the chatbot",
  description:
    "Every role in your business staffed by AI employees who bid for work, get reviewed, draw pay — and get fired when they lose you money.",
};

export default function Page() {
  return (
    <div className={inter.variable}>
      <LandingPage />
    </div>
  );
}
