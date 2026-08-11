import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ATE Financial Desk | Autonomous Trading Engine',
  description: 'Institutional Grade Autonomous Trading Engine powered by Multi-AI & MT5',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <meta name="theme-color" content="#020305" />
        <meta name="color-scheme" content="dark" />
      </head>
      <body style={{
        margin: 0,
        padding: 0,
        backgroundColor: '#020305',
        color: '#f1f5f9',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: 'hidden',
      }}>
        {children}
      </body>
    </html>
  );
}
