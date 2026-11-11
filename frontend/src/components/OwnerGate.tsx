import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { KeyRound, LogOut, ShieldAlert } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import type { OwnerSession } from '../types';
import { Logo } from './Layout';
import { Button, Card, Field, inputClass } from './ui';

const OwnerContext = createContext<{ session: OwnerSession | null; signOut: () => Promise<void> }>({
  session: null,
  signOut: async () => undefined,
});

export const useOwner = () => useContext(OwnerContext);

/** Shows the Control Center only to the owner when the server has owner sign-in turned on. */
export const OwnerGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<OwnerSession | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSession(await pactApi.getOwnerSession());
    } catch {
      // Backend unreachable: let the app render its own "API unreachable" states.
      setSession({ auth_enabled: false, authenticated: true, misconfigured: false });
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onAuth = () => void refresh();
    window.addEventListener('pact:owner-auth', onAuth);
    return () => window.removeEventListener('pact:owner-auth', onAuth);
  }, [refresh]);

  const signOut = useCallback(async () => {
    await pactApi.ownerLogout().catch(() => undefined);
    setPassword('');
    await refresh();
  }, [refresh]);

  if (!session) return null;
  if (session.authenticated) return <OwnerContext.Provider value={{ session, signOut }}>{children}</OwnerContext.Provider>;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSession(await pactApi.ownerLogin(password));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm p-6 animate-rise">
        <div className="flex items-center gap-3">
          <Logo />
          <div>
            <p className="text-[15px] font-semibold leading-none text-fg">PACT Control Center</p>
            <p className="mt-1 text-[11px] text-faint">Authorization Gateway</p>
          </div>
        </div>
        {session.misconfigured ? (
          <div className="mt-6 flex gap-3 rounded-lg border border-bad/30 bg-bad/[0.07] p-3 text-xs leading-relaxed text-bad">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            Owner sign-in is required on this deployment, but no owner password is configured on the server. Owner actions are disabled until
            OWNER_PASSWORD is set.
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <p className="text-sm text-muted">Only the owner can approve purchases, edit mandates and manage agents. AI agents use their own keys.</p>
            <Field label="Owner password" error={error}>
              {(id) => (
                <input id={id} type="password" autoComplete="current-password" className={inputClass} value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
              )}
            </Field>
            <Button type="submit" loading={busy} disabled={!password} className="w-full" icon={<KeyRound className="h-4 w-4" />}>
              Sign in
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
};

export const SignOutButton: React.FC = () => {
  const { session, signOut } = useOwner();
  if (!session?.auth_enabled) return null;
  return (
    <button onClick={() => void signOut()} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[12px] text-muted hover:bg-white/[0.04] hover:text-fg">
      <LogOut className="h-3.5 w-3.5" /> Sign out
    </button>
  );
};
