import React from 'react';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ToastProvider } from './components/Toast';
import { EmptyState } from './components/ui';
import { AuditTrail } from './pages/AuditTrail';
import { Authorization } from './pages/Authorization';
import { Catalog } from './pages/Catalog';
import { Dashboard } from './pages/Dashboard';
import { Mandates } from './pages/Mandates';
import { ShoppingAssistant } from './pages/ShoppingAssistant';
import { Transactions } from './pages/Transactions';

const NotFound: React.FC = () => (
  <EmptyState
    title="Page not found"
    description="That address does not exist in PACT."
    action={
      <Link to="/" className="text-sm font-medium text-accent hover:underline">
        Back to the Command Center
      </Link>
    }
  />
);

export const App: React.FC = () => (
  <ToastProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="assistant" element={<ShoppingAssistant />} />
          <Route path="mandates" element={<Mandates />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="proposals/:id" element={<Authorization />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="catalog" element={<Catalog />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </ToastProvider>
);

export default App;
