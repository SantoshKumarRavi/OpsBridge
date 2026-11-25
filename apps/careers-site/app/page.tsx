import Link from 'next/link';
import { jobs } from './jobs/data';

export default function Home() {
  return <main className="wrap"><nav><b>◈ OPSBRIDGE</b><Link href="#roles">Open roles</Link></nav>
    <section className="hero"><span className="eyebrow">CAREERS · BUILD WITH CARE</span><h1>Make everyday work clearer and safer.</h1><p>Join a team building onboarding and compliance tools that keep people in control.</p><a className="button" href="#roles">Explore open roles</a></section>
    <section id="roles"><div className="section-head"><div><span className="eyebrow">OPPORTUNITIES</span><h2>Open roles</h2></div><span>{jobs.length} positions</span></div>
      <div className="roles">{jobs.map((job) => <article className="role" key={job.id}><div><span className="eyebrow">{job.team} · {job.type}</span><h3><Link href={`/jobs/${job.id}`}>{job.title}</Link></h3><p>{job.summary}</p><small>{job.location}</small></div><Link aria-label={`View ${job.title}`} className="arrow" href={`/jobs/${job.id}`}>→</Link></article>)}</div>
    </section><footer>OpsBridge · Example public careers experience for the portfolio project.</footer>
  </main>;
}
