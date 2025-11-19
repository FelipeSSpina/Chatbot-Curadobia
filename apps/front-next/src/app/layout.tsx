// src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import { Poppins } from "next/font/google";
import ChatWidget from "@/components/ChatWidget";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "BIA - Curadobia",
  description: "Atendimento com identidade visual própria",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-br">
      <head>
        <link rel="stylesheet" href="https://www.curadobia.com.br/css/common-store-vendor.css" />
        <link rel="stylesheet" href="https://www.curadobia.com.br/css/common.css" />
        <link rel="stylesheet" href="https://www.curadobia.com.br/css/common-themes-area.css" />
        <link rel="stylesheet" href="https://www.curadobia.com.br/assets/themes/curadobia/css/store-common.css?v=1.118.20-curadobia.3" />
        <link rel="stylesheet" href="https://www.curadobia.com.br/assets/themes/curadobia/css/store-desk.css?v=1.118.20-curadobia.3" />
      </head>
      <body className={`${poppins.className} antialiased bg-white`}>
        {children}
        {/* ÚNICA instância do chat */}
        <ChatWidget />
      </body>
    </html>
  );
}
