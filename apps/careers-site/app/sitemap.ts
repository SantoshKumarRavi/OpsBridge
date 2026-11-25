import type { MetadataRoute } from 'next';
import { jobs } from './jobs/data';

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3002';
  return [
    { url: origin, changeFrequency: 'weekly', priority: 1 },
    ...jobs.map((job) => ({ url: `${origin}/jobs/${job.id}`, changeFrequency: 'weekly' as const, priority: 0.7 })),
  ];
}
