import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Mandates } from './pages/Mandates';
import { ShoppingAssistant } from './pages/ShoppingAssistant';
import { Transactions } from './pages/Transactions';
import { AuditTrail } from './pages/AuditTrail';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="mandates" element={<Mandates />} />
          <Route path="assistant" element={<ShoppingAssistant />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="audit" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
