import React from 'react';
import {
  BookOpen,
  Coffee,
  Dumbbell,
  Gamepad2,
  Headphones,
  Keyboard,
  Mouse,
  Package,
  Shirt,
  Usb,
  UtensilsCrossed,
  type LucideIcon,
} from 'lucide-react';
import { cx } from './ui';

/** Designed product tiles (no third-party photos): icon chosen from product name, then category. */
function pick(name: string, category: string): { Icon: LucideIcon; hue: string } {
  const n = `${name} ${category}`.toLowerCase();
  if (/mouse/.test(n)) return { Icon: Mouse, hue: 'from-accent/25 to-violet/10 text-accent' };
  if (/keyboard/.test(n)) return { Icon: Keyboard, hue: 'from-violet/25 to-accent/10 text-violet' };
  if (/headphone|headset/.test(n)) return { Icon: Headphones, hue: 'from-info/20 to-accent/10 text-info' };
  if (/hub|adapter|usb/.test(n)) return { Icon: Usb, hue: 'from-accent/20 to-info/10 text-accent' };
  if (/playstation|xbox|console|gaming/.test(n)) return { Icon: Gamepad2, hue: 'from-bad/20 to-caution/10 text-bad' };
  if (/book/.test(n)) return { Icon: BookOpen, hue: 'from-warn/20 to-caution/10 text-warn' };
  if (/kettle|coffee/.test(n)) return { Icon: Coffee, hue: 'from-caution/20 to-warn/10 text-caution' };
  if (/kitchen|knife|container/.test(n)) return { Icon: UtensilsCrossed, hue: 'from-caution/20 to-warn/10 text-caution' };
  if (/clothing|sweater|shirt|jacket/.test(n)) return { Icon: Shirt, hue: 'from-info/20 to-ok/10 text-info' };
  if (/sport|yoga|dumbbell|bottle|band/.test(n)) return { Icon: Dumbbell, hue: 'from-ok/20 to-info/10 text-ok' };
  return { Icon: Package, hue: 'from-white/10 to-white/5 text-muted' };
}

const SIZES = {
  sm: 'h-9 w-9 rounded-lg [&>svg]:h-4 [&>svg]:w-4',
  md: 'h-12 w-12 rounded-xl [&>svg]:h-5 [&>svg]:w-5',
  lg: 'h-20 w-20 rounded-2xl [&>svg]:h-9 [&>svg]:w-9',
  xl: 'h-28 w-28 rounded-2xl [&>svg]:h-12 [&>svg]:w-12',
};

export const ProductTile: React.FC<{ name: string; category: string; size?: keyof typeof SIZES; className?: string }> = ({
  name,
  category,
  size = 'md',
  className,
}) => {
  const { Icon, hue } = pick(name, category);
  return (
    <div
      aria-hidden
      className={cx('flex shrink-0 items-center justify-center border border-white/[0.07] bg-gradient-to-br', hue, SIZES[size], className)}
    >
      <Icon strokeWidth={1.6} />
    </div>
  );
};

export default ProductTile;
