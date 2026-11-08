import { Mandate, Proposal, AuditLogEntry, Product, DashboardStats } from '../types';

export const mockStats: DashboardStats = {
  activeMandates: 4,
  pendingApprovals: 2,
  totalTransactions: 18,
  budgetRemaining: 3420.50,
  totalBudget: 5000.00,
};

export const mockMandates: Mandate[] = [
  {
    id: 'man-9821',
    name: 'Q1 Developer Equipment & Peripherals',
    max_budget: 1500.00,
    current_spend: 649.99,
    allowed_merchants: ['Keychron', 'Logitech', 'Dell', 'Best Buy', 'Amazon'],
    allowed_categories: ['Electronics', 'Peripherals', 'Ergonomics'],
    restrictions: ['No gaming consoles', 'Max $300 per single peripheral item', 'Pre-approval required over $500'],
    is_active: true,
    created_at: '2026-03-01T10:00:00Z',
  },
  {
    id: 'man-9822',
    name: 'Cloud Infrastructure & API Tooling',
    max_budget: 2000.00,
    current_spend: 850.00,
    allowed_merchants: ['AWS', 'GitHub', 'OpenAI', 'Anthropic', 'Vercel'],
    allowed_categories: ['Cloud Services', 'Developer Tools', 'AI APIs'],
    restrictions: ['Production tier upgrades require manual review', 'No personal accounts'],
    is_active: true,
    created_at: '2026-03-05T14:30:00Z',
  },
  {
    id: 'man-9823',
    name: 'Team Learning & Engineering Books',
    max_budget: 500.00,
    current_spend: 79.51,
    allowed_merchants: ['O\'Reilly Media', 'Pragmatic Bookshelf', 'Amazon', 'Manning'],
    allowed_categories: ['Books', 'Education', 'Training'],
    restrictions: ['Technical books only', 'Digital or paperback only'],
    is_active: true,
    created_at: '2026-03-10T09:15:00Z',
  },
  {
    id: 'man-9824',
    name: 'Remote Ergonomics Wellness Stipend',
    max_budget: 1000.00,
    current_spend: 0.00,
    allowed_merchants: ['Herman Miller', 'Fully', 'Autonomous', 'Ergotron'],
    allowed_categories: ['Furniture', 'Ergonomics'],
    restrictions: ['Home office use only', 'Requires manager sign-off'],
    is_active: false,
    created_at: '2026-02-15T11:00:00Z',
  },
];

export const mockProducts: Product[] = [
  {
    id: 'prod-001',
    name: 'Keychron Q1 Pro Wireless Mechanical Keyboard',
    description: 'QMK/VIA wireless custom mechanical keyboard with CNC aluminum body.',
    price: 199.99,
    category: 'Peripherals',
    merchant: 'Keychron',
    image_url: 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&auto=format&fit=crop&q=60',
    in_stock: true,
  },
  {
    id: 'prod-002',
    name: 'Logitech MX Master 3S Performance Mouse',
    description: 'Advanced quiet click wireless mouse with 8K DPI tracking and MagSpeed scrolling.',
    price: 99.99,
    category: 'Peripherals',
    merchant: 'Logitech',
    image_url: 'https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=500&auto=format&fit=crop&q=60',
    in_stock: true,
  },
  {
    id: 'prod-003',
    name: 'Dell UltraSharp 27" 4K USB-C Hub Monitor (U2723QE)',
    description: 'IPS Black technology, 98% DCI-P3 color gamut, 90W USB-C power delivery.',
    price: 499.99,
    category: 'Electronics',
    merchant: 'Dell',
    image_url: 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&auto=format&fit=crop&q=60',
    in_stock: true,
  },
  {
    id: 'prod-004',
    name: 'Designing Data-Intensive Applications by Martin Kleppmann',
    description: 'The definitive guide to the architecture of data systems and storage engines.',
    price: 44.99,
    category: 'Books',
    merchant: 'O\'Reilly Media',
    image_url: 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=500&auto=format&fit=crop&q=60',
    in_stock: true,
  },
  {
    id: 'prod-005',
    name: 'PlayStation 5 Pro Digital Edition',
    description: 'Next-gen gaming console with advanced ray tracing and high frame rate support.',
    price: 699.99,
    category: 'Gaming Consoles',
    merchant: 'Sony Direct',
    image_url: 'https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=500&auto=format&fit=crop&q=60',
    in_stock: true,
  },
];

