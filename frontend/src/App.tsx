import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { OwnerGate } from './components/OwnerGate';
import { ToastProvider } from './components/Toast';
import { EmptyState } from './components/ui';
import { Agents } from './pages/Agents';
import { AuditTrail } from './pages/AuditTrail';
import { Authorization } from './pages/Authorization';
import { Catalog } from './pages/Catalog';
import { Dashboard } from './pages/Dashboard';
import { Mandates } from './pages/Mandates';
import { ShoppingAssistant } from './pages/ShoppingAssistant';
import { Transactions } from './pages/Transactions';

const Analytics = lazy(() => import('./pages/Analytics'));

const NotFound: React.FC = () => (
  <EmptyState
    title="Page not found"
    description="That address does not exist in PACT."
    action={
      <Link to="/" className="text-sm font-medium text-accent hover:underline">
        Back to the Control Center
      </Link>
    }
  />
);

export const App: React.FC = () => (
  <ToastProvider>
    <BrowserRouter>
      <OwnerGate>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="assistant" element={<ShoppingAssistant />} />
          <Route path="mandates" element={<Mandates />} />
          <Route path="agents" element={<Agents />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="proposals/:id" element={<Authorization />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="catalog" element={<Catalog />} />
          <Route path="analytics" element={<Suspense fallback={null}><Analytics /></Suspense>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      </OwnerGate>
    </BrowserRouter>
  </ToastProvider>
);

export default App;
