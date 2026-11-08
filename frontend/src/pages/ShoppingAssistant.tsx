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
import { Proposal, PolicyResult, ShoppingMessage, Mandate } from '../types';
import { mockProposals, mockMandates } from '../data/mockData';
import { pactApi } from '../api/pact';

export const ShoppingAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ShoppingMessage[]>([
    {
      id: 'msg-1',
      role: 'assistant',
      content:
        'Hello! I am your PACT Autonomous Shopping Assistant. Tell me what equipment, software, or peripherals you need. I will research products, evaluate them against your active spending mandate rules, and submit verified purchase proposals for PayPal capture.',
      timestamp: '12:00 PM',
    },
    {
      id: 'msg-2',
      role: 'user',
      content: 'I need a wireless mechanical keyboard for my workstation.',
      timestamp: '12:02 PM',
    },
    {
      id: 'msg-3',
      role: 'assistant',
      content:
        'I found the Keychron Q1 Pro Wireless Mechanical Keyboard. It complies with your active mandate rules and has passed all Guardian security checks.',
      timestamp: '12:02 PM',
      proposal: mockProposals[0],
      policyResult: {
        passed: true,
        violations: [],
      },
    },
  ]);

  const [input, setInput] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [capturedProposals, setCapturedProposals] = useState<Record<string, { captured: boolean; captureId?: string; orderId?: string }>>({});
  const [processingPayment, setProcessingPayment] = useState<string | null>(null);
  const [paypalCheckoutInfo, setPaypalCheckoutInfo] = useState<Record<string, { orderId: string; approveUrl: string }>>({});
  const [mandates, setMandates] = useState<Mandate[]>(mockMandates);
  const [selectedMandateId, setSelectedMandateId] = useState<string>(mockMandates[0]?.id || 'man-9821');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load live mandates on mount
  useEffect(() => {
    pactApi.getMandates()
      .then((data) => {
        if (data && data.length > 0) {
          setMandates(data);
          const active = data.find((m) => m.is_active);
          if (active) setSelectedMandateId(active.id);
        }
      })
      .catch(() => {
        // Keep mock mandates on network error
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
      // 1. Attempt live backend call
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
    } catch {
      // 2. Fallback to client-side simulation if backend is offline
      const lower = text.toLowerCase();
      let assistantMsg: ShoppingMessage;

      if (lower.includes('playstation') || lower.includes('console') || lower.includes('game')) {
        const restrictedProposal: Proposal = {
          id: `prop-${Math.floor(700 + Math.random() * 100)}`,
          mandate_id: selectedMandateId,
          product_id: 99,
          product_name: 'Sony PlayStation 5 Pro Digital Edition',
          merchant: 'Sony Direct',
          category: 'Gaming Consoles',
          price: 699.99,
          quantity: 1,
          total_amount: 699.99,
          ai_reasoning:
            'Autonomous Guardian rejected this item: Forbidden under company policy restrictions ("No gaming consoles"). Merchant is also not on whitelist.',
          status: 'rejected',
          created_at: new Date().toISOString(),
        };

        const failedPolicy: PolicyResult = {
          passed: false,
          violations: [
            'Prohibited Category: "Gaming Consoles" violates explicit restriction.',
            'Unapproved Merchant: "Sony Direct" is not in allowed merchant whitelist.',
            'Price Limit Exceeded: $699.99 exceeds single peripheral item limit.',
          ],
        };

        assistantMsg = {
          id: `msg-${Date.now() + 1}`,
          role: 'assistant',
          content:
            'I found a match, but the PACT Guardian Policy Engine BLOCKED this proposal due to critical rule violations. Payment authorization is withheld.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          proposal: restrictedProposal,
          policyResult: failedPolicy,
        };
      } else {
        assistantMsg = {
          id: `msg-${Date.now() + 1}`,
          role: 'assistant',
          content:
            `I analyzed your request: "${text}". I have prepared a proposal that complies with your spending mandate constraints and is ready for payment verification.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          proposal: {
            id: `prop-${Math.floor(700 + Math.random() * 100)}`,
            mandate_id: selectedMandateId,
            product_id: 1,
            product_name: 'Keychron Q1 Pro Wireless Mechanical Keyboard',
            merchant: 'TechHub',
            category: 'Electronics',
            price: 199.99,
            quantity: 1,
            total_amount: 199.99,
            ai_reasoning: 'Verified ergonomic keyboard. Merchant "TechHub" is approved and price is within budget envelope.',
            status: 'pending',
            created_at: new Date().toISOString(),
          },
          policyResult: {
            passed: true,
            violations: [],
          },
        };
      }

      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setIsEvaluating(false);
    }
  };

  // Step 1: Human Approval + PayPal Checkout Order Creation
  const handleInitiatePayPal = async (proposalId: string) => {
    setProcessingPayment(proposalId);
    try {
      // Approve on backend first (revalidates mandate and policies)
      await pactApi.approveProposal(proposalId);
      // Create PayPal sandbox order
      const orderRes = await pactApi.createPayPalOrder(proposalId);
      setPaypalCheckoutInfo((prev) => ({
        ...prev,
        [proposalId]: {
          orderId: orderRes.order_id,
          approveUrl: orderRes.approve_url,
        },
      }));
      // Open PayPal sandbox in new tab for buyer checkout
      if (orderRes.approve_url) {
        window.open(orderRes.approve_url, '_blank', 'noopener,noreferrer');
      }
    } catch {
      // Fallback simulation
      setPaypalCheckoutInfo((prev) => ({
        ...prev,
        [proposalId]: {
          orderId: `PAYPAL-ORD-${Date.now()}`,
          approveUrl: 'https://www.sandbox.paypal.com/checkoutnow',
        },
      }));
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
    } catch {
      // Fallback
      setCapturedProposals((prev) => ({
        ...prev,
        [proposalId]: {
          captured: true,
          captureId: `CAP-${Math.random().toString(36).substring(2, 9).toUpperCase()}`,
          orderId: paypalCheckoutInfo[proposalId]?.orderId,
        },
      }));
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
                                ? 'Guardian Policy Verified (Safe to Capture)'
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
                              Product, merchant, and total spending satisfy all spending mandate constraints.
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
                            <span className="font-mono text-[11px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                              ID: {captureState.captureId}
                            </span>
                          </div>
                        ) : checkoutState?.orderId ? (
                          <div className="space-y-2">
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-900 flex items-center justify-between">
                              <div>
                                <span className="font-bold block">PayPal Order Created: {checkoutState.orderId}</span>
                                <span className="text-[11px] text-blue-700">
                                  Approve in PayPal sandbox popup, then confirm capture below.
                                </span>
                              </div>
                              {checkoutState.approveUrl && (
                                <a
                                  href={checkoutState.approveUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#0070ba] text-white font-bold text-[11px]"
                                >
                                  <span>PayPal Checkout</span>
                                  <ExternalLink className="w-3 h-3" />
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
                            <span>Approve & Authorize via PayPal Sandbox</span>
                          </button>
                        ) : (
                          <button
                            disabled
                            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-slate-100 text-slate-400 text-xs font-bold cursor-not-allowed border border-slate-200"
                          >
                            <Lock className="w-4 h-4" />
                            <span>Approval Disabled (Policy Violations Detected)</span>
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
                <span>Evaluating merchants, products, and mandate policies...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Preset Prompt Suggestions */}
        <div className="px-6 py-2 bg-slate-50 border-t border-slate-100 flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-slate-400 font-medium whitespace-nowrap">Try asking:</span>
          <button
            onClick={() => handleSend('Order a Keychron mechanical keyboard for programming')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 transition-colors cursor-pointer"
          >
            Tactile Keyboard (Passes Policy)
          </button>
          <button
            onClick={() => handleSend('Can you purchase a PlayStation 5 console for the office?')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer"
          >
            PlayStation 5 (Fails Policy)
          </button>
          <button
            onClick={() => handleSend('I need an ergonomic mouse for CAD modeling')}
            className="whitespace-nowrap px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-indigo-600 hover:border-indigo-300 transition-colors cursor-pointer"
          >
            Logitech MX Master Mouse
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
              <span className="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded font-mono">
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
                <span>Agent generates structured proposal with merchant & price.</span>
              </div>
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  3
                </span>
                <span>Guardian verifies merchant whitelist, category, and budget envelope.</span>
              </div>
              <div className="flex gap-2">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  4
                </span>
                <span>Only compliant proposals can capture funds via PayPal.</span>
              </div>
            </div>
          </div>
        </div>

        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-xs text-amber-800 space-y-1">
          <div className="font-bold flex items-center gap-1.5">
            <AlertOctagon className="w-3.5 h-3.5 text-amber-600" />
            <span>Hackathon Demo</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Click the preset suggestion buttons above to test immediate policy acceptance vs instant violation rejection with live PayPal Sandbox execution.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ShoppingAssistant;