export const mockProposals: Proposal[] = [
  {
    id: 'prop-701',
    mandate_id: 'man-9821',
    product_id: 'prod-001',
    product_name: 'Keychron Q1 Pro Wireless Mechanical Keyboard',
    merchant: 'Keychron',
    category: 'Peripherals',
    price: 199.99,
    quantity: 1,
    total_amount: 199.99,
    ai_reasoning: 'Matches developer peripheral allowance. Merchant "Keychron" is explicitly whitelisted. Price $199.99 is below single item cap of $300.00 and within remaining mandate budget.',
    status: 'pending',
    created_at: '2026-11-08T16:20:00Z',
  },
  {
    id: 'prop-702',
    mandate_id: 'man-9821',
    product_id: 'prod-002',
    product_name: 'Logitech MX Master 3S Performance Mouse',
    merchant: 'Logitech',
    category: 'Peripherals',
    price: 99.99,
    quantity: 1,
    total_amount: 99.99,
    ai_reasoning: 'Ergonomic mouse requested for team engineer. Category "Peripherals" and merchant "Logitech" comply with policy. Mandate balance covers full cost.',
    status: 'pending',
    created_at: '2026-11-08T15:10:00Z',
  },
  {
    id: 'prop-703',
    mandate_id: 'man-9823',
    product_id: 'prod-004',
    product_name: 'Designing Data-Intensive Applications',
    merchant: 'O\'Reilly Media',
    category: 'Books',
    price: 44.99,
    quantity: 1,
    total_amount: 44.99,
    ai_reasoning: 'Core technical architecture book ordered for backend engineer. Complies with team learning budget and approved bookstore list.',
    status: 'captured',
    created_at: '2026-11-07T12:00:00Z',
    paypal_order_id: 'PAYID-MT799201889X',
  },
  {
    id: 'prop-704',
    mandate_id: 'man-9821',
    product_id: 'prod-003',
    product_name: 'Dell UltraSharp 27" 4K Monitor',
    merchant: 'Dell',
    category: 'Electronics',
    price: 499.99,
    quantity: 1,
    total_amount: 499.99,
    ai_reasoning: 'High-res monitor for frontend design inspection. Approved by engineering manager under equipment refresh cycle.',
    status: 'approved',
    created_at: '2026-11-06T18:40:00Z',
    paypal_order_id: 'PAYID-MT662198002Y',
  },
  {
    id: 'prop-705',
    mandate_id: 'man-9821',
    product_id: 'prod-005',
    product_name: 'PlayStation 5 Pro Digital Edition',
    merchant: 'Sony Direct',
    category: 'Gaming Consoles',
    price: 699.99,
    quantity: 1,
    total_amount: 699.99,
    ai_reasoning: 'Rejected by Guardian Engine: Violates policy restriction "No gaming consoles" and merchant "Sony Direct" is not in allowed merchants list.',
    status: 'rejected',
    created_at: '2026-11-05T09:30:00Z',
  },
];

export const mockAuditLogs: AuditLogEntry[] = [
  {
    id: 'aud-301',
    event_type: 'POLICY_EVALUATED',
    entity_type: 'proposal',
    entity_id: 'prop-701',
    details: {
      result: 'PASSED',
      rule_checks: [
        { rule: 'Merchant Whitelist', passed: true, note: 'Keychron in allowed list' },
        { rule: 'Category Whitelist', passed: true, note: 'Peripherals in allowed list' },
        { rule: 'Budget Threshold', passed: true, note: '$199.99 <= remaining $850.01' },
        { rule: 'Single Item Cap', passed: true, note: '$199.99 <= $300.00 cap' }
      ]
    },
    timestamp: '2026-11-08T16:20:05Z',
  },
  {
    id: 'aud-302',
    event_type: 'PROPOSAL_GENERATED',
    entity_type: 'proposal',
    entity_id: 'prop-701',
    details: {
      user_prompt: 'I need a good tactile mechanical keyboard for coding',
      selected_product: 'Keychron Q1 Pro Wireless Mechanical Keyboard',
      mandate: 'man-9821'
    },
    timestamp: '2026-11-08T16:20:00Z',
  },
  {
    id: 'aud-303',
    event_type: 'POLICY_EVALUATED',
    entity_type: 'proposal',
    entity_id: 'prop-702',
    details: {
      result: 'PASSED',
      rule_checks: [
        { rule: 'Merchant Whitelist', passed: true, note: 'Logitech in allowed list' },
        { rule: 'Category Whitelist', passed: true, note: 'Peripherals in allowed list' },
        { rule: 'Budget Threshold', passed: true, note: '$99.99 <= remaining $850.01' }
      ]
    },
    timestamp: '2026-11-08T15:10:04Z',
  },
  {
    id: 'aud-304',
    event_type: 'PAYMENT_CAPTURED',
    entity_type: 'transaction',
    entity_id: 'PAYID-MT799201889X',
    details: {
      amount: 44.99,
      currency: 'USD',
      merchant: 'O\'Reilly Media',
      paypal_capture_status: 'COMPLETED',
      proposal_id: 'prop-703'
    },
    timestamp: '2026-11-07T12:05:22Z',
  },
  {
    id: 'aud-305',
    event_type: 'APPROVAL_GRANTED',
    entity_type: 'proposal',
    entity_id: 'prop-703',
    details: {
      approved_by: 'Automated Policy Guardian',
      mandate: 'Team Learning & Engineering Books'
    },
    timestamp: '2026-11-07T12:00:15Z',
  },
  {
    id: 'aud-306',
    event_type: 'APPROVAL_REJECTED',
    entity_type: 'proposal',
    entity_id: 'prop-705',
    details: {
      reason: 'Prohibited category "Gaming Consoles" and unlisted merchant "Sony Direct"',
      guard_action: 'BLOCKED_INSTANTLY'
    },
    timestamp: '2026-11-05T09:30:10Z',
  },
  {
    id: 'aud-307',
    event_type: 'MANDATE_CREATED',
    entity_type: 'mandate',
    entity_id: 'man-9821',
    details: {
      name: 'Q1 Developer Equipment & Peripherals',
      max_budget: 1500.00,
      scope: 'Engineering org'
    },
    timestamp: '2026-03-01T10:00:00Z',
  },
];
