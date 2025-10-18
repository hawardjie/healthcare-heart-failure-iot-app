import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Heart Failure IoT Dashboard',
  description: 'Real-time monitoring dashboard for CardioMEMS HF devices',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
