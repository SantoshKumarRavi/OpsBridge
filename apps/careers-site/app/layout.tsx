import type { Metadata } from 'next';
import './style.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3002'),
  title: { default: 'Careers at OpsBridge', template: '%s · OpsBridge Careers' },
  description: 'Build safer, clearer onboarding workflows with the OpsBridge team.',
  openGraph: { title: 'Careers at OpsBridge', description: 'Roles in product engineering and operations.', type: 'website' },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
