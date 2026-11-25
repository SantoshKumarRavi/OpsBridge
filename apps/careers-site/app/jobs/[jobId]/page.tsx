import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { jobs } from '../data';

export function generateStaticParams() { return jobs.map(({ id }) => ({ jobId: id })); }

export async function generateMetadata({ params }: { params: Promise<{ jobId: string }> }): Promise<Metadata> {
  const { jobId } = await params;
  const job = jobs.find((item) => item.id === jobId);
  return job ? { title: job.title, description: job.summary, openGraph: { title: job.title, description: job.summary, type: 'article' } } : {};
}

export default async function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const job = jobs.find((item) => item.id === jobId);
  if (!job) notFound();
  const structuredData = { '@context': 'https://schema.org', '@type': 'JobPosting', title: job.title, description: job.summary, employmentType: 'FULL_TIME', hiringOrganization: { '@type': 'Organization', name: 'OpsBridge' }, jobLocationType: job.location.startsWith('Remote') ? 'TELECOMMUTE' : undefined };
  return <main className="wrap detail"><Link href="/">← All roles</Link><span className="eyebrow">{job.team} · {job.location} · {job.type}</span><h1>{job.title}</h1><p>{job.summary}</p><h2>What you will work on</h2><ul><li>Deliver an end-to-end workflow with clear ownership and audit history.</li><li>Build resilient services and accessible product experiences.</li><li>Work with product and operations teams to turn real needs into useful software.</li></ul><a className="button" href="mailto:careers@example.invalid?subject=OpsBridge%20role">Apply by email</a><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} /></main>;
}
