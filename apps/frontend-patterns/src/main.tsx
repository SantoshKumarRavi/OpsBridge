import React, { createContext, lazy, memo, Suspense, useCallback, useContext, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { configureStore, createSlice } from '@reduxjs/toolkit';
import { Provider, useDispatch, useSelector } from 'react-redux';
import { Box, Button, Card, CardContent, Chip, Divider, Typography } from '@mui/material';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles.css';

const reviewSlice = createSlice({
  name: 'reviewQueue',
  initialState: { simulatedReviews: 0 },
  reducers: {
    reviewCompleted(state) { state.simulatedReviews += 1; },
    reviewReverted(state) { state.simulatedReviews = Math.max(0, state.simulatedReviews - 1); },
  },
});
const store = configureStore({ reducer: { reviewQueue: reviewSlice.reducer } });
type RootState = ReturnType<typeof store.getState>;
const DensityContext = createContext<'comfortable' | 'compact'>('comfortable');
const LazyPolicyPanel = lazy(() => import('./policy-panel'));

const MemoizedHint = memo(function MemoizedHint({ text }: { text: string }) {
  return <p className="hint">{text}</p>;
});

function ReduxWorkflowDemo() {
  const count = useSelector((state: RootState) => state.reviewQueue.simulatedReviews);
  const dispatch = useDispatch<typeof store.dispatch>();
  return <div className="card border-0 shadow-sm"><div className="card-body">
    <h2 className="h5">Redux Toolkit · review queue state</h2>
    <p>Local training counter: <strong>{count}</strong></p>
    <button className="btn btn-success me-2" onClick={() => dispatch(reviewSlice.actions.reviewCompleted())}>Complete mock review</button>
    <button className="btn btn-outline-secondary" onClick={() => dispatch(reviewSlice.actions.reviewReverted())}>Undo</button>
  </div></div>;
}

function FilterDemo() {
  const [query, setQuery] = useState('');
  const sample = ['Submitted', 'Processing', 'Needs review', 'Approved', 'Changes requested'];
  const filtered = useMemo(() => sample.filter((item) => item.toLowerCase().includes(query.toLowerCase())), [query]);
  const changeQuery = useCallback((event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value), []);
  return <Card variant="outlined"><CardContent>
    <Typography variant="h6">MUI · memoized filtering</Typography>
    <Typography color="text.secondary" sx={{ mb: 2 }}>useMemo filters a larger list; useCallback keeps the input handler stable.</Typography>
    <input aria-label="Filter case states" className="form-control mb-3" value={query} onChange={changeQuery} placeholder="Filter statuses" />
    <Box display="flex" gap={1} flexWrap="wrap">{filtered.map((item) => <Chip key={item} label={item} color="success" variant="outlined" />)}</Box>
  </CardContent></Card>;
}

function ContextDemo() {
  const density = useContext(DensityContext);
  return <Card variant="outlined"><CardContent>
    <Typography variant="h6">Context API · shared UI preference</Typography>
    <Typography color="text.secondary">The nested panel reads “{density}” density without threading a prop through each layer.</Typography>
  </CardContent></Card>;
}

function App() {
  return <main className="container py-4 py-lg-5">
    <header className="d-flex flex-wrap justify-content-between align-items-end gap-3 mb-4">
      <div><span className="eyebrow">OPSBRIDGE LEARNING MICROFRONTEND</span><h1 className="display-6 fw-bold mt-2">Frontend patterns lab</h1><p className="text-secondary mb-0">Each panel isolates one UI toolkit or state-management approach.</p></div>
      <Chip label="Responsive · accessible labels · CSR" color="success" />
    </header>
    <section className="grid">
      <div className="tw-panel rounded-4 p-4 text-white shadow-sm"><span className="text-white-50 small">TAILWIND CSS</span><h2 className="h4 mt-2">Utility-driven layout</h2><p className="mb-0">This panel uses Tailwind utility classes; the rest of this lab keeps its own styling boundary.</p></div>
      <ReduxWorkflowDemo />
      <FilterDemo />
      <Card variant="outlined"><CardContent><Typography variant="h6">Component boundary</Typography><Divider sx={{ my: 1.5 }} /><MemoizedHint text="This small child uses React.memo. The sample focuses on the API and trade-offs; profile a real page before adding memoization everywhere." /><Button variant="contained" color="success" onClick={() => window.alert('Reusable component action')}>Reusable MUI action</Button></CardContent></Card>
      <ContextDemo />
      <Suspense fallback={<Card><CardContent>Loading optional policy panel…</CardContent></Card>}><LazyPolicyPanel /></Suspense>
    </section>
    <footer className="text-secondary small mt-4">Educational examples only. The production workflows stay in their existing frontends.</footer>
  </main>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><DensityContext.Provider value="comfortable"><Provider store={store}><App /></Provider></DensityContext.Provider></React.StrictMode>);
