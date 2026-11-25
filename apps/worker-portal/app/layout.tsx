import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Worker onboarding · OpsBridge', description: 'Secure worker onboarding portal' };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
