import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  ShieldCheck,
  ShieldAlert,
  CheckCircle,
  Lock,
  Loader2,
  DollarSign,
  AlertOctagon,
  ExternalLink,
} from 'lucide-react';
import { ShoppingMessage, Mandate } from '../types';
import { pactApi } from '../api/pact';

export const ShoppingAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ShoppingMessage[]>([
    {
      id: 'msg-welcome',
      role: 'assistant',
      content:
        'Hello! I am your PACT Autonomous Shopping Assistant. Tell me what equipment, books, or peripherals you need. I will research the product catalog, formulate a purchase proposal, and submit it to the deterministic Guardian Policy Engine for strict validation.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [input, setInput] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [capturedProposals, setCapturedProposals] = useState<Record<string, { captured: boolean; captureId?: string; orderId?: string }>>({});
  const [processingPayment, setProcessingPayment] = useState<string | null>(null);
  const [paypalCheckoutInfo, setPaypalCheckoutInfo] = useState<Record<string, { orderId: string; approveUrl: string }>>({});
  const [mandates, setMandates] = useState<Mandate[]>([]);
  const [selectedMandateId, setSelectedMandateId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load live mandates on mount
  useEffect(() => {
    pactApi.getMandates()
      .then((data) => {
        if (data && data.length > 0) {
          setMandates(data);
          const active = data.find((m) => m.is_active) || data[0];
          setSelectedMandateId(active.id);
        }
      })
      .catch((err) => {
        console.error('Failed to load mandates from backend:', err);
      });
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isEvaluating]);

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || input;
    if (!text.trim()) return;

    if (!selectedMandateId) {
      alert('Please select an active spending mandate first.');
      return;
    }

    const userMsg: ShoppingMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setIsEvaluating(true);

    try {
      // Live backend call to generate recommendation and evaluate policy
      const res = await pactApi.generateProposal(text, selectedMandateId);
      const assistantMsg: ShoppingMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: res.message || res.proposal.ai_reasoning || 'Proposal generated and evaluated against mandate.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        proposal: res.proposal,
        policyResult: res.policy,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Backend request failed';
      const errorMsg: ShoppingMessage = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: `⚠️ Error from Guardian Backend: ${errorMessage}. Please ensure the FastAPI backend is running on port 8000.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsEvaluating(false);
    }
  };

  // Step 1: Human Approval + PayPal Checkout Order Creation
  const handleInitiatePayPal = async (proposalId: string) => {
    setProcessingPayment(proposalId);
    try {
      // 1. Approve proposal on backend (revalidates mandate and policies)
      await pactApi.approveProposal(proposalId);

      // 2. Create PayPal sandbox order with exact proposal details
      const orderRes = await pactApi.createPayPalOrder(proposalId);

      setPaypalCheckoutInfo((prev) => ({
        ...prev,
        [proposalId]: {
          orderId: orderRes.order_id,
          approveUrl: orderRes.approve_url,
        },
      }));

      // 3. Open PayPal sandbox checkout in a new window/tab
      if (orderRes.approve_url) {
        window.open(orderRes.approve_url, '_blank', 'noopener,noreferrer');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create PayPal order';
      alert(`PayPal Order Error: ${errorMessage}`);
    } finally {
      setProcessingPayment(null);
    }
  };

  // Step 2: Server-side Payment Capture
  const handleCapturePayPal = async (proposalId: string) => {
    setProcessingPayment(proposalId);
    try {
      const captureRes = await pactApi.capturePayPalPayment(proposalId);
      setCapturedProposals((prev) => ({
        ...prev,
        [proposalId]: {
          captured: true,
          captureId: captureRes.capture_id,
          orderId: paypalCheckoutInfo[proposalId]?.orderId,
        },
      }));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Payment capture failed';
      alert(`PayPal Capture Error: ${errorMessage}`);
    } finally {
      setProcessingPayment(null);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-10rem)] min-h-[600px]">
      {/* Left Area: Chat Stream (Flex 1) */}
      <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex flex-col overflow-hidden">
        {/* Chat Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-indigo-600 text-white shadow-xs">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                Autonomous Shopping Agent
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              </h2>
              <p className="text-[11px] text-slate-500">
                Armed with PayPal Sandbox integration and real-time policy evaluation
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-xs font-medium text-slate-500">Active Mandate:</label>
            <select
              value={selectedMandateId}
              onChange={(e) => setSelectedMandateId(e.target.value)}
              className="text-xs font-semibold text-slate-700 bg-white px-2.5 py-1 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {mandates.length === 0 && <option value="">No Mandates Loaded</option>}
              {mandates.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} (${Number(m.max_budget).toFixed(2)})
                </option>
              ))}
            </select>
            <div className="hidden sm:flex items-center space-x-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Guarded</span>
            </div>
          </div>
        </div>

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((message) => {
            const isUser = message.role === 'user';
            const proposal = message.proposal;
            const policy = message.policyResult;
            const captureState = proposal ? capturedProposals[proposal.id] : null;
            const checkoutState = proposal ? paypalCheckoutInfo[proposal.id] : null;
            const isBusy = proposal && processingPayment === proposal.id;

            return (
              <div
                key={message.id}
                className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div className={`max-w-xl space-y-3 ${isUser ? 'items-end' : 'items-start'}`}>
                  {/* Chat bubble text */}
                  <div
                    className={`p-4 rounded-2xl text-xs leading-relaxed shadow-xs ${
                      isUser
                        ? 'bg-slate-900 text-white rounded-tr-xs'
                        : 'bg-slate-50 border border-slate-100 text-slate-800 rounded-tl-xs'
                    }`}
                  >
                    <p>{message.content}</p>
                    <span
                      className={`text-[10px] block mt-1.5 ${
                        isUser ? 'text-slate-400 text-right' : 'text-slate-400'
                      }`}
                    >
                      {message.timestamp}
                    </span>
                  </div>

                  {/* Proposal & Policy Verification Card */}
                  {proposal && (
                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm space-y-4">
                      {/* Product Header */}
                      <div className="flex items-start justify-between border-b border-slate-100 pb-3">
                        <div>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                            Purchase Proposal
                          </span>
                          <h4 className="text-sm font-bold text-slate-900 mt-0.5">
                            {proposal.product_name}
                          </h4>
                          <div className="flex items-center space-x-2 mt-1 text-xs text-slate-500">
                            <span>Merchant: <strong className="text-slate-700">{proposal.merchant}</strong></span>
                            <span>•</span>
                            <span>Category: <strong className="text-slate-700">{proposal.category}</strong></span>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-base font-extrabold text-slate-900">
                            ${Number(proposal.total_amount).toFixed(2)}
                          </span>
                          <span className="text-[10px] text-slate-400 block font-mono">
                            Qty: {proposal.quantity} @ ${Number(proposal.price).toFixed(2)}
                          </span>
                        </div>
                      </div>

                      {/* AI Reasoning */}
                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs">
                        <span className="font-semibold text-slate-700 block mb-1">AI Recommendation Justification:</span>
                        <p className="text-slate-600 italic">"{proposal.ai_reasoning}"</p>
                      </div>

                      {/* Policy Verification Banner */}
                      <div
                        className={`p-3 rounded-lg border flex items-start gap-2.5 text-xs ${
                          policy?.passed
                            ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                            : 'bg-rose-50/70 border-rose-200 text-rose-900'
                        }`}
                      >
                        {policy?.passed ? (
                          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        ) : (
                          <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 space-y-1">
                          <div className="font-bold flex items-center justify-between">
                            <span>
                              {policy?.passed
                                ? 'Guardian Policy Verified (Safe to Authorize)'
                                : 'Guardian Policy Violations Detected'}
                            </span>
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold uppercase ${
                                policy?.passed
                                  ? 'bg-emerald-200/80 text-emerald-800'
                                  : 'bg-rose-200/80 text-rose-800'
                              }`}
                            >
                              {policy?.passed ? 'PASSED' : 'BLOCKED'}
                            </span>
                          </div>

                          {policy?.passed ? (
                            <p className="text-[11px] text-emerald-700">
                              Product, merchant, category, and total price satisfy all spending mandate constraints.
                            </p>
                          ) : (
                            <ul className="list-disc list-inside text-[11px] text-rose-700 space-y-0.5 mt-1 font-medium">
                              {policy?.violations.map((violation, i) => (
                                <li key={i}>{violation}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>

                      {/* Payment Action Bar */}
                      <div>
                        {captureState?.captured ? (
                          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-800 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <CheckCircle className="w-4 h-4 text-emerald-600" />
                              <span className="font-bold">PayPal Sandbox Payment Captured!</span>
                            </div>
                            <span className="font-mono text-[11px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                              Capture ID: {captureState.captureId}
                            </span>
                          </div>
                        ) : checkoutState?.orderId ? (
                          <div className="space-y-2">
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-900 flex items-center justify-between">
                              <div>
                                <span className="font-bold block">Live PayPal Order: {checkoutState.orderId}</span>
                                <span className="text-[11px] text-blue-700">
                                  Approve in the PayPal checkout window, then click Complete Capture below.
                                </span>
                              </div>
                              {checkoutState.approveUrl && (
                                <a
                                  href={checkoutState.approveUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#0070ba] hover:bg-[#005ea6] text-white font-bold text-xs transition-colors"
                                >
                                  <span>PayPal Checkout</span>
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                              )}
                            </div>
                            <button
                              onClick={() => handleCapturePayPal(proposal.id)}
                              disabled={isBusy}
                              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                            >
                              {isBusy ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <CheckCircle className="w-4 h-4" />
                              )}
                              <span>Complete & Capture Payment via PayPal Sandbox</span>
                            </button>
                          </div>
                        ) : policy?.passed ? (
                          <button
                            onClick={() => handleInitiatePayPal(proposal.id)}
                            disabled={isBusy}
                            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#0070ba] hover:bg-[#005ea6] text-white text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                          >
                            {isBusy ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <DollarSign className="w-4 h-4" />
                            )}
                            <span>Human Approve & Authorize via PayPal Sandbox</span>
                          </button>
                        ) : (
                          <button
                            disabled
                            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-slate-100 text-slate-400 text-xs font-bold cursor-not-allowed border border-slate-200"
                          >
                            <Lock className="w-4 h-4" />
                            <span>Authorization Blocked (Guardian Policy Violations Detected)</span>
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}

          {isEvaluating && (
            <div className="flex gap-3 items-center text-slate-500 text-xs italic">
              <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
              <div className="flex items-center space-x-2 bg-slate-100 px-4 py-2.5 rounded-2xl rounded-tl-xs">
                <span>AI evaluating catalog and checking Guardian policy rules...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Preset Prompt Suggestions */}
        <div className="px-6 py-2 bg-slate-50 border-t border-slate-100 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-slate-400 font-medium whitespace-nowrap">Try asking:</span>
          <button
            onClick={() => handleSend('I need an ergonomic mouse for CAD modeling')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 transition-colors cursor-pointer font-medium"
          >
            Ergonomic Mouse (Passes Policy)
          </button>
          <button
            onClick={() => handleSend('Order a Keychron mechanical keyboard for programming')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 transition-colors cursor-pointer font-medium"
          >
            Custom Keyboard (Passes Policy)
          </button>
          <button
            onClick={() => handleSend('Can you purchase a PlayStation 5 console for the office?')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer font-medium"
          >
            PlayStation 5 (Fails Policy)
          </button>
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-white border-t border-slate-200">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              placeholder="Ask assistant to source equipment, software, or peripherals..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isEvaluating}
              className="flex-1 px-4 py-2.5 bg-slate-50 rounded-xl text-xs text-slate-900 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isEvaluating || !input.trim()}
              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* Right Area: Guardian Inspector Panel */}
      <div className="w-full lg:w-80 bg-white rounded-2xl border border-slate-200/90 shadow-xs p-5 flex flex-col justify-between space-y-4">
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-md bg-indigo-50 text-indigo-600">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Guardian Guardrails</h3>
              <p className="text-[11px] text-slate-500">Autonomous enforcement</p>
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs space-y-2">
            <div className="font-semibold text-slate-700 flex items-center justify-between">
              <span>Active Spending Mandates</span>
              <span className="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-mono font-bold">
                {mandates.filter((m) => m.is_active).length} Active
              </span>
            </div>
            <ul className="text-[11px] text-slate-600 space-y-1">
              {mandates.filter((m) => m.is_active).map((m) => (
                <li key={m.id} className="flex items-center justify-between">
                  <span className="truncate pr-2">{m.name}</span>
                  <strong className="text-slate-800">${Number(m.max_budget).toFixed(2)}</strong>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-2.5">
            <span className="text-xs font-bold text-slate-700 block">How PACT Protects You</span>
            <div className="text-xs text-slate-600 space-y-2">
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  1
                </span>
                <span>User asks for a tool or product in natural language.</span>
              </div>
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  2
                </span>
                <span>AI Agent formulates structured proposal with merchant & price.</span>
              </div>
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  3
                </span>
                <span>Deterministic Guardian verifies whitelist, category, and budget envelope.</span>
              </div>
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  4
                </span>
                <span>Human must explicitly approve before live PayPal checkout can execute.</span>
              </div>
            </div>
          </div>
        </div>

        <div className="p-3 bg-indigo-50 rounded-xl border border-indigo-200 text-xs text-indigo-900 space-y-1">
          <div className="font-bold flex items-center gap-1.5">
            <AlertOctagon className="w-3.5 h-3.5 text-indigo-600" />
            <span>PayPal Sandbox Live</span>
          </div>
          <p className="text-[11px] leading-relaxed text-indigo-800">
            Real PayPal Orders API v2 tokens are generated. Click <strong>PayPal Checkout</strong> to log in with your sandbox buyer account:
            <br />
            <code className="text-[10px] bg-white/70 px-1 py-0.5 rounded font-mono block mt-1">
              sb-1r1ra53751334@personal.example.com
            </code>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ShoppingAssistant;
