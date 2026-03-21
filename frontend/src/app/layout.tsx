import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EDI Parser",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui", margin: 20, maxWidth: 800 }}>
        {children}
      </body>
    </html>
  );
}
