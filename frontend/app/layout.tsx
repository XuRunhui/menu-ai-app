import type { Metadata } from "next";
import "./globals.css";
import { AppProvider } from "@/context/AppContext";
import { AuthProvider } from "@/context/AuthContext";
import DemoGuide from "@/components/demo/DemoGuide";

export const metadata: Metadata = {
  title: "Menuist — AI Menu Guide",
  description: "Discover dishes, parse menus, and get AI-powered dining recommendations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-background text-foreground">
        <AuthProvider>
          <AppProvider>
            {children}
            <DemoGuide />
          </AppProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
