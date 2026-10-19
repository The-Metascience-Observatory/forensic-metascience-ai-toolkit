import { flipArrow, FLIP_LABEL, type Point, type FlipDirection } from '@/lib/flipArrow';
export function FlipArrow({points, direction, color}: {points: Point[]; direction?: FlipDirection; color: string}) {
  const arrow = flipArrow(points, direction);
  return arrow.length ? <polygon data-flip-arrow={direction} points={arrow.map(p=>p.join(',')).join(' ')}
    fill={color} stroke="#111" strokeWidth={1} vectorEffect="non-scaling-stroke"><title>{FLIP_LABEL}</title></polygon> : null;
}
